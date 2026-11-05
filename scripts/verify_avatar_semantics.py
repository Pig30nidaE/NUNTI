#!/usr/bin/env python3
"""Run the separate 30-case natural-language intent regression set without APIs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from nunti.avatar_studio.design_intent import build_design_intent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".local/avatar-quality-v6/semantic-holdout.json",
    )
    args = parser.parse_args()
    manifest = json.loads(
        (ROOT / "docs/design/avatar-v6/semantic-holdout.json").read_text()
    )
    rows = []
    for case in manifest["cases"]:
        actual = build_design_intent(
            [[0.1, 0.8], [0.5, 0.4], [0.9, 0.2]],
            "서울역",
            "",
            case["purpose"],
            fine_detail_seed="semantic-holdout",
        )["characterPlan"]["purpose"]
        rows.append(
            {
                **case,
                "actualRole": actual["role"],
                "actualResolution": actual["resolution"],
                "excluded": actual["excluded"],
                "passed": actual["role"] == case["role"]
                and actual["resolution"] == case["resolution"],
            }
        )
    report = {
        "cases": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "unknown": sum(r["actualResolution"] == "UNKNOWN" for r in rows),
        "scope": "Authored regression set, not a general language understanding benchmark",
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "results"}, ensure_ascii=False
        )
    )
    if report["passed"] != report["cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
