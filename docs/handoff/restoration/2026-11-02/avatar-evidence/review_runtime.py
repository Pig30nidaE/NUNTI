#!/usr/bin/env python3
"""Check PM runtime log observations. Screenshots require separate visual review."""

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    source = args.evidence.resolve()
    names = ["events-moving.jsonl", "events-reparked.jsonl", "events-cancel-on-drive.jsonl"]
    logs = {name: [json.loads(line) for line in (source / name).read_text().splitlines() if line.strip()] for name in names}
    assert logs[names[1]][:len(logs[names[0]])] == logs[names[0]]
    assert logs[names[2]][:len(logs[names[1]])] == logs[names[1]]
    events = logs[names[2]]
    platform = [event for event in events if event["kind"] == "PLATFORM"]
    drive = [event for event in platform if event["gear"] == 8]
    assert drive and all(event["uxKnown"] and event["requiresDO"] and not event["parked"] and not event["avatarVisible"] and event["reason"] == "PLATFORM_BLOCKED" for event in drive)
    moving = [event for event in drive if event["speed"] > 0]
    assert moving
    reparked = next(event for event in logs[names[1]] if event["kind"] == "PLATFORM" and event["at"] > moving[-1]["at"] and event["gear"] == 4 and event["speed"] == 0)
    assert reparked["parked"] and reparked["uxKnown"] and not reparked["requiresDO"] and reparked["avatarVisible"] and reparked["reason"] == "PARKED_STATIC_MVP"
    cancelled = next(event for event in events if event["kind"] == "SPEECH" and event["status"] == "CANCELLED" and event["reason"] == "SPEECH_NOT_ALLOWED")
    speech = [event for event in events if event.get("requestId") == cancelled["requestId"]]
    assert [event["status"] for event in speech] == ["QUEUED", "STARTED", "CANCELLED"]
    assert all(event["mode"] == "ON_DEVICE" for event in speech)
    files = names + ["parked.png", "moving.png", "reparked.png", "vehicle-state-moving.json", "vehicle-state-reparked.json", "ux-moving.txt"]
    result = {
        "reviewedAt": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "sourceDirectory": str(source),
        "sourceSha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files},
        "cumulativeEventCounts": {name: len(values) for name, values in logs.items()},
        "logsAreCumulativePrefixes": True,
        "uniqueDriveSamples": len(drive),
        "uniqueMovingSamples": len(moving),
        "allDriveSamplesBlocked": True,
        "firstDrive": drive[0],
        "firstMoving": moving[0],
        "maximumLoggedSpeed": max(event["speed"] for event in moving),
        "reparked": reparked,
        "cancelledSpeechSequence": speech,
        "scope": "Read-only review of PM capture. No new emulator run, audio capture, listening, accessibility inspection, or timing benchmark.",
    }
    destination = Path(__file__).resolve().parent / "runtime-review.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"PASS: {len(drive)} unique Drive samples blocked, {len(moving)} moving samples, reparked visible, active speech cancelled")
    print(destination)


if __name__ == "__main__":
    main()
