#!/usr/bin/env python3
"""Verify actual background cancellation and capture final installed APK visuals.

Standard library only. Uses the existing local WAV bundle on an automotive
emulator. Opens Android Settings to observe the Activity leave the foreground,
then checks cancellation, a silent return, and the existing repeat-text policy.
Extra restriction cancellation runs in a separate cold app session. The visual
pass selects eight cases without playing their voice clips and captures the
existing expression and native 64/128px QA scenes. It does not run the 24-WAV
suite, change vehicle state, synthesize audio, or download a model.
"""

import argparse
import json
from pathlib import Path

from verify_android_mvp import (
    CAR_SOURCE,
    NAMESPACE,
    PROVIDER,
    ROOT,
    RuntimeAudit,
    VerificationError,
    digest,
    emit,
    now,
    read_bundle,
    require,
)


class LifecycleAudit(RuntimeAudit):
    def background_cancellation(self):
        self.restart()
        case = max(self.bundle["characters"],
                   key=lambda item: self.clips[item["clipIds"]["greeting"]]["durationMs"])
        if self.selected["caseId"] != case["caseId"]:
            self.select(case)
        clip = self.clips[case["clipIds"]["greeting"]]
        playing = self.speech(case, "greeting", terminal=None)

        # No parked()/speech() call while this request is active. parked()
        # toggles an extra restriction and would cancel the request itself.
        offset = self.events.cursor()
        launched = self.device.run("shell", "am", "start", "--user", str(self.args.user),
                                   "-a", "android.settings.SETTINGS")
        require("Error:" not in launched and "Exception" not in launched, "Settings launch failed")
        background = self.events.wait(
            offset, lambda event: event["kind"] == "MVP_GATE"
            and event["source"] == CAR_SOURCE and event["foreground"] is False,
            "fresh actual foreground=false gate after opening Settings")
        require(background["visible"] is False, "Background presentation stayed visible")

        # onStop emits cancellation before its refreshed gate. First prove that
        # the Activity stopped, then inspect the same fresh request's terminal.
        terminal = self.events.wait(
            offset, lambda event: event["kind"] == "MVP_SPEECH"
            and event["requestId"] == playing["request"]["requestId"]
            and event["status"] in {"CANCELLED", "COMPLETED", "FAILED", "REJECTED"},
            "same-request background cancellation")
        require(terminal["status"] == "CANCELLED" and terminal.get("reason") == "BACKGROUND",
                "Background request terminal differs: " + str(terminal.get("status"))
                + "/" + str(terminal.get("reason")))
        group = self.speech_group(playing["request"]["requestId"])
        require([event["status"] for event in group] == ["QUEUED", "STARTED", "CANCELLED"],
                "Background cancellation sequence differs")
        require(all(event["mode"] == "LOCAL_FILE" and event["providerId"] == PROVIDER
                    and event["profileId"] == clip["profileId"] and event["speakerId"] == clip["speakerId"]
                    for event in group), "Background request voice identity differs")

        return_offset = self.events.cursor()
        self.device.start()  # No quiet confirmation and no speech action.
        returned = self.events.wait(
            return_offset, lambda event: event["kind"] == "MVP_GATE"
            and event["source"] == CAR_SOURCE and event["foreground"] is True
            and event["parked"] is True and event["visible"] is True
            and event["knownUX"] is True and event["requiresDO"] is False
            and event.get("quietConfirmed") is False and event.get("quietAccepted") is False
            and event.get("audioMode") == 0 and event.get("musicActive") is False,
            "actual Park foreground return without quiet confirmation")
        observation = self.events.observe_silent(self.args.idle_seconds, "background return", return_offset)
        repeat = self.speech(case, "greeting", terminal="REJECTED", reason="REPEATED_TEXT", parked=False)
        self.record("actual background cancels and return stays silent with repeat protection",
                    caseId=case["caseId"], clipId=clip["clipId"], durationMs=clip["durationMs"],
                    playing=playing, backgroundGate=background, terminal=terminal,
                    foregroundReturnGate=returned, returnObservation=observation, repeat=repeat)

    def assert_no_visual_playback(self, offset):
        self.events.pull()
        require(not any(event["kind"] == "MVP_SPEECH_REQUEST"
                        or (event["kind"] == "MVP_SPEECH" and event.get("status") in {"QUEUED", "STARTED"})
                        for event in self.events.events[offset:]),
                "Visual capture unexpectedly submitted or started speech")

    def final_visual_smoke(self):
        self.device.start("experience")
        offset = self.events.cursor()
        captured = []
        for case in self.bundle["characters"]:
            case_offset = self.events.cursor()
            presented = self.select(case)
            selection = next((event for event in reversed(self.events.events[case_offset:])
                              if event["kind"] == "MVP_SELECTION" and event.get("caseId") == case["caseId"]), None)
            require(selection is not None, "Visual smoke did not observe a fresh case selection")
            shot = self.device.screenshot("case-" + case["caseId"])
            self.screenshots.append({"caseId": case["caseId"], **shot})
            self.assert_no_visual_playback(offset)
            captured.append(case["caseId"])
            self.record("final APK visual selection " + case["caseId"], selection=selection,
                        presented=presented, screenshot=shot,
                        sourceIdentity={"characterId": case["characterId"], "identity": case["expectedIdentity"],
                                        "visualSha256": case["visualSha256"], "voiceProfileId": case["voiceProfileId"],
                                        "clipIds": case["clipIds"]})
        require(len(captured) == len(set(captured)) == 8, "Eight distinct cases were not captured")
        self.record("eight final APK cases captured without voice requests", caseIds=captured,
                    fromEventCursor=offset, toEventCursor=len(self.events.events))
        return offset

    def run(self):
        self.preflight()
        self.background_cancellation()
        self.extra_block()  # Existing audit starts its own cold app session.
        offset = self.final_visual_smoke()
        self.visual_qa()
        self.native_size_qa()
        self.assert_no_visual_playback(offset)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--user", type=int, default=10)
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / ".local/journey-mvp/bundle")
    parser.add_argument("--output-dir", type=Path, required=True, help="New, non-existing evidence directory")
    parser.add_argument("--timeout", type=float, default=40, help="Each app-event wait, 5..120 seconds")
    parser.add_argument("--idle-seconds", type=float, default=2, help="No-replay observation, 2..15 seconds")
    args = parser.parse_args()
    if not (0 <= args.user <= 1000 and 5 <= args.timeout <= 120 and 2 <= args.idle_seconds <= 15):
        parser.error("Invalid user or timeout bounds")
    args.qa_only = False  # RuntimeAudit requires actual automotive Car observations for speech.
    output = args.output_dir.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.error("Evidence directory must be new: " + str(error))

    audit = None
    report = {
        "startedAt": now(), "status": "FAIL",
        "scope": "Fresh actual automotive emulator lifecycle events, extra restriction cancellation, and final installed APK screenshot capture. This is a separate run with no 24-WAV loop.",
        "notVerified": ["Screenshot pixels or visual quality", "Independent pixel measurement of 64/128px QA scenes",
                        "PCM/audio content, audible latency or cancel-to-silence", "Human Korean listening",
                        "Physical vehicle behavior", "24-WAV completion and eight-case save/restore suite",
                        "Installed audio missing/corrupt negative tests", "Actual D/zero-speed/P transition", "Stop-button cancellation"],
        "eventNamespace": NAMESPACE, "appStateNamespace": NAMESPACE,
        "vehicleStateChangedByTool": False,
    }
    try:
        bundle_dir = args.bundle_dir.resolve()
        bundle, clips = read_bundle(bundle_dir)
        report.update(bundleId=bundle["bundleId"], bundleSha256=digest((bundle_dir / "bundle.json").read_bytes()))
        audit = LifecycleAudit(args, bundle, clips, output)
        audit.run()
        report["status"] = "PASS_LIFECYCLE_AND_VISUAL_CAPTURE"
    except (VerificationError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        report["error"] = str(error)
        emit(state="FAIL", reason=str(error))
    finally:
        if audit is not None:
            if report["status"] == "FAIL" and audit.events is not None:
                try:
                    audit.device.start("stop")
                    audit.events.pull()
                    report["failureCleanup"] = "Submitted stop without quiet confirmation; vehicle state was not changed"
                except (VerificationError, OSError, ValueError, KeyError, TypeError):
                    report["failureCleanup"] = "Could not confirm stop; inspect the emulator before continuing"
            report["checks"] = audit.results
            report["screenshots"] = audit.screenshots
            if audit.events is not None:
                report["initialDeviceEventCursor"] = audit.events.initial_cursor
                report["freshEventCount"] = len(audit.events.events)
        report["finishedAt"] = now()
        (output / "verification.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
        emit(state="FINISHED", status=report["status"], report=str(output / "verification.json"))
    return 0 if report["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
