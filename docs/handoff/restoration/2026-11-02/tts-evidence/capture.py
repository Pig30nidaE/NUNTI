#!/usr/bin/env python3
"""Capture a restoration command, its log, timestamps, and actual exit code."""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required")
    directory = Path(__file__).resolve().parent
    timestamp = lambda: datetime.now(timezone(timedelta(hours=9))).isoformat()
    record = {
        "command": command,
        "cwd": str(Path.cwd()),
        "startedAt": timestamp(),
        "environment": {key: os.environ[key] for key in (
            "JAVA_HOME", "NUNTI_JAVA", "ANDROID_HOME", "ANDROID_USER_HOME",
            "GRADLE_USER_HOME", "JAVA_TOOL_OPTIONS"
        ) if key in os.environ},
        "log": args.name + ".log",
    }
    with (directory / record["log"]).open("w", encoding="utf-8") as output:
        try:
            result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
            code = result.returncode
        except OSError as error:
            output.write(str(error) + "\n")
            code = 127
    record.update(endedAt=timestamp(), exitCode=code)
    (directory / (args.name + ".json")).write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, ensure_ascii=False))
    sys.exit(code)


if __name__ == "__main__":
    main()
