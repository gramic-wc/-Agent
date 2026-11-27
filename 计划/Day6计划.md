# Day 6 计划 · 2 小时（2026-11-27 周五，VLM 权限阻塞）

> **今天的唯一硬目标**：在 Day5 的干净库基础上，给 **339 张图**补上可检索的 VLM 描述，重建索引并证明图纸类检索开始生效。
>
> **没有“改前/改后覆盖率 + 5 张人工抽查 + W1 召回回归”三项证据，今天不算完成。**
>
> **实测结论：Day6 未完成。** VLM 成功 **0/339**，账号/模型权限未通；
> 文本索引和 W1 召回保持稳定，但图纸描述、质量抽查、图纸检索均未进入可验收状态。

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
| **VLM 真实调用** | ❌ `qwen-vl-max-latest` 首图 `HTTP 403 access_denied`；前序请求还有 `WinError 10061` | 当前账号/模型权限未通，禁止直接跑全量 |
| **备用模型探测** | ❌ `qwen-vl-plus` / `qwen-vl-max` 均返回 `404 model_not_found` | 不能只换模型名，需在百炼控制台确认可用视觉模型与账号授权 |
| **本次长跑结果** | ❌ 约 19 分钟、成功 **0**、失败 47，已手动停止 | `chunks.jsonl` / Qdrant 保持 **1956 / 1956**，未写半成品 |

> **按最新排期：VLM 图纸描述是 Day6 的主变量。**
> 原学习计划里的“补手册 / 缩范围”会引入第二个变量，今天不混做；放到 Day7 复盘时再决策。

## 0.1 执行复盘：做对 / 没做对 / 需要改

| 类别 | 事实 | 判断 |
| --- | --- | --- |
| ✅ 做对 | 先记录 Day5 基线和门禁，确认 `1956 / 339 / 0 / 339` | Day6 输入干净，问题不来自 Day5 |
| ✅ 做对 | 失败后停止长跑，并确认 `chunks.jsonl` / Qdrant 仍为 `1956 / 1956` | 没有把 0 覆盖率的半成品写进索引 |
| ✅ 做对 | 三自检仍然通过：点数==行数、孤儿点 0、不一致 0.0%、dense 30/30 | 文本索引没有被 VLM 失败污染 |
| ❌ 没做对 | 预检只打印了 key/model，没有先真实调用一张图 | 让一个已知的 403 权限问题进入全量任务 |
| ❌ 没做对 | 第一版 `_post` 对 403 仍重试，`describe_figures` 又吞掉每张图的失败 | 约 19 分钟空跑、成功 0，日志累计 47 次失败 |
| ❌ 没做对 | 日志没有强制 UTF-8，PowerShell 管道里中文变乱码 | 故障文本可读性差，排查成本增加 |
| 🔧 已改 | 400/401/403/404 不重试；鉴权/模型错误立即中止；其他错误连续 3 张中止 | 受控复测约 23 秒退出，不再空跑 |
| 🔧 已改 | 预检新增“真实调用一张图”的冒烟测试 | 以后先验权限，再开全量 |
| ⏭️ 待处理 | `qwen-vl-max-latest` 返回 403；`qwen-vl-plus` / `qwen-vl-max` 返回 404 | 需要到百炼控制台确认可用视觉模型和账号授权 |

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

只打印配置**不算通过**，必须真实调用一张图：

```powershell
uv run python -c "import json; from eqagent import llm; from eqagent.ingest.image_desc import PROMPT; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; r=next(x for x in rows if x.get('block_type')=='figure' and x.get('image_path')); desc=llm.vlm_describe(r['image_path'],PROMPT); print('VLM_PREFLIGHT_OK'); print(desc[:200])"
```

合格：命令输出 `VLM_PREFLIGHT_OK` 和非空中文描述。
不合格：出现 `401/403 access_denied`、`404 model_not_found` 或网络拒绝时，**立即停止**，不要跑全量。
本次实测：`qwen-vl-max-latest` 返回 403，备用 `qwen-vl-plus` / `qwen-vl-max` 返回 404；
因此 2.2 之后的步骤都没有继续。

## 2.2 记录改前基线

```powershell
uv run python -c "import json,os; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; figs=[r for r in rows if r.get('block_type')=='figure']; print('chunks_before=',len(rows)); print('figures_before=',len(figs)); print('vlm_ok_before=',sum(bool(r.get('vlm_desc')) for r in figs)); print('images_exist=',sum(bool(r.get('image_path') and os.path.exists(r['image_path'])) for r in figs))"
```

把下面四个数字先写到纸上/便签里：

- 改前总块数：1956
- 改前图块数：339
- 改前 VLM 覆盖率：0
- 图片存在数：339

> 当前预期：`1956 / 339 / 0 / 339`。如果图片存在数不是 339，先查 `data/figure_cache`，不要跑 VLM。

---

# 第三部分 · 全量 VLM 描述 + 重建（45 分钟）

## 3.1 只跑这一条主命令

```powershell
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
New-Item -ItemType Directory -Force 'data\index\logs' | Out-Null
$sw = [System.Diagnostics.Stopwatch]::StartNew()
uv run eq-ingest 2>&1 | Tee-Object -FilePath 'data\index\logs\day6_vlm.log'
$sw.Stop()
"耗时分钟: $([math]::Round($sw.Elapsed.TotalMinutes, 1))"
if ($LASTEXITCODE -ne 0) { throw "eq-ingest 失败，退出码 $LASTEXITCODE" }
```

这条命令会：

1. 重新解析/切块；
2. 给 figure 块调用 VLM；
3. 写新的 `chunks.jsonl`；
4. 删除并重建 Qdrant collection。

> **不要先手动删 `data/qdrant`。** `eq-ingest` 内部会重建 collection，手动删除容易制造新的“库与切块不同代”问题。

## 3.2 运行中的观察点

- 日志应持续出现 `VLM n/339 ...`；
- 若出现 401/403：API Key 或模型权限问题，停止；当前代码已改成 **401/403 不重试**；
- **10 分钟内没有一条成功的 `VLM n/339` 就停止**，不要等 45 分钟；这通常不是慢，而是鉴权、模型权限或网络持续失败；
- 若出现 429：限流，记录出现在第几张；
- 若连续 3 张 `图纸描述失败`，当前代码会主动中止全量任务，避免把失败图循环完再进入重嵌入。

## 3.3 超时护栏

- 超过 45 分钟仍未结束：先看日志处理到第几张；
- 如果只是慢，允许最多再跑 10 分钟，占用后续抽查时间；
- **10 分钟无成功进度立即停止**；如果已明确鉴权/模型权限/大量失败，停止全量运行，记录 coverage 与失败原因；
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
| VLM 覆盖率 | ≥ 95%（≥ 323 / 339），且失败都有日志 | ❌ **0 / 339** |
| 三类设备都有成功描述 | GA55 / VMC850 / YE3 均 > 0 | ❌ **GA55 0 / VMC850 0 / YE3 0** |
| 点数 == `chunks.jsonl` 行数 | 完全相等 | ✅ **1956 == 1956** |
| 孤儿点 | 0 | ✅ **0** |
| `payload.text` 不一致率 | < 1% | ✅ **0.0%** |
| dense 条数 | 30/30 | ✅ **30/30** |
| 总块数 | 不应因 VLM 大幅变化 | ✅ **1956 → 1956** |

> 说明：VLM 只补 `vlm_desc` 并把描述拼进图块 `text`，不应改变正文块/表格块数量和切块逻辑。
> 如果总块数变化异常，先查是不是误跑了另一版切块代码。

## 4.2 失败处理

| 现象 | 处理 |
| --- | --- |
| `401/403 access_denied` | 当前账号无模型权限；立即停止，去控制台开通/授权，不要继续全量 |
| `404 model_not_found` | 模型名不可用；查控制台当前可用模型，不能盲试模型名 |
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

**Day6 实测：未执行（0 / 5）。** 原因是没有生成任何 `vlm_desc`，不能拿原图猜“描述质量”。

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

**Day6 实测：0 / 3。**

| query | top5 是否出现 figure | 说明 |
| --- | --- | --- |
| GA55 油冷却器 结构 拆装 | ❌ | top5 全是 text/table |
| VMC850 刀库 结构 图 | ❌ | top5 全是 text/table |
| YE3 接线盒 接线图 | ❌ | top5 全是 text/table |

> 这不是检索参数需要马上调整，而是 VLM 覆盖率仍为 0；先解决模型权限，再看图纸是否可检索。

## 5.3 W1 召回回归

把 Day5 的术语 8 条和口语 d01~d08 再跑一次，记成 C 列：

- Day5 B：术语 **8 / 8**，口语 **8 / 8**，术语污染 **7 / 40**，口语污染 **2 / 40**；
- Day6 C：术语 **8 / 8**，口语 **8 / 8**，术语污染 **7 / 40**，口语污染 **2 / 40**。

**合格线：C 不低于 B。**
如果下降 1 条，先看是否是图块描述挤掉了原来的正文/表格；不要当天改 `top_k` 或 RRF。

**Day6 实测：C = B。** 因为 VLM 没有写入任何图块，索引与 Day5 完全同代；这只证明“没有破坏原召回”，不能证明“VLM 检索生效”。

---

# 第六部分 · 收尾（15 分钟）

## 6.1 写 `docs/metrics.md`

实测行：

```markdown
| 2026-11-27（Day6 阻塞） | 尝试全量 VLM 图纸描述；预检改为真实单图调用；403/404 改为快速失败，连续失败中止 | — | — | — | — | — | VLM **0/339**，设备分布 GA55 0 / VMC850 0 / YE3 0；`qwen-vl-max-latest` 403 access_denied，`qwen-vl-plus`/`qwen-vl-max` 404 model_not_found；人工抽查未执行 **0/5**；图纸检索 **0/3**；索引 **1956==1956**、孤儿点 0、不一致 0.0%、dense 30/30；W1 **B=C**：术语 8/8、口语 8/8、术语污染 7/40、口语污染 2/40；长跑约 19 分钟成功 0，修复后受控失败约 23 秒退出 |
```

## 6.2 提交

```powershell
git status --short
git diff --stat
git add -A
git commit -m "feat(ingest): 完成图纸VLM描述并重建索引；记录Day6覆盖率、抽查与W1回归"
git push
```

本次覆盖率未过线，提交信息应为：

```text
wip(vlm): Day6 VLM权限阻塞(0/339)；增加单图预检与403快速失败
```

**不许把“试了但没数字”的改动留在工作区过夜。**

## 6.3 给下一天留一句话

> 今天动的层是 **VLM 图纸描述 + 索引重建**。
> 结果是：覆盖率 **0 / 339**，抽查 **0 / 5**，图纸检索 **0 / 3**，W1 **B=C（术语/口语 8/8）**。
> 明天第一件事应该是：**先修通百炼 VLM 模型权限，并跑单图预检**；
> 因为今天的数据说明：**VLM 描述完全没有生成，任何 claim 出图/抽查/图纸检索的结论都不成立，但文本索引和三自检没有退化**。

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

| 验收项 | 结果 | 判定 |
| --- | --- | --- |
| 覆盖率 VLM 非空 ≥ 323 / 339 | **0 / 339** | ❌ 未通过 |
| 索引一致：点数==行数、孤儿点 0、不一致 <1%、dense 30/30 | **1956==1956 / 0 / 0.0% / 30/30** | ✅ 通过 |
| 5 张原图人工抽查，5/5 无幻觉 | **0 / 5（无可抽查描述）** | ❌ 未执行 |
| 至少 1 条图纸 query top5 命中相关 figure，且 W1 不低于 Day5 | 图纸检索 **0 / 3**；W1 **B=C** | ❌ 图纸部分未通过 |

> **最终判定：Day6 未完成，属于外部权限阻塞，不是“部分完成可宣布”。**
> 做对的隔离是：失败没有污染文本索引，W1 没有退化。
> 下一步只有先修通视觉模型权限并产出至少 1 条真实描述，才能继续全量。
