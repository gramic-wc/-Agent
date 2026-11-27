# Day 7 计划 · 2 小时（2026-11-28 周六，VLM 权限修复 + 图纸验收 + 周复盘）

> **今天的唯一硬目标**：先修通视觉模型权限，再给 **339 张图**生成可检索的 VLM 描述，
> 完成覆盖率、5 张人工抽查、图纸检索和 W1 回归。
>
> **只有“单图预检成功 + 覆盖率 ≥ 95% + 5 张抽查 + 图纸检索 + W1 不低于 Day5”全部有数字，
> 才能宣布 Day7 完成。**
>
> 如果 25 分钟内仍无法真实生成 1 条 VLM 描述，立即切到复盘分支，不再盲试模型或空跑全量。

---

## 0. 昨天到哪了

| 项目 | Day6 结果 | 对 Day7 的影响 |
| --- | --- | --- |
| Day5 门禁 | ✅ 通过 | 文本库干净，块数 **1956**，W1 基线可复用 |
| 总块数 / 图块数 | **1956 / 339** | VLM 不应改变块数 |
| 图片文件存在 | **339 / 339** | 不需要重新裁图 |
| `vlm_desc` 非空 | ❌ **0 / 339** | Day7 主目标仍未完成 |
| 主模型 | ❌ `qwen-vl-max-latest` 返回 `403 access_denied` | 账号/模型权限未通 |
| 备用模型名 | ❌ `qwen-vl-plus` / `qwen-vl-max` 返回 `404 model_not_found` | 禁止继续猜模型名，先看百炼控制台 |
| 三自检 | ✅ `1956==1956`、孤儿点 0、不一致 0.0%、dense 30/30 | 失败没有污染文本库 |
| W1 | ✅ 术语 8/8、口语 8/8 | Day7 C 列不得下降 |
| 图纸检索 | ❌ **0 / 3** | 尚无任何 VLM 描述，不能判断检索链路 |

> **Day6 不是“跑得慢”，而是视觉模型权限阻塞。**
> 一次无权限长跑持续约 19 分钟、成功 0；修复后的代码会在第一张图 `403` 后快速退出。

---

## 今天的变量纪律

**主变量 = VLM 图纸描述。**

今天不改：

- `chunker.py`、正文切块、页眉规则；
- `top_k`、`RRF_K`、embedding、rerank；
- VLM prompt；
- 手册数据、`identify` 节点；
- 设备过滤策略。

**允许改的唯一代码层**：为了 VLM 调用正确性而修复错误处理、日志和预检。
如果只是账号/模型权限问题，只改 `.env`，不要继续改业务代码。

---

## 时间表（2 小时）

| 时段 | 主干路径 | 分钟 |
| --- | --- | --- |
| 0:00-0:10 | **门禁**：Git、Day6 指标、三自检、1956/339 基线 | 10 |
| 0:10-0:25 | **权限修复 + 单图预检** | 15 |
| 0:25-1:10 | **全量 VLM 描述 + 重嵌入/重建** | 45 |
| 1:10-1:20 | 休息 | 10 |
| 1:20-1:35 | **覆盖率 + 索引一致性** | 15 |
| 1:35-1:50 | **5 张人工抽查 + 图纸检索 + W1 回归** | 15 |
| 1:50-2:00 | **metrics + 提交 + 周复盘结论** | 10 |

**0:25 硬门禁**：

- 单图预检成功 → 走主干路径；
- 单图预检仍失败 → 立即停止，不跑全量，转“复盘分支”。

---

# 第一部分 · 门禁与基线（10 分钟）

```powershell
cd "D:\pi 工作文件夹\项目学习"

git status --short
git log -1 --oneline
Select-String -LiteralPath 'docs\metrics.md' -Pattern '2026-11-27' -Encoding UTF8
uv run python scripts/verify_day3.py 2>$null
```

基线：

```powershell
uv run python -c "import json,os,collections; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; figs=[r for r in rows if r.get('block_type')=='figure']; print('chunks=',len(rows)); print('figures=',len(figs)); print('vlm_ok=',sum(bool(r.get('vlm_desc')) for r in figs)); print('images_exist=',sum(bool(r.get('image_path') and os.path.exists(r['image_path'])) for r in figs)); print('by_device=',dict(collections.Counter(r.get('device_model') or '未识别' for r in figs)))"
```

合格基线：

- `chunks=1956`
- `figures=339`
- `vlm_ok=0`
- `images_exist=339`
- `GA55=57 / VMC850=256 / YE3=26`
- `verify_day3.py`：点数==行数、孤儿点 0、不一致 <1%、dense 30/30

---

# 第二部分 · 修通 VLM 权限（15 分钟）

## 2.1 先修配置，不要猜模型名

只做三件事：

1. 在阿里云百炼控制台确认账号已开通视觉理解模型；
2. 从控制台复制**当前账号可调用**的完整模型名；
3. 更新 `.env` 的 `VLM_MODEL=`，不把模型名写死在代码里。

已知错误：

- `qwen-vl-max-latest` → `403 access_denied`
- `qwen-vl-plus` → `404 model_not_found`
- `qwen-vl-max` → `404 model_not_found`

> `403` 是权限/访问被拒，`404` 是模型名不存在。
> 不要继续随手换模型名；必须从控制台确认当前可用模型。

## 2.2 单图真实预检

```powershell
uv run python -c "import json; from eqagent import llm; from eqagent.ingest.image_desc import PROMPT; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; r=next(x for x in rows if x.get('block_type')=='figure' and x.get('image_path')); print('image=',r['image_path']); desc=llm.vlm_describe(r['image_path'],PROMPT); print('VLM_PREFLIGHT_OK'); print(desc[:300])"
```

合格：

- 输出 `VLM_PREFLIGHT_OK`；
- 描述非空、中文可读；
- 没有 `401/403/404`。

不合格：

- 立即停止；
- 记录 request_id、HTTP 状态和错误文本；
- 不运行 `eq-ingest` 全量。

---

# 第三部分 · 全量 VLM + 重建（45 分钟）

只有 2.2 成功才能执行。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
New-Item -ItemType Directory -Force 'data\index\logs' | Out-Null
$sw = [System.Diagnostics.Stopwatch]::StartNew()
uv run eq-ingest 2>&1 | Tee-Object -FilePath 'data\index\logs\day7_vlm.log'
$sw.Stop()
"耗时分钟: $([math]::Round($sw.Elapsed.TotalMinutes, 1))"
if ($LASTEXITCODE -ne 0) { throw "eq-ingest 失败，退出码 $LASTEXITCODE" }
```

## 3.1 运行观察点

- 日志必须出现成功的 `VLM n/339 ...`；
- 10 分钟内仍是 `0 / 339` 成功 → 停止；
- `401/403/404` → 权限/模型错误，立即停止；
- 连续 3 张失败 → 当前代码自动中止；
- `429` → 记录第几张，按实际进度判断是否当天继续；
- 不边跑边改 prompt。

## 3.2 失败保护

- `eq-ingest` 在 VLM 阶段失败时，不会写出新 `chunks.jsonl`；
- 失败后必须复核 `chunks.jsonl` / Qdrant 仍为 `1956 / 1956`；
- 不把失败日志当成“部分完成”；
- 不手删 `data/qdrant`。

---

# 第四部分 · 覆盖率 + 索引自检（15 分钟）

```powershell
uv run python -c "import json,collections,os; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; figs=[r for r in rows if r.get('block_type')=='figure']; ok=[r for r in figs if r.get('vlm_desc')]; print('chunks_after=',len(rows)); print('figures_after=',len(figs)); print('vlm_ok_after=',len(ok)); print('vlm_missing=',len(figs)-len(ok)); print('by_device_ok=',dict(collections.Counter(r.get('device_model') or '未识别' for r in ok))); print('images_exist=',sum(bool(r.get('image_path') and os.path.exists(r['image_path'])) for r in figs))"

uv run python scripts/verify_day3.py 2>$null
uv run python scripts/chunk_stats.py 2>$null
```

| 检查项 | 合格线 | 实测 |
| --- | --- | --- |
| VLM 覆盖率 | ≥ **323 / 339** | ____ / 339 |
| 三类设备成功描述 | GA55 / VMC850 / YE3 均 > 0 | ____ |
| 点数 == `chunks.jsonl` 行数 | 完全相等 | ____ == ____ |
| 孤儿点 | 0 | ____ |
| `payload.text` 不一致率 | < 1% | ____ |
| dense 条数 | 30/30 | ____ |
| 总块数 | 仍为 1956 | 1956 → ____ |

如果覆盖率 90%~95%：

- 记录失败块 ID 与错误；
- 今天只能记“部分完成”；
- 明天只补失败项，不重跑全量。

如果覆盖率 < 90%：

- 今天不合格；
- 不写“已完成”；
- 先判断是权限、限流、图片格式还是 API 稳定性。

---

# 第五部分 · 人工抽查 + 图纸检索 + W1 回归（15 分钟）

## 5.1 选 5 张图

要求：GA55 2 张、VMC850 2 张、YE3 1 张。

```powershell
uv run python -c "import json; rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')]; figs=[r for r in rows if r.get('block_type')=='figure' and r.get('vlm_desc')]; [print('\n',dev,*[(r['page'],r['chunk_id'],r['image_path'],r['vlm_desc'][:160]) for r in [x for x in figs if x['device_model']==dev][:n]],sep='\n  ') for dev,n in [('GA55',2),('VMC850',2),('YE3-160M',1)]]"
```

逐张打开 `image_path`，检查：

1. 图类型判断是否正确；
2. 部件名称、编号是否来自图面；
3. 是否编造了拆装顺序、尺寸、扭矩或接线关系；
4. 看不清时是否明确写“不清晰”。

**合格线：5/5 无明显幻觉。**

## 5.2 图纸检索

```powershell
uv run python -c "from eqagent.agent.tools import search_manual; qs=['GA55 油冷却器 结构 拆装','VMC850 刀库 结构 图','YE3 接线盒 接线图']; [print('\n###',q,*[(h['device_model'],h['doc_title'][:14],'p'+str(h['page']),h['block_type']) for h in search_manual(q,top_k=5)],sep='\n  ') for q in qs]"
```

记录：

- 3 条 query 中，top5 出现相关 `figure` 的条数；
- 命中的图是否确实对应问题；
- 如果没有 figure，对比描述是否进入 `text`，不要先调 `top_k` / RRF。

**合格线：至少 1 / 3 命中相关 figure。**

## 5.3 W1 回归

Day5/Day6 B 基线：

- 术语 **8 / 8**
- 口语 **8 / 8**
- 术语污染 **7 / 40**
- 口语污染 **2 / 40**

Day7 C：

- 术语 ____ / 8
- 口语 ____ / 8
- 术语污染 ____ / 40
- 口语污染 ____ / 40

**合格线：C 不低于 B。**

> 若下降 1 条，先看是否是图块描述挤掉正文/表格；当天不改检索参数。

---

# 第六部分 · 收尾与周复盘（10 分钟）

## 6.1 写 `docs/metrics.md`

模板：

```markdown
| 2026-11-28（Day7 实测） | 修通 VLM 权限并完成图纸描述/重建（当前 prompt 不变） | — | — | — | — | — | VLM **0/339 → ____/339**；设备分布 GA55 __ / VMC850 __ / YE3 __；抽查 __/5；图纸检索 __/3；索引 ____==____、孤儿点 __、不一致 __%、dense __/30；W1 B 术语 8/8、口语 8/8 → C 术语 __/8、口语 __/8；术语污染 7/40→__/40、口语污染 2/40→__/40；耗时 __ 分钟、失败 __ 张 |
```

## 6.2 周复盘：写 3 个坑

从本周已经出现的事实中选，不写空话：

1. **G 类：索引与切块不同代**——孤儿点和错位文本会让 dense 假性不足；
2. **页眉规则过宽**——重复短句不等于页眉，需要页面位置和原始字号中位数保护；
3. **VLM 403 被吞掉并重试**——配置预检必须真实调用，鉴权错误必须 fail-fast。

每条都补一句“下次怎么防”。

## 6.3 提交

```powershell
git status --short
git diff --stat
git add -A
git commit -m "feat(vlm): 完成Day7图纸描述与检索验收；记录覆盖率、抽查和W1回归"
git push
```

如果 VLM 仍未通：

```text
wip(vlm): Day7 VLM权限仍未通；保留单图预检与失败证据
```

## 6.4 给 Day8 留一句话

> Day7 的 VLM 覆盖率是 **____ / 339**，抽查 **__ / 5**，图纸检索 **__ / 3**，W1 **B → C = ____**。
> Day8 的第一件事应该是：**____**。
> 如果覆盖率 ≥ 95% 且图纸检索 ≥ 1/3，进入完整作业卡；否则先补失败图，不跳步。

---

# 分支 B · 0:25 权限仍不通（必须执行）

如果单图预检仍返回 `401/403/404` 或网络拒绝：

1. **立刻停止 VLM 全量**；
2. 记录模型名、HTTP 状态、request_id、错误文本；
3. 不再尝试猜测模型名；
4. 用剩余时间完成：
   - Week 1 周复盘；
   - 3 个坑及防复发措施；
   - 检查 `.env`、百炼账号权限和可用模型清单；
   - 更新 `docs/metrics.md` 的 Day7 阻塞行；
   - 提交失败证据和下一步操作清单。

**分支 B 的结论只能是“外部权限阻塞”，不能写成“VLM 已部分完成”。**

---

# 附 · 今天不做的

| 内容 | 为什么不做 |
| --- | --- |
| 补 GA55/VMC850 手册 | 会和 VLM 覆盖率形成两个变量 |
| 改 VLM prompt | 先证明当前 prompt 能跑通，再谈质量优化 |
| 改 `chunker.py` / `top_k` / `RRF_K` | Day5 基线刚稳定，不能混变量 |
| 改 embedding / rerank 模型 | 成本高且会污染 W1 回归 |
| `identify` 型号识别 | Day8 之后再处理 |
| 随机试更多模型名 | `404 model_not_found` 已证明这是无效排查 |

---

# 附 · Day7 硬验收

| 验收项 | 合格线 |
| --- | --- |
| 单图预检 | 1 张真实图片返回非空中文描述 |
| VLM 覆盖率 | ≥ 323 / 339 |
| 三类设备 | GA55 / VMC850 / YE3 均 > 0 |
| 人工抽查 | 5 / 5 无明显幻觉 |
| 图纸检索 | 至少 1 / 3 query 的 top5 出现相关 figure |
| 索引一致 | 点数 == 行数、孤儿点 0、不一致 <1%、dense 30/30 |
| W1 回归 | C 不低于 B |
| 块数 | 仍为 1956 |

