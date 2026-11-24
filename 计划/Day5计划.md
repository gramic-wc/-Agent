# Day 5 计划 · 2 小时（重点：**清掉 284 条死卡片，然后在干净库上重跑 W1 硬验收**）

> **今天的唯一硬目标**：把 4.2 写好的页眉规则**落进代码并重建**，然后用「同一套 query」证明
> **清页眉没让召回掉下去**（术语 8 条 A→B、口语 d01~d08）。
> **没有 A/B 两张召回表，今天不算完成。**

---

## 0. 昨天到哪了（先对一下，别重复劳动）

| 昨天的事 | 状态 | 证据 |
| --- | --- | --- |
| 修 G（重建向量库） | ✅ 已做 | 点数 **2023 == 2023**、孤儿点 **494 → 0**、不一致率 **41.2% → 0.0%**、dense **20/30 → 30/30** |
| d06 复测 | ✅ 已填修前/修后 | `p14 table 1440`：全无 → **①15 / ③25 / ④8** |
| 示范 1 复测 | ✅ 已填 | 表 20 ④ **#7 → #6**（H 由修库自然消解） |
| `top_k` 6→10 | ✅ 验完，**不改** | 6 与 10 里表 20 都排第 6，无增量 |
| 切块 `max_len` 400 实验 | ⏭️ **跳过**（前提不成立） | 1440 已进榜 → D 类不成立；`chunker.py` 零改动 |
| 4.2 页眉规则 | ✅ 规则已定，**代码没改** | 抽样 12 条 → **10/12 是纯页眉**（`User manual` ×9）；284/440 来自 SINUMERIK |
| **W1 召回硬验收** | ❌ **一直没在新库上跑过** | Day2 的 8/8、8/8 是**脏库**时期的数，不能当验收 |

**为什么今天先清页眉、却先量召回**：
> 页眉清理是**删块**的改动，删错了召回会掉，而且掉了不容易发现（看着还是 8/8，其实命中的页变了）。
> 所以顺序必须是 **先量 A（干净库、未清页眉）→ 再改 → 再量 B**。**先改后量，你分不清是清页眉的功劳还是库的功劳。**

---

## 今天的变量纪律

**唯一改动 = `src/eqagent/ingest/parse.py` 里的页眉规则**（以及它必须附带的**重切 + 重建**）。
下面这些今天**一律不动**：`chunker.py` 的 `max_len`、`top_k`、`RRF_K`、embedding、rerank 模型、`identify` 节点。

---

## 时间表（2 小时，含一次休息）

| 时段 | 干什么 | 分钟 |
| --- | --- | --- |
| 0:00-0:10 | **量 A**：干净库 + 页眉未清，术语 8 条召回 | 10 |
| 0:10-0:40 | **落地规则**：改 `parse.py` → 重切 + 重建 | 30 |
| 0:40-0:55 | **自检**：三条 + 块长对比 + 抽样确认 `User manual` 归零 | 15 |
| 0:55-1:10 | **量 B**：同 8 条 query，填 A/B 对比表 | 15 |
| 1:10-1:20 | 休息 | 10 |
| 1:20-1:40 | **口语 d01~d08** 复测 + 跨设备污染重新计数 | 20 |
| 1:40-1:50 | **护栏**：B < A 就回滚/收窄规则（只改一处再量） | 10 |
| 1:50-2:00 | `docs/metrics.md` 补一行 + 提交 | 10 |

**铁律不变**：任意一步卡 **超过 10 分钟就跳过**，标 `?` 继续往下。
**顺序反了（先改后量）今天白干。**

---

# 第一部分 · 量 A：干净库的召回基线（10 分钟）

🎯 目的：拿到「**库同代、但页眉还没清**」这一代的召回数，作为今天唯一变量的对照。

⌨️ 敲什么（8 条术语 query，`top_k=5`）

```powershell
cd "D:\pi 工作文件夹\项目学习"
uv run python -c "from eqagent.agent.tools import search_manual; qs=['排气温度高 处理','油冷却器 清洗','油压不足 检查','刀库卡刀 报警 2021','伺服过载 排查','轴承 温度 上限','振动 11mm/s 标准','绝缘 0.3M 兆欧']; [print('\n###',q,*[(h['device_model'],h['doc_title'][:14],'p'+str(h['page']),h['block_type']) for h in search_manual(q,top_k=5)],sep='\n  ') for q in qs]" 2>$null
```

✍️ **判定标准（Day2 的同一把尺子，别换）**：
1. 设备 `device_model` 必须和 query 里的设备一致（问 YE3 却返回 GA55 → 不算）；
2. 维修工只看这一页**能动手**（能查到限值/步骤/该换什么件）→ 算命中；（宽松：能查到下一步去哪查也算）

✍️ **填 A（今天第一次填，Day2 的数只作参考）**

| # | query | 目标设备 | Day2 判据页 | A：top5 里命中数 | A：第几名 | A 命中？ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 排气温度高 处理 | GA55 | 团标 p13 / p20 | ___ | ___ | ___ |
| 2 | 油冷却器 清洗 | GA55 | 团标 p14 / p9 | ___ | ___ | ___ |
| 3 | 油压不足 检查 | GA55 | 团标 p14 / p15 | ___ | ___ | ___ |
| 4 | 刀库卡刀 报警 2021 | VMC850 | VMC850 p32 | ___ | ___ | ___ |
| 5 | 伺服过载 排查 | VMC850 | VMC850 p4 | ___ | ___ | ___ |
| 6 | 轴承 温度 上限 | YE3-160M | YE3 p4 | ___ | ___ | ___ |
| 7 | 振动 11mm/s 标准 | YE3-160M | YE3 p11 / p21 | ___ | ___ | ___ |
| 8 | 绝缘 0.3M 兆欧 | YE3-160M | YE3 p12 / p8 / p21 | ___ | ___ | ___ |

**A = ___ / 8**（Day2 脏库基线是 8/8 = 1.00；今天**掉到 6/8 以下就是大新闻**，先记 `?`，别现场改代码）

> 📌 顺带记一行：8 条里 **top5 有多少条不是目标设备**（跨设备污染）→ A 污染 = ___ / 40。
> Day2 的口径是「不过滤」3/30 = 10%，这里口径换成了 top5 × 8 条 = 40 个位子，**数字不能直接和 10% 比，要说清口径**。

---

# 第二部分 · 落地页眉规则（30 分钟）

## 2.1 改哪儿（看完再动手，别改错地方）

`src/eqagent/ingest/parse.py`：**在 `pages` 从缓存/解析拿回来之后、进页循环之前**插一步过滤。
这样做的三个好处，改之前先认一下：

| 选择 | 为什么 |
| --- | --- |
| 在 **pagecache 之后**过滤，而不是改 `_extract_page` | 改规则**不用重解析 PDF**（`data/index/pagecache/` 还能用），试错只要几十秒 |
| 只删 `lines`，不碰 `tables` / `images` | 表格和图纸不参与这条规则，不会误伤 |
| **不加**「带数字的重复行」 | 标准号 `T/GDCAGO 1—2024` 也是每页重复，但它是合规页眉、无害；今天只清**纯文字页眉**，一次只动一小步 |

```python
# parse.py 顶部常量区（跟 HEADING_RATIO 放一起）
HEADER_MAX_CHARS = 40   # 超过 40 字的多半是正文，不当页眉
HEADER_MIN_PAGES = 5    # 同一文档里重复 ≥5 次才算"跑动页眉"


def _drop_running_headers(pages: list[dict]) -> list[dict]:
    """删掉「同文档内重复 ≥5 次、<40 字、不带数字、不是题注」的页眉页脚行。

    4.2 抽样依据：SINUMERIK 的 `User manual`（p8~p16 每页一条）、`Line/Indicates/Remarks`。
    """
    from collections import Counter

    def norm(t: str) -> str:
        return re.sub(r"\s+", " ", t).strip().lower()

    def is_candidate(t: str) -> bool:
        t = t.strip()
        return (
            0 < len(t) <= HEADER_MAX_CHARS
            and not re.search(r"\d", t)          # 带数字的不是纯页眉（标准号/表号/页码）
            and not CAP_TAB.match(t)             # 题注不动
            and not CAP_FIG.match(t)
        )

    cnt = Counter(norm(ln["text"]) for p in pages for ln in p["lines"] if is_candidate(ln["text"]))
    bad = {k for k, n in cnt.items() if n >= HEADER_MIN_PAGES}
    out = []
    for p in pages:
        keep = [ln for ln in p["lines"] if not (is_candidate(ln["text"]) and norm(ln["text"]) in bad)]
        out.append({**p, "lines": keep})
    return out
```

接线（`parse_pdf` 里，**别搞错顺序**）：

```python
        if fresh:
            pages = _extract_document(doc)     # ← 这句保持原样，缓存里存的是"原始行"

        pages = _drop_running_headers(pages)    # ← 新增：每份文档独立统计，所以放在 parse_pdf 内、页循环前
```

> ⚠️ **坑（会白干半小时）**：`if fresh: _save_page_cache(...)` 在函数**末尾**，`pages` 这时已经被过滤过 →
> 存进缓存的就是删过的版本。要么把过滤结果放另一个变量（`pages_f = _drop_running_headers(pages)`，循环用 `pages_f`），
> 要么就别依赖缓存。**建议用前者**，缓存永远存原始数据。

## 2.2 重切 + 重建（两个都做，少一个就再造一个 G）

```powershell
# 改前记数字
uv run python -c "import json;print('块数前', sum(1 for _ in open('data/index/chunks.jsonl',encoding='utf-8')))" 2>$null

uv run python -c "from eqagent.retrieve.index import get_client, recreate_collection; recreate_collection(get_client()); print('recreated')" 2>$null
uv run eq-ingest --no-vlm
```

**期望（不是合格线，是"改对了没"的体感）**：块数 **2023 → 1700±40**（284 条 SINUMERIK 页眉 + 其它文档的页眉一起消失）。
如果块数几乎没变 → 规则没生效（`is_candidate` 全军覆没 / 没接上 / 读了旧 pagecache），先看日志里 `_drop_running_headers` 删了多少行。

🚑 **失败了怎么办**

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 块数一点没变 | 函数没接上，或者 pagecache 里存的已是过滤后版本 | 在函数里 `log.info("丢页眉行 %d", ...)`，看一眼就知道 |
| 块数掉到 <1200 | 阈值太松（把重复的正文短行也删了） | 先把 `HEADER_MIN_PAGES` 5 → 8 再跑，**别改别的** |
| `eq-ingest` 报错 | 语法/缩进 | 先 `uv run python -c "import eqagent.ingest.parse"` 单独验 |

---

# 第三部分 · 自检 + 块长对比（15 分钟）

## 3.1 三条自检（和昨天同一把尺子，少一条都不算数）

```powershell
uv run python scripts/verify_day3.py 2>$null
```

| 自检 | 合格线 | 修前（Day4） | 今天 |
| --- | --- | --- | --- |
| ① 点数 == `chunks.jsonl` 行数 | 完全相等 | 2023 == 2023 | ___ |
| ② 孤儿点 | 0 | 0 | ___ |
| ③ `payload.text` 不一致率 | < 1% | 0.0% | ___ |
| ④ ① dense 条数 | 30/30 | 30/30 | ___ |

> 🚨 **③ 一旦不为 0，说明你又造了一个 G**（改完 parse 没重建 / 重建没删旧点）。别往下走，回去重跑 2.2。

## 3.2 块长对比（这是今天的核心数字）

```powershell
uv run python scripts/chunk_stats.py 2>$null
```

| 指标 | Day4（未清页眉） | Day5 清完后 | 说明 |
| --- | --- | --- | --- |
| 总块数 | 2023 | ___ | 期望 1700±40 |
| 正文块数 | 1394 | ___ | |
| 正文中位数 | 108 | ___ | **应该基本不变**（±10）；大跳 = 动了不该动的东西 |
| 超短块（<40 字） | **440（31.6%）** | ___ | 期望 **~156（~9%）** |
| 超长块（>900） | 25（1.8%） | ___ | 应该基本不变 |
| 超短块来源 Top1 | SINUMERIK 284 | ___ | **期望这个数字塌到 <20** |
| 抽样 12 条里还有几条 `User manual` | 10 | ___ | 期望 **0** |

🚑 **口径提醒**：超短块**占比**的分母变了（块总数变少了），所以"31.6% → 9%"里有一半是分母的功劳。
**报告时两个数都要写：440 → 156（条）和 31.6% → ~9%（比）**，只写百分比会被误读成"删了 3/4 的短块"。

---

# 第四部分 · 量 B：同一套 query 再跑一次（15 分钟）

⌨️ 命令和第 1 部分**一字不差**（换窗口重跑，别改参数）：

```powershell
uv run python -c "from eqagent.agent.tools import search_manual; qs=['排气温度高 处理','油冷却器 清洗','油压不足 检查','刀库卡刀 报警 2021','伺服过载 排查','轴承 温度 上限','振动 11mm/s 标准','绝缘 0.3M 兆欧']; [print('\n###',q,*[(h['device_model'],h['doc_title'][:14],'p'+str(h['page']),h['block_type']) for h in search_manual(q,top_k=5)],sep='\n  ') for q in qs]" 2>$null
```

✍️ **填 A/B 对比表（今天的交付物 #1）**

| # | query | A 命中 | B 命中 | B 的 top1（设备+页码） | 变好 / 变差 / 不变 |
| --- | --- | --- | --- | --- | --- |
| 1 | 排气温度高 处理 | ___ | ___ | ___ | ___ |
| 2 | 油冷却器 清洗 | ___ | ___ | ___ | ___ |
| 3 | 油压不足 检查 | ___ | ___ | ___ | ___ |
| 4 | 刀库卡刀 报警 2021 | ___ | ___ | ___ | ___ |
| 5 | 伺服过载 排查 | ___ | ___ | ___ | ___ |
| 6 | 轴承 温度 上限 | ___ | ___ | ___ | ___ |
| 7 | 振动 11mm/s 标准 | ___ | ___ | ___ | ___ |
| 8 | 绝缘 0.3M 兆欧 | ___ | ___ | ___ | ___ |

**A = ___ / 8 → B = ___ / 8（验收线 ≥ 6/8 = 0.75）**
**A 污染 ___ / 40 → B 污染 ___ / 40**

🎯 **三种结果，三种下一步**

| B 相对 A | 说明 | 下一步 |
| --- | --- | --- |
| **B ≥ A（不掉或更好）** | 页眉清理是净收益，删的都是死卡片 | **保留规则**，进第六部分 |
| **B 掉 1 条** | 大概率删到了"看着像页眉"的短句（`relevant instruction book.` 那类） | 阈值 5→8 再跑一次（**只改这个数**），仍掉就回滚 |
| **B 掉 ≥2 条** | 规则误伤正文/题注 | **直接回滚**（见第七部分），今天改成"只写规则不落地"，把 4.2 结论带进 Day6 |

> 📌 **为什么必须两列都填**：光看 B = 7/8 你不知道是"页眉删得好"还是"库本来就这样"。
> **A 是今天真正的对照，Day2 的 8/8 只是故事背景。**

---

# 第五部分 · 休息 10 分钟

**别刷技术内容。** 回来只做两件事：跑一条命令、数 30 个数。

---

# 第六部分 · 口语 query 复测 + 污染（20 分钟）

⌨️ 敲什么（**带型号过滤**，和 Day2 2.3 同一条命令）

```powershell
uv run python -c "import json; from eqagent.agent.tools import search_manual; rows=json.load(open('data/dev_cn.json',encoding='utf-8'))[:8]; [print('\n###',r['id'],r['symptom'],'\n  期望原因:',','.join(r['expect_causes']),'\n  结果:',*[(h['device_model'],h['doc_title'][:14],'p'+str(h['page']),h['block_type']) for h in search_manual(r['symptom'],device_model=r['device_model'] or None,top_k=5)],sep='\n    ') for r in rows]" 2>$null
```

✍️ **填表（今天的交付物 #2）**

| id | symptom（缩写） | 型号 | Day2 top1 | Day5 top1 | 命中？ | top5 里设备不符条数 |
| --- | --- | --- | --- | --- | --- | --- |
| d01 | GA55 排气温度高跳机 | GA55 | user p30 | ___ | ___ | ___ |
| d02 | GA55 升到 108℃ 停机 | GA55 | user p30 | ___ | ___ | ___ |
| d03 | GA55 E-305 油压 0.15MPa | GA55 | user p31 | ___ | ___ | ___ |
| d04 | 油压建立缓慢（**无型号**） | — | 团标 p13 | ___ | ___ | ___（Day2：2/5 是 VMC850 ❗） |
| d05 | 加卸载间隔不到 30 秒 | GA55 | user p28 | ___ | ___ | ___ |
| d06 | 频繁加卸载（**无型号**） | — | 团标 p7 | ___ | ___ | ___ |
| d07 | 排污口油水混合物 | GA55 | user p20 | ___ | ___ | ___ |
| d08 | 油耗上升 + 压差报警 | GA55 | user p31 | ___ | ___ | ___ |

**口语命中 = ___ / 8**（Day2 是 8/8 = 1.00）
**污染 = ___ / 40**（Day2 口径是 3/30 = 10%，**口径不同，比较时要写清楚**）

> ⚠️ 别指望口语掉分：**口语 query 里的 `User manual` 页眉本来就是噪声**，清掉它，GA55 那几条一般只会更好或不变。
> **真掉了**，看掉的那条 top1 原来靠哪一页 —— 如果是 `GA55_user_manual p30/p31`（真实表格页），那说明你的规则误删了表格上方那行短标题，回滚。

---

# 第七部分 · 护栏：回滚 or 收窄（10 分钟）

**只有 B < A 或块数掉得离谱才进这里。**

```powershell
# 看改了什么
git diff src/eqagent/ingest/parse.py

# 二选一：收窄（改阈值再跑一次）
#   HEADER_MIN_PAGES 5 → 8  然后重跑 2.2 的"重切 + 重建"

# 二选一：全部回滚
git checkout -- src/eqagent/ingest/parse.py
uv run python -c "from eqagent.retrieve.index import get_client, recreate_collection; recreate_collection(get_client()); print('recreated')" 2>$null
uv run eq-ingest --no-vlm
```

| 情况 | 保留什么 | 写进 Day6 |
| --- | --- | --- |
| B ≥ A | **保留代码** + 保留数字 | 页眉已清，可以上 VLM 图纸描述 |
| 收窄后 B ≥ A | 保留**收窄版**（阈值 8）+ 记下"5 太松" | 同上，但要复查其它文档有没有残留页眉 |
| 回滚 | 代码回滚，**规则和数字留下** | Day6 用"只删 ASCII-only 且重复 ≥10 次"的版本再试一次 |

**收工前必做**：`git status` 干净（要么提交了，要么回滚了）。**"试了但没结论"的改动不许带进明天。**

---

# 第八部分 · 收尾（10 分钟）

## 8.1 `docs/metrics.md` 记一行

```markdown
| 2026-11-25（Day5 实测） | `parse.py` 新增「同文档重复 ≥5 次、<40 字、不带数字、非题注」的页眉行过滤（`_drop_running_headers`）→ 重切 + 重建 | ___ | ___ | ___ | ___ | ___ | 块数 2023→____、超短块 **440→____**（31.6%→____%）、SINUMERIK 页眉 284→____；三自检 点数____/行数____、孤儿点____、不一致____%；术语 8 条 **A __/8 → B __/8**、口语 **__/8 → __/8**、污染 **__/40 → __/40** |
```

**合格标准**：至少 **3 个「改前 → 改后」的数字** + 一张 A/B 召回表。没有 A 列 = 没做对照实验。

## 8.2 提交

```powershell
cd "D:\pi 工作文件夹\项目学习"
git add -A
git commit -m "feat(ingest): 页眉行过滤(同文档重复≥5次/<40字/无数字)→重切重建；Day5 A/B 召回对照 + 口语复测"
git push
```

## 8.3 给明天的自己留一句话

> 今天动的层是 **切块前处理（`parse.py` 页眉规则）**，验证方式是 **三自检 + 块长 440→____ + A/B 召回对照**。
> 明天的第一件事应该是 **____**（VLM 图纸描述 / 补 GA55 中文手册 / `identify` 型号识别），
> 因为今天的数据显示 **____**（例：页眉清了、召回没掉 → 终于可以烧 API 做图纸描述；或 B 掉了 → 先复盘误删再谈图纸）。

---

# 附 · 今天不做的（防发散）

| 内容 | 为什么不做 | 什么时候 |
| --- | --- | --- |
| **全量 VLM 图纸描述**（原 Day 4 顺延） | 它要**烧 API 额度 + 重建索引**，是"另一个变量"，必须单独一天当主角 | **Day 6**（页眉干净之后） |
| 改 `chunker.py` 的 `max_len` | Day4 已判 D 类不成立（1440 进榜） | 不再做，除非新数据翻案 |
| 改 `top_k` / `RRF_K` / `MIN_CONFIDENCE` | 昨天刚验过 `top_k` 无增量；一次只动一个变量 | 有新证据再说 |
| 换 embedding / rerank 模型 | 先把"同一模型下的干净数字"定下来当基线 | 下周 |
| `identify` 节点（型号识别） | 污染今天只**量**不修；修它要等干净基线 | Day 8/9 |
| 补 GA55 中文手册 | 是"加数据"不是"修链路"，会污染今天的 A/B 对照 | Day 6 |

# 附 · 命令速查

```powershell
cd "D:\pi 工作文件夹\项目学习"

# 1. 术语 8 条召回（A 和 B 用同一条命令，一字不改）
uv run python -c "from eqagent.agent.tools import search_manual; qs=['排气温度高 处理','油冷却器 清洗','油压不足 检查','刀库卡刀 报警 2021','伺服过载 排查','轴承 温度 上限','振动 11mm/s 标准','绝缘 0.3M 兆欧']; [print('\n###',q,*[(h['device_model'],h['doc_title'][:14],'p'+str(h['page']),h['block_type']) for h in search_manual(q,top_k=5)],sep='\n  ') for q in qs]" 2>$null

# 2. 口语 d01~d08（带型号过滤）
uv run python -c "import json; from eqagent.agent.tools import search_manual; rows=json.load(open('data/dev_cn.json',encoding='utf-8'))[:8]; [print('\n###',r['id'],r['symptom'],'\n  期望原因:',','.join(r['expect_causes']),'\n  结果:',*[(h['device_model'],h['doc_title'][:14],'p'+str(h['page']),h['block_type']) for h in search_manual(r['symptom'],device_model=r['device_model'] or None,top_k=5)],sep='\n    ') for r in rows]" 2>$null

# 3. 重建（改完 parse/切块必须做，两件都要）
uv run python -c "from eqagent.retrieve.index import get_client, recreate_collection; recreate_collection(get_client()); print('recreated')" 2>$null
uv run eq-ingest --no-vlm

# 4. 自检 + 块长 + 抽样
uv run python scripts/verify_day3.py 2>$null
uv run python scripts/chunk_stats.py 2>$null

# 5. 单条透视（怀疑某条时看 4 站，别靠眼睛）
uv run python scripts/search_debug.py "振动11mm/s标准" --show 5 2>$null
```

# 附 · 今天的四条验收线

1. **清干净了**：超短块 **440 → ≤180**，抽样里 `User manual` **0 条**，SINUMERIK 页眉 284 → **<20**。
2. **没造新 G**：点数 == 行数、孤儿点 = 0、不一致率 < 1%（三个数字都写出来）。
3. **有对照**：术语 8 条 **A 与 B 两列都填**，并且能说出"掉了/没掉"的原因。
4. **只动一层**：今天改过的文件能列成一行（`parse.py` + 必须的重建），`chunker.py` / `tools.py` diff 为空。

> 做到 1、2 = **合格**；四条全做到 = **满分**（W1 的召回硬验收也就顺手过了）。
