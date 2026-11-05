#!/usr/bin/env python3
"""Audit delivered journey TTS files and recorded emulator evidence, without replaying audio.

Uses Python's standard library only. This checks saved bytes, PCM statistics and
event consistency. It does not assess listening quality, exact audible mute
latency, a production integration, or current device behavior.
"""

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import wave


ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs/design/journey-characters"
SAMPLES = ROOT / "prototypes/journey_voice/samples-v2"
DEBUG_ASSETS = ROOT / "android/app/src/debug/assets/journey-voice"
EVIDENCE = DESIGN / "tts-evidence"
PROVIDER = "supertonic3-local-catalog"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_file(directory, filename):
    require(isinstance(filename, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.wav", filename),
            "WAV path must be a single basename")
    path = directory / filename
    require(path.resolve().parent == directory.resolve(), "WAV path escapes its directory")
    return path


def pcm_stats(path):
    with wave.open(str(path), "rb") as source:
        rate, channels, width, frames = (source.getframerate(), source.getnchannels(),
                                          source.getsampwidth(), source.getnframes())
        require(source.getcomptype() == "NONE" and width == 2 and rate > 0 and channels in (1, 2),
                "expected uncompressed PCM16 mono/stereo")
        pcm = source.readframes(frames)
    require(frames > 0 and len(pcm) == frames * channels * width, "truncated or empty PCM")
    count = len(pcm) // 2
    nonzero = peak = total_squares = 0
    first = last = None
    for index, (sample,) in enumerate(struct.iter_unpack("<h", pcm)):
        peak = max(peak, abs(sample))
        total_squares += sample * sample
        if sample:
            nonzero += 1
            if first is None:
                first = index
            last = index
    return {"sha256": sha(path.read_bytes()), "sampleRateHz": rate, "channels": channels,
            "sampleWidthBytes": width, "frames": frames, "pcmDurationSeconds": frames / rate,
            "nonzeroSamples": nonzero, "peak": peak, "rms": math.sqrt(total_squares / count),
            "firstNonzeroPcmSeconds": None if first is None else (first // channels) / rate,
            "lastNonzeroPcmSeconds": None if last is None else (last // channels) / rate}


class Audit:
    def __init__(self):
        self.checks = []
        self.details = {}

    def check(self, name, condition):
        self.checks.append({"check": name, "ok": bool(condition)})

    def section(self, name, action):
        try:
            action()
        except (OSError, ValueError, TypeError, KeyError, IndexError, wave.Error) as error:
            self.checks.append({"check": name, "ok": False, "error": str(error)})

    def manifest(self):
        manifest_path = SAMPLES / "manifest.json"
        manifest = read_json(manifest_path)
        self.check("v2 manifest shape", manifest["schemaVersion"] == 1 and manifest["candidateVersion"] == 2
                   and manifest["providerId"] == PROVIDER and len(manifest["clips"]) == 6)
        self.check("debug manifest exact bytes", manifest_path.read_bytes() == (DEBUG_ASSETS / "manifest.json").read_bytes())
        clips = manifest["clips"]
        self.check("unique clip and character/text keys", len({c["clipId"] for c in clips}) == len(clips)
                   and len({(c["characterId"], c["textSha256"]) for c in clips}) == len(clips))
        common = [c for c in clips if c["category"] == "common"]
        self.check("three distinct comparison speakers", len(common) == 3
                   and {c["speakerId"] for c in common} == {"F3", "F4", "F5"}
                   and len({c["textSha256"] for c in common}) == 1
                   and len({c["audioSha256"] for c in common}) == 3)
        character_bindings = {}
        result = []
        for clip in clips:
            label = clip["clipId"]
            path = local_file(SAMPLES, clip["audioPath"])
            stats = pcm_stats(path)
            self.check(label + " exact text and WAV digests", sha(clip["text"].encode("utf-8")) == clip["textSha256"]
                       and stats["sha256"] == clip["audioSha256"])
            self.check(label + " PCM metadata and duration", all(stats[k] == clip[k] for k in
                       ("sampleRateHz", "channels", "sampleWidthBytes")) and stats["sampleRateHz"] == 44100
                       and stats["channels"] == 1 and abs(stats["pcmDurationSeconds"] * 1000 - clip["durationMs"]) <= 1
                       and 0 < clip["durationMs"] <= 30000)
            self.check(label + " debug WAV exact bytes", path.read_bytes() == local_file(DEBUG_ASSETS, clip["audioPath"]).read_bytes())
            binding = clip["binding"]
            body = {key: value for key, value in binding.items() if key != "bindingId"}
            self.check(label + " canonical voice/DSP binding", binding["bindingId"] == "vb-" + sha(canonical(body))[:32]
                       and all(clip[key] == binding[key] for key in ("providerId", "characterId", "profileId", "speakerId",
                                                                   "locale", "bindingId", "sourceModelRevision", "preset", "postprocess")))
            previous = character_bindings.setdefault(clip["characterId"], binding)
            self.check(label + " same character stable binding", previous == binding)
            result.append({"clipId": label, "speakerId": clip["speakerId"], "audioSha256": stats["sha256"],
                           "durationMs": clip["durationMs"]})
        self.details["sourceClips"] = result

    def imported_files(self):
        inventory = read_json(EVIDENCE / "imported-files.json")
        self.check("imported inventory has 41 files", len(inventory["files"]) == 41)
        for relative, expected in inventory["files"].items():
            path = ROOT / relative
            require(path.resolve().is_relative_to(ROOT), "import path escapes repository")
            self.check("imported SHA " + relative, sha(path.read_bytes()) == expected)
        self.details["importedFiles"] = len(inventory["files"])

    def event(self, value, raw, status, reason=None, request=None):
        require(value in raw, "reported event is missing from raw events")
        require(value["kind"] == "SPEECH" and value["status"] == status and value.get("reason") == reason,
                "unexpected speech status/reason")
        require(value["mode"] == "LOCAL_FILE" and value["providerId"] == PROVIDER, "unexpected speech provider")
        if request is not None:
            require(value["requestId"] == request["requestId"], "speech request mismatch")
            if status != "REJECTED":
                require(all(value[key] == request[key] for key in ("profileId", "speakerId")), "applied voice mismatch")

    def request(self, value, raw, clips):
        require(value in raw and value["kind"] == "LOCAL_REQUEST", "request missing from raw events")
        clip = clips[value["clipId"]]
        require(all(value[key] == clip[key] for key in ("characterId", "profileId", "speakerId", "textSha256", "audioSha256")),
                "request does not match delivered source clip")
        require(value["providerId"] == PROVIDER, "unexpected request provider")

    def observation(self, value, seconds):
        require(value["observedSecondsAtLeast"] >= seconds, "observation duration too short")
        require(not any(e.get("kind") == "SPEECH" and e.get("status") in ("QUEUED", "STARTED")
                        for e in value["events"]), "unexpected automatic playback in bounded observation")

    def parked_runtime(self):
        base = EVIDENCE / "runtime-v2"
        report = read_json(base / "verification.json")
        raw = read_events(base / "runtime-events.jsonl")
        clips = {c["clipId"]: c for c in read_json(SAMPLES / "manifest.json")["clips"]}
        require(report["status"] == "PASSED_APP_EVENTS_AND_INSTALLED_ASSET_IDENTITY", "parked report did not pass")
        require(report["manifestSha256"] == sha((SAMPLES / "manifest.json").read_bytes()), "runtime manifest mismatch")
        require(report["humanListeningPerformed"] is False, "unexpected human listening claim")
        require(report["installedWavSha256"] == {key: clip["audioSha256"] for key, clip in clips.items()}, "installed WAV digest mismatch")
        cases = {case["case"]: case for case in report["cases"]}
        require(len(cases) == len(report["cases"]) == 8, "expected eight unique parked cases")
        for name in ("coast-common", "mountain-common", "city-common"):
            case = cases[name]
            self.request(case["request"], raw, clips)
            require([e["status"] for e in case["speech"]] == ["QUEUED", "STARTED", "COMPLETED"], "playback sequence mismatch")
            for event, status in zip(case["speech"], ("QUEUED", "STARTED", "COMPLETED")):
                self.event(event, raw, status, request=case["request"])
            repeat = cases[name + "-repeat"]
            self.request(repeat["request"], raw, clips)
            self.event(repeat["terminal"], raw, "REJECTED", "REPEATED_TEXT", repeat["request"])
            self.observation(repeat["noAutomaticPlayback"], 1.25)
            self.check(name + " completed and repeat rejected", True)
        for name, reason in (("stop", "USER_CANCELLED"), ("background", "BACKGROUND")):
            case = cases[name]
            self.request(case["request"], raw, clips)
            self.event(case["started"], raw, "STARTED", request=case["request"])
            self.event(case["cancelled"], raw, "CANCELLED", reason, case["request"])
            self.request(case["repeatRequest"], raw, clips)
            self.event(case["repeatTerminal"], raw, "REJECTED", "REPEATED_TEXT", case["repeatRequest"])
            self.observation(case["returnObservation"], 1.25)
            self.observation(case["noAutomaticPlayback"], 1.25)
            self.check(name + " cancellation and bounded no replay", True)
        self.observation(report["finalIdleObservation"], 1.25)
        captures = report["captures"]
        require(len(captures) == 3, "expected three recorded captures")
        for capture in captures:
            require(capture["sourceAudioSha256"] == clips[capture["clipId"]]["audioSha256"], "capture source digest mismatch")
            require(capture["captureSummary"] == read_json(base / (capture["clipId"] + ".summary.json")), "capture summary mismatch")
        self.details["parkedCases"] = len(cases)

    def driving_runtime(self):
        base = EVIDENCE / "runtime-drive-v2"
        report = read_json(base / "verification.json")
        raw_path = base / "runtime-events.jsonl"
        raw = read_events(raw_path)
        require(report["status"] == "PASSED_REAL_EMULATOR_D_CANCEL_AND_REJECT", "D report did not pass")
        require(sha(raw_path.read_bytes()) == report["rawEventsSha256"], "D raw event digest mismatch")
        sequence = report["cancelledRequest"]
        require([e["status"] for e in sequence] == ["QUEUED", "STARTED", "CANCELLED"], "D cancellation sequence mismatch")
        request_id = sequence[0]["requestId"]
        require(all(e["requestId"] == request_id for e in sequence), "D request mismatch")
        clips = {c["clipId"]: c for c in read_json(SAMPLES / "manifest.json")["clips"]}
        request = next((e for e in raw if e.get("kind") == "LOCAL_REQUEST" and e.get("requestId") == request_id), None)
        require(request is not None, "D cancellation request missing")
        self.request(request, raw, clips)
        for event, status in zip(sequence, ("QUEUED", "STARTED", "CANCELLED")):
            self.event(event, raw, status, "SPEECH_NOT_ALLOWED" if status == "CANCELLED" else None, request)
        rejected = report["driveRejected"]
        self.event(rejected, raw, "REJECTED", "SPEECH_NOT_ALLOWED")
        platforms = [e for e in raw if e["kind"] == "PLATFORM"]
        def stamp(event):
            return datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
        require(any(e["gear"] == 8 and e["requiresDO"] is True and e["parked"] is False
                    and abs((stamp(e) - stamp(sequence[-1])).total_seconds()) < 1 for e in platforms),
                "D transition did not accompany cancellation")
        prior = [e for e in platforms if e["at"] <= rejected["at"]]
        require(prior and prior[-1]["gear"] == 8 and prior[-1]["requiresDO"] is True
                and prior[-1]["parked"] is False, "new request was not rejected in D")
        parked = report["parkReturn"]
        require(parked in raw and parked["gear"] == 4 and parked["speed"] == 0 and parked["parked"] is True
                and parked["requiresDO"] is False and parked["at"] > rejected["at"], "P return missing")
        self.observation(report["parkReturnNoAutoReplay"], 2.0)
        require(not any(e["kind"] == "SPEECH" and e.get("status") in ("QUEUED", "STARTED")
                        and e["at"] > sequence[-1]["at"] for e in raw), "unexpected replay after D cancellation")
        require(report["longDurationOrAudibleMuteLatencyProven"] is False, "unexpected acoustic/long-duration claim")
        self.check("D cancellation, new-request denial, P return and recorded 2s no replay", True)

    def captures(self):
        results = []
        for folder in ("runtime-v2", "runtime-drive-v2"):
            base = EVIDENCE / folder
            summaries = sorted(base.glob("*.summary.json"))
            require(len(summaries) == (3 if folder == "runtime-v2" else 1), "capture count mismatch")
            for path in summaries:
                summary = read_json(path)
                name = path.name.removesuffix(".summary.json")
                stats = pcm_stats(base / (name + ".wav"))
                same = all(math.isclose(actual, summary[key], rel_tol=1e-9, abs_tol=1e-9)
                           if isinstance(actual, float) else actual == summary[key] for key, actual in stats.items())
                self.check(folder + "/" + name + " WAV hash and measured PCM summary", same)
                require(summary["evidenceLevel"] == "RAW_PCM_ONLY_NOT_SPEECH_ACCEPTANCE"
                        and summary["humanListeningPerformed"] is False
                        and summary["source"] == "AUTHENTICATED_EMULATOR_SPEAKER_STREAM", "unexpected capture evidence claim")
                packets = read_events(base / (name + ".packets.jsonl"))
                cursor = 0
                for index, packet in enumerate(packets):
                    require(packet["index"] == index and packet["pcmStartFrame"] == cursor
                            and packet["bytes"] == packet["frames"] * stats["channels"] * stats["sampleWidthBytes"],
                            "packet frame boundary mismatch")
                    cursor += packet["frames"]
                self.check(folder + "/" + name + " packet/frame totals", len(packets) == summary["packetCount"]
                           and cursor == stats["frames"])
                results.append({"capture": folder + "/" + name, "sha256": stats["sha256"],
                                "peak": stats["peak"], "nonzeroSamples": stats["nonzeroSamples"]})
        self.details["captures"] = results

    def run(self):
        for name, action in (("manifest and debug assets", self.manifest), ("import inventory", self.imported_files),
                             ("parked runtime records", self.parked_runtime), ("D/P runtime records", self.driving_runtime),
                             ("actual capture PCM", self.captures)):
            self.section(name, action)
        ok = all(row["ok"] for row in self.checks)
        return {"status": "PASS" if ok else "FAIL", "ok": ok,
                "scope": "Repository delivery and saved evidence audit only; no device commands or new playback.",
                "notVerified": ["Human Korean listening, cuteness and speech attribution", "Exact audible start or cancel-to-silence latency",
                                "Production host integration or real vehicle behavior", "Behavior outside the recorded bounded observation windows"],
                "passedChecks": sum(row["ok"] for row in self.checks), "totalChecks": len(self.checks),
                "checks": self.checks, "details": self.details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write JSON to a new file; existing files are never overwritten.")
    args = parser.parse_args()
    report = Audit().run()
    result = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(result)
        except OSError as error:
            parser.error(str(error))
    print(result, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
