"""命令行入口：eq-ask "3号车间GA55排气温度高报警"。"""

from __future__ import annotations

import argparse
import logging
import sys

from .graph import run_agent


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="设备检修作业 Agent")
    ap.add_argument("symptom", help="故障描述")
    ap.add_argument("--model", default="", help="设备型号，如 GA55 / VMC850 / YE3-160M")
    ap.add_argument("--alarm", default="", help="报警码")
    ap.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = ap.parse_args()

    card = run_agent(args.symptom, args.model, args.alarm)
    if args.json:
        print(card.model_dump_json(indent=2))
    else:
        print(card.to_markdown())
    sys.exit(0)


if __name__ == "__main__":
    main()
