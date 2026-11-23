"""Day3 收尾自检：一次跑完「G 类是否成立」+「坐标到底第几名」+「示范 1 的 ③ 名次」。

为什么需要它：
    `search_debug.py` 打印的是 payload 里的 `text`（可能是隔壁块的），
    `trace_block.py`(旧版) 只按 page+block_type 匹配（同页同类型多块必然认错）。
    这里一律按 **chunk_id** 定位，并把 Qdrant 与 chunks.jsonl 的文本逐条比对。

用法：
    uv run python scripts/verify_day3.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eqagent import llm  # noqa: E402
from eqagent.config import settings  # noqa: E402
from eqagent.retrieve.hybrid import (  # noqa: E402
    DENSE_K,
    RERANK_K,
    RRF_K,
    SPARSE_K,
    get_retriever,
)

D06 = "用气端没变化但空压机频繁加卸载，储气罐压力不稳"
DEMO1 = "振动11mm/s标准"
COORDS = {
    "p9 text 685 (GDCAGO 5.2.2)": "GA55_维护保养规范_团标:p9:text:17",
    "p14 table 1440 (点检表/检查加卸载)": "GA55_维护保养规范_团标:p14:table:2",
    "p9 text 692 (JSJXXH 5.18 最小压力阀)": "单螺杆_变频喷水_团标:p9:text:22",
}


def _norm(t: str) -> str:
    """去掉空白/标点，只比"字"。用来区分「真错位」和「旧解析的标点差异」。"""
    return re.sub(r"[\s、，,。：:；;|【】()（）\-—]", "", t or "")


def check_index_sync(r) -> None:
    print("\n" + "=" * 78 + "\n【1】向量库 vs chunks.jsonl 是否同一代（G 类证伪/证实）\n" + "=" * 78)
    client = r.client
    coll = settings.collection
    info = client.get_collection(coll)
    n_points = info.points_count
    print(f"Qdrant  collection={coll}  points={n_points}")
    print(f"jsonl   行数={len(r.ids)}    差值={n_points - len(r.ids)}")

    payloads: dict[str, str] = {}
    no_id = 0
    offset = None
    while True:
        pts, offset = client.scroll(
            coll, limit=512, offset=offset, with_payload=True, with_vectors=False
        )
        for p in pts:
            pl = p.payload or {}
            cid = pl.get("chunk_id")
            if cid:
                payloads[cid] = pl.get("text", "")
            else:
                no_id += 1
        if offset is None:
            break

    both = [cid for cid in r.ids if cid in payloads]
    orphan = [cid for cid in payloads if cid not in r.by_id]
    print(f"\n两边都有的 id = {len(both)}")
    print(f"孤儿点（向量库有、jsonl 里已经没有的 id）= {len(orphan)} "
          f"({len(orphan) / max(n_points, 1):.1%} of points)")
    print(f"缺 chunk_id 的点 = {no_id}")
    print("→ dense 请求 top30 只返回 20 条，就是这些孤儿点占位后被 _match_id 丢掉")

    diff = [cid for cid in both if payloads[cid] != r.by_id[cid].get("text", "")]
    idx = {cid: i for i, cid in enumerate(r.ids)}
    shifted, punct = [], []
    for cid in diff:
        i = idx[cid]
        if i > 0 and payloads[cid] == r.by_id[r.ids[i - 1]].get("text", ""):
            shifted.append(cid)
        elif _norm(payloads[cid]) == _norm(r.by_id[cid].get("text", "")):
            punct.append(cid)
        else:
            shifted.append(cid)  # 归到"内容真的不是它自己"
    print(f"\ntext 逐字不一致 = {len(diff)} / {len(both)} = {len(diff) / len(both):.1%}")
    print(f"  ├ 真错位（= 上一块的文本 / 内容整体不是自己的）= {len(shifted)}")
    print(f"  └ 只是旧解析的空白·标点差异（字完全一样，无害）      = {len(punct)}")

    print("\n抽样：一条「标点差异」和一条「真错位」")
    for label, pool_ in (("标点差异", punct), ("真错位", shifted)):
        if not pool_:
            continue
        cid = pool_[0]
        print(f"  [{label}] {cid}")
        print(f"      qdrant: {payloads[cid][:46]!r}")
        print(f"      jsonl : {r.by_id[cid].get('text', '')[:46]!r}")


def ranks(r, query: str, device: str | None, title: str, coords: dict[str, str]) -> None:
    tag = f"device={device}" if device else "不过滤"
    print("\n" + "=" * 78 + f"\n【2】{title} | {query}（{tag}，chunk_id 口径）\n" + "=" * 78)
    dense = r._dense(query, DENSE_K, device, None)
    sparse = r._sparse(query, SPARSE_K, device, None)

    fused: dict[str, float] = {}
    pool = {}
    for hits in (dense, sparse):
        for i, h in enumerate(hits):
            fused[h.chunk_id] = fused.get(h.chunk_id, 0.0) + 1.0 / (RRF_K + i + 1)
            pool.setdefault(h.chunk_id, h)
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:RERANK_K]
    cands = [pool[cid] for cid, _ in ranked]

    rr = llm.rerank(query, [h.text[:800] for h in cands], top_n=len(cands)) or []
    reranked = [cands[i] for i, _ in rr]

    def where(hits, cid):
        for i, h in enumerate(hits, 1):
            if h.chunk_id == cid:
                return str(i)
        return "—"

    print(f"  {'坐标':<38}{'①dense':>8}{'②sparse':>9}{'③RRF':>7}{'④rerank':>9}")
    for name, cid in coords.items():
        print(
            f"  {name:<38}{where(dense, cid):>8}{where(sparse, cid):>9}"
            f"{where(cands, cid):>7}{where(reranked, cid):>9}"
        )
    print(f"\n  （① 返回 {len(dense)}/{DENSE_K} 条  ② {len(sparse)}/{SPARSE_K} 条  "
          f"③④ {len(cands)}/{RERANK_K} 条；rerank 返回 {len(reranked)} 条 = "
          f"{'正常' if reranked else '失败/退化成 RRF'}）")


def main() -> None:
    r = get_retriever()
    check_index_sync(r)
    ranks(r, D06, None, "d06", COORDS)
    ranks(r, D06, "GA55", "d06", COORDS)
    ranks(r, DEMO1, None, "示范 1", {"YE3 p21 table 表20 振动限值": "YE3_YE5_团标:p21:table:23"})


if __name__ == "__main__":
    main()

