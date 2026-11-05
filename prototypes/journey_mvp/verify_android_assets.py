#!/usr/bin/env python3
"""Run three installed-WAV negative tests in the emulator validation namespace.

The only device file this tool removes or writes is the verified first-case
greeting WAV under files/journey-mvp-validation/voice/. Original bytes come
from the verified PC bundle and are restored in finally through shell-v2/dd.
Selection and binding files are read only. No synthesis, downloads or PCM capture.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import time

from verify_android_mvp import (
    Events, NAMESPACE, PACKAGE, ROOT, RuntimeAudit, VerificationError,
    digest, emit, now, read_bundle, require,
)


SELECTION = "files/journey-mvp-validation/selection.json"
BINDINGS = "files/journey-mvp-validation/voice-bindings.txt"


class AssetEvents(Events):
    expected_error = None

    def pull(self):
        offset = len(self.events)
        try:
            return super().pull()
        except VerificationError:
            fresh = self.events[offset:]
            errors = [e for e in fresh if e["kind"] == "MVP_ERROR"]
            if self.expected_error and errors and all(e.get("reason") == self.expected_error for e in errors):
                return fresh
            raise


class AssetAudit(RuntimeAudit):
    def preflight(self):
        require(NAMESPACE == "journey-mvp-validation", "Validation namespace changed")
        require(re.fullmatch(r"emulator-[0-9]+", self.args.serial), "Only an explicit emulator serial is accepted")
        hardware = self.device.run("shell", "getprop", "ro.hardware").strip()
        require(hardware in {"ranchu", "goldfish"}, "Refusing a physical device")
        features = self.device.run("shell", "pm", "list", "features")
        require("feature:android.hardware.type.automotive" in features.splitlines(), "Actual Car observations are required")
        require(self.device.run("shell", "am", "get-current-user").strip() == str(self.args.user), "Current Android user differs from --user")
        self.record("emulator and user preflight", hardware=hardware, automotive=True,
                    fingerprint=self.device.run("shell", "getprop", "ro.build.fingerprint").strip(), user=self.args.user)
        self.events = AssetEvents(self.device, self.output)
        self.restart()


class InstalledGreeting:
    def __init__(self, audit, clip, bundle_dir):
        self.audit = audit
        self.clip = clip
        name = clip["audioPath"]
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.wav", name), "Invalid installed WAV basename")
        self.path = "files/journey-mvp-validation/voice/" + name
        self.source_path = bundle_dir / "voice" / name
        require(self.source_path.resolve().parent == (bundle_dir / "voice").resolve(), "Source WAV escapes the bundle")
        self.original = self.source_path.read_bytes()
        require(44 <= len(self.original) <= 16_777_216 and digest(self.original) == clip["audioSha256"], "Original source WAV differs")
        require(self.read() == self.original, "Installed WAV must initially equal the verified bundle")
        self.armed = False
        self.operations = []
        (audit.output / "source-original.wav").write_bytes(self.original)
        observation = {"observedAt": now(), "clipId": clip["clipId"], "characterId": clip["characterId"],
                       "source": str(self.source_path), "devicePath": self.path,
                       "bytes": len(self.original), "sourceSha256": digest(self.original),
                       "installedSha256": digest(self.read()), "originalBytesEqual": True}
        (audit.output / "source-observation.json").write_text(json.dumps(observation, ensure_ascii=True, indent=2) + "\n", encoding="ascii")

    def read(self):
        return self.audit.device.run("exec-out", "run-as", PACKAGE, "--user", str(self.audit.args.user), "cat", self.path, binary=True)

    def remove(self):
        self.armed = True
        self.audit.device.run("exec-out", "run-as", PACKAGE, "--user", str(self.audit.args.user), "rm", self.path)
        self.operations.append({"operation": "remove", "at": now(), "path": self.path})

    def write(self, data, label):
        # No shell interpolation. The only of= path is assembled from a checked basename.
        require(self.path.startswith("files/journey-mvp-validation/voice/")
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.wav", self.path.rsplit("/", 1)[1]), "Device mutation path is outside validation voice assets")
        self.armed = True
        device = self.audit.device
        device.number += 1
        # Legacy exec-in lost the final partial block in an actual restoration.
        # shell -T uses shell-v2 stdin/EOF plus the remote process exit status.
        command = device.prefix + ["shell", "-T", "run-as", PACKAGE, "--user", str(self.audit.args.user),
                                   "dd", "of=" + self.path, "bs=65536"]
        started = now()
        try:
            result = subprocess.run(command, input=data, capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VerificationError("Validation audio write failed: " + type(error).__name__) from None
        with (self.audit.output / "commands.jsonl").open("a", encoding="ascii") as log:
            log.write(json.dumps({"number": device.number, "startedAt": started, "finishedAt": now(),
                                  "command": command, "exitCode": result.returncode,
                                  "inputBytes": len(data), "inputSha256": digest(data),
                                  "stderr": result.stderr.decode("utf-8", errors="replace")[-2000:]}, ensure_ascii=True) + "\n")
        require(result.returncode == 0, "shell-v2/dd did not restore/write the validation WAV")
        deadline = time.monotonic() + 5
        actual = b""
        while time.monotonic() < deadline:
            actual = self.read()
            if actual == data and digest(actual) == digest(data):
                break
            time.sleep(0.2)
        require(actual == data and digest(actual) == digest(data),
                "Device WAV readback differs: expectedBytes=" + str(len(data)) + " actualBytes=" + str(len(actual))
                + " expectedSha256=" + digest(data) + " actualSha256=" + digest(actual))
        self.operations.append({"operation": label, "at": now(), "path": self.path,
                                "bytes": len(actual), "sha256": digest(actual), "transport": "ADB_SHELL_V2_NO_PTY"})

    def corrupt_one_byte(self):
        changed = bytearray(self.original)
        changed[-1] ^= 1
        require(digest(changed) != self.clip["audioSha256"], "Mutation did not change the audio hash")
        self.write(bytes(changed), "flip_last_byte")

    def restore(self):
        require(digest(self.original) == self.clip["audioSha256"], "Original restoration bytes changed")
        self.write(self.original, "restore_exact_bundle_bytes")


def private_bytes(audit, path, missing=False):
    require(path in {SELECTION, BINDINGS}, "Unexpected state read path")
    return audit.device.run("exec-out", "run-as", PACKAGE, "--user", str(audit.args.user), "cat", path,
                            binary=True, allow_missing=missing)


def require_unchanged(audit, selection, bindings):
    selected = private_bytes(audit, SELECTION)
    ledger = private_bytes(audit, BINDINGS, missing=True)
    require(selected == selection, "Validation selection bytes changed during an audio negative test")
    require(ledger == bindings, "Validation voice binding ledger changed during an audio negative test")
    return {"selectionSha256": digest(selected), "selectionBytes": len(selected),
            "bindingsSha256": digest(ledger), "bindingsBytes": len(ledger), "unchanged": True}


def no_playback_events(audit, offset, label):
    observation = audit.events.observe_silent(audit.args.idle_seconds, label, offset)
    require(not any(e["kind"] == "MVP_SPEECH" and e.get("status") in {"QUEUED", "STARTED", "COMPLETED"}
                    for e in audit.events.events[offset:]), "Unexpected fallback or playback in an asset negative test")
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--user", type=int, default=10)
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / ".local/journey-mvp/bundle")
    parser.add_argument("--output-dir", type=Path, required=True, help="New, non-existing evidence directory")
    parser.add_argument("--timeout", type=float, default=40)
    parser.add_argument("--idle-seconds", type=float, default=2)
    parser.set_defaults(qa_only=False)
    args = parser.parse_args()
    if not (0 <= args.user <= 1000 and 5 <= args.timeout <= 120 and 1.25 <= args.idle_seconds <= 15):
        parser.error("Invalid user or timeout bounds")
    output = args.output_dir.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.error("Evidence directory must be new: " + str(error))
    report = {"startedAt": now(), "status": "FAIL", "namespace": NAMESPACE,
              "scope": "Three installed-WAV negatives on the automotive emulator. No synthesis, physical device, PCM capture or listening claim.",
              "deviceMutationScope": "One verified first-case greeting WAV under files/journey-mvp-validation/voice/ only",
              "notVerified": ["Audio quality or audible cancellation latency", "Physical vehicle behavior", "Parser/store boundaries covered by the separate runtime tool"]}
    audit = asset = None
    selection_baseline = binding_baseline = None
    checks = []
    try:
        bundle_dir = args.bundle_dir.resolve()
        bundle, clips = read_bundle(bundle_dir)
        first = bundle["characters"][0]
        clip = clips[first["clipIds"]["greeting"]]
        audit = AssetAudit(args, bundle, clips, output)
        audit.preflight()
        audit.select(first)
        audit.parked()
        asset = InstalledGreeting(audit, clip, bundle_dir)
        selection_baseline = private_bytes(audit, SELECTION)
        binding_baseline = private_bytes(audit, BINDINGS, missing=True)
        (output / "selection-baseline.json").write_bytes(selection_baseline)
        (output / "voice-bindings-baseline.txt").write_bytes(binding_baseline)
        report.update(bundleId=bundle["bundleId"], caseId=first["caseId"], characterId=first["characterId"],
                      identity=first["expectedIdentity"], clipId=clip["clipId"], sourceAudioSha256=clip["audioSha256"])

        offset = audit.events.cursor()
        asset.remove()
        missing = audit.speech(first, "greeting", terminal="REJECTED", reason="VOICE_FILE_MISSING")
        observation = no_playback_events(audit, offset, "missing WAV, no fallback/start")
        protected = require_unchanged(audit, selection_baseline, binding_baseline)
        checks.append({"check": "ready Activity rejects a missing greeting WAV without fallback", "ok": True,
                       "request": missing, "observation": observation, "protectedState": protected})
        emit(state="PASS", check="VOICE_FILE_MISSING without playback")
        asset.restore()

        restored = audit.restart()
        require(restored["characterId"] == first["characterId"] and restored["identity"] == first["expectedIdentity"], "Selection changed before corruption test")
        audit.parked()
        require_unchanged(audit, selection_baseline, binding_baseline)
        offset = audit.events.cursor()
        asset.corrupt_one_byte()
        corrupt = audit.speech(first, "greeting", terminal="REJECTED", reason="VOICE_FILE_CORRUPT")
        observation = no_playback_events(audit, offset, "changed WAV, no fallback/start")
        protected = require_unchanged(audit, selection_baseline, binding_baseline)
        checks.append({"check": "ready Activity rejects a one-byte changed greeting WAV without fallback", "ok": True,
                       "request": corrupt, "observation": observation, "protectedState": protected})
        emit(state="PASS", check="VOICE_FILE_CORRUPT without playback")

        audit.device.run("shell", "am", "force-stop", "--user", str(args.user), PACKAGE)
        offset = audit.events.cursor()
        audit.events.expected_error = "INSTALLED_AUDIO_CHANGED"
        audit.device.start()
        rejected = audit.events.wait(offset, lambda e: e["kind"] == "MVP_ERROR" and e.get("reason") == "INSTALLED_AUDIO_CHANGED",
                                     "changed installed WAV blocked at cold start")
        observation = no_playback_events(audit, offset, "corrupt cold launch")
        require(not any(e["kind"] in {"MVP_READY", "MVP_SPEECH_REQUEST", "MVP_SPEECH"}
                        for e in audit.events.events[offset:]), "Corrupt cold launch became ready or emitted automatic speech")
        protected = require_unchanged(audit, selection_baseline, binding_baseline)
        checks.append({"check": "cold launch rejects changed installed audio and preserves state bytes", "ok": True,
                       "errorEvent": rejected, "observation": observation, "protectedState": protected})
        emit(state="PASS", check="INSTALLED_AUDIO_CHANGED blocks cold start")
        report["status"] = "PASS_THREE_ASSET_NEGATIVES"
    except (VerificationError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        report["error"] = str(error)
        emit(state="FAIL", reason=str(error))
    finally:
        if asset is not None and asset.armed:
            try:
                asset.restore()
                audit.events.expected_error = None
                restored = audit.restart()
                protected = require_unchanged(audit, selection_baseline, binding_baseline)
                report["finallyRestoration"] = {"ok": True, "audioSha256": digest(asset.read()),
                                                 "restored": restored, "protectedState": protected,
                                                 "coldLaunchAutomaticSpeech": False}
            except (VerificationError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
                report["status"] = "FAIL"
                report["finallyRestoration"] = {"ok": False, "error": str(error), "devicePath": asset.path,
                                                 "verifiedSource": str(asset.source_path)}
                emit(state="RESTORATION_FAILED", path=asset.path, reason=str(error))
        if asset is not None:
            report["assetOperations"] = asset.operations
        report["checks"] = checks
        if audit is not None:
            report["preflightAndRestartChecks"] = audit.results
            if audit.events is not None:
                report["initialDeviceEventCursor"] = audit.events.initial_cursor
                report["freshEventCount"] = len(audit.events.events)
        report["finishedAt"] = now()
        (output / "verification.json").write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
        emit(state="FINISHED", status=report["status"], report=str(output / "verification.json"))
    return 0 if report["status"] == "PASS_THREE_ASSET_NEGATIVES" and report.get("finallyRestoration", {}).get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
