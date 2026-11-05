#!/usr/bin/env python3
"""Render an immutable local avatar voice; no network, API account or recording."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from nunti.avatar_studio.voice_design import build_voice_design
from nunti.avatar_studio.voice_render import render_voice, runtime_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, help="Stored build_voice_design result")
    parser.add_argument(
        "--input",
        type=Path,
        help="AvatarInput or artifact JSON; used to design a voice",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".local/avatar-generator/voices"
    )
    parser.add_argument(
        "--text",
        help="Optional new line, using the frozen synthetic greeting as reference",
    )
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(runtime_status()))
        return
    if bool(args.plan) == bool(args.input):
        parser.error("Supply exactly one of --plan and --input")
    if args.plan:
        plan = json.loads(args.plan.read_text())
    else:
        data = json.loads(args.input.read_text())
        plan = build_voice_design(data, data.get("design"))
    with redirect_stdout(sys.stderr):
        result = render_voice(plan, args.output, args.text)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
