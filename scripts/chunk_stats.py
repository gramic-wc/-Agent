"""块长分布体检：找出"入库了但很难被搜到"的死卡片。

为什么需要它：
    一块只有 15 个字的卡片（表格页码、页眉、残留编号）既没信息量，
    又占着向量库的名额，重排时还会跟好块抢位置。
    切块颗粒度是这个项目最灵敏的旋钮，所以要把基线量出来。

用法：
    uv run python scripts/chunk_stats.py
    uv run python scripts/chunk_stats.py --min 40 --max 900
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eqagent.config import settings  # noqa: E402
from eqagent.ingest.quality import explain, is_garbage  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="块长分布体检")
    ap.add_argument("--min", type=int, default=40, help="短于这个算超短块")
    ap.add_argument("--max", type=int, default=900, help="长于这个算超长块")
    ap.add_argument("--samples", type=int, default=12, help="每类抽样打印几条")
    args = ap.parse_args()

    path = Path(settings.index_dir) / "chunks.jsonl"
    if not path.exists():
        raise SystemExit(f"缺少索引文件 {path}，先跑：uv run eq-ingest --no-vlm")

    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    print(f"索引文件：{path}")
    print(f"总块数 {len(rows)}   ", end="")
    print("类型分布：", dict(Counter(r["block_type"] for r in rows)))

    # 只对正文块量长度：表格和图纸另有长度规律，混在一起会失真
    texts = [r for r in rows if r["block_type"] == "text"]
    lengths = sorted(len(r["text"]) for r in texts)
    n = len(texts)
    short = [r for r in texts if len(r["text"]) < args.min]
    long_ = [r for r in texts if len(r["text"]) > args.max]

    print(f"\n正文块 {n}")
    print(f"  最短 {lengths[0]}   中位数 {median(lengths):.0f}   最长 {lengths[-1]}")
    print("  分位：", {p: lengths[max(0, int(n * p / 100) - 1)] for p in (10, 25, 50, 75, 90, 99)})
    print(f"  超短块 (<{args.min} 字)：{len(short)} 条（{len(short) / n * 100:.1f}%）")
    print(f"  超长块 (>{args.max} 字)：{len(long_)} 条（{len(long_) / n * 100:.1f}%）")

    health = []
    if median(lengths) < 100:
        health.append("△ 中位数 < 100：切得太碎，检索会把半句话当答案 → 调 chunker 时往大改")
    elif median(lengths) > 600:
        health.append("△ 中位数 > 600：块太长，重排打分会被拉平 → 往小改")
    if len(short) / n > 0.15:
        health.append(f"△ 超短块 > 15%：{len(short)} 条占位但没信息量 → Day 13 处理")
    if len(long_) / n > 0.05:
        health.append(f"△ 超长块 > 5%：{len(long_)} 条 → 重排的 800 字截断会丢掉后半段")
    print()
    for h in health or ["✅ 长度分布看起来健康（中位数 150~400、超短 <10%、超长 <5%）"]:
        print(h)

    if short:
        print(f"\n超短块来自哪些文档：")
        for doc, cnt in Counter(r["doc_id"] for r in short).most_common(8):
            print(f"  {cnt:4d}  {doc}")

        print(f"\n抽 {args.samples} 条超短块，并复检质检规则是否漏判：")
        missed = 0
        for r in short[: args.samples]:
            verdict = explain(r["text"])
            bad = is_garbage(r["text"])
            missed += 1 if bad else 0
            flag = "  ← 质检其实判它是垃圾，却没被拦住（改过规则就要重跑 ingest）" if bad else ""
            print(f"  p{r['page']:<4d} {r['block_type']:5s} {r['text']!r:32s} [{verdict}]{flag}")
        if missed:
            print(f"\n⚠️  {missed}/{min(len(short), args.samples)} 条超短块本应被质检拦住。")
            print("    说明这份索引是旧规则生成的 → 重跑 uv run eq-ingest --no-vlm 再看")


if __name__ == "__main__":
    main()
