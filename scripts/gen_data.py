"""生成学习用的历史工单与备件台账（离线、可复现）。

用法：uv run python scripts/gen_data.py --cases 200
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eqagent.config import DATA_DIR  # noqa: E402
from eqagent.knowledge import FAULTS, SITES, TECHS  # noqa: E402


def build_cases(total: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    cases: list[dict] = []
    per_fault = max(4, total // len(FAULTS))
    idx = 0
    for fault in FAULTS:
        for k in range(per_fault):
            idx += 1
            symptom = rng.choice(fault["symptoms"])
            site = rng.choice(SITES)
            day = rng.randint(1, 28)
            month = rng.randint(1, 12)
            cases.append(
                {
                    "case_id": f"C{idx:04d}",
                    "device_model": fault["model"],
                    "fault_type": fault["fault"],
                    "alarm_code": fault["alarm"],
                    "symptom": f"{site}{fault['model']}{symptom}",
                    "cause": fault["causes"][k % len(fault["causes"])],
                    "candidate_causes": fault["causes"],
                    "solution": fault["solution"],
                    "parts": fault["parts"],
                    "man_hours": round(fault["man_hours"] * rng.uniform(0.8, 1.3), 1),
                    "technician": rng.choice(TECHS),
                    "date": f"2025-{month:02d}-{day:02d}",
                    "downtime_min": rng.randint(20, 480),
                }
            )
    rng.shuffle(cases)
    return cases


def build_parts() -> list[dict]:
    parts: dict[str, dict] = {}
    code = 1000
    for fault in FAULTS:
        for name in fault["parts"]:
            if name in parts:
                continue
            code += 1
            parts[name] = {
                "code": f"P-{code}",
                "name": name,
                "spec": f"{fault['model']} 专用",
                "device_model": fault["model"],
                "stock": random.Random(code).randint(0, 12),
                "lead_days": random.Random(code).choice([1, 3, 7, 15]),
            }
    return list(parts.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=200)
    args = ap.parse_args()

    cases_dir = DATA_DIR / "cases"
    parts_dir = DATA_DIR / "parts"
    cases_dir.mkdir(parents=True, exist_ok=True)
    parts_dir.mkdir(parents=True, exist_ok=True)

    cases = build_cases(args.cases)
    with (cases_dir / "cases.jsonl").open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")

    parts = build_parts()
    (parts_dir / "parts.json").write_text(
        json.dumps(parts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ cases: {len(cases)} 条 → {cases_dir / 'cases.jsonl'}")
    print(f"✅ parts: {len(parts)} 条 → {parts_dir / 'parts.json'}")


if __name__ == "__main__":
    main()
