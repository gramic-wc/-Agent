"""入库 CLI：PDF → chunks.jsonl → Qdrant。

用法：
    eq-ingest                       # 扫描 data/manuals 下所有 PDF（按文件名推断型号）
    eq-ingest --manifest data/manuals/manifest.csv
    eq-ingest --no-vlm              # 跳过图纸理解，先验证文本/表格链路
    eq-ingest --no-index            # 只产出 chunks.jsonl，不动向量库
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

from ..config import DEVICES, ROOT, guess_device, settings
from ..schema import Chunk
from . import image_desc, parse

log = logging.getLogger("eqagent.ingest")


def _read_manifest(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if not row.get("file"):
                continue
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def _scan_manuals(root: Path) -> list[dict]:
    rows = []
    for pdf in sorted(root.rglob("*.pdf")):
        doc_id = pdf.stem
        model = guess_device(pdf.name) or guess_device(str(pdf.parent))
        rows.append(
            {
                "file": str(pdf.relative_to(root).as_posix()),
                "doc_id": doc_id,
                "device_model": model,
                "device_type": "",
                "title": pdf.stem,
            }
        )
    return rows


def collect_chunks(rows: list[dict], base_dir: Path, use_vlm: bool) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for row in rows:
        pdf = Path(row["file"])
        if not pdf.is_absolute():
            pdf = base_dir / pdf
        if not pdf.exists():
            log.warning("跳过（文件不存在）：%s", pdf)
            continue
        model = row.get("device_model") or guess_device(pdf.name)
        if model and model not in DEVICES:
            log.warning("型号 %s 不在 DEVICES 里，检索过滤会失效（在 config.py 里补上）", model)
        chunks = parse.parse_pdf(
            pdf,
            doc_id=row.get("doc_id") or pdf.stem,
            device_model=model,
            doc_title=row.get("title", ""),
            device_type=row.get("device_type", ""),
        )
        all_chunks.extend(chunks)
    if use_vlm:
        image_desc.describe_figures(all_chunks)
    return all_chunks


def write_chunks(chunks: list[Chunk]) -> Path:
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    out = settings.index_dir / "chunks.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c.model_dump(), ensure_ascii=False) + "\n")
    return out


def build_index(chunks: list[Chunk]) -> None:
    from ..retrieve import index as idx

    client = idx.get_client()
    idx.recreate_collection(client)
    idx.upsert_chunks(client, chunks)
    log.info("已写入 Qdrant collection=%s，共 %d 块", settings.collection, len(chunks))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="设备手册入库")
    ap.add_argument("--manifest", type=Path, default=None, help="manifest.csv 路径")
    ap.add_argument("--manuals-dir", type=Path, default=settings.manuals_dir)
    ap.add_argument("--no-vlm", action="store_true", help="跳过图纸理解")
    ap.add_argument("--no-index", action="store_true", help="只写 chunks.jsonl")
    args = ap.parse_args()

    if args.manifest:
        rows = _read_manifest(args.manifest)
        base = args.manifest.parent
    else:
        rows = _scan_manuals(args.manuals_dir)
        base = args.manuals_dir

    if not rows:
        raise SystemExit(
            f"没找到 PDF。把手册放进 {args.manuals_dir}，"
            f"或提供 manifest（列：file,doc_id,device_model,device_type,title）"
        )

    log.info("待处理 %d 份文档", len(rows))
    chunks = collect_chunks(rows, base, use_vlm=not args.no_vlm)
    out = write_chunks(chunks)
    log.info("chunks 已写出：%s（%d 块）", out.relative_to(ROOT), len(chunks))
    if not args.no_index:
        build_index(chunks)
        print("✅ 入库完成，可以跑：eq-ask \"空压机排气温度高怎么查\"")


if __name__ == "__main__":
    main()
