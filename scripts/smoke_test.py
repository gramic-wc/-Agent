"""离线自检：不需要 API key，验证「解析 → 切块 → 关键词检索 → 作业卡渲染」这条不依赖模型的路。

用法：uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pymupdf as fitz  # noqa: E402

from eqagent.agent.tools import get_spare_parts, search_cases  # noqa: E402
from eqagent.ingest.parse import parse_pdf  # noqa: E402
from eqagent.retrieve.hybrid import Retriever  # noqa: E402
from eqagent.schema import Cause, Citation, SparePart, Step, WorkCard  # noqa: E402


def build_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()

    # 标题（大字号 → 应被识别为 heading）
    page.insert_text((72, 80), "第3章 故障排除", fontsize=22, fontname="china-s")
    page.insert_text((72, 110), "3.2 排气温度高", fontsize=15, fontname="china-s")

    # 正文
    body = (
        "排气温度高的常见原因包括油冷却器堵塞、冷却风扇故障以及油位过低。"
        "现场处理时应先停机泄压，再检查冷却器翅片是否积灰。"
    )
    page.insert_text((72, 140), body, fontsize=10.5, fontname="china-s")

    # 表格（画网格线 → find_tables 才能识别）
    x0, y0, w, h = 72, 170, 400, 24
    for row in range(3):
        page.draw_line((x0, y0 + row * h), (x0 + w, y0 + row * h))
    for col in range(3):
        page.draw_line((x0 + col * (w / 2), y0), (x0 + col * (w / 2), y0 + 2 * h))
    cells = [
        ["报警码", "含义", "处理"],
        ["E-201", "排气温度高", "清洗冷却器"],
        ["E-305", "油压不足", "更换油滤芯"],
    ]
    for r, row in enumerate(cells):
        for c, text in enumerate(row):
            page.insert_text(
                (x0 + c * (w / 2) + 4, y0 + r * h + 16), text, fontsize=8, fontname="china-s"
            )

    # 图（先用另一页画点东西，取成图片再插入本页）
    art = doc.new_page()
    art.draw_rect(fitz.Rect(100, 100, 300, 220), color=(0, 0, 1), width=2)
    art.draw_line((100, 160), (300, 160), color=(1, 0, 0), width=2)
    png = art.get_pixmap(dpi=150).tobytes("png")
    doc.delete_page(1)
    page = doc[0]
    page.insert_image(fitz.Rect(72, 230, 372, 380), stream=png)
    page.insert_text((72, 400), "图 3-2 润滑油路示意", fontsize=9, fontname="china-s")

    doc.save(str(path))
    doc.close()


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="eqsmoke_"))
    pdf = tmp / "ga55_manual.pdf"
    build_pdf(pdf)
    print(f"[1] 生成测试 PDF：{pdf.name}")

    chunks = parse_pdf(
        pdf,
        doc_id="ga55_manual",
        device_model="GA55",
        doc_title="GA55 螺杆空压机维修手册",
        figure_dir=tmp / "figs",
    )
    kinds = {}
    for chunk in chunks:
        kinds[chunk.block_type] = kinds.get(chunk.block_type, 0) + 1
    print(f"[2] 解析出 {len(chunks)} 块：{kinds}")
    assert kinds.get("text"), "没解析出正文"
    assert kinds.get("table"), "没解析出表格"
    assert kinds.get("figure"), "没解析出图纸"
    assert any(c.section_path for c in chunks), "章节路径为空"
    assert any(c.figure_no for c in chunks), "图号未关联"

    # 用解析结果建一个临时关键词索引，验证 BM25 召回（不联网）
    chunks_file = tmp / "chunks.jsonl"
    with chunks_file.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")

    retriever = Retriever(chunks_file)
    retriever._dense = lambda *a, **k: []  # type: ignore[method-assign]  # 只测关键词路
    hits = retriever.search("排气温度高 报警码 E-201", top_k=3)
    print(f"[3] BM25 召回 {len(hits)} 条，首条：{hits[0].text[:40]!r}")
    assert hits, "关键词检索无命中"

    # 工单 / 备件 / 作业卡渲染
    cases = search_cases("GA55 排气温度高跳机", device_model="GA55", top_k=3)
    parts = get_spare_parts("冷却器", device_model="GA55")
    print(f"[4] 工单召回 {len(cases)} 条，备件 {len(parts)} 条")
    assert cases and parts, "工单或备件为空（先跑 scripts/gen_data.py）"

    card = WorkCard(
        device_model="GA55",
        device_type="螺杆空压机",
        fault_summary="排气温度高跳机",
        causes=[
            Cause(
                cause="油冷却器堵塞",
                confidence=0.72,
                citations=[
                    Citation(
                        doc_id="ga55_manual",
                        doc_title="GA55 螺杆空压机维修手册",
                        page=1,
                        block_type="text",
                        quote="排气温度高的常见原因包括油冷却器堵塞",
                    )
                ],
            )
        ],
        steps=[Step(no=1, action="停机泄压并挂牌上锁", risk="high", safety="确认压力归零")],
        tools=["压力表"],
        spare_parts=[SparePart(code="P-1001", name="油冷却器芯", qty=1)],
        est_man_hours=3.5,
        evidence_completeness=1.0,
    )
    md = card.to_markdown()
    assert "🔴" in md and "油冷却器堵塞" in md
    print("[5] 作业卡渲染 OK")
    print("\n✅ 自检通过（离线链路正常）")


if __name__ == "__main__":
    main()
