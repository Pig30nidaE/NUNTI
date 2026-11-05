#!/usr/bin/env python3
"""Exercise actual D/zero-speed/P cancellation separately from the 24-WAV audit.

Only the official Console's GET /vehicle/state is used. The operator changes
gear through the existing Console browser after SELECT_DRIVE_NOW and
RETURN_TO_P_NOW. This tool never publishes a heartbeat or changes vehicle state.
All app intents and event checks use the isolated validation namespace.
"""

import argparse
import json
import sys
from pathlib import Path
import time
from urllib.parse import urlsplit

from verify_android_mvp import (
    CAR_SOURCE, NAMESPACE, PROVIDER, ROOT, RuntimeAudit,
    VerificationError, digest, emit, now, read_bundle, require,
)


class DriveAudit(RuntimeAudit):
    def snapshot_console(self, name, state=None):
        if state is None:
            state = self.console()
        target = self.output / (name + ".json")
        data = (json.dumps(state, ensure_ascii=True, indent=2) + "\n").encode("ascii")
        target.write_bytes(data)
        return {"file": target.name, "sha256": digest(data), "state": state}

    def run_drive(self):
        self.preflight()
        require(self.results[0]["automotive"] is True, "Actual automotive Car service is required")
        self.parked()
        before = self.console()
        require(before["gear"]["actual"]["value"] == "Park" and before["controls"]["speed_kph"] == 0,
                "Actual Console must initially be Park at zero speed")
        initial = self.snapshot_console("console-before-park", before)

        # The pinned 8-case bundle currently selects 04-coast-next/greeting, 8160ms.
        clip = max(self.clips.values(), key=lambda value: (value["durationMs"], value["clipId"]))
        case = next(c for c in self.bundle["characters"] if clip["clipId"] in c["clipIds"].values())
        category = next(name for name, clip_id in case["clipIds"].items() if clip_id == clip["clipId"])
        require(clip["durationMs"] >= 8000, "The longest source clip is too short for the operator D transition")
        self.select(case)  # Produces a fresh selected-case presentation even after restoring that case.
        parked_shot = self.device.screenshot("before-drive-parked")
        self.screenshots.append(parked_shot)
        self.record("actual Park and longest local clip selected", sourceClip={
            "caseId": case["caseId"], "category": category, "clipId": clip["clipId"],
            "durationMs": clip["durationMs"], "audioSha256": clip["audioSha256"],
            "characterId": clip["characterId"], "profileId": clip["profileId"]},
                    console=initial, screenshot=parked_shot)
        emit(state="DRIVE_TEST_PREPARED", clipId=clip["clipId"], durationMs=clip["durationMs"],
             instruction="Keep official Console visible. Wait for SELECT_DRIVE_NOW, then select D without accelerating.")
        if self.args.arm_stdin:
            emit(state="WAIT_START", instruction="Write START to stdin when the Console operator is ready.")
            require(sys.stdin.readline().strip() == "START", "Drive test was not armed")
        playing = self.speech(case, category, terminal=None)
        offset = self.events.cursor()
        emit(state="SELECT_DRIVE_NOW", requestId=playing["request"]["requestId"], clipDurationMs=clip["durationMs"],
             instruction="Operator: select D in the official Console now. Do not accelerate.")
        terminal = self.events.wait(offset, lambda e: e["kind"] == "MVP_SPEECH"
                                    and e["requestId"] == playing["request"]["requestId"]
                                    and e["status"] in {"CANCELLED", "COMPLETED", "FAILED"},
                                    "actual D transition cancellation", self.args.drive_timeout)
        require(terminal["status"] == "CANCELLED" and terminal["reason"] == "SPEECH_NOT_ALLOWED",
                "The local clip completed/failed instead of being cancelled during D")
        require([e["status"] for e in self.speech_group(terminal["requestId"])] == ["QUEUED", "STARTED", "CANCELLED"],
                "D cancellation did not follow the active queue request")
        require(terminal["mode"] == "LOCAL_FILE" and terminal["providerId"] == PROVIDER
                and terminal["profileId"] == clip["profileId"] and terminal["speakerId"] == clip["speakerId"],
                "Cancelled voice identity differs")
        gate = self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and e["source"] == CAR_SOURCE
                                and e["motion"] == "STOPPED" and not e["parked"] and e["foreground"]
                                and e["knownUX"] and e["requiresDO"] and not e["visible"],
                                "actual Car/UX blocked D-at-zero gate", self.args.drive_timeout)
        state = self.console()
        require(state["gear"]["actual"]["value"] == "Drive" and state["controls"]["speed_kph"] == 0,
                "The Console did not confirm actual Drive at zero speed")
        driven = self.snapshot_console("console-drive-zero", state)
        drive_shot = self.device.screenshot("drive-zero-blocked")
        self.screenshots.append(drive_shot)
        rejected = self.speech(case, category, terminal="REJECTED", reason="SPEECH_NOT_ALLOWED", parked=False)
        require(rejected["request"]["requestId"] != playing["request"]["requestId"], "D rejection reused the active request ID")
        self.record("actual D hides renderer, cancels active voice and rejects a new request",
                    playing=playing, terminal=terminal, gate=gate, console=driven,
                    rejected=rejected, screenshot=drive_shot)

        offset = self.events.cursor()
        emit(state="RETURN_TO_P_NOW", instruction="Operator: select Park in the official Console. No automatic replay is allowed.")
        end = time.monotonic() + self.args.drive_timeout
        next_progress = time.monotonic() + 10
        returned = None
        while time.monotonic() < end:
            self.events.pull()
            state = self.console()
            require(not any(e["kind"] == "MVP_SPEECH" and e.get("status") in {"QUEUED", "STARTED"}
                            for e in self.events.events[offset:]), "Unexpected replay while awaiting Park")
            if state["gear"]["actual"]["value"] == "Park" and state["controls"]["speed_kph"] == 0:
                returned = state
                break
            if time.monotonic() >= next_progress:
                emit(state="WAIT_OPERATOR_PARK", remainingSeconds=round(max(0, end - time.monotonic()), 3))
                next_progress = time.monotonic() + 10
            time.sleep(0.3)
        require(returned is not None, "Timed out waiting for operator Park return")
        returned_gate = self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and e["source"] == CAR_SOURCE
                                         and e["motion"] == "PARKED" and e["parked"] and e["foreground"]
                                         and e["knownUX"] and not e["requiresDO"] and e["visible"], "actual visible Park return")
        observation = self.events.observe_silent(self.args.idle_seconds, "actual D/P return", offset)
        parked = self.snapshot_console("console-returned-park", returned)
        final_shot = self.device.screenshot("returned-park-visible")
        self.screenshots.append(final_shot)
        self.record("actual P return is visible and does not replay", gate=returned_gate, console=parked,
                    observation=observation, screenshot=final_shot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--user", type=int, default=10)
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / ".local/journey-mvp/bundle")
    parser.add_argument("--output-dir", type=Path, required=True, help="New, non-existing evidence directory")
    parser.add_argument("--timeout", type=float, default=40)
    parser.add_argument("--idle-seconds", type=float, default=2)
    parser.add_argument("--drive-timeout", type=float, default=90)
    parser.add_argument("--arm-stdin", action="store_true", help="Pause before playback until START arrives on stdin")
    parser.add_argument("--console-url", default="http://127.0.0.1:8088", help="GET-only official Console origin")
    parser.set_defaults(qa_only=False)
    args = parser.parse_args()
    if not (0 <= args.user <= 1000 and 5 <= args.timeout <= 120 and 1.25 <= args.idle_seconds <= 15
            and 5 <= args.drive_timeout <= 180):
        parser.error("Invalid user or timeout bounds")
    url = urlsplit(args.console_url)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
        parser.error("Console must be an unauthenticated http://127.0.0.1:<port> origin")
    output = args.output_dir.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.error("Evidence directory must be new: " + str(error))
    audit = None
    report = {"startedAt": now(), "status": "FAIL", "namespace": NAMESPACE,
              "scope": "Separate actual automotive emulator D/zero-speed/P app-event check; no Console state mutations, PCM capture or model inference.",
              "vehicleControl": "Operator uses the official Console UI. This script performs GET only.",
              "notVerified": ["Physical vehicle behavior", "PCM/audio content, listening or audible stop latency",
                              "Renderer pixels or accessibility subtree", "Moving-speed behavior beyond the actual D/zero-speed gate"]}
    try:
        require(NAMESPACE == "journey-mvp-validation", "Validation namespace changed")
        bundle, clips = read_bundle(args.bundle_dir.resolve())
        report.update(bundleId=bundle["bundleId"], bundleSha256=digest((args.bundle_dir / "bundle.json").read_bytes()))
        audit = DriveAudit(args, bundle, clips, output)
        audit.run_drive()
        report["status"] = "PASS_ACTUAL_D_ZERO_CANCEL_REJECT_AND_P_SILENT_RETURN"
    except (VerificationError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        report["error"] = str(error)
        emit(state="FAIL", reason=str(error))
        emit(state="CHECK_PARK_REQUIRED", instruction="Operator: verify Park at zero speed in the official Console. This tool never changes vehicle state.")
    finally:
        if audit is not None:
            if report["status"] == "FAIL" and audit.events is not None:
                try:
                    audit.device.start("stop")
                    audit.events.pull()
                    report["failureCleanup"] = "Submitted stop without quiet confirmation; vehicle state was not changed"
                except (VerificationError, OSError, ValueError, KeyError, TypeError):
                    report["failureCleanup"] = "Stop could not be confirmed; inspect the emulator"
            report["checks"] = audit.results
            report["screenshots"] = audit.screenshots
            if audit.events is not None:
                report["initialDeviceEventCursor"] = audit.events.initial_cursor
                report["freshEventCount"] = len(audit.events.events)
        report["finishedAt"] = now()
        (output / "verification.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
        emit(state="FINISHED", status=report["status"], report=str(output / "verification.json"))
    return 0 if report["status"] == "PASS_ACTUAL_D_ZERO_CANCEL_REJECT_AND_P_SILENT_RETURN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
