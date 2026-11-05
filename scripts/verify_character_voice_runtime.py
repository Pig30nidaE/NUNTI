#!/usr/bin/env python3
"""Exercise the installed debug-only character voice probe on Pleos user10.

Uses real Car/platform events and private installed WAV bytes. Optional speaker
PCM recording is a separate evidence layer; NCC and human listening are separate.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "ai.nunti.avatar.demo"
COMPONENT = PACKAGE + "/ai.nunti.app.RuntimeProbeActivity"
CHARACTERS = ("coast", "mountain", "city")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_manifest(path):
    raw = path.read_bytes()
    manifest = json.loads(raw)
    clips = {}
    for clip in manifest["clips"]:
        clip_id = clip["clipId"]
        require(clip_id not in clips, "Duplicate clipId")
        audio = PurePosixPath(clip["audioPath"])
        require(not audio.is_absolute() and all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) and part not in (".", "..") for part in audio.parts), "Unsafe audioPath")
        source = path.parent / str(audio)
        require(digest(source.read_bytes()) == clip["audioSha256"], "Source WAV digest mismatch: " + clip_id)
        require(digest(clip["text"].encode("utf-8")) == clip["textSha256"], "Source text digest mismatch: " + clip_id)
        require(clip["providerId"] == manifest["providerId"], "Provider mismatch")
        clips[clip_id] = clip
    for character in CHARACTERS:
        common, greeting = (clips[character + "-" + category] for category in ("common", "greeting"))
        require(common["text"] == manifest["commonComparisonText"], "Common comparison text differs")
        require(all(common[key] == greeting[key] for key in ("characterId", "profileId", "speakerId", "providerId")), "Common/greeting identity mismatch")
    require(len({clips[character + "-common"]["speakerId"] for character in CHARACTERS}) == 3, "Three distinct declared speakers required")
    return manifest, clips, digest(raw)


class Probe:
    def __init__(self, args):
        self.args = args
        self.adb = [args.adb, "-s", args.serial]
        self.sessions = []
        self.active = None
        self.commands = []

    def run(self, *command, binary=False, allow_missing_events=False):
        started = time.time_ns()
        result = subprocess.run(self.adb + list(command), capture_output=True, timeout=20)
        self.commands.append({"argv": list(command), "startedEpochNs": started, "finishedEpochNs": time.time_ns(), "returnCode": result.returncode})
        if result.returncode:
            detail = (result.stdout + result.stderr).decode("utf-8", errors="replace")
            if allow_missing_events and "No such file or directory" in detail:
                return b"" if binary else ""
            raise RuntimeError("ADB command failed: " + " ".join(command) + "\n" + detail)
        return result.stdout if binary else result.stdout.decode("utf-8")

    def events(self):
        raw = self.run("shell", "run-as", PACKAGE, "--user", "10", "cat", "files/runtime-probe.jsonl", allow_missing_events=True)
        lines = raw.splitlines()
        if raw and not raw.endswith("\n"):
            # A concurrent append may not have finished its last JSON line yet.
            lines = lines[:-1]
        rows = [json.loads(line) for line in lines if line.strip()]
        return rows

    def start(self, action=None, character=None, main=False):
        command = ["shell", "am", "start", "--user", "10", "-W"]
        if main:
            command += ["-n", PACKAGE + "/ai.nunti.app.MainActivity"]
        else:
            command += ["-f", "0x14000000", "-n", COMPONENT, "--ez", "confirm_quiet_test", "true"]
            if action:
                command += ["--es", "probe_action", action]
            if character:
                command += ["--es", "character", character]
        response = self.run(*command)
        require("Error:" not in response and "Exception" not in response, "Activity start failed: " + response)
        return response

    def since(self, offset):
        rows = self.events()
        require(len(rows) >= offset, "Runtime event file was truncated during verification")
        return rows[offset:]

    def wait(self, offset, predicate, description, seconds=12):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            matching = [row for row in self.since(offset) if predicate(row)]
            if matching:
                return matching[0]
            time.sleep(0.12)
        raise AssertionError("Timed out waiting for " + description)

    @staticmethod
    def ready(row):
        speed = row.get("speed")
        return row.get("kind") == "PLATFORM" and row.get("gear") == 4 and row.get("parked") is True and isinstance(speed, (int, float)) and math.isfinite(speed) and abs(speed) < .01 and row.get("uxKnown") is True and row.get("requiresDO") is False and row.get("avatarVisible") is True and row.get("audioContext") == "OPERATOR_CONTROLLED_TEST"

    def fresh(self, label):
        self.run("shell", "am", "force-stop", "--user", "10", PACKAGE)
        offset = len(self.events())
        session = {"label": label, "offset": offset, "startedEpochNs": time.time_ns()}
        self.sessions.append(session)
        self.active = session
        self.start()
        created = self.wait(offset, lambda row: row.get("kind") == "PROBE_CREATED", "fresh probe creation")
        require(created.get("fingerprint", "").startswith("Pleos/") and any(value in created.get("hardware", "") for value in ("ranchu", "goldfish")), "Probe runtime target mismatch")
        self.wait(offset, lambda row: row.get("kind") == "CAR_CONNECTION" and row.get("ready") is True, "Car connection")
        ready = self.wait(offset, self.ready, "real P/speed0/known UX/controlled audio", seconds=25)
        session.update({"created": created, "platformReady": ready})
        return offset

    def snapshot(self):
        rows = self.events()
        for index, session in enumerate(self.sessions):
            end = self.sessions[index + 1]["offset"] if index + 1 < len(self.sessions) else len(rows)
            session["events"] = rows[session["offset"]:end]
        return rows

    def request(self, clip, action="local_speak"):
        offset = len(self.events())
        self.start(action, clip["clipId"].split("-", 1)[0])
        row = self.wait(offset, lambda event: event.get("kind") == "LOCAL_REQUEST", "local voice request")
        for key in ("clipId", "characterId", "profileId", "speakerId", "textSha256", "audioSha256", "providerId"):
            require(row.get(key) == clip[key], "LOCAL_REQUEST manifest mismatch: " + key)
        return offset, row

    def speech(self, offset, request, status):
        return self.wait(offset, lambda row: row.get("kind") == "SPEECH" and row.get("requestId") == request["requestId"] and row.get("status") == status, status + " for " + request["requestId"])

    def assert_identity(self, clip, queued):
        for key in ("providerId", "profileId", "speakerId"):
            require(queued.get(key) == clip[key], "QUEUED voice mismatch: " + key)
        require(queued.get("mode") == "LOCAL_FILE", "Expected LOCAL_FILE queue")

    def no_auto(self, offset, seconds=1.25):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rows = self.since(offset)
            require(not any(row.get("kind") == "LOCAL_REQUEST" or row.get("kind") == "SPEECH" and row.get("status") in ("QUEUED", "STARTED") for row in rows), "Unexpected automatic request/playback")
            time.sleep(.12)
        return {"observedSecondsAtLeast": seconds, "events": self.since(offset)}

    def repeat_rejected(self, clip):
        offset, request = self.request(clip)
        terminal = self.speech(offset, request, "REJECTED")
        require(terminal.get("reason") == "REPEATED_TEXT", "Duplicate text was not suppressed")
        statuses = [row.get("status") for row in self.since(offset) if row.get("kind") == "SPEECH" and row.get("requestId") == request["requestId"]]
        require(statuses == ["REJECTED"], "Rejected repeat unexpectedly entered playback")
        return request, terminal


class Recording:
    def __init__(self, args, clip):
        self.path = args.output_dir / (clip["clipId"] + ".wav")
        self.log_path = args.output_dir / (clip["clipId"] + "-capture.log")
        self.log = self.log_path.open("x")
        self.process = subprocess.Popen([
            args.record_python, str(ROOT / "scripts/record_emulator_audio.py"),
            "--serial", args.serial, "--seconds", "10", "--output", str(self.path),
        ], stdout=self.log, stderr=subprocess.STDOUT)
        self.clip = clip
        self.started = time.monotonic()
        end = self.started + 10
        while time.monotonic() < end:
            if '"state": "CAPTURING"' in self.log_path.read_text():
                return
            if self.process.poll() is not None:
                break
            time.sleep(.1)
        self.abort()
        raise RuntimeError("Recorder did not become ready; inspect " + str(self.log_path))

    def finish(self):
        self.process.wait(timeout=max(1, 16 - (time.monotonic() - self.started)))
        self.log.close()
        require(self.process.returncode in (0, 2), "Recorder failed; inspect " + str(self.log_path))
        summary_path = self.path.with_suffix(".summary.json")
        summary = json.loads(summary_path.read_text())
        require(summary["source"] == "AUTHENTICATED_EMULATOR_SPEAKER_STREAM" and summary["packetCount"] > 0, "No authenticated speaker packets")
        require(digest(self.path.read_bytes()) == summary["sha256"], "Capture WAV digest mismatch")
        return {"clipId": self.clip["clipId"], "sourceAudioSha256": self.clip["audioSha256"], "captureSummary": summary, "captureExitCode": self.process.returncode, "nccPerformed": False, "speechAttributionAccepted": False}

    def abort(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.log.close()


def execute(args):
    manifest, clips, manifest_sha = load_manifest(args.manifest)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = {"status": "RUNNING", "manifestPath": str(args.manifest.resolve()), "manifestSha256": manifest_sha, "providerId": manifest["providerId"], "serial": args.serial, "user": 10, "cases": [], "captures": [], "humanListeningPerformed": False, "drivingTestPerformed": False}
    probe = Probe(args)
    recorder = None
    exit_code = 1
    try:
        hardware = probe.run("shell", "getprop", "ro.hardware").strip()
        fingerprint = probe.run("shell", "getprop", "ro.build.fingerprint").strip()
        user = probe.run("shell", "am", "get-current-user").strip()
        require(any(value in hardware for value in ("ranchu", "goldfish")), "Non-emulator target refused")
        require(fingerprint.startswith("Pleos/"), "Pleos image required")
        require(user == "10", "Current foreground Android user must be10; refusing to switch automatically")
        result["device"] = {"hardware": hardware, "fingerprint": fingerprint, "currentUser": user}
        print(json.dumps({"state": "RUNNING", "case": "install"}), flush=True)
        offset = probe.fresh("install")
        probe.start("local_install")
        installed = probe.wait(offset, lambda row: row.get("kind") == "LOCAL_ASSETS_INSTALLED", "local assets installation")
        require(installed.get("count") == len(clips) and installed.get("providerId") == manifest["providerId"], "Installed asset metadata mismatch")
        installed_hashes = {}
        for clip_id, clip in clips.items():
            raw = probe.run("exec-out", "run-as", PACKAGE, "--user", "10", "cat", "files/journey-voice/" + clip["audioPath"], binary=True)
            installed_hashes[clip_id] = digest(raw)
            require(installed_hashes[clip_id] == clip["audioSha256"], "Installed WAV digest mismatch: " + clip_id)
        result["installedWavSha256"] = installed_hashes
        for character in CHARACTERS:
            clip = clips[character + "-common"]
            print(json.dumps({"state": "RUNNING", "case": clip["clipId"]}), flush=True)
            probe.fresh(clip["clipId"])
            if args.record_python:
                recorder = Recording(args, clip)
            offset, request = probe.request(clip)
            queued = probe.speech(offset, request, "QUEUED")
            probe.assert_identity(clip, queued)
            started = probe.speech(offset, request, "STARTED")
            completed = probe.speech(offset, request, "COMPLETED")
            for event in (started, completed):
                require(event.get("mode") == "LOCAL_FILE" and event.get("providerId") == clip["providerId"], "Runtime source mismatch")
            rows = [row for row in probe.since(offset) if row.get("kind") == "SPEECH" and row.get("requestId") == request["requestId"]]
            require([row.get("status") for row in rows] == ["QUEUED", "STARTED", "COMPLETED"], "Unexpected speech transition sequence")
            result["cases"].append({"case": clip["clipId"], "request": request, "speech": rows})
            if recorder:
                result["captures"].append(recorder.finish())
                recorder = None
            repeat, rejected = probe.repeat_rejected(clip)
            result["cases"].append({"case": clip["clipId"] + "-repeat", "request": repeat, "terminal": rejected, "noAutomaticPlayback": probe.no_auto(len(probe.events()))})
        clip = clips["coast-common"]
        for action, reason in (("stop", "USER_CANCELLED"), ("background", "BACKGROUND")):
            print(json.dumps({"state": "RUNNING", "case": action}), flush=True)
            probe.fresh(action)
            offset, request = probe.request(clip)
            queued = probe.speech(offset, request, "QUEUED")
            probe.assert_identity(clip, queued)
            started = probe.speech(offset, request, "STARTED")
            probe.start("stop") if action == "stop" else probe.start(main=True)
            cancelled = probe.speech(offset, request, "CANCELLED")
            require(cancelled.get("reason") == reason, "Incorrect lifecycle cancellation")
            resume_offset = len(probe.events())
            probe.start()
            quiet = probe.no_auto(resume_offset)
            repeat, rejected = probe.repeat_rejected(clip)
            result["cases"].append({"case": action, "request": request, "started": started, "cancelled": cancelled, "returnObservation": quiet, "repeatRequest": repeat, "repeatTerminal": rejected, "noAutomaticPlayback": probe.no_auto(len(probe.events()))})
        probe.fresh("final-idle")
        result["finalIdleObservation"] = probe.no_auto(len(probe.events()))
        result["status"] = "PASSED_APP_EVENTS_AND_INSTALLED_ASSET_IDENTITY"
        exit_code = 0
    except Exception as error:
        result.update({"status": "FAILED", "errorType": type(error).__name__, "error": str(error)})
        print(str(error), file=sys.stderr)
    finally:
        if recorder:
            recorder.abort()
        try:
            raw_events = probe.snapshot()
            (args.output_dir / "runtime-events.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in raw_events))
        except Exception as error:
            result["snapshotError"] = str(error)
            result["status"] = "FAILED_EVENT_SNAPSHOT"
            exit_code = 1
        result["sessions"] = probe.sessions
        result["commands"] = probe.commands
        result["limits"] = ["Route/emotion are MOCK and quiet context is operator controlled.", "No D/moving test, human listening, acoustic quality or wall-clock audible latency acceptance.", "Capture nonzero samples alone do not prove speech attribution; baseline peak2 was observed previously.", "Automatic replay was observed only during explicit bounded windows recorded per case."]
        (args.output_dir / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "outputDirectory": str(args.output_dir.resolve()), "caseCount": len(result["cases"])}), flush=True)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory only; existing paths refused")
    parser.add_argument("--record-python", help="Optional gRPC venv Python. Captures three common clips for10seconds each")
    args = parser.parse_args()
    os.environ.setdefault("ADB_LIBUSB", "1")
    try:
        return execute(args)
    except (AssertionError, OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
