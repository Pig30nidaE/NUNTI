"""Exercise generated character clips through the real parked Pleos Debug queue."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_character_voice_runtime import Probe, Recording, PACKAGE, COMPONENT, require


class DynamicProbe(Probe):
    def start(self, action=None, character=None, main=False):
        command = ["shell", "am", "start", "--user", "10", "-W"]
        if main:
            command += ["-n", PACKAGE + "/ai.nunti.app.MainActivity"]
        else:
            command += ["-f", "0x14000000", "-n", COMPONENT, "--ez", "confirm_quiet_test", "true",
                        "--es", "voice_catalog", "dynamic"]
            if action:
                command += ["--es", "probe_action", action]
            if character:
                command += ["--es", "character", character]
        response = self.run(*command)
        require("Error:" not in response and "Exception" not in response, "Activity start failed")
        return response

    def request(self, clip, action="local_speak"):
        offset = len(self.events())
        self.start(action, clip["characterId"])
        row = self.wait(offset, lambda event: event.get("kind") == "LOCAL_REQUEST", "generated voice request")
        for key in ("clipId", "characterId", "profileId", "speakerId", "textSha256", "audioSha256", "providerId"):
            require(row.get(key) == clip[key], "Runtime generated identity mismatch: " + key)
        return offset, row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record-python")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    require(manifest["schemaVersion"] == 2 and manifest["providerId"] == "qwen3-tts-sohee-local", "Expected directed Sohee manifest")
    clips = [dict(clip, providerId=manifest["providerId"]) for clip in manifest["clips"]]
    common = [clip for clip in clips if clip["clipId"].endswith("-common")]
    require(len(common) >= 2 and len({clip["textSha256"] for clip in common}) == 1, "Need same-text character comparison")
    for clip in clips:
        require(hashlib.sha256((args.manifest.parent / clip["audioPath"]).read_bytes()).hexdigest() == clip["audioSha256"], "Input WAV changed")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    probe = DynamicProbe(args)
    result = {"status": "RUNNING", "manifestSha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              "cases": [], "captures": [], "humanListeningPerformed": False,
              "androidModelInference": False, "newAvatarRenderer": False, "drivingTransitionRetested": False}
    recorder = None
    code = 1
    try:
        require(probe.run("shell", "am", "get-current-user").strip() == "10", "Foreground Android user10 required")
        offset = probe.fresh("dynamic-install")
        require(not any(row.get("kind") == "LOCAL_CATALOG_ERROR" for row in probe.since(offset)), "Android JSON catalog parse failed")
        probe.start("local_install")
        installed = probe.wait(offset, lambda row: row.get("kind") == "LOCAL_ASSETS_INSTALLED", "dynamic assets install")
        require(installed["providerId"] == manifest["providerId"] and installed["count"] == len(clips), "Installed catalog mismatch")
        result["installedWavSha256"] = {}
        for clip in clips:
            data = probe.run("exec-out", "run-as", PACKAGE, "--user", "10", "cat", "files/journey-dynamic/" + clip["audioPath"], binary=True)
            actual = hashlib.sha256(data).hexdigest()
            require(actual == clip["audioSha256"], "Installed audio differs from generated source")
            result["installedWavSha256"][clip["clipId"]] = actual
        for index, clip in enumerate(common):
            print(json.dumps({"case": clip["clipId"], "state": "RUNNING"}), flush=True)
            probe.fresh(clip["clipId"])
            if args.record_python and index == 0:
                recorder = Recording(args, clip)
            offset, request = probe.request(clip)
            queued = probe.speech(offset, request, "QUEUED")
            probe.assert_identity(clip, queued)
            probe.speech(offset, request, "STARTED")
            probe.speech(offset, request, "COMPLETED")
            events = [row for row in probe.since(offset) if row.get("kind") == "SPEECH" and row.get("requestId") == request["requestId"]]
            require([row["status"] for row in events] == ["QUEUED", "STARTED", "COMPLETED"], "Unexpected speech lifecycle")
            require(all(row.get("providerId") == manifest["providerId"] for row in events), "Provider changed during playback")
            result["cases"].append({"clipId": clip["clipId"], "request": request, "events": events})
            if recorder:
                result["captures"].append(recorder.finish())
                recorder = None
            _, rejected = probe.repeat_rejected(clip)
            result["cases"].append({"case": "repeat", "terminal": rejected})
        clip = common[0]
        for action, reason in (("stop", "USER_CANCELLED"), ("background", "BACKGROUND")):
            probe.fresh(action)
            offset, request = probe.request(clip)
            probe.speech(offset, request, "STARTED")
            probe.start("stop") if action == "stop" else probe.start(main=True)
            cancelled = probe.speech(offset, request, "CANCELLED")
            require(cancelled.get("reason") == reason, "Wrong cancellation reason")
            resume = len(probe.events())
            probe.start()
            quiet = probe.no_auto(resume)
            result["cases"].append({"case": action, "terminal": cancelled, "returnObservation": quiet})
        probe.fresh("final-idle")
        result["finalIdleObservation"] = probe.no_auto(len(probe.events()))
        result["status"] = "PASSED_GENERATED_ASSETS_ANDROID_PARSE_QUEUE_AND_LIFECYCLE"
        code = 0
    except Exception as error:
        result.update(status="FAILED", error=str(error), errorType=type(error).__name__)
    finally:
        if recorder:
            recorder.abort()
        try:
            rows = probe.snapshot()
            (args.output_dir / "runtime-events.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
        except Exception as error:
            result["snapshotError"] = str(error)
            result["status"] = "FAILED"
            code = 1
        result["sessions"] = probe.sessions
        result["commands"] = probe.commands
        result["limits"] = ["Debug emulator and MOCK visual/route only", "No new model inference on Android", "No perceived voice uniqueness or new 2.5D renderer acceptance", "Cancellation events do not prove acoustic silence latency"]
        (args.output_dir / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "cases": len(result["cases"]), "error": result.get("error")}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
