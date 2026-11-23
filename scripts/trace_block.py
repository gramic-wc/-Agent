"""查一个"正确页"在 4 站各排第几（按 chunk_id 追，不靠眼睛数文字）。用法：

    uv run python scripts/trace_block.py "振动11mm/s标准" --page 21 --type table --device YE3-160M
    uv run python scripts/trace_block.py "用气端没变化但空压机频繁加卸载，储气罐压力不稳" --page 9 --type text --device GA55 --chars 692

为什么需要它：
    `search_debug.py` 打印的是 `text` 预览，而**同一页同一 block_type 可能有多个块**，
    肉眼数名次会把 A 块认成 B 块（d06 上就是这么误判成 E 的）。
    这里用 chunk_id 精确定位：先按 page/type/字数筛出候选，再把每个候选的 4 站名次打出来。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eqagent import llm  # noqa: E402
from eqagent.retrieve.hybrid import (  # noqa: E402
    DENSE_K,
    RERANK_K,
    RRF_K,
    SPARSE_K,
    get_retriever,
)


def rank_of(hits, chunk_id: str) -> int | None:
    for i, h in enumerate(hits, 1):
        if h.chunk_id == chunk_id:
            return i
    return None


def fmt(rk: int | None, cap: int) -> str:
    return f"❌ 没进 top{cap}" if rk is None else f"第 {rk} 名"


def candidates(by_id: dict, page: int | None, btype: str | None, device: str | None,
               chars: int | None) -> list[str]:
    out = []
    for cid, row in by_id.items():
        if page is not None and row.get("page") != page:
            continue
        if btype and row.get("block_type") != btype:
            continue
        if device and row.get("device_model") != device:
            continue
        if chars is not None and abs(len(row.get("text") or "") - chars) > 5:
            continue
        out.append(cid)
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="按 chunk_id 追 4 站名次")
    ap.add_argument("query")
    ap.add_argument("--device", default=None, help="设备型号过滤，如 GA55")
    ap.add_argument("--page", type=int, default=None, help="页码")
    ap.add_argument("--type", default=None, help="块类型：text / table / figure")
    ap.add_argument("--chars", type=int, default=None, help="块字数（±5 容差），用来区分同页同类型的多个块")
    ap.add_argument("--doc", default=None, help="只留 chunk_id 里含这个子串的块")
    args = ap.parse_args()

    r = get_retriever()
    print(f"\nQuery  : {args.query}")
    print(f"Device : {args.device or '不过滤'}")

    dense = r._dense(args.query, DENSE_K, args.device, None)
    sparse = r._sparse(args.query, SPARSE_K, args.device, None)

    fused: dict[str, float] = {}
    pool: dict[str, object] = {}
    for hits in (dense, sparse):
        for rank, h in enumerate(hits):
            fused[h.chunk_id] = fused.get(h.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
            pool.setdefault(h.chunk_id, h)
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:RERANK_K]
    cands = [pool[cid] for cid, _ in ranked]

    print(f"① dense {len(dense)} 条 / ② sparse {len(sparse)} 条 / ③ RRF {len(cands)} 条 → ④ rerank…")
    reranked = llm.rerank(args.query, [h.text[:800] for h in cands], top_n=len(cands))
    if not reranked:
        print("⚠️  rerank 没返回（RERANK_ENABLED=0 或网络失败），④ 这一段不打印")

    ids = candidates(r.by_id, args.page, args.type, args.device, args.chars)
    if args.doc:
        ids = [cid for cid in ids if args.doc in cid]
    if not ids:
        print("❌ 库里没有符合 page/type/device/chars 的块 —— 先确认坐标，别急着调检索（A 类）")
        return

    print(f"\n找到 {len(ids)} 个候选块：\n")
    for cid in ids:
        text = (r.by_id[cid].get("text") or "").replace("\n", " ")[:44]
        print(f"── {cid}  ({len(r.by_id[cid].get('text') or '')} 字)  {text}")
        print(f"   ① dense  {fmt(rank_of(dense, cid), DENSE_K)}")
        print(f"   ② sparse {fmt(rank_of(sparse, cid), SPARSE_K)}")
        print(f"   ③ RRF    {fmt(rank_of(cands, cid), RERANK_K)}")
        if reranked:
            order = [cands[idx].chunk_id for idx, _ in reranked]
            rk = order.index(cid) + 1 if cid in order else None
            print(f"   ④ rerank {fmt(rk, RERANK_K)}")
        print()


if __name__ == "__main__":
    main()
