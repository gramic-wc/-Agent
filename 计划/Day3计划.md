# Day 3 计划 · 2 小时（重点：先把 2.5 的「定位失败」实操弄懂）

> **今天的唯一硬目标**：拿到一条 query，你能**自己**说出"**正确的那个块死在哪一站**"，并说出该改哪一层。
> 其它（污染率、块长、写 metrics）都是顺手收尾，做不完不亏。

---

## 0. 昨天到哪了（先对一下进度，别重复劳动）

| Day2 的段落 | 状态 | 证据 |
| --- | --- | --- |
| 0.1~0.2 索引确认 / 4 步链路 | ✅ 已理解 | `docs/metrics.md` 有 W1 基线 |
| 1.1~1.3 固定 query 召回率 | ✅ 表已填 | `Day2任务.md` 1.3 → **7/8**（第 3 条资料缺数据） |
| 2.1~2.4 口语化 query + 对比 | ✅ 表已填 | 2.3 → **8/8**；2.4 → 阶段1 0.875 vs 阶段2 1.00 |
| **2.5 深挖一条失败的** | ❌ **没做（今天的主角）** | 模板还是空的 |
| 3.x 跨设备污染 | ⬜ 未做（今天顺带跑） | metrics 里已有参考值 3/30 |
| 4.x 块长分布 | ⬜ 未做（今天只跑 4.1） | metrics 里已有参考值 108 / 31.6% |
| 5.x 写 metrics / 6.x 读 hybrid.py / 7.x 收尾 | ⬜ 未做 | 顺延到 Day 4 |

**为什么今天必须先做 2.5 而不是往后冲**：
后面所有调参（Day 3 原计划的切块实验、Day 9 的过滤、Day 10 的 query 改写）**都要靠 2.5 的结论决定改哪一层**。
2.5 不做，你明天就是在**猜**该调哪个参数。

---

## 时间表（2 小时，含一次休息）

| 时段 | 干什么 | 分钟 |
| --- | --- | --- |
| 0:00-0:12 | 讲透：2.5 到底在干什么（4 站 + A~F 六类结论） | 12 |
| 0:12-0:25 | **跟着复现示范 1**：亲眼看到"BM25 第 3 名 → 重排后消失" | 13 |
| 0:25-0:50 | **自己跑一条（d06）**，填"物流单" | 25 |
| 0:50-1:00 | 休息 | 10 |
| 1:00-1:28 | 阶段 3：跨设备污染，填 3.2 表 | 28 |
| 1:28-1:45 | 阶段 4.1（只跑分布，不做实验） | 17 |
| 1:45-2:00 | 收尾：把 2.5 结论写进 `docs/metrics.md` + 提交 | 15 |

**铁律不变**：任意一步卡 **超过 10 分钟就跳过**，标 `?` 继续往下。

---

# 第一部分 · 2.5 到底在干什么（12 分钟，只讲不动手）

## 1.1 一句话版本

> **命中率回答"有没有捞到"；2.5 回答"捞到的是不是那一条、如果不是，是 4 个环节里哪一个把它弄丢的"。**

把检索想成 **4 道筛子 + 1 条流水线**：

```
你的问题
  │
  ├─① dense  （向量，靠"意思像"）     取 30 张
  ├─② sparse （BM25，靠"字一样"）     取 30 张
  ├─③ RRF    （两榜合并，只看名次）    留 30 张
  └─④ rerank （逐条打分重排）          给 5~6 张
                                        ↓
                              你看到的 top5
```

**"正确答案那个块"（我们叫它「正确页」）就像一个包裹**，它有可能在任意一站被弄丢。
2.5 做的事，就是**查快递**：在第 ① ② ③ ④ 站的名单里分别找它一次，记下它排第几。

- ① 就没有 → 向量没找到它
- ② 里第 3、④ 里没了 → **重排把它压下去了**（最常见、也最容易冤枉向量模型）
- 四站都没有 → 可能**库里根本没有**（grep 证明）
- 有，但 `device_model` 是别人家的 → **跨设备污染**

> 💡 **一句话记住**：**正确页死在哪一站，就是哪一类问题。** 不用猜，去数名次就行。

## 1.2 三条判之前必须接受的规矩

| 规矩 | 为什么 | 具体怎么做 |
| --- | --- | --- |
| **坐标要 3 个字段：文档 + 页码 + 块类型** | 同一页经常被切成两块：`p21 text`（讲绝缘电阻）和 `p21 table`（表20 振动限值）是**两个东西**，混了必然判错 | 一律写成 `YE3-160M p21 table` 这种格式 |
| **只看 top5 = 没证据** | 正确页常常在 ② 排第 3、在 ④ 的 top5 之外。你不看 30 条，就不知道它是被重排压的 | 命令里一律 `--show 30` |
| **先证明库里有，再怪检索** | 90% 的"检索不行"最后是"库里没有/切碎了" | 第一步永远是 `chunks.jsonl` 全文 grep |

## 1.3 A~F 六类结论 → 直接决定改哪一层（今天背下这张表就够）

| 类型 | 现象（在哪一站看到的） | 该改哪一层 | 什么时候动 |
| --- | --- | --- | --- |
| **A 数据缺失** | ①②③④ 全没有，且 grep 也搜不到 | 不关检索的事 → 补手册 / 修解析 | Day 6 |
| **B 分词失效** | ② sparse 几乎没结果或全噪声，① 却正常 | 加领域词典 / 同义词表 | Day 10 |
| **C 块太碎** | ①② 都对，但 `text` 只有半句话（表格只剩表头） | `chunker.py` 的切块逻辑 | **Day 4（原 Day3 的切块实验↑优先级会因此提高）** |
| **D 块太大** | ①② 都对，块特别长，④ 分数全挤在 0.16x | 减小 `max_len` / 加子标题 | Day 4 |
| **E 重排误判** | ② 或 ③ 里排在前面，**④ 里没了/掉了** | 调 `RERANK_K` / 换重排模型 / 喂小标题 | Day 10 |
| **F 跨设备污染** | 四站都在，但 `device_model` 是别人家的 | 检索前强制设备过滤 | Day 9 |

> ⚠️ **顺序不能反**：先 A（库里有吗）→ 再 F（设备对不对）→ 再 B/C/D（哪一路坏）→ 最后才 E（重排坑人）。

## 1.4 今天要产出的"物流单"（一张 4 行的表，就这么简单）

| 站 | 正确页在不在 | 第几名 |
| --- | --- | --- |
| ① dense（向量） | | |
| ② sparse（BM25） | | |
| ③ RRF（融合） | | |
| ④ rerank（重排） | | |

**结论行**：`失败类型 = ___`，`证据 = ___`，`下一步先试 = ___`。

> 这张表 + 结论行，就是 2.5 要求的全部交付物。**不要写小作文。**

---

# 第二部分 · 跟着复现示范 1（13 分钟，只看不动手）

🎯 **目的**：先"看见"一次 E 类（重排误判），你才知道自己要找什么。

⌨️ **敲什么**

```powershell
cd "D:\pi 工作文件夹\项目学习"
uv run python scripts/search_debug.py "振动11mm/s标准" --show 30 2>$null
```

👀 **你要在屏幕上找到这 3 件事**（找到就打勾，找不到就往下看"报错了怎么办"）

- [ ] **① dense** 里 `YE3-160M p21` 出现了，但它的文字开头是"**4.15 定子绕组绝缘电阻…**" → 说明它是**同页的另一块**（不是表20）
- [ ] **② sparse** 里有一行写着 `[YE3-160M] p21 **table**`，内容开头是 `【表格】表20 不同轴中心高H(mm)…振动强度限值` → **这就是"正确页"（标准答案）**，记住它排第几（应该是 **第 3 名**）
- [ ] **④ rerank** 的 top5 里**没有这张表**（只有 p11 的"振动≤2.8mm/s"、GA55 p8 两条、p4、以及又是"绝缘电阻"那块 p21 text）

**填出示范的物流单**（照着屏幕抄）

| 站 | 正确页（`YE3-160M p21 table`）在不在 | 第几名 |
| --- | --- | --- |
| ① dense | ❌ 不在（① 里是 p21 的 **text** 块） | — |
| ② sparse | ✅ 在 | **3** |
| ③ RRF | 看屏幕（应在，名次 ≤ 10） | ___ |
| ④ rerank top30 | ❌ **没了** | 没进 |

→ **结论：E（重排误判）**。正确页在 BM25 第 3 名就被捞到了，是 ④ 把它挤出去的。
→ **下一步先试**：把 `RERANK_K` 调大（30→50）或重排时把"表20 振动强度限值"这类小标题拼进去，然后**重测这一条**。**先别动向量模型和切块。**

🚑 **报错了怎么办**

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| ② 里找不到 `p21 table` | `block_type` 变了（重跑过 ingest） | 直接搜屏幕上的 `表20`，记下它实际的页/类型 |
| ④ 那段提示"rerank 没返回，退回 RRF" | 网络/额度/`RERANK_ENABLED=0` | 先把 rerank 修好再看，否则 ④ 这一段是假的 |
| ④ 的 5 条全是 0.16x 附近 | 重排退化成 RRF | 同上 |
| 整段输出很长 | `--show 30` 打印 4×30 行 | 正常，往上滚，只看有 `p21` 的行 |

---

# 第三部分 · 自己跑一条：d06（25 分钟，这 25 分钟是今天的钱）

🎯 **为什么选 d06**：`用气端没变化但空压机频繁加卸载，储气罐压力不稳`。
它在 2.3 里的 top5 和 d01/d03 高度重叠（`团标 p7 / p13 / p20` 反复出现），
**极可能是 C（块太碎）或 D（块太大）**，正好和示范 1 的 E 类形成对比。

## 步骤 1（5 分钟）· 先把"正确页"坐标定下来

d06 的期望原因是 `传感器,用气量,压力阀`。先在库里找讲这些的块，把 **文档 + 页码 + 块类型** 抄下来：

```powershell
uv run python -c "import json;rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')];hit=[r for r in rows if ('\u52a0\u5378\u8f7d' in r['text'] or '\u538b\u529b\u9600' in r['text']) and r['device_model']=='GA55'];print('\u547d\u4e2d\u5757\u6570',len(hit));[print(r['device_model'],'p'+str(r['page']),r['block_type'],len(r['text']),r['text'][:45].replace(chr(10),' ')) for r in hit[:10]]" 2>$null
```

👀 输出里每条都带 `块类型` 和 `字数`。**从里面挑 1~2 个"看起来最该回答这个问题"的块**当坐标，写下来：

```
我的坐标：GA55 p___  ______（text/table）    字数约 ___
```

> 📌 挑的窍门：**字数特别短（< 40 字）的那条，很可能就是 C 类的证据**；
> 字数特别长（> 800）的，很可能是 D 类。**先记下来，判完再回来看这条预测对不对。**

## 步骤 2（8 分钟）· 跑透视镜，数名次

```powershell
uv run python scripts/search_debug.py "用气端没变化但空压机频繁加卸载，储气罐压力不稳" --show 30 2>$null
```

在 4 段输出里分别找你的坐标 `GA55 p___ ___(类型)`，照抄名次：

| 站 | 在不在 | 第几名 |
| --- | --- | --- |
| ① dense | | |
| ② sparse | | |
| ③ RRF | | |
| ④ rerank | | |

## 步骤 3（7 分钟）· 判决 + 填结论

对照 1.3 的表，只允许落进下面某一格：

| 你的情况 | 结论 |
| --- | --- |
| 四站都没有，且步骤 1 grep 也搜不到 | **A 数据缺失** |
| ①② 有，但 ④ 里 device 是 VMC850 等 | **F 跨设备污染** |
| ② 或 ③ 在前面、④ 里没了 | **E 重排误判** |
| ② 几乎没有、① 正常 | **B 分词失效** |
| ①② 有但 text 是断的（`【表格】` 后没内容） | **C 块太碎** |
| ①② 有、块很长、④ 分数全挨在一起 | **D 块太大** |
| ④ 里排第 1 | 这条不算失败案例，换 d08 或阶段 1 第 5 条 |

**把结论写进 `Day2任务.md` 2.5 的空白模板**（文件里已经给了空白模板，照抄格式）：

```
我选的失败案例：d06  用气端没变化但空压机频繁加卸载，储气罐压力不稳
透视镜里 ① dense 第1名：______  ② sparse 第1名：______
正确答案页在 ②/③ 里排第几（关键！）：______
失败类型：____（A/B/C/D/E/F）
证据：______________________________
下一步先试什么：____________________
```

## 步骤 4（5 分钟）· 自查"我是不是在骗自己"

- [ ] 我的坐标是 **3 个字段**（文档+页+块类型），不是只有页码
- [ ] 我用了 `--show 30`，不是只看 top5
- [ ] 我说得出"正确页在第 ② 站排第几"这个具体数字
- [ ] 我给的"下一步"只改**一层**（不是"同时调切块+重排+向量模型"）

> 🎁 **可选加速器（以后每条都用它，省 10 分钟）**：把"数名次"写成 10 行脚本
> `scripts/trace_block.py`，输入 query + 坐标，直接打印 4 站名次。
> 今天**先手数一遍**（你要体会一次这个过程），明天再写它。
>
> ```python
> """查一个"正确页"在 4 站各排第几。用法：
> uv run python scripts/trace_block.py "振动11mm/s标准" --page 21 --type table --device YE3-160M
> """
> from __future__ import annotations
> import argparse, sys
> from pathlib import Path
> ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
> from eqagent import llm
> from eqagent.retrieve.hybrid import DENSE_K, RERANK_K, RRF_K, SPARSE_K, get_retriever
>
> def rank_of(hits, page, btype):
>     for i, h in enumerate(hits, 1):
>         if h.payload.get("page") == page and h.payload.get("block_type") == btype:
>             return i
>     return None
>
> def fmt(name, rk, cap):
>     return f"{name:<10} ❌ 没进 top{cap}" if rk is None else f"{name:<10} 第 {rk} 名"
>
> ap = argparse.ArgumentParser()
> ap.add_argument("query"); ap.add_argument("--page", type=int, required=True)
> ap.add_argument("--type", required=True, choices=["text", "table", "figure"])
> ap.add_argument("--device", default=None)
> a = ap.parse_args()
>
> r = get_retriever()
> dense = r._dense(a.query, DENSE_K, a.device, None)
> sparse = r._sparse(a.query, SPARSE_K, a.device, None)
> fused, pool = {}, {}
> for hits in (dense, sparse):
>     for i, h in enumerate(hits):
>         fused[h.chunk_id] = fused.get(h.chunk_id, 0.0) + 1.0 / (RRF_K + i + 1)
>         pool.setdefault(h.chunk_id, h)
> ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:RERANK_K]
> cands = [pool[cid] for cid, _ in ranked]
> rr = llm.rerank(a.query, [h.text[:800] for h in cands], top_n=len(cands)) or []
> reranked = [cands[i] for i, _ in rr]
> print(f"\nquery = {a.query}   目标 = p{a.page} {a.type}\n")
> print(fmt("① dense", rank_of(dense, a.page, a.type), DENSE_K))
> print(fmt("② sparse", rank_of(sparse, a.page, a.type), SPARSE_K))
> print(fmt("③ RRF", rank_of(cands, a.page, a.type), RERANK_K))
> print(fmt("④ rerank", rank_of(reranked, a.page, a.type), len(cands)))
> ```

---

# 第四部分 · 休息 10 分钟

**别刷技术内容**。回来直接进阶段 3，那是纯抄表，不需要脑力。

---

# 第五部分 · 阶段 3 跨设备污染（28 分钟，纯跑 + 抄表）

⌨️ **敲什么**

```powershell
uv run python -c "from eqagent.agent.tools import search_manual; qs=['\u6392\u6c14\u6e29\u5ea6\u9ad8','\u4e3b\u8f74\u5f02\u54cd','\u8f74\u627f\u6e29\u5ea6\u9ad8','\u4f3a\u670d\u62a5\u8b66','\u5200\u5e93\u5361\u5200','\u632f\u52a8\u8d85\u6807']; [print('\n###',q,'\n  \u4e0d\u8fc7\u6ee4:',[h['device_model'] for h in search_manual(q,top_k=5)],'\n  GA55  :',[h['device_model'] for h in search_manual(q,device_model='GA55',top_k=5)]) for q in qs]" 2>$null
```

✍️ **把这些**抄进 `Day2任务.md` 的 3.2 表（列：不过滤时 top5 的设备 / 污染条数 / 加过滤后是否干净）：

| query | 我的实测（event 数） |
| --- | --- |
| 排气温度高 | |
| 主轴异响 | |
| 轴承温度高 | |
| 伺服报警 | |
| 刀库卡刀 | |
| 振动超标 | |

**污染率 = 污染条数 ÷ 30 = `___`**

> 参考：全部 6 条口径 **3/30 = 10%**；只算"跨设备类"（主轴异响、振动超标）是 **5/10 = 50%**。
> **报数字必须带口径**——写"10%"不写"只算多设备类 50%"，等于没说清。

💡 **今天只需要想清一件事**：如果你把"空压机"认成了"加工中心"，加了过滤后结果会怎样？
→ **比不过滤还糟**（会 100% 返回错设备）。所以 Day 9 的过滤必须和 Day 8 的"型号识别"一起做。

---

# 第六部分 · 阶段 4.1 块长分布（17 分钟，只跑不发散）

⌨️ **敲什么**

```powershell
uv run python scripts/chunk_stats.py 2>$null
```

✍️ **只抄 3 个数字**（抄进 `Day2任务.md` 4.1 的表）

| 指标 | 健康范围 | 我今天跑出来的值 |
| --- | --- | --- |
| 正文块中位数 | 150~400 字 | |
| 超短块（<40 字）占比 | < 10% | |
| 超长块（>900 字）占比 | < 5% | |

**只回答一句**：如果超短块占比明显 > 15%，它和第三部分你判的 **C/D 类**对得上吗？

> 参考（昨天基线）：中位数 **108**、超短块 **31.6%（440 条）**、其中 **284 条来自 SINUMERIK 的页眉**。
> 这一条会直接改明天的优先级：**如果 2.5 判出 C/D，明天（Day 4）就先做切块实验，别做图纸理解。**

---

# 第七部分 · 收尾（15 分钟）

## 7.1 把 2.5 的结论写进 `docs/metrics.md`

在「已知失败模式」表里加 **1~2 行**，格式照现有行：

```markdown
| **<你的现象一句话>** | <类型 E/C/D/F + 一句原因> | <下一步：改哪一层> |
```

合格标准（比"写得好"更重要）**必须带页码级证据**，例如：
> `| 表20 振动强度限值被重排挤掉 | E 重排误判：② sparse 第 3 名 → ④ top5 消失 | 调大 RERANK_K / 重排带小标题上下文 |`

## 7.2 提交

```powershell
cd "D:\pi 工作文件夹\项目学习"
git add "计划/Day2任务.md" "计划/Day3计划.md" docs/metrics.md
git commit -m "docs(day3): 2.5 失败定位实操（d06）+ 跨设备污染与块长实测 + metrics 失败模式"
git push
```

## 7.3 给明天的自己留一句话

> 我今天判出的类型是 **___**，所以 Day 4 第一件事应该是 **___**（切块 / 重排 / 过滤 / 补手册）。
> 这个"类型 → 下一动作"的对应关系，就是我以后调检索的**唯一依据**。

---

# 附 · 今天不做的（明确划出去，防发散）

| 内容 | 为什么不今天做 | 什么时候 |
| --- | --- | --- |
| 4.2 超短块抽样、4.3 质检规则实验 | 要先有 4.1 的数字才好解读 | Day 4 |
| 5.2/5.3 metrics 全量填 + 3 条失败模式 | 等 2.5 + 阶段 3/4 结论齐了再一次性写 | Day 4 收尾 |
| 6.x 读 `hybrid.py` | 需要先有"哪个参数在坑我"的具体问题，读了才有用 | Day 4 |
| 改任何代码（`chunker.py` / `RERANK_K`） | **今天只测量不改**，一次只动一个变量 | Day 4 |
| 7.1 四句话总结 | 攒到 Day 4 一起写 | Day 4 |

# 附 · 命令速查

```powershell
cd "D:\pi 工作文件夹\项目学习"

# 1. 示范 1（E 类：重排把对的压掉了）
uv run python scripts/search_debug.py "振动11mm/s标准" --show 30 2>$null

# 2. 自己跑 d06
uv run python scripts/search_debug.py "用气端没变化但空压机频繁加卸载，储气罐压力不稳" --show 30 2>$null

# 3. 先在库里 grep 坐标（证伪 A 类）
uv run python -c "import json;rows=[json.loads(l) for l in open('data/index/chunks.jsonl',encoding='utf-8')];hit=[r for r in rows if ('\u52a0\u5378\u8f7d' in r['text'] or '\u538b\u529b\u9600' in r['text']) and r['device_model']=='GA55'];print('\u547d\u4e2d\u5757\u6570',len(hit));[print(r['device_model'],'p'+str(r['page']),r['block_type'],len(r['text']),r['text'][:45].replace(chr(10),' ')) for r in hit[:10]]" 2>$null

# 4. 阶段 3 污染
uv run python -c "from eqagent.agent.tools import search_manual; qs=['\u6392\u6c14\u6e29\u5ea6\u9ad8','\u4e3b\u8f74\u5f02\u54cd','\u8f74\u627f\u6e29\u5ea6\u9ad8','\u4f3a\u670d\u62a5\u8b66','\u5200\u5e93\u5361\u5200','\u632f\u52a8\u8d85\u6807']; [print('\n###',q,'\n  \u4e0d\u8fc7\u6ee4:',[h['device_model'] for h in search_manual(q,top_k=5)],'\n  GA55  :',[h['device_model'] for h in search_manual(q,device_model='GA55',top_k=5)]) for q in qs]" 2>$null

# 5. 阶段 4.1 块长分布
uv run python scripts/chunk_stats.py 2>$null
```

# 附 · 今天的三条验收线

1. **能讲**：不用看文档，说清"4 站分别靠什么找"和"E 类的判据是什么"。
2. **能做**：给你一条新 query + 一个坐标，你能在 10 分钟内写出 4 行物流单 + 类型 + 下一步。
3. **留痕**：`docs/metrics.md` 里多 1~2 行**带页码级证据**的失败模式；`Day2任务.md` 2.5 的模板被填满。

> 三条都做到 = 今天满分。只做到第 1、2 条也算过——**能定位，比能背下来值钱。**
