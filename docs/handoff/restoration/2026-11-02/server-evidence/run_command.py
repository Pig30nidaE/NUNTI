#!/usr/bin/env python3
"""Record restoration commands without capturing process environment values."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("command is required")
    evidence = Path(__file__).resolve().parent
    started = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    result = subprocess.run(command, cwd=args.cwd, capture_output=True, text=True)
    finished = datetime.now(ZoneInfo("Asia/Seoul")).isoformat()
    log = evidence / f"{args.name}.log"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    entry = {
        "name": args.name,
        "startedAt": started,
        "finishedAt": finished,
        "cwd": str(args.cwd.resolve()),
        "command": command,
        "exitCode": result.returncode,
        "log": log.name,
    }
    with (evidence / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps(entry, ensure_ascii=False))
    print((result.stdout + result.stderr)[-5000:])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
