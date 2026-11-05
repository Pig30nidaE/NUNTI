#!/usr/bin/env python3
"""Verify stop cancels active voice after duplicate and queued submissions.

Standard library only. The existing validation namespace and bundled local WAVs
are used on an actual automotive emulator. The official Console is read by GET
only. App intents may select a case in validation state; this tool writes no
private state files and changes no policy, vehicle state, or audio assets.
"""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from verify_android_mvp import (
    CAR_SOURCE, NAMESPACE, PROVIDER, ROOT, RuntimeAudit,
    VerificationError, digest, emit, now, read_bundle, require,
)


class StopAudit(RuntimeAudit):
    def actual_park(self, label):
        """Read current Car state without toggling the app's extra restriction."""
        state = self.console()
        require(state["gear"]["actual"]["value"] == "Park" and state["controls"]["speed_kph"] == 0,
                "Actual Car state changed during " + label)
        self.events.pull()
        gates = [event for event in self.events.events if event["kind"] == "MVP_GATE"]
        require(gates, "No actual app Car gate was observed")
        gate = gates[-1]
        require(gate["source"] == CAR_SOURCE and gate["motion"] == "PARKED"
                and gate["parked"] is True and gate["foreground"] is True and gate["visible"] is True
                and gate["knownUX"] is True and gate["requiresDO"] is False,
                "App actual Car/foreground gate changed during " + label)
        # Audio activity can change during our own active clip. Only the initial
        # request uses parked() to establish actual fresh quiet eligibility.
        target = self.output / (label + "-console.json")
        data = (json.dumps(state, ensure_ascii=True, indent=2) + "\n").encode("ascii")
        target.write_bytes(data)
        return {"consoleFile": target.name, "sha256": digest(data), "console": state, "latestAppGate": gate}

    def active(self, playing):
        self.events.pull()
        group = self.speech_group(playing["request"]["requestId"])
        require([event["status"] for event in group] == ["QUEUED", "STARTED"],
                "Original clip was no longer active before stop")

    def submit_during_playback(self, case, category, status, reason=None):
        """Do not call speech()/parked(): either would toggle force_block."""
        clip = self.clips[case["clipIds"][category]]
        offset = self.events.cursor()
        self.device.start(category, quiet=True)
        request = self.events.wait(offset, lambda event: event["kind"] == "MVP_SPEECH_REQUEST",
                                   "fresh additional " + category + " request")
        require(request["requestId"] not in self.requests, "Additional request identifier was reused")
        self.requests.add(request["requestId"])
        require(request["clipId"] == clip["clipId"] and request["identity"] == case["expectedIdentity"]
                and all(request[key] == clip[key] for key in ("characterId", "profileId", "audioSha256", "textSha256")),
                "Additional speech source identity differs")
        result = self.events.wait(offset, lambda event: event["kind"] == "MVP_SPEECH"
                                  and event["requestId"] == request["requestId"],
                                  "additional request " + status)
        require(result["status"] == status and result.get("reason") == reason,
                "Additional request differs: " + str(result.get("status")) + "/" + str(result.get("reason")))
        group = self.speech_group(request["requestId"])
        require([event["status"] for event in group] == [status],
                "Additional request unexpectedly started or terminated")
        require(all(event["mode"] == "LOCAL_FILE" and event["providerId"] == PROVIDER for event in group),
                "Additional request escaped the local provider")
        if status == "QUEUED":
            require(result["profileId"] == clip["profileId"] and result["speakerId"] == clip["speakerId"],
                    "Queued voice identity differs")
        return {"request": request, "speech": group, "fromEventCursor": offset}

    def stop_and_confirm(self, playing, queued=None):
        self.active(playing)
        offset = self.events.cursor()
        # No other app intent is sent between active/queued proof and stop.
        self.device.start("stop")
        targets = [playing] + ([queued] if queued is not None else [])
        terminals = []
        for target in targets:
            request_id = target["request"]["requestId"]
            terminal = self.events.wait(
                offset, lambda event: event["kind"] == "MVP_SPEECH" and event["requestId"] == request_id
                and event["status"] in {"CANCELLED", "COMPLETED", "FAILED", "REJECTED"},
                "same-request USER_CANCELLED " + request_id)
            require(terminal["status"] == "CANCELLED" and terminal.get("reason") == "USER_CANCELLED",
                    "Stop did not cancel the original active/queued request")
            group = self.speech_group(request_id)
            expected = ["QUEUED", "STARTED", "CANCELLED"] if target is playing else ["QUEUED", "CANCELLED"]
            require([event["status"] for event in group] == expected, "Stop cancellation sequence differs")
            clip = self.clips[target["request"]["clipId"]]
            for event in group:
                require(event["mode"] == "LOCAL_FILE" and event["providerId"] == PROVIDER,
                        "Stopped request escaped the local provider")
                if event["status"] != "CANCELLED" or target is playing:
                    require(event["profileId"] == clip["profileId"] and event["speakerId"] == clip["speakerId"],
                            "Stopped voice identity differs")
                else:
                    # cancelAll removes pending entries before provider selection.
                    require(event.get("profileId") in (None, clip["profileId"])
                            and event.get("speakerId") in (None, clip["speakerId"]),
                            "Pending cancellation carries a different voice")
            terminals.append({"requestId": request_id, "terminal": terminal, "speech": group})
        return terminals

    def return_silent(self, label):
        offset = self.events.cursor()
        self.device.start()  # No speech action or quiet confirmation on return.
        observation = self.events.observe_silent(self.args.idle_seconds, label, offset)
        self.actual_park(label + "-returned")
        shot = self.device.screenshot(label)
        self.screenshots.append(shot)
        return {"observation": observation, "screenshot": shot}

    def prepare_long_greeting(self):
        case = max(self.bundle["characters"],
                   key=lambda value: self.clips[value["clipIds"]["greeting"]]["durationMs"])
        clip = self.clips[case["clipIds"]["greeting"]]
        require(clip["durationMs"] >= 8000, "Longest greeting is too short for the stop regression")
        if self.selected["caseId"] != case["caseId"]:
            self.select(case)
        state = self.actual_park("prepared-" + str(len(self.results)))
        playing = self.speech(case, "greeting", terminal=None)
        return case, clip, playing, state

    def run(self):
        self.preflight()
        require(self.results[0]["automotive"] is True, "Actual automotive Car observations are required")
        case, clip, playing, before = self.prepare_long_greeting()
        self.active(playing)
        duplicate = self.submit_during_playback(case, "greeting", "REJECTED", "DUPLICATE_TEXT")
        during = self.actual_park("duplicate-active")
        self.active(playing)
        terminals = self.stop_and_confirm(playing)
        self.events.pull()
        require([event["status"] for event in self.speech_group(duplicate["request"]["requestId"])] == ["REJECTED"],
                "Rejected duplicate later entered playback")
        returned = self.return_silent("duplicate-stop-return")
        self.record("stop cancels the original active clip after duplicate rejection", clipId=clip["clipId"],
                    durationMs=clip["durationMs"], initialCar=before, playing=playing, duplicate=duplicate,
                    unchangedCar=during, cancellations=terminals, returned=returned)

        self.restart()  # A real new process provides the independent second regression.
        case, clip, playing, before = self.prepare_long_greeting()
        self.active(playing)
        queued = self.submit_during_playback(case, "common", "QUEUED")
        during = self.actual_park("pending-active")
        self.active(playing)
        require([event["status"] for event in self.speech_group(queued["request"]["requestId"])] == ["QUEUED"],
                "Pending common clip started/terminated before stop")
        terminals = self.stop_and_confirm(playing, queued)
        returned = self.return_silent("active-and-pending-stop-return")
        self.record("stop cancels both active and pending clips without replay", clipId=clip["clipId"],
                    durationMs=clip["durationMs"], initialCar=before, playing=playing, queued=queued,
                    unchangedCar=during, cancellations=terminals, returned=returned)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--user", type=int, default=10)
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / ".local/journey-mvp/bundle")
    parser.add_argument("--output-dir", type=Path, required=True, help="New, non-existing evidence directory")
    parser.add_argument("--timeout", type=float, default=40)
    parser.add_argument("--idle-seconds", type=float, default=2)
    parser.add_argument("--console-url", default="http://127.0.0.1:8088", help="GET-only official Console origin")
    parser.set_defaults(qa_only=False)
    args = parser.parse_args()
    if not (0 <= args.user <= 1000 and 5 <= args.timeout <= 120 and 2 <= args.idle_seconds <= 15):
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
              "scope": "Separate actual automotive emulator stop regression after duplicate rejection and queued submission, using fresh app events and existing local WAVs.",
              "vehicleStateChangedByTool": False,
              "notVerified": ["Physical vehicle behavior", "PCM/audio content, human listening or audible stop latency",
                              "Renderer pixels", "24-WAV completion", "Actual D transition", "Background lifecycle"]}
    try:
        require(NAMESPACE == "journey-mvp-validation", "Validation namespace changed")
        bundle_dir = args.bundle_dir.resolve()
        bundle, clips = read_bundle(bundle_dir)
        report.update(bundleId=bundle["bundleId"], bundleSha256=digest((bundle_dir / "bundle.json").read_bytes()))
        audit = StopAudit(args, bundle, clips, output)
        audit.run()
        report["status"] = "PASS_ACTIVE_AND_PENDING_STOP_REGRESSIONS"
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
                    report["failureCleanup"] = "Stop could not be confirmed; inspect the emulator"
            report["checks"] = audit.results
            report["screenshots"] = audit.screenshots
            if audit.events is not None:
                report["initialDeviceEventCursor"] = audit.events.initial_cursor
                report["freshEventCount"] = len(audit.events.events)
        report["finishedAt"] = now()
        (output / "verification.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
        emit(state="FINISHED", status=report["status"], report=str(output / "verification.json"))
    return 0 if report["status"] == "PASS_ACTIVE_AND_PENDING_STOP_REGRESSIONS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
