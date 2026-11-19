"""检修作业 Agent：LangGraph 状态机。

流程：identify → retrieve → diagnose → plan → self_check →(ok/human)→ finalize
                                              └─(retry)→ diagnose（最多 1 次）

要点：模型只能引用 [E1]..[En] 这类证据编号，引用映射由代码完成，
     所以作业卡里不可能出现"模型编出来的文档出处"。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from .. import llm
from ..config import DEVICES, device_type_of, guess_device
from ..schema import Cause, Citation, SparePart, Step, WorkCard
from . import tools

log = logging.getLogger(__name__)

MAX_TRIES = 1
MIN_CONFIDENCE = 0.35

SYSTEM = (
    "你是资深设备维修工程师，负责把现场故障描述转成可执行的检修作业卡。"
    "我给你若干条证据（编号 E1、E2…），你只能依据这些证据判断，"
    "每条结论必须标注它引用的证据编号。证据不足时明确说证据不足，不要编造。"
)

DIAG_SCHEMA = """输出 JSON：
{{"causes":[{{"cause":"原因（≤20字）","confidence":0.0,"refs":["E1"]}}],
 "alarm_code":"",
 "need_more_info":"缺少什么信息才能判断，没有就留空"}}
最多 3 条原因，confidence 取 0~1。"""

PLAN_SCHEMA = """输出 JSON：
{{"steps":[{{"no":1,"action":"具体动作","risk":"low|medium|high","safety":"安全要点"}}],
 "tools":["工具"],
 "spare_parts":[{{"code":"","name":"","qty":1}}],
 "est_man_hours":1.5}}
步骤 3~8 条，按现场执行顺序。高风险动作（带电/带压/高处/旋转部件）risk 必须为 high。"""


class AgentState(TypedDict, total=False):
    symptom: str
    alarm_code: str
    device_model: str
    evidence: list[dict]
    causes: list[dict]
    plan: dict
    workcard: dict
    status: Literal["ok", "retry", "human"]
    human_reason: str
    tries: int
    trace: list[str]


# ---------------------------------------------------------------- 工具函数
def _render_evidence(evidence: list[dict]) -> str:
    if not evidence:
        return "（无检索结果）"
    lines = []
    for ev in evidence:
        loc = f"《{ev['doc_title']}》第{ev['page']}页"
        if ev.get("block_type") == "figure" and ev.get("figure_no"):
            loc += f" 图{ev['figure_no']}"
        elif ev.get("block_type") == "table":
            loc += " 表格"
        body = (ev.get("text") or "").strip().replace("\n", " ")
        lines.append(f"[{ev['id']}] {loc}：{body[:600]}")
    return "\n".join(lines)


def _ev_index(evidence: list[dict]) -> dict[str, dict]:
    return {ev["id"]: ev for ev in evidence}


def _to_citation(ev: dict) -> Citation:
    return Citation(
        doc_id=ev.get("doc_id", ""),
        doc_title=ev.get("doc_title", ""),
        page=int(ev.get("page") or 0),
        block_type=ev.get("block_type", ""),
        figure_no=ev.get("figure_no", ""),
        quote=(ev.get("text") or "")[:200],
    )


def _latency_note(trace: list[str], msg: str) -> list[str]:
    return [*trace, msg]


# ---------------------------------------------------------------- 节点
def identify(state: AgentState) -> AgentState:
    symptom = state.get("symptom", "")
    model = state.get("device_model") or guess_device(symptom)
    note = f"identify: 型号={model or '未识别'}"
    return {
        "device_model": model,
        "tries": state.get("tries", 0),
        "trace": _latency_note(state.get("trace", []), note),
    }


def retrieve(state: AgentState) -> AgentState:
    symptom = state.get("symptom", "")
    model = state.get("device_model") or None
    query = f"{symptom} {state.get('alarm_code','')}".strip()

    manual = tools.search_manual(query, device_model=model, top_k=6)
    cases = tools.search_cases(symptom, device_model=model, top_k=4)

    evidence: list[dict] = []
    for i, hit in enumerate(manual, 1):
        evidence.append({"id": f"E{i}", **hit})
    for j, case in enumerate(cases, len(evidence) + 1):
        evidence.append(
            {
                "id": f"E{j}",
                "chunk_id": case.get("case_id", ""),
                "doc_id": f"case:{case.get('case_id','')}",
                "doc_title": f"历史工单 {case.get('case_id','')}",
                "page": 0,
                "block_type": "sop",
                "figure_no": "",
                "section": "历史工单",
                "text": (
                    f"症状：{case.get('symptom','')}；判定原因：{case.get('cause','')}；"
                    f"处理：{case.get('solution','')}；耗时：{case.get('man_hours','')}h"
                ),
                "score": 0.0,
            }
        )
    note = f"retrieve: 手册 {len(manual)} 条 / 工单 {len(cases)} 条"
    return {"evidence": evidence, "trace": _latency_note(state.get("trace", []), note)}


def diagnose(state: AgentState) -> AgentState:
    evidence = state.get("evidence") or []
    if not evidence:
        return {
            "causes": [],
            "status": "human",
            "human_reason": "知识库无相关内容（可能还未入库或型号不匹配）",
            "trace": _latency_note(state.get("trace", []), "diagnose: 无证据，转人工"),
        }
    user = (
        f"设备型号：{state.get('device_model') or '未知'}\n"
        f"故障描述：{state.get('symptom','')}\n"
        f"报警码：{state.get('alarm_code') or '无'}\n\n"
        f"证据：\n{_render_evidence(evidence)}\n\n{DIAG_SCHEMA}"
    )
    try:
        data = llm.json_chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        )
    except (llm.LLMError, ValueError) as exc:
        log.warning("diagnose 解析失败：%s", exc)
        return {
            "causes": [],
            "status": "human",
            "human_reason": f"模型输出异常：{exc}",
            "trace": _latency_note(state.get("trace", []), "diagnose: 解析失败"),
        }

    index = _ev_index(evidence)
    causes = []
    for item in (data.get("causes") or [])[:3]:
        refs = [index[r] for r in (item.get("refs") or []) if r in index]
        causes.append(
            {
                "cause": str(item.get("cause", "")).strip(),
                "confidence": float(item.get("confidence") or 0.0),
                "citations": [_to_citation(ev).model_dump() for ev in refs],
            }
        )
    note = f"diagnose: {len(causes)} 条原因"
    return {
        "causes": causes,
        "alarm_code": state.get("alarm_code") or data.get("alarm_code", ""),
        "trace": _latency_note(state.get("trace", []), note),
    }


def plan(state: AgentState) -> AgentState:
    evidence = state.get("evidence") or []
    causes = state.get("causes") or []
    cause_lines = "\n".join(
        f"- {c['cause']}（置信度 {c['confidence']:.2f}，引用 {len(c['citations'])} 条）"
        for c in causes
    )
    user = (
        f"设备型号：{state.get('device_model') or '未知'}\n"
        f"故障描述：{state.get('symptom','')}\n"
        f"已判定原因：\n{cause_lines or '（无）'}\n\n"
        f"证据：\n{_render_evidence(evidence)}\n\n{PLAN_SCHEMA}"
    )
    try:
        data = llm.json_chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        )
    except (llm.LLMError, ValueError) as exc:
        log.warning("plan 解析失败：%s", exc)
        data = {}
    return {"plan": data, "trace": _latency_note(state.get("trace", []), "plan: 作业卡草稿")}


def self_check(state: AgentState) -> AgentState:
    causes = state.get("causes") or []
    evidence = state.get("evidence") or []
    trace = state.get("trace", [])

    if not causes or not evidence:
        return {
            "status": "human",
            "human_reason": state.get("human_reason") or "无可靠原因",
            "trace": _latency_note(trace, "self_check: 无原因 → 转人工"),
        }

    cited = [c for c in causes if c.get("citations")]
    completeness = len(cited) / len(causes)
    top_conf = max(float(c.get("confidence") or 0.0) for c in causes)

    if completeness < 1.0 and state.get("tries", 0) < MAX_TRIES:
        return {
            "status": "retry",
            "tries": state.get("tries", 0) + 1,
            "trace": _latency_note(trace, f"self_check: 引用缺失({completeness:.0%}) → 重判"),
        }

    reason = ""
    if not state.get("device_model"):
        reason = "设备型号未识别，需人工确认"
    elif top_conf < MIN_CONFIDENCE:
        reason = f"最高置信度 {top_conf:.2f} 低于阈值 {MIN_CONFIDENCE}"
    elif completeness < 1.0:
        reason = "部分结论缺少可追溯引用"

    note = f"self_check: 引用完整率 {completeness:.0%}, 最高置信度 {top_conf:.2f}"
    return {
        "status": "human" if reason else "ok",
        "human_reason": reason,
        "evidence_completeness": completeness,
        "trace": _latency_note(trace, note),
    }


def finalize(state: AgentState) -> AgentState:
    plan_data = state.get("plan") or {}
    steps = [
        Step(
            no=int(s.get("no") or i + 1),
            action=str(s.get("action", "")).strip(),
            risk=s.get("risk") if s.get("risk") in {"low", "medium", "high"} else "medium",
            safety=str(s.get("safety", "")),
        )
        for i, s in enumerate(plan_data.get("steps") or [])
        if str(s.get("action", "")).strip()
    ]
    parts = [
        SparePart(
            code=str(p.get("code", "")),
            name=str(p.get("name", "")),
            qty=int(p.get("qty") or 1),
        )
        for p in (plan_data.get("spare_parts") or [])
        if str(p.get("name", "")).strip()
    ]
    status = state.get("status") or "human"

    card = WorkCard(
        device_model=state.get("device_model", ""),
        device_type=device_type_of(state.get("device_model", "")),
        fault_summary=state.get("symptom", ""),
        alarm_code=state.get("alarm_code", ""),
        causes=[Cause(**c) for c in (state.get("causes") or [])],
        steps=steps,
        tools=[str(t) for t in (plan_data.get("tools") or []) if str(t).strip()],
        spare_parts=parts,
        est_man_hours=float(plan_data.get("est_man_hours") or 0.0),
        need_human=status == "human",
        human_reason=state.get("human_reason", "") if status == "human" else "",
        evidence_completeness=float(state.get("evidence_completeness") or 0.0),
        trace=state.get("trace", []),
    )
    if card.need_human:
        card.trace = _latency_note(card.trace, f"escalate: {card.human_reason}")
        tools.escalate_to_human(card.human_reason, card.fault_summary)
    return {"workcard": card.model_dump()}


def route(state: AgentState) -> str:
    return {"ok": "finalize", "human": "finalize", "retry": "diagnose"}.get(
        state.get("status") or "human", "finalize"
    )


# ---------------------------------------------------------------- 组图
@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("identify", identify)
    g.add_node("retrieve", retrieve)
    g.add_node("diagnose", diagnose)
    g.add_node("plan", plan)
    g.add_node("self_check", self_check)
    g.add_node("finalize", finalize)

    g.set_entry_point("identify")
    g.add_edge("identify", "retrieve")
    g.add_edge("retrieve", "diagnose")
    g.add_edge("diagnose", "plan")
    g.add_edge("plan", "self_check")
    g.add_conditional_edges(
        "self_check", route, {"finalize": "finalize", "diagnose": "diagnose"}
    )
    g.add_edge("finalize", END)
    return g.compile()


def run_agent(
    symptom: str, device_model: str = "", alarm_code: str = ""
) -> WorkCard:
    model = device_model or guess_device(symptom)
    state: AgentState = {
        "symptom": symptom,
        "alarm_code": alarm_code,
        "device_model": model if model in DEVICES else "",
        "tries": 0,
        "trace": [],
    }
    if model and model not in DEVICES:
        state["trace"] = [f"identify: 型号 {model} 不在支持列表 {list(DEVICES)}"]
    out = build_graph().invoke(state)
    return WorkCard(**out["workcard"])
