# 设备检修知识检索与作业 Agent

> 4 周学习项目。业务场景借自「中国软件杯 A1 基于多模态大模型技术的设备检修知识检索与作业系统」，
> **不参赛**，只把赛题当业务域，目标是把 Agent 工程的完整闭环跑一遍：检索 → 判因 → 出作业卡 → 可追溯 → 可评测。

核心主张：**不是做一个「问答机器人」，而是产出能被维修班组直接执行的作业卡，且每条结论都能点到手册页码。**

---

## 1. 架构

```
                    ┌──────────────── 入库（离线，跑一次） ────────────────┐
  PDF 手册 ──▶ 版面切分 ──▶ 正文 / 表格 / 图纸 三类 chunk ──▶ VLM 描述图纸
                    │            （带 doc/page/section/图号 元数据）
                    └──────────▶ chunks.jsonl ──▶ Qdrant(向量) ──┘
                                                             │
  现场描述 ─▶ identify ─▶ retrieve(混合检索) ─▶ diagnose ─▶ plan ─▶ self_check ─▶ 作业卡
                │              ▲                    ▲                  │
                │          手册+历史工单        只允许引用 E1..En      │ 低置信度/引用缺失
                └──── 型号识别 ─┘                    │                 ▼
                                                  引用映射（代码做，不信模型）   转人工
```

## 2. 目录

```
src/eqagent/
├─ config.py          参数中心：模型、路径、三台设备的型号别名
├─ schema.py          Chunk / WorkCard 数据结构（作业卡 schema 定死，后面全靠它）
├─ llm.py             通义千问：对话 / VL / embedding / rerank，统一重试
├─ knowledge.py       12 类高发故障（生成工单 + 评测期望答案）
├─ ingest/
│  ├─ parse.py        PDF → chunk（表格、图纸、标题栈、页码）
│  ├─ chunker.py      切块与表格转 Markdown
│  ├─ image_desc.py   图纸 → VLM 结构化描述（多模态的关键一步）
│  └─ pipeline.py     入库 CLI
├─ retrieve/
│  ├─ index.py        Qdrant 封装（默认嵌入式，免 Docker）
│  └─ hybrid.py       向量 + BM25 → RRF → rerank
├─ agent/
│  ├─ graph.py        LangGraph 状态机 + 自检 + 转人工
│  ├─ tools.py        业务动作工具（检索 / 备件 / 建单 / 转人工）
│  └─ run.py          命令行入口
└─ eval/runner.py     离线评测：命中率 / 引用覆盖 / 拒答 / 延迟
app/streamlit_app.py  演示界面（左引用、右作业卡）
data/                 manuals(手册) / cases(工单) / parts(备件) / eval(评测集)
docs/plan.md          4 周排期与验收标准
docs/metrics.md       指标记录表（每次调参填一行）
```

## 3. 快速开始

```powershell
# 0) 环境（本机 python 是 Store 假链，用 uv 管理）
copy .env.example .env      # 填入 DASHSCOPE_API_KEY
uv sync

# 1) 造历史工单 + 备件台账（离线，可复现）
uv run python scripts/gen_data.py --cases 200

# 2) 放手册到 data/manuals/（见该目录 README），然后入库
uv run eq-ingest --no-vlm          # 先验证文本/表格链路
uv run eq-ingest                   # 再补图纸理解（消耗 VL 额度）

# 3) 跑一张作业卡
uv run eq-ask "3号车间GA55运行20分钟后排气温度高跳机"

# 4) 网页演示
uv run streamlit run app/streamlit_app.py

# 5) 评测（调完 prompt / 检索参数必跑）
uv run eq-eval
```

> 本机 Docker 未启动，所以 Qdrant 默认走**嵌入式本地模式**（`data/qdrant/`，无需 Docker）。
> 想跑服务端：`docker compose up -d` 后在 `.env` 设 `QDRANT_URL=http://localhost:6333`。

## 4. 三个关键设计（面试会被问）

1. **图纸不是什么都没做**：图注 + VLM 描述一起写进 chunk text，图号进元数据。
   否则「图 3-2 润滑油路」这类信息永远检索不到。
2. **模型不许编出处**：prompt 只允许它引用 `E1/E2…`，映射回文档由代码完成 →
   作业卡里的 `citations` 一定是真实检索结果。
3. **副作用工具默认 dry-run**：建工单必须人工确认；低置信度/引用缺失自动转人工并附摘要。

## 5. 明确没做（写出来比藏起来好）

- 不与真实工单系统（EAM/ERP）对接，`create_work_order` 是 mock
- 不做多 Agent 协作、不做自动规划、不微调模型
- 不做用户体系 / 权限 / 多租户
- 手册是公开资料整理，非客户真实文档
- 评测集 30 条规模，指标用于自我迭代，不构成产品级结论

## 6. 排期与指标

见 `docs/plan.md`（4 周任务与验收）与 `docs/metrics.md`（指标记录）。
