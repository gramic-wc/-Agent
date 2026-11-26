# Day 6 计划 · 2 小时（2026-11-27 周五）

> **今天的唯一硬目标**：在 Day5 的干净库基础上，给 **339 张图**补上可检索的 VLM 描述，重建索引并证明图纸类检索开始生效。
>
> **没有“改前/改后覆盖率 + 5 张人工抽查 + W1 召回回归”三项证据，今天不算完成。**

---

## 0. 当前状态（2026-11-26 Day5 完成后核对）

| 项目 | 当前状态 | 对明天的意义 |
| --- | --- | --- |
| Git | Day5 代码、计划和资料已提交 | 从干净基线启动 Day6 |
| `parse.py` 页眉规则 | 已有收紧版 `_drop_running_headers` | 只删顶部跨页重复页眉，保留原始字号中位数 |
| `docs/metrics.md` | 已有 Day5 实测行 | W1 A/B 与三自检数字可复用 |
| 当前块数 | **1956**（2023→1956，移除 69 行页眉） | Day6 VLM 不应改变正文/表格块数 |
| 图纸块 | 339 张（GA55 57 / VMC850 256 / YE3 26） | 今天要处理的主体 |
| `vlm_desc` 非空 | **0 / 339** | 多模态检索链路还没打开 |
| 图片文件存在 | 339 / 339 | 不需要重新裁图 |
| W1 基线 | 术语 **8/8**、口语 **8/8** | VLM 后必须做 C 列回归 |

> **按最新排期：VLM 图纸描述是 Day6 的主变量。**
> 原学习计划里的“补手册 / 缩范围”会引入第二个变量，今天不混做；放到 Day7 复盘时再决策。

---

## 1. Day5 门禁结果与执行路径

### Day5 门禁：已通过

| 门禁项 | 结果 |
| --- | --- |
| `docs/metrics.md` 有 Day5 行 | ✅ 2026-11-26 |
| `parse.py` 页眉函数 + 重切重建 | ✅ `_drop_running_headers`，块数 2023→1956 |
| 三自检 | ✅ 1956==1956、孤儿点 0、不一致 0.0%、dense 30/30 |
| W1 A/B | ✅ 术语 8/8→8/8；口语 8/8 |
| 工作区 | ✅ Day5 提交后干净 |

> 今天执行 VLM 图纸描述主路径。若 Day6 开始时复核发现门禁失效，
> 立即停止，不跑全量 VLM，回到 `Day5计划.md` 收口。

> VLM 会烧 API 额度并重建整个索引，因此必须在 Day5 的 1956 块干净文本库上单变量执行。

---

## 2. 时间表（2 小时，含一次休息）

| 时段 | 干什么 | 分钟 |
| --- | --- | --- |
| 0:00-0:10 | **门禁**：确认 Day5 已完成，记录当前块数/图数 | 10 |
| 0:10-0:20 | **预检**：API Key、VLM 模型、图片完整性 | 10 |
| 0:20-1:05 | **全量 VLM 描述 + 重建索引** | 45 |
| 1:05-1:15 | 休息 | 10 |
| 1:15-1:30 | **覆盖率 + 索引一致性自检** | 15 |
| 1:30-1:45 | **5 张人工抽查 + 图纸检索验证 + W1 回归** | 15 |
| 1:45-2:00 | 写 `docs/metrics.md`、提交、给下一天留结论 | 15 |

**铁律**：当天只动 VLM 这一层。
`chunker.py`、`top_k`、`RRF_K`、embedding、rerank 模型、`identify` 节点、手册数据，一律不改。

---

# 第一部分 · 门禁（10 分钟）

```powershell
cd "D:\pi 工作文件夹\项目学习"

git status --short
git log -1 --oneline
Select-String -LiteralPath 'docs\metrics.md' -Pattern '2026-11-26' -Encoding UTF8
Select-String -LiteralPath 'src\eqagent\ingest\parse.py' -Pattern '_drop_running_headers' -Encoding UTF8
uv run python scripts/verify_day3.py 2>$null
```

### 通过标准

- `git status --short` 为空；
- `metrics.md` 能找到 Day5 行；
- `parse.py` 能找到页眉函数；
- `verify_day3.py` 显示点数 == 行数、孤儿点 0、不一致率 < 1%、dense 30/30。

### 不通过

立即停止：打开 `计划\Day5计划.md`，先收口 Day5 门禁。
**不要抱着“先试 10 张 VLM”的心态跳步。**

---

# 第二部分 · 预检（10 分钟）

## 2.1 确认 API 和模型

```powershell
uv run python -c "from eqagent.config import settings; print('has_key=', settings.has_key); print('vlm_model=', settings.vlm_model)"
```

合格：`has_key=True`，模型为预期 VLM。
不合格：不要开始全量任务；先修 `.env`，这一步最多 10 分钟。

## 2.2 记录改前基线

```powershell
uv run python -c "import json,os; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; figs=[r for r in rows if r.get('block_type')=='figure']; print('chunks_before=',len(rows)); print('figures_before=',len(figs)); print('vlm_ok_before=',sum(bool(r.get('vlm_desc')) for r in figs)); print('images_exist=',sum(bool(r.get('image_path') and os.path.exists(r['image_path'])) for r in figs))"
```

把下面四个数字先写到纸上/便签里：

- 改前总块数：____
- 改前图块数：____
- 改前 VLM 覆盖率：____ / ____
- 图片存在数：____ / ____

> 当前预期：`1956 / 339 / 0 / 339`。如果图片存在数不是 339，先查 `data/figure_cache`，不要跑 VLM。

---

# 第三部分 · 全量 VLM 描述 + 重建（45 分钟）

## 3.1 只跑这一条主命令

```powershell
New-Item -ItemType Directory -Force 'data\index\logs' | Out-Null
$sw = [System.Diagnostics.Stopwatch]::StartNew()
uv run eq-ingest 2>&1 | Tee-Object -FilePath 'data\index\logs\day6_vlm.log'
$sw.Stop()
"耗时分钟: $([math]::Round($sw.Elapsed.TotalMinutes, 1))"
```

这条命令会：

1. 重新解析/切块；
2. 给 figure 块调用 VLM；
3. 写新的 `chunks.jsonl`；
4. 删除并重建 Qdrant collection。

> **不要先手动删 `data/qdrant`。** `eq-ingest` 内部会重建 collection，手动删除容易制造新的“库与切块不同代”问题。

## 3.2 运行中的观察点

- 日志应持续出现 `VLM n/339 ...`；
- 若出现 401/403：API Key 或模型权限问题，停止；
- 若出现 429：限流，记录出现在第几张；
- 若出现大量 `图纸描述失败`：记录失败率和错误文本，不要现场改 prompt。

## 3.3 超时护栏

- 超过 45 分钟仍未结束：先看日志处理到第几张；
- 如果只是慢，允许最多再跑 10 分钟，占用后续抽查时间；
- 如果已明确限流/大量失败，停止全量运行，记录 coverage 与失败原因；
- **不要当天临时改成多线程并同时改 prompt**，那会变成无法归因的新实验。

---

# 第四部分 · 覆盖率 + 索引自检（15 分钟）

```powershell
uv run python -c "import json,collections; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; figs=[r for r in rows if r.get('block_type')=='figure']; print('chunks_after=',len(rows)); print('figures_after=',len(figs)); print('vlm_ok_after=',sum(bool(r.get('vlm_desc')) for r in figs)); print('vlm_missing=',sum(not r.get('vlm_desc') for r in figs)); print('by_device_ok=',dict(collections.Counter(r.get('device_model') or '未识别' for r in figs if r.get('vlm_desc'))))"

uv run python scripts/verify_day3.py 2>$null
uv run python scripts/chunk_stats.py 2>$null
```

## 4.1 今天的合格线

| 检查项 | 合格线 | 实测 |
| --- | --- | --- |
| VLM 覆盖率 | ≥ 95%（≥ 323 / 339），且失败都有日志 | ____ / 339 |
| 三类设备都有成功描述 | GA55 / VMC850 / YE3 均 > 0 | ____ |
| 点数 == `chunks.jsonl` 行数 | 完全相等 | ____ |
| 孤儿点 | 0 | ____ |
| `payload.text` 不一致率 | < 1% | ____ |
| dense 条数 | 30/30 | ____ |
| 总块数 | 不应因 VLM 大幅变化 | 1956 → ____ |

> 说明：VLM 只补 `vlm_desc` 并把描述拼进图块 `text`，不应改变正文块/表格块数量和切块逻辑。
> 如果总块数变化异常，先查是不是误跑了另一版切块代码。

## 4.2 失败处理

| 现象 | 处理 |
| --- | --- |
| 覆盖率 90%~95% | 记录失败图块 ID 和原因，明天只补失败项；今天可判“部分完成” |
| 覆盖率 < 90% | 今天不合格，不写“已完成”；先查 429/网络/图片格式 |
| 点数与行数不一致 | 立即重跑 `eq-ingest`，不要继续抽查 |
| 不一致率 ≥ 1% | 同上，说明重建没做干净 |

---

# 第五部分 · 人工抽查 + 检索回归（15 分钟）

## 5.1 抽 5 张图，人工对照

要求覆盖：GA55 2 张、VMC850 2 张、YE3 1 张。

每张检查三件事：

1. 图类型判断对不对（零件图/剖面图/流程图/接线图/检修示意）；
2. 部件名称和编号有没有“看图编造”；
3. 与检修相关的信息是否只来自图上可见内容。

**合格线：5/5 无明显幻觉。**
“不清晰”是允许的答案；“猜一个不存在的零件编号”不允许。

## 5.2 图纸检索验证

```powershell
uv run python -c "from eqagent.agent.tools import search_manual; qs=['GA55 油冷却器 结构 拆装','VMC850 刀库 结构 图','YE3 接线盒 接线图']; [print('\n###',q,*[(h['device_model'],h['doc_title'][:14],'p'+str(h['page']),h['block_type']) for h in search_manual(q,top_k=5)],sep='\n  ') for q in qs]"
```

记录：

- 3 条 query 中，有多少条 top5 出现 `figure`；
- 命中的图是否确实与 query 相关；
- 如果一条都没有，不要改检索参数，先判断是“描述没有进入 text”还是“query 不自然”。

**建议验收：至少 1 条 query 的 top5 出现相关 figure。**
这不是最终指标，只证明 VLM 描述已经能参与检索。

## 5.3 W1 召回回归

把 Day5 的术语 8 条和口语 d01~d08 再跑一次，记成 C 列：

- Day5 B：术语 **8 / 8**，口语 **8 / 8**，术语污染 **7 / 40**，口语污染 **2 / 40**；
- Day6 C：术语 ____ / 8，口语 ____ / 8，污染 ____ / 40。

**合格线：C 不低于 B。**
如果下降 1 条，先看是否是图块描述挤掉了原来的正文/表格；不要当天改 `top_k` 或 RRF。

---

# 第六部分 · 收尾（15 分钟）

## 6.1 写 `docs/metrics.md`

追加一行，至少包含：

- 2026-11-27 Day6 实测；
- VLM 图块覆盖率：0/339 → ____ / 339；
- 成功设备分布；
- 5 张抽查通过数：____ / 5；
- 图纸检索命中：____ / 3；
- W1 B → C（术语 / 口语 / 污染）；
- 索引自检：点数、孤儿点、不一致率、dense 条数；
- 运行耗时、失败数和主要原因。

## 6.2 提交

```powershell
git status --short
git diff --stat
git add -A
git commit -m "feat(ingest): 完成图纸VLM描述并重建索引；记录Day6覆盖率、抽查与W1回归"
git push
```

如果覆盖率未过线，提交信息改成：

```text
wip(ingest): Day6 VLM图纸描述部分完成；记录覆盖率与失败原因
```

**不许把“试了但没数字”的改动留在工作区过夜。**

## 6.3 给下一天留一句话

> 今天动的层是 **VLM 图纸描述 + 索引重建**。
> 结果是：覆盖率 ____ / 339，抽查 ____ / 5，图纸检索 ____ / 3，W1 ____。
> 明天第一件事应该是：**补失败图 / 优化 VLM prompt / 补手册缺口 / Day7 复盘** 中的一项，因为今天的数据说明：____。

---

# 附 · 今天明确不做（防发散）

| 内容 | 为什么不做 |
| --- | --- |
| 补 GA55 中文手册、VMC850 整机手册 | 这是“加数据”变量，会和 VLM 覆盖率混在一起 |
| 改 VLM prompt | 今天先量“现有 prompt 的真实覆盖率”，明天再优化 |
| 改 `chunker.py` / `top_k` / `RRF_K` | Day5 刚建立干净基线，不能同时移动检索参数 |
| 改 embedding / rerank 模型 | 成本高、变量大，等 W1 完全收口 |
| `identify` 型号识别节点 | 属于 Day8/9，不在今天 |
| 只做 10 张图就宣布完成 | 10 张只能算试跑，不能代表 339 张图块 |

---

# 附 · 今天的四条硬验收

1. **覆盖率**：VLM 非空 ≥ 323 / 339，失败项有日志解释。
2. **索引一致**：点数 == 行数、孤儿点 0、不一致率 < 1%、dense 30/30。
3. **质量证据**：5 张原图人工对照，5/5 无明显幻觉。
4. **可检索**：至少 1 条图纸类 query 在 top5 命中相关 figure，且 W1 召回不低于 Day5。

> 1 + 2 = 合格；四条全做到 = 满分。
> 若 Day5 门禁未通过，今天不做以上任何一项，直接回到 `Day5计划.md`。
