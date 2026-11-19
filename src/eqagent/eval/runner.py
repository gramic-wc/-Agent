"""离线评测：把项目从"能演示"变成"能报数字"。

指标：
  cause_hit@3     前 3 条可能原因里是否命中期望原因（关键词）
  cite_coverage   结论带可追溯引用的比例
  card_complete   作业卡字段完整率（步骤≥3、工具非空、工时>0）
  reject_acc      知识库外问题是否正确拒答/转人工
  latency         端到端耗时 p50/p95
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from ..config import ROOT, settings
from ..agent.graph import run_agent


def load_eval(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def card_complete(card) -> bool:
    return bool(card.steps) and len(card.steps) >= 3 and bool(card.tools) and card.est_man_hours > 0


def main() -> None:
    ap = argparse.ArgumentParser(description="评测检修 Agent")
    ap.add_argument("--eval", type=Path, default=settings.eval_path)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    items = load_eval(args.eval)
    if args.limit:
        items = items[: args.limit]

    rows = []
    for item in items:
        t0 = time.perf_counter()
        card = run_agent(
            item["symptom"], item.get("device_model", ""), item.get("alarm_code", "")
        )
        cost = time.perf_counter() - t0
        cause_texts = [c.cause for c in card.causes[:3]]
        joined = " ".join(cause_texts)
        expects = item.get("expect_causes") or []
        hit = any(kw in joined for kw in expects) if expects else None
        cited = sum(1 for c in card.causes if c.citations)
        coverage = cited / len(card.causes) if card.causes else 0.0
        rows.append(
            {
                "id": item.get("id"),
                "reject_case": bool(item.get("expect_reject")),
                "cause_hit": hit,
                "cite_coverage": coverage,
                "card_complete": card_complete(card),
                "need_human": card.need_human,
                "causes": cause_texts,
                "seconds": round(cost, 2),
            }
        )
        flag = "拒答" if item.get("expect_reject") else ("命中" if hit else "未命中")
        print(f"[{item.get('id')}] {flag}  {card.causes[0].cause if card.causes else '-'}  {cost:.1f}s")

    answer = [r for r in rows if not r["reject_case"]]
    reject = [r for r in rows if r["reject_case"]]
    lat = [r["seconds"] for r in rows]

    metrics = {
        "n": len(rows),
        "n_answer": len(answer),
        "n_reject": len(reject),
        "cause_hit@3": round(sum(1 for r in answer if r["cause_hit"]) / max(1, len(answer)), 3),
        "cite_coverage": round(sum(r["cite_coverage"] for r in answer) / max(1, len(answer)), 3),
        "card_complete": round(sum(1 for r in answer if r["card_complete"]) / max(1, len(answer)), 3),
        "reject_acc": round(sum(1 for r in reject if r["need_human"]) / max(1, len(reject)), 3),
        "latency_p50": round(statistics.median(lat), 2),
        "latency_p95": round(sorted(lat)[int(len(lat) * 0.95) - 1], 2) if lat else 0,
    }

    print("\n| 指标 | 值 |\n| --- | --- |")
    for key, value in metrics.items():
        print(f"| {key} | {value} |")

    out = args.out or ROOT / "data" / "eval" / f"results_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"metrics": metrics, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n结果已写出：{out}")


if __name__ == "__main__":
    main()
