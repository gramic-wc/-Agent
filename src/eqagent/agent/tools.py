"""Agent 的工具集。

设计原则：每个工具只做一件业务动作，带清晰 schema，副作用类工具默认 dry-run。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import jieba

from ..config import settings
from ..retrieve import hybrid

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- 知识库
def search_manual(
    query: str, device_model: str | None = None, top_k: int = 6
) -> list[dict]:
    """检索设备手册（正文/表格/图纸）。"""
    try:
        retriever = hybrid.get_retriever()
    except RuntimeError as exc:
        log.warning("%s", exc)
        return []
    hits = retriever.search(query, top_k=top_k, device_model=device_model or None)
    return [
        {
            "chunk_id": h.chunk_id,
            "doc_id": h.payload.get("doc_id", ""),
            "doc_title": h.doc_title,
            "device_model": h.payload.get("device_model", ""),
            "page": h.page,
            "block_type": h.payload.get("block_type", ""),
            "figure_no": h.payload.get("figure_no", ""),
            "section": h.payload.get("section_path", ""),
            "text": h.text,
            "score": round(h.score, 4),
        }
        for h in hits
    ]


def _load_cases() -> list[dict]:
    path = Path(settings.cases_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def search_cases(
    symptom: str, device_model: str | None = None, top_k: int = 5
) -> list[dict]:
    """检索历史工单：同类故障之前怎么判、怎么修的。"""
    cases = _load_cases()
    if device_model:
        cases = [c for c in cases if c.get("device_model") == device_model] or cases
    tokens = {t for t in jieba.lcut(symptom) if len(t) > 1}
    scored = []
    for case in cases:
        bag = " ".join(
            [case.get("symptom", ""), case.get("cause", ""), case.get("alarm_code", "")]
        ).lower()
        hit = sum(1 for t in tokens if t in bag)
        if hit:
            scored.append((hit, case))
    scored.sort(key=lambda x: (-x[0], x[1].get("date", "")))
    return [c for _, c in scored[:top_k]]


def get_spare_parts(
    keyword: str = "", device_model: str | None = None, top_k: int = 8
) -> list[dict]:
    """查备件编码与库存。"""
    path = Path(settings.parts_path)
    if not path.exists():
        return []
    parts = json.loads(path.read_text(encoding="utf-8"))
    tokens = {t for t in jieba.lcut(keyword) if len(t) > 1}
    out = []
    for part in parts:
        if device_model and part.get("device_model") not in {device_model, "", None}:
            continue
        bag = f"{part.get('name','')} {part.get('code','')} {part.get('spec','')}"
        if tokens and not any(t in bag for t in tokens):
            continue
        out.append(part)
        if len(out) >= top_k:
            break
    return out


# ---------------------------------------------------------------- 副作用类
def create_work_order(card: dict, dry_run: bool = True) -> dict:
    """建工单。默认 dry-run：Agent 不允许自己拍板落库。"""
    order_id = f"WO-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "order_id": order_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "card": card,
    }
    if not dry_run:
        settings.workorder_dir.mkdir(parents=True, exist_ok=True)
        (settings.workorder_dir / f"{order_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {"ok": True, "order_id": order_id, "dry_run": dry_run}


def escalate_to_human(reason: str, summary: str = "") -> dict:
    """转人工：把已收集的上下文摘要一并交出去，人工不用重新问一遍。"""
    return {"ok": True, "escalated": True, "reason": reason, "summary": summary}
