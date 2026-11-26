"""PDF → 结构化 chunk。

关键点：按版面把内容分成 **正文 / 表格 / 图纸** 三类，分别保留页码、章节路径、图号表号。
赛题里的「多模态」不是指接了个视觉模型，而是指这三类内容都能被正确切分、检索、引用。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import pymupdf as fitz  # PyMuPDF ≥1.24

from ..config import ROOT, device_type_of, settings
from ..schema import Chunk
from . import chunker

log = logging.getLogger(__name__)

CAP_FIG = re.compile(r"^\s*(?:图|Figure|Fig\.?)\s*([0-9]+(?:[-－.．][0-9]+)*)")
CAP_TAB = re.compile(r"^\s*表\s*([0-9]+(?:[-－.．][0-9]+)*)")

HEADER_MAX_CHARS = 40
HEADER_MIN_PAGES = 5
HEADER_MIN_TEXT_CHARS = 6
HEADER_TOP_RATIO = 0.10
MIN_FIG_SIDE = 90.0  # 短边小于此值多半是图标/装饰
MIN_FIG_AREA = 15000.0  # 面积下限（约 120×125pt），避免把无意义小图送进 VL
HEADING_RATIO = 1.15  # 字号超过正文中位数 15% 视为标题
MAX_HEADING_LEN = 40
MAX_GAP_RATIO = 2.5  # 行间距超过 2.5 倍字号视为段落断开


def _overlap(a, b) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    w = min(ax1, bx1) - max(ax0, bx0)
    h = min(ay1, by1) - max(ay0, by0)
    if w <= 0 or h <= 0:
        return 0.0
    area = (ax1 - ax0) * (ay1 - ay0)
    return (w * h) / area if area > 0 else 0.0


def _find_tables(page, use_layout: bool = False) -> list[tuple[tuple, str]]:
    out: list[tuple[tuple, str]] = []
    # use_layout=False：新版 PyMuPDF 默认先跑 MuPDF 版面分析器（多线程模型推理），
    # 实测 407 页 137s → 8s，表格数与内容一致甚至更好（版面分析会把中文标点打散）。
    # 但 GA55_user_manual 这类「无框线表格」只有版面分析认得出来 → 整份文档兜底，见 _extract_document。
    try:
        try:
            finder = page.find_tables(use_layout=use_layout)
        except TypeError:  # PyMuPDF <1.26 没有 use_layout 参数
            finder = page.find_tables()
    except Exception:  # 老版本 PyMuPDF 没有该方法
        return out
    for table in getattr(finder, "tables", []) or []:
        try:
            rows = table.extract()
        except Exception:
            continue
        md = chunker.table_to_markdown(rows)
        if len(md.strip()) < 12:
            continue
        out.append((tuple(table.bbox), md))
    return out


def _find_images(page) -> list[tuple[tuple, int]]:
    out: list[tuple[tuple, int]] = []
    try:
        infos = page.get_image_info(xrefs=True)
    except Exception:
        return out
    for info in infos or []:
        bbox = info.get("bbox")
        if not bbox:
            continue
        r = tuple(float(v) for v in bbox)
        w, h = r[2] - r[0], r[3] - r[1]
        if min(w, h) < MIN_FIG_SIDE or w * h < MIN_FIG_AREA:
            continue
        out.append((r, int(info.get("xref") or 0)))
    return out


def _lines(page, exclude: list[tuple]) -> list[dict]:
    """抽出表格/图片区域之外的文本行，带字号与 bbox。"""
    lines: list[dict] = []
    try:
        data = page.get_text("dict")
    except Exception:
        return lines
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if (s.get("text") or "").strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans).strip()
            if not text:
                continue
            bbox = tuple(float(v) for v in (line.get("bbox") or block.get("bbox")))
            if any(_overlap(bbox, ex) > 0.5 for ex in exclude):
                continue
            lines.append(
                {
                    "text": text,
                    "size": max(float(s.get("size", 0.0)) for s in spans),
                    "bbox": bbox,
                }
            )
    lines.sort(key=lambda x: (round(x["bbox"][1], 1), x["bbox"][0]))
    return lines


def _nearest_caption(
    lines: list[dict], rect: tuple, pattern: re.Pattern, consumed: set[int], above: bool = False
) -> int | None:
    best, best_gap = None, 1e9
    for idx, ln in enumerate(lines):
        if idx in consumed or not pattern.match(ln["text"]):
            continue
        b = ln["bbox"]
        gap = (rect[1] - b[3]) if above else (b[1] - rect[3])
        if gap < -20 or gap > 140:
            continue
        if gap < best_gap:
            best, best_gap = idx, gap
    return best


def _crop(page, rect: tuple, out_dir: Path, name: str, fresh: bool = True) -> str:
    out = out_dir / name
    # fresh=True（PDF 刚变过或首次解析）时必须重渲染，否则会留下同名旧图。
    if fresh or not out.exists():
        pix = page.get_pixmap(clip=fitz.Rect(*rect), dpi=180)
        pix.save(str(out))
    try:
        return out.relative_to(ROOT).as_posix()
    except ValueError:
        return str(out)


# 页级解析缓存：PDF 的表格/图片/文本行抽取结果按页落盘。
# 改 chunker/分块逻辑不用重解析 PDF；只有 PDF 本身变了（mtime/size）才失效。
# ponytail: 只按 mtime+size 判失效，同一 mtime 内改内容不会发现；手册是只读输入，够了。
CACHE_VERSION = 2


def _cache_target(pdf_path: Path, doc_id: str) -> tuple[Path, dict]:
    st = pdf_path.stat()
    meta = {
        "v": CACHE_VERSION,
        "mtime": st.st_mtime,
        "size": st.st_size,
    }
    key = hashlib.md5(json.dumps(meta, sort_keys=True).encode()).hexdigest()[:16]
    return settings.index_dir / "pagecache" / f"{doc_id}.{key}.json", meta


def _load_page_cache(path: Path, meta: dict, page_count: int) -> list[dict] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("meta") != meta or len(data.get("pages") or []) != page_count:
        return None
    return data["pages"]


def _save_page_cache(path: Path, meta: dict, pages: list[dict]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"meta": meta, "pages": pages}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:  # 缓存写不进去不该让整次入库失败
        log.warning("页缓存写入失败（忽略）：%s", exc)


def _extract_page(page, use_layout: bool) -> dict:
    tables = _find_tables(page, use_layout=use_layout)
    images = _find_images(page)
    lines = _lines(page, [r for r, _ in tables] + [r for r, _ in images])
    return {
        "tables": [[list(r), md] for r, md in tables],
        "images": [[list(r), x] for r, x in images],
        "lines": lines,
    }


def _extract_document(doc) -> list[dict]:
    """先跑快的 plain 模式；整份文档一个表都没认出来才回退版面分析重扫。

    绝大多数手册有框线，plain 就够（407 页 8s vs 137s）；GA55_user_manual 那类
    无框线表格只有版面分析认得出，所以按文档兜底，而不是全局开。
    ponytail: 只看「有没有表」，一份文档里同时存在框线表和无框线表时认不全——手册没这情况。
    """
    pages = [_extract_page(page, use_layout=False) for page in doc]
    if any(p["tables"] for p in pages):
        return pages
    log.info("%s: plain 模式未识别到表格，回退版面分析重扫", doc.name)
    return [_extract_page(page, use_layout=True) for page in doc]


def _drop_running_headers(pages: list[dict]) -> list[dict]:
    """删除同文档中至少 5 页重复出现在页面顶部的纯文字页眉。"""

    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()

    def is_candidate(text: str) -> bool:
        text = text.strip()
        return (
            HEADER_MIN_TEXT_CHARS <= len(text) <= HEADER_MAX_CHARS
            and not re.search(r"\d", text)
            and not CAP_TAB.match(text)
            and not CAP_FIG.match(text)
        )

    occurrences: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for pno, page in enumerate(pages):
        bottoms = [line["bbox"][3] for line in page["lines"]]
        bottoms += [rect[3] for rect, _ in page["tables"]]
        bottoms += [rect[3] for rect, _ in page["images"]]
        page_bottom = max(bottoms or [1.0])

        for line in page["lines"]:
            if is_candidate(line["text"]):
                occurrences[norm(line["text"])].append((pno, line["bbox"][1] / page_bottom))

    bad = {
        text
        for text, hits in occurrences.items()
        if len({pno for pno, _ in hits}) >= HEADER_MIN_PAGES
        and sum(y <= HEADER_TOP_RATIO for _, y in hits) / len(hits) >= 0.8
    }

    out = []
    removed = 0
    for page in pages:
        keep = []
        for line in page["lines"]:
            if is_candidate(line["text"]) and norm(line["text"]) in bad:
                removed += 1
            else:
                keep.append(line)
        out.append({**page, "lines": keep})

    if removed:
        names = "、".join(sorted(bad)[:10])
        log.info("页眉过滤：移除 %d 行；候选 %s", removed, names)
    return out


def parse_pdf(
    pdf_path: Path | str,
    doc_id: str,
    device_model: str,
    doc_title: str = "",
    device_type: str = "",
    figure_dir: Path | None = None,
) -> list[Chunk]:
    pdf_path = Path(pdf_path)
    doc_title = doc_title or pdf_path.stem
    device_type = device_type or device_type_of(device_model)
    fig_dir = Path(figure_dir or settings.figure_dir) / doc_id
    fig_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[Chunk] = []
    counter = {"text": 0, "table": 0, "figure": 0}
    doc = fitz.open(pdf_path)

    cache_path, cache_meta = _cache_target(pdf_path, doc_id)
    pages = _load_page_cache(cache_path, cache_meta, doc.page_count)
    fresh = pages is None

    try:
        if fresh:
            pages = _extract_document(doc)

        # 过滤只用于本次切块，pagecache 仍保存原始行。
        pages_f = _drop_running_headers(pages)
        for pno in range(doc.page_count):
            page = doc[pno]
            page_no = pno + 1
            hit = pages_f[pno]
            tables = [(tuple(r), md) for r, md in hit["tables"]]
            images = [(tuple(r), x) for r, x in hit["images"]]
            lines = hit["lines"]
            if not lines and not tables and not images:
                continue

            # 页眉不参与字号分布，避免过滤后把正文短行重新判成标题。
            sizes = sorted(ln["size"] for ln in pages[pno]["lines"]) or [10.0]
            median = sizes[len(sizes) // 2]

            # 1) 先摘掉图注/表注，避免它们混进正文
            consumed: set[int] = set()
            table_items: list[tuple[str, str]] = []
            for rect, md in tables:
                idx = _nearest_caption(lines, rect, CAP_TAB, consumed, above=True)
                cap = ""
                if idx is not None:
                    consumed.add(idx)
                    cap = lines[idx]["text"]
                table_items.append((cap, md))
            figure_items: list[tuple[str, str]] = []
            for rect, xref in images:
                idx = _nearest_caption(lines, rect, CAP_FIG, consumed, above=False)
                cap = ""
                if idx is not None:
                    consumed.add(idx)
                    cap = lines[idx]["text"]
                name = f"p{page_no}_{xref or len(figure_items)}.png"
                figure_items.append((cap, _crop(page, rect, fig_dir, name, fresh=fresh)))

            # 2) 正文 + 标题栈 → 章节路径
            stack: list[tuple[int, str]] = []
            para: list[str] = []
            prev_bottom: float | None = None

            def section_path() -> str:
                return " > ".join(t for _, t in stack)

            def flush() -> None:
                if not para:
                    return
                text = "\n".join(para)
                para.clear()
                for piece in chunker.split_text(text):
                    counter["text"] += 1
                    chunks.append(
                        Chunk(
                            chunk_id=chunker.chunk_id(doc_id, page_no, "text", counter["text"]),
                            doc_id=doc_id,
                            doc_title=doc_title,
                            device_model=device_model,
                            device_type=device_type,
                            page=page_no,
                            block_type="text",
                            section_path=section_path(),
                            heading=stack[-1][1] if stack else "",
                            text=piece,
                        )
                    )

            for idx, ln in enumerate(lines):
                if idx in consumed:
                    continue
                text = ln["text"]
                size = ln["size"]
                is_heading = size >= median * HEADING_RATIO and len(text) <= MAX_HEADING_LEN
                if is_heading:
                    flush()
                    level = 1 if size >= median * 1.5 else 2
                    while stack and stack[-1][0] >= level:
                        stack.pop()
                    stack.append((level, text))
                    prev_bottom = ln["bbox"][3]
                    continue
                gap = (ln["bbox"][1] - prev_bottom) if prev_bottom is not None else 0.0
                if prev_bottom is not None and gap > size * MAX_GAP_RATIO:
                    flush()
                para.append(text)
                prev_bottom = ln["bbox"][3]
            flush()

            # 3) 表格 / 图纸单独成块（等第 4 步再补 VLM 描述）
            for cap, md in table_items:
                counter["table"] += 1
                no = CAP_TAB.match(cap).group(1) if cap and CAP_TAB.match(cap) else ""
                chunks.append(
                    Chunk(
                        chunk_id=chunker.chunk_id(doc_id, page_no, "table", counter["table"]),
                        doc_id=doc_id,
                        doc_title=doc_title,
                        device_model=device_model,
                        device_type=device_type,
                        page=page_no,
                        block_type="table",
                        section_path=section_path(),
                        table_no=no,
                        text=f"【表格】{cap}\n{md}".strip(),
                    )
                )
            for cap, img_path in figure_items:
                counter["figure"] += 1
                no = CAP_FIG.match(cap).group(1) if cap and CAP_FIG.match(cap) else ""
                chunks.append(
                    Chunk(
                        chunk_id=chunker.chunk_id(doc_id, page_no, "figure", counter["figure"]),
                        doc_id=doc_id,
                        doc_title=doc_title,
                        device_model=device_model,
                        device_type=device_type,
                        page=page_no,
                        block_type="figure",
                        section_path=section_path(),
                        figure_no=no,
                        image_path=img_path,
                        text=f"【图纸】{cap}（第{page_no}页）".strip(),
                    )
                )
    finally:
        doc.close()

    if fresh:
        _save_page_cache(cache_path, cache_meta, pages)

    log.info("%s → %d chunks (%s)", pdf_path.name, len(chunks), counter)
    return chunks
