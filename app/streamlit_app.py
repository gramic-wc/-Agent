"""演示界面：左边看引用，右边看作业卡。

启动：uv run streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eqagent.agent.graph import run_agent  # noqa: E402
from eqagent.agent.tools import search_manual  # noqa: E402
from eqagent.config import DEVICES  # noqa: E402

st.set_page_config(page_title="设备检修作业 Agent", page_icon="🔧", layout="wide")
st.title("🔧 设备检修知识检索与作业 Agent")
st.caption("故障描述 → 检索手册/图纸/历史工单 → 判因 → 生成可执行检修作业卡（结论均可追溯到页码）")

with st.sidebar:
    st.subheader("故障输入")
    model = st.selectbox(
        "设备型号", ["（自动识别）", *DEVICES.keys()], index=0
    )
    alarm = st.text_input("报警码（可选）", placeholder="如 E-201")
    symptom = st.text_area(
        "现场描述",
        value="3号车间GA55空压机运行约20分钟后排气温度高报警并跳机，环境温度35℃",
        height=120,
    )
    run = st.button("生成检修作业卡", type="primary", use_container_width=True)
    st.divider()
    st.caption("提示：先用 eq-ingest 把手册入库，否则只能命中历史工单。")

if run and symptom.strip():
    with st.spinner("检索 + 研判中…"):
        try:
            card = run_agent(symptom, "" if model.startswith("（") else model, alarm)
        except Exception as exc:  # 演示界面不做细粒度异常分类
            st.error(f"运行失败：{exc}")
            st.stop()

    left, right = st.columns([5, 4], gap="large")

    with right:
        st.markdown(card.to_markdown())
        if card.need_human:
            st.warning(f"已转人工：{card.human_reason}")

    with left:
        st.subheader("引用溯源")
        if not card.causes:
            st.info("本次没有可用证据。")
        for i, cause in enumerate(card.causes, 1):
            with st.expander(f"{i}. {cause.cause} · 置信度 {cause.confidence:.2f}", expanded=i == 1):
                if not cause.citations:
                    st.warning("该结论缺少引用（应触发转人工）。")
                for cit in cause.citations:
                    st.markdown(
                        f"**《{cit.doc_title or cit.doc_id}》** 第 {cit.page} 页 "
                        f"· {cit.block_type}{f' · 图{cit.figure_no}' if cit.figure_no else ''}"
                    )
                    st.code(cit.quote, language="text")

        with st.expander("原始检索结果（调参用）"):
            hits = search_manual(
                symptom, device_model=None if model.startswith("（") else model, top_k=8
            )
            if not hits:
                st.info("无检索结果——先跑 `uv run eq-ingest`。")
            for h in hits:
                st.markdown(
                    f"- `{h['score']}` **{h['doc_title']}** p{h['page']} "
                    f"[{h['block_type']}] {h['text'][:160]}"
                )
else:
    st.info("在左侧填入现场描述后点击生成。")
