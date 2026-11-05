#!/usr/bin/env python3
"""Validate the recorded local emulator run; this does not exercise a device."""

import argparse
from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "docs/handoff/restoration/2026-11-02/pm-evidence")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = args.evidence
    before = json.loads((base / "vehicle-state-before-browser.json").read_text())
    opened = json.loads((base / "vehicle-state-browser-open.json").read_text())
    events = [json.loads(line) for line in (base / "events-final.jsonl").read_text().splitlines()]
    lifecycle = json.loads((base / "lifecycle-results.json").read_text())
    checks = []

    def check(name, condition):
        checks.append({"check": name, "ok": bool(condition)})

    check("browser activates emulator and DDS", not before["browser"]["active"]
          and opened["browser"]["active"] and opened["browser"]["clients"] >= 1
          and not before["controls"]["emulator_active"] and opened["controls"]["emulator_active"]
          and opened["controls"]["dds_ready"]["all"] and opened["gear"]["bridge_ready"])
    platform = [e for e in events if e.get("kind") == "PLATFORM"]
    speech = [e for e in events if e.get("kind") == "SPEECH"]
    moving = [e for e in platform if e.get("gear") == 8 and e.get("speed", 0) > 0]
    check("moving Car API state hides avatar", moving and all(
        e["uxKnown"] and e["requiresDO"] and not e["avatarVisible"] for e in moving))
    check("30 kmh observed", any(abs(e["speed"] * 3.6 - 30) < 0.1 for e in moving))
    last = platform[-1]
    check("reparked and visible", last["gear"] == 4 and last["speed"] == 0
          and last["parked"] and not last["requiresDO"] and last["avatarVisible"]
          and moving and last["at"] > moving[-1]["at"])
    groups = {}
    for event in speech:
        groups.setdefault(event["requestId"], []).append(event)
    check("ON_DEVICE completed", any(
        [e["status"] for e in group] == ["QUEUED", "STARTED", "COMPLETED"]
        and all(e["mode"] == "ON_DEVICE" for e in group) for group in groups.values()))
    expected = {"stop": "USER_CANCELLED", "background": "BACKGROUND",
                "repeat_after_stop": "REPEATED_TEXT", "repeat_after_background": "REPEATED_TEXT"}
    cases = {row["case"]: row for row in lifecycle}
    lifecycle_ok = len(lifecycle) == len(cases) == 4 and set(cases) == set(expected)
    if lifecycle_ok:
        for case, reason in expected.items():
            terminal = cases[case]["terminal"]
            repeated = case.startswith("repeat_after_")
            lifecycle_ok &= terminal["reason"] == reason and terminal["status"] == (
                "REJECTED" if repeated else "CANCELLED")
            if repeated:
                prior = cases[case.removeprefix("repeat_after_")]["terminal"]
                lifecycle_ok &= (terminal["requestId"] != prior["requestId"]
                                 and 0 < (datetime.fromisoformat(terminal["at"].replace("Z", "+00:00"))
                                          - datetime.fromisoformat(prior["at"].replace("Z", "+00:00"))).total_seconds() < 60)
            else:
                started = cases[case]["started"]
                lifecycle_ok &= (started["status"] == "STARTED"
                                 and started["requestId"] == terminal["requestId"]
                                 and started["at"] < terminal["at"])
    check("lifecycle cancellation and repeat suppression", lifecycle_ok)
    rejected_in_drive = False
    for event in speech:
        if event["status"] != "REJECTED" or event.get("reason") != "SPEECH_NOT_ALLOWED":
            continue
        prior_platform = [p for p in platform if p["at"] <= event["at"]]
        if prior_platform:
            state = prior_platform[-1]
            rejected_in_drive |= state["gear"] == 8 and state["speed"] == 0 and state["requiresDO"]
    check("D at zero speed rejects a new request", rejected_in_drive)
    cancelled = [e for e in speech if e["status"] == "CANCELLED" and e.get("reason") == "SPEECH_NOT_ALLOWED"]
    drive_times = [datetime.fromisoformat(p["at"].replace("Z", "+00:00"))
                   for p in platform if p["gear"] == 8 and p["requiresDO"]]
    check("D transition cancels active speech", any(
        [e["status"] for e in groups[c["requestId"]]] == ["QUEUED", "STARTED", "CANCELLED"]
        and any(abs((stamp - datetime.fromisoformat(c["at"].replace("Z", "+00:00"))).total_seconds()) < 1
                for stamp in drive_times) for c in cancelled))
    check("no automatic replay after D cancellation", cancelled and not any(
        e["status"] == "QUEUED" and e["at"] > cancelled[-1]["at"] for e in speech))
    report = {"scope": "Recorded emulator evidence only. No new playback, PCM, listening, physical vehicle, or acoustic latency verification.",
              "ok": all(c["ok"] for c in checks), "checks": checks,
              "maxCarApiSpeedKmh": max(e.get("speed", 0) * 3.6 for e in platform),
              "finalPlatform": last}
    result = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    print(result, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
