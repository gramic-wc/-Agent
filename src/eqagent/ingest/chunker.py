"""切块与文本规整。切法直接决定检索效果，改这里要重跑评测。"""

from __future__ import annotations

import re

_SENT_END = re.compile(r"(?<=[。！？；；!?;])")
_SPACES = re.compile(r"[ \t\u3000]+")


def table_to_markdown(rows) -> str:
    """PyMuPDF 的 extract() 结果 → Markdown 表。表格在向量库里最容易被压扁，转 MD 是硬要求。"""
    clean: list[list[str]] = []
    for row in rows or []:
        cells = [("" if c is None else str(c)).replace("\n", " ").strip() for c in row]
        if not any(cells):
            continue
        clean.append(cells)
    if not clean:
        return ""
    width = max(len(r) for r in clean)
    clean = [r + [""] * (width - len(r)) for r in clean]
    # 丢掉整列全空的列（表格识别常见伪列，会把噪声带进向量化文本）
    keep = [i for i in range(width) if any(row[i] for row in clean)]
    clean = [[row[i] for i in keep] for row in clean]
    if not clean or not clean[0]:
        return ""
    width = len(keep)
    head, body = clean[0], clean[1:]
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def split_text(text: str, max_len: int = 700) -> list[str]:
    text = _SPACES.sub(" ", text or "").strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    out: list[str] = []
    buf = ""
    for sent in _SENT_END.split(text):
        if not sent:
            continue
        if buf and len(buf) + len(sent) > max_len:
            out.append(buf.strip())
            buf = sent
        else:
            buf += sent
    if buf.strip():
        out.append(buf.strip())
    return out


def chunk_id(doc_id: str, page: int, block_type: str, idx: int) -> str:
    return f"{doc_id}:p{page}:{block_type}:{idx}"
