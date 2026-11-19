"""数据结构：入库 chunk 与最终产物「检修作业卡」。"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

BlockType = Literal["text", "table", "figure", "sop"]


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    doc_title: str = ""
    device_model: str = ""
    device_type: str = ""
    page: int = 0
    block_type: BlockType = "text"
    section_path: str = ""
    heading: str = ""
    figure_no: str = ""
    table_no: str = ""
    image_path: str = ""
    vlm_desc: str = ""
    text: str = ""

    def embed_text(self) -> str:
        """用于向量化：把型号/章节这类元信息也写进语义文本。"""
        head = " ".join(
            x for x in [self.doc_title, self.device_model, self.device_type, self.section_path] if x
        )
        return f"{head}\n{self.text}".strip()

    def payload(self) -> dict:
        d = self.model_dump()
        d.pop("text", None)
        return d


class Citation(BaseModel):
    doc_id: str
    doc_title: str = ""
    page: int = 0
    block_type: str = "text"
    figure_no: str = ""
    quote: str = ""


class Cause(BaseModel):
    cause: str
    confidence: float = 0.0
    citations: list[Citation] = Field(default_factory=list)


class Step(BaseModel):
    no: int = 1
    action: str
    risk: Literal["low", "medium", "high"] = "low"
    safety: str = ""


class SparePart(BaseModel):
    code: str = ""
    name: str
    qty: int = 1


class WorkCard(BaseModel):
    device_model: str = ""
    device_type: str = ""
    fault_summary: str
    alarm_code: str = ""
    causes: list[Cause] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    spare_parts: list[SparePart] = Field(default_factory=list)
    est_man_hours: float = 0.0
    need_human: bool = False
    human_reason: str = ""
    evidence_completeness: float = 0.0
    trace: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        flag = f"⚠️ 需转人工：{self.human_reason}" if self.need_human else "✅ 可自动执行"
        lines = [
            f"## 检修作业卡 · {self.device_model or '型号未识别'}（{self.device_type}）",
            "",
            f"**故障**：{self.fault_summary}"
            + (f"  **报警码**：{self.alarm_code}" if self.alarm_code else ""),
            f"**状态**：{flag}    **引用完整率**：{self.evidence_completeness:.0%}"
            f"    **预估工时**：{self.est_man_hours}h",
            "",
            "### 可能原因（按置信度）",
        ]
        if not self.causes:
            lines.append("- 无可靠原因（证据不足）")
        for i, c in enumerate(self.causes, 1):
            lines.append(f"{i}. **{c.cause}** — 置信度 {c.confidence:.2f}")
            for cit in c.citations:
                loc = f"第{cit.page}页" if cit.page else ""
                lines.append(
                    f"   - 依据《{cit.doc_title or cit.doc_id}》{loc} {cit.figure_no}: "
                    f"{cit.quote[:120]}"
                )
        lines += ["", "### 检修步骤"]
        for s in self.steps:
            mark = {"high": "🔴", "medium": "🟡", "low": "🟢"}[s.risk]
            lines.append(f"{s.no}. {mark} {s.action}" + (f"（{s.safety}）" if s.safety else ""))
        if self.tools:
            lines += ["", f"**工具**：{'、'.join(self.tools)}"]
        if self.spare_parts:
            lines += ["", "**备件**：" + "、".join(f"{p.name}×{p.qty}" for p in self.spare_parts)]
        if self.trace:
            lines += ["", "<details><summary>执行轨迹</summary>", ""]
            lines += [f"- {t}" for t in self.trace]
            lines += ["", "</details>"]
        return "\n".join(lines)


def dumps(obj) -> str:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump()
    return json.dumps(obj, ensure_ascii=False, indent=2)
