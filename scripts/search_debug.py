"""检索透视镜：同一句 query，分别打印 4 步的结果。

为什么需要它：
    search_manual() 只给最终结果。调检索时必须知道
    「这条是被向量找上来的 还是被关键词找上来的 还是被重排救回来的」。

用法：
    uv run python scripts/search_debug.py "排气温度高 处理" --device GA55
    uv run python scripts/search_debug.py "3号车间GA55运行20分钟后排气温度高跳机" --show 3
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


def show(title: str, hits, n: int) -> None:
    print(f"\n{'=' * 78}\n{title}（{len(hits)} 条）\n{'=' * 78}")
    for rank, h in enumerate(hits[:n], 1):
        page = h.payload.get("page", 0)
        model = h.payload.get("device_model", "-")
        btype = h.payload.get("block_type", "-")
        text = (h.text or "").replace("\n", " ")[:56]
        print(f"  {rank:2d}. [{model:9s}] p{page:<4d} {btype:6s} {h.score:8.4f}  {text}")


def main() -> None:
    ap = argparse.ArgumentParser(description="检索透视镜")
    ap.add_argument("query")
    ap.add_argument("--device", default=None, help="只在这些设备里找，如 GA55")
    ap.add_argument("--show", type=int, default=5, help="打印前几条")
    args = ap.parse_args()

    r = get_retriever()
    print(f"\nQuery  : {args.query}")
    print(f"Device : {args.device or '不过滤'}")

    dense = r._dense(args.query, DENSE_K, args.device, None)
    sparse = r._sparse(args.query, SPARSE_K, args.device, None)
    show(f"① dense（向量）top{DENSE_K}", dense, args.show)
    show(f"② sparse（BM25）top{SPARSE_K}", sparse, args.show)

    # ③ 只看融合排名，不做重排
    fused: dict[str, float] = {}
    pool: dict[str, object] = {}
    for hits in (dense, sparse):
        for rank, h in enumerate(hits):
            fused[h.chunk_id] = fused.get(h.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
            pool.setdefault(h.chunk_id, h)
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:RERANK_K]
    cands = []
    for cid, _ in ranked:
        h = pool[cid]
        h.score = fused[cid]
        cands.append(h)
    show(f"③ RRF 融合（无重排）top{len(cands)}", cands, args.show)

    print(f"\n{'=' * 78}\n④ rerank 重排（这一步要联网，约 1~2 秒）\n{'=' * 78}")
    reranked = llm.rerank(args.query, [h.text[:800] for h in cands], top_n=args.show)
    if not reranked:
        print("  rerank 没返回（可能 RERANK_ENABLED=0 或网络失败），退回 RRF 顺序")
        return
    for new_rank, (idx, score) in enumerate(reranked, 1):
        h = cands[idx]
        old = idx + 1
        delta = old - new_rank
        mark = f"↑{delta}" if delta > 0 else (f"↓{-delta}" if delta < 0 else "=")
        page = h.payload.get("page", 0)
        model = h.payload.get("device_model", "-")
        text = (h.text or "").replace("\n", " ")[:50]
        print(
            f"  {new_rank:2d}. (融合第{old:2d} {mark:3s}) [{model:9s}] p{page:<4d} {score:7.4f}  {text}"
        )
    print("\n↑ 表示重排后升了（重排认为它更相关），↓ 表示降了。")


if __name__ == "__main__":
    main()
