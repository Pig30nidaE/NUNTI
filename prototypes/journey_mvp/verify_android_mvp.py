#!/usr/bin/env python3
"""Exercise the installed debug Journey MVP on an emulator using fresh app events.

Standard library only. This runs the app and plays its existing local WAV files;
it never synthesizes audio, downloads a model, or grants synthetic vehicle access.
Screenshots are evidence for a separate visual review, not a pixel-quality verdict.
Use --drive-test only with the official Console open; the operator changes D/P.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "ai.nunti.avatar.demo"
COMPONENT = PACKAGE + "/ai.nunti.app.journey.JourneyMvpActivity"
EVENT_FILE = "files/journey-mvp-events.jsonl"
NAMESPACE = "journey-mvp-validation"
PROVIDER = "qwen3-tts-sohee-local"
CAR_SOURCE = "ACTUAL_CAR_SERVICE"
BODIES = {"pebble", "droplet", "bean", "sprout", "pillow", "lantern", "cloud", "acorn"}
EMOTIONS = ("NEUTRAL", "RELAXED", "CONCERNED", "STARTLED", "RELIEVED", "JOYFUL")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


class VerificationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def emit(**value):
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")), flush=True)


def read_bundle(directory):
    bundle = json.loads((directory / "bundle.json").read_text(encoding="utf-8"))
    voice = json.loads((directory / "voice/manifest.json").read_text(encoding="utf-8"))
    require(bundle["schemaVersion"] == 1 and voice["schemaVersion"] == 2, "Unsupported bundle or voice schema")
    require(bundle["rendererVersion"] == "journey-keepsake-canvas-1", "Unsupported renderer version")
    require(voice["providerId"] == PROVIDER, "Expected the pinned local Sohee provider")
    cases = bundle["characters"]
    require(len(cases) == 8 and {c["visual"]["bodyFamily"] for c in cases} == BODIES,
            "Expected eight cases covering all eight body families")
    require(len({c["caseId"] for c in cases}) == len({c["characterId"] for c in cases}) == 8,
            "Case and character identifiers must be unique")
    clips = {clip["clipId"]: clip for clip in voice["clips"]}
    require(len(clips) == len(voice["clips"]), "Duplicate clip identifier")
    for case in cases:
        require(TOKEN.fullmatch(case["caseId"]), "Invalid case identifier")
        require(digest(canonical(case["visual"])) == case["visualSha256"], "Visual digest differs from the bundle")
        require(set(case["clipIds"]) == {"greeting", "arrival", "common"}, "Expected three clip categories")
        parts = [case[k] for k in ("characterId", "journeyId", "bindingId", "voiceProfileId",
                                   "visualSha256", "recipeSha256", "sourcePlanSha256", "directionSha256")]
        for category, clip_id in sorted(case["clipIds"].items()):
            clip = clips[clip_id]
            source = clip["source"]
            require(clip_id == case["characterId"] + "-" + category
                    and clip["characterId"] == case["characterId"] and clip["profileId"] == case["voiceProfileId"]
                    and source["kind"] == "directed-sohee-v1" and source["bindingId"] == case["bindingId"]
                    and source["directionSha256"] == case["directionSha256"], "Visual/voice identity join differs")
            require(digest(clip["text"].encode("utf-8")) == clip["textSha256"], "Source text digest differs")
            name = clip["audioPath"]
            require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.wav", name), "Invalid source WAV basename")
            audio = directory / "voice" / name
            require(audio.resolve().parent == (directory / "voice").resolve(), "Source WAV escapes voice directory")
            require(digest(audio.read_bytes()) == clip["audioSha256"], "Source WAV digest differs")
            binding = [PROVIDER, clip["characterId"], clip["profileId"], clip["speakerId"], clip["locale"],
                       "directed-sohee-v1", source["sourceModelRevision"], source["bindingId"],
                       source["engineFingerprint"], source["directionSha256"], str(source["seed"])]
            fingerprint = digest("|".join(binding).encode("utf-8"))
            parts.append("|".join((clip_id, clip["textSha256"], clip["audioSha256"], fingerprint)))
        # Same field order and separators as JourneyMvpCatalog.parse.
        case["expectedIdentity"] = digest("\n".join(parts).encode("utf-8"))
    require(set(clips) == {clip for case in cases for clip in case["clipIds"].values()}, "Bundle voice set differs")
    return bundle, clips


class Device:
    def __init__(self, args, output):
        self.args = args
        self.output = output
        self.prefix = [args.adb, "-s", args.serial]
        self.number = 0

    def run(self, *command, binary=False, allow_missing=False):
        self.number += 1
        started = now()
        try:
            result = subprocess.run(self.prefix + list(command), capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VerificationError("ADB command failed or timed out: " + type(error).__name__) from None
        stderr = result.stderr.decode("utf-8", errors="replace")
        with (self.output / "commands.jsonl").open("a", encoding="ascii") as log:
            log.write(json.dumps({"number": self.number, "startedAt": started, "finishedAt": now(),
                                  "command": self.prefix + list(command), "exitCode": result.returncode,
                                  "stderr": stderr[-2000:]}, ensure_ascii=True) + "\n")
        if result.returncode:
            if allow_missing and "No such file" in (stderr + result.stdout.decode("utf-8", errors="replace")):
                return b"" if binary else ""
            raise VerificationError("ADB command returned " + str(result.returncode) + ": " + " ".join(command[:4]))
        require(len(result.stdout) <= 16_777_216, "ADB output exceeded the evidence size limit")
        return result.stdout if binary else result.stdout.decode("utf-8", errors="strict")

    def start(self, action=None, quiet=False, **extras):
        command = ["shell", "am", "start", "--user", str(self.args.user), "-W", "-f", "0x14000000", "-n", COMPONENT,
                   "--es", "mvp_namespace", "validation"]
        if action:
            require(TOKEN.fullmatch(action), "Invalid action")
            command += ["--es", "mvp_action", action]
        if quiet:
            command += ["--ez", "confirm_quiet_test", "true"]
        for key, value in extras.items():
            require(TOKEN.fullmatch(key), "Invalid extra key")
            if isinstance(value, bool):
                command += ["--ez", key, str(value).lower()]
            else:
                require(isinstance(value, str) and TOKEN.fullmatch(value), "Invalid extra value")
                command += ["--es", key, value]
        result = self.run(*command)
        require("Error:" not in result and "Exception" not in result, "Activity launch failed")

    def screenshot(self, name):
        target = self.output / "screenshots" / (name + ".png")
        target.parent.mkdir(exist_ok=True)
        time.sleep(0.3)
        data = self.run("exec-out", "screencap", "-p", binary=True)
        require(data.startswith(b"\x89PNG\r\n\x1a\n"), "screencap did not return PNG")
        target.write_bytes(data)
        return {"file": str(target.relative_to(self.output)), "sha256": digest(data), "pixelInspection": "NOT_PERFORMED"}


class Events:
    def __init__(self, device, output):
        self.device = device
        self.output = output
        self.lines = self.read_lines()
        self.initial_cursor = len(self.lines)
        self.events = []
        self.started_observed_monotonic = {}
        previous = [json.loads(line) for line in self.lines]
        with (output / "events-before-run.jsonl").open("w", encoding="ascii") as log:
            for value in previous:
                if isinstance(value, dict) and value.get("namespace") == NAMESPACE:
                    log.write(json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n")

    def read_lines(self):
        text = self.device.run("exec-out", "run-as", PACKAGE, "--user", str(self.device.args.user), "cat", EVENT_FILE,
                               allow_missing=True)
        lines = text.splitlines()
        if lines and not text.endswith("\n"):
            lines.pop()  # Do not consume an app write that has not finished its line.
        return [line for line in lines if line.strip()]

    def pull(self):
        lines = self.read_lines()
        require(len(lines) >= len(self.lines) and lines[:len(self.lines)] == self.lines,
                "App event file was truncated/rotated; refusing to reuse a cursor")
        fresh = []
        for line in lines[len(self.lines):]:
            value = json.loads(line)
            require(isinstance(value, dict), "Malformed app event")
            if value.get("namespace") != NAMESPACE:
                continue
            require(isinstance(value.get("kind"), str) and isinstance(value.get("at"), str),
                    "Malformed app event")
            datetime.fromisoformat(value["at"].replace("Z", "+00:00"))
            fresh.append(value)
        self.lines = lines
        self.events.extend(fresh)
        for value in fresh:
            if value["kind"] == "MVP_SPEECH" and value.get("status") == "STARTED":
                self.started_observed_monotonic.setdefault(value["requestId"], time.monotonic())
        with (self.output / "runtime-events.jsonl").open("a", encoding="ascii") as log:
            for value in fresh:
                log.write(json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n")
        errors = [value for value in fresh if value["kind"] == "MVP_ERROR"]
        require(not errors, "App reported MVP_ERROR: " + str(errors[-1].get("reason")) if errors else "")
        return fresh

    def cursor(self):
        self.pull()
        return len(self.events)

    def wait(self, offset, predicate, description, timeout=None):
        end = time.monotonic() + (timeout or self.device.args.timeout)
        while time.monotonic() < end:
            self.pull()
            matches = [value for value in self.events[offset:] if predicate(value)]
            if matches:
                return matches[-1]
            time.sleep(0.2)
        raise VerificationError("Timed out waiting for " + description)

    def observe_silent(self, seconds, label, offset=None):
        current = self.cursor()
        if offset is None:
            offset = current
        started = time.monotonic()
        while time.monotonic() - started < seconds:
            self.pull()
            require(not any(e["kind"] == "MVP_SPEECH" and e.get("status") in ("QUEUED", "STARTED")
                            for e in self.events[offset:]), "Unexpected automatic speech: " + label)
            time.sleep(0.2)
        return {"label": label, "observedSecondsAtLeast": time.monotonic() - started,
                "fromEventCursor": offset, "toEventCursor": len(self.events), "events": self.events[offset:]}


class RuntimeAudit:
    def __init__(self, args, bundle, clips, output):
        self.args, self.bundle, self.clips, self.output = args, bundle, clips, output
        self.device = Device(args, output)
        self.events = None
        self.results = []
        self.screenshots = []
        self.requests = set()
        self.selected = None
        self.text_last_started = {}

    def record(self, name, **detail):
        row = {"check": name, "ok": True, **detail}
        self.results.append(row)
        emit(state="PASS", check=name)
        return row

    def preflight(self):
        require(re.fullmatch(r"emulator-[0-9]+", self.args.serial), "Only an explicit emulator serial is accepted")
        hardware = self.device.run("shell", "getprop", "ro.hardware").strip()
        require(hardware in {"ranchu", "goldfish"}, "Refusing a physical device")
        features = self.device.run("shell", "pm", "list", "features")
        automotive = "feature:android.hardware.type.automotive" in features.splitlines()
        require(automotive or self.args.qa_only, "Actual Car observations are required for TTS; use --qa-only for non-automotive screenshots")
        current_user = self.device.run("shell", "am", "get-current-user").strip()
        require(current_user == str(self.args.user), "Current Android user differs from --user")
        self.record("emulator and user preflight", hardware=hardware, automotive=automotive,
                    fingerprint=self.device.run("shell", "getprop", "ro.build.fingerprint").strip(), user=self.args.user)
        self.events = Events(self.device, self.output)
        self.restart()

    def restart(self):
        self.device.run("shell", "am", "force-stop", "--user", str(self.args.user), PACKAGE)
        offset = self.events.cursor()
        self.device.start()  # Quiet confirmation and an utterance are never restored.
        ready = self.events.wait(offset, lambda e: e["kind"] == "MVP_READY", "fresh MVP_READY")
        require(ready["bundleId"] == self.bundle["bundleId"] and ready["cases"] == len(self.bundle["characters"]),
                "Installed bundle differs from the selected PC bundle")
        restored = self.events.wait(offset, lambda e: e["kind"] == "MVP_RESTORED", "fresh MVP_RESTORED")
        self.selected = next((c for c in self.bundle["characters"] if c["characterId"] == restored["characterId"]), None)
        require(self.selected is not None and restored["identity"] == self.selected["expectedIdentity"], "Restored identity differs")
        self.text_last_started.clear()  # The actual cold process has a new, empty queue.
        observation = self.events.observe_silent(self.args.idle_seconds, "cold launch/restore", offset)
        self.record("cold launch restores without automatic speech", restored=restored, observation=observation)
        return restored

    def parked(self):
        # These intents only add/remove an extra block. They cannot grant Car permission.
        offset = self.events.cursor()
        self.device.start("force_block", blocked=True)
        self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and not e["visible"], "extra block")
        offset = self.events.cursor()
        self.device.start("force_block", blocked=False)
        source = "NON_AUTOMOTIVE_LAB" if self.args.qa_only and not self.results[0]["automotive"] else CAR_SOURCE
        gate = self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and e["source"] == source
                                and e["motion"] == "PARKED" and e["parked"] and e["visible"]
                                and e["foreground"] and e["knownUX"] and not e["requiresDO"]
                                and (self.args.qa_only or (e.get("audioMode") == 0 and e.get("musicActive") is False)),
                                "fresh parked display gate with actual MODE_NORMAL and no active music", min(self.args.timeout, 10))
        if not self.args.qa_only:
            dump = self.device.run("shell", "dumpsys", "audio")
            require(re.search(r"(?m)^\s*-\s*Actual mode\s*=\s*MODE_NORMAL\s*$", dump), "Actual AudioManager mode is not confirmed NORMAL")
            (self.output / ("audio-mode-%04d.txt" % self.device.number)).write_text(dump, encoding="utf-8")
        return gate

    def presented(self, offset, case, **values):
        event = self.events.wait(offset, lambda e: e["kind"] == "MVP_PRESENTED" and e["characterId"] == case["characterId"]
                                 and all(e.get(k) == v for k, v in values.items()), "selected case presentation")
        require(event["identity"] == case["expectedIdentity"] and event["visible"] is True
                and event["bodyFamily"] == case["visual"]["bodyFamily"] and event["shapeId"] == case["visual"]["shapeId"]
                and event["visualVoiceJoined"] is True and event["rendererVersion"] == self.bundle["rendererVersion"],
                "Presented visual/voice identity differs")
        return event

    def select(self, case):
        self.parked()
        if self.selected["caseId"] == case["caseId"]:
            alternate = next(c for c in self.bundle["characters"] if c["caseId"] != case["caseId"])
            self.select(alternate)
        offset = self.events.cursor()
        self.device.start("select", case_id=case["caseId"])
        selected = self.events.wait(offset, lambda e: e["kind"] == "MVP_SELECTION" and e.get("caseId") == case["caseId"], "fresh case selection")
        require(selected["characterId"] == case["characterId"] and selected["identity"] == case["expectedIdentity"], "Selected identity differs")
        self.selected = case
        return self.presented(offset, case)

    def speech(self, case, category, terminal="COMPLETED", reason=None, parked=True):
        require(not self.args.qa_only, "QA-only mode cannot submit speech")
        clip = self.clips[case["clipIds"][category]]
        text_key = re.sub(r"\s+", " ", clip["text"].strip())
        if terminal == "COMPLETED" and text_key in self.text_last_started:
            previous = self.text_last_started[text_key]
            deadline = previous["firstObservedMonotonic"] + 60.25
            remaining = deadline - time.monotonic()
            if remaining > 0:
                emit(state="WAIT_REPEAT_WINDOW", clipId=clip["clipId"], secondsAtMost=round(remaining, 3),
                     instruction="Waiting for the existing 60-second policy; no session or policy reset.")
                offset = self.events.cursor()
                started_wait = time.monotonic()
                next_progress = started_wait + 10
                while time.monotonic() < deadline:
                    self.events.pull()
                    require(not any(e["kind"] == "MVP_SPEECH" and e.get("status") in {"QUEUED", "STARTED"}
                                    for e in self.events.events[offset:]), "Unexpected playback while awaiting repeat eligibility")
                    if time.monotonic() >= next_progress:
                        emit(state="WAIT_REPEAT_WINDOW", remainingSeconds=round(max(0, deadline - time.monotonic()), 3))
                        next_progress = time.monotonic() + 10
                    time.sleep(0.2)
                self.record("waited for repeat eligibility " + clip["clipId"],
                            observedSecondsAtLeast=time.monotonic() - started_wait,
                            policyWindowSeconds=60, previousActualStartedEvent=previous["event"],
                            elapsedSinceFirstObservedStartedSeconds=time.monotonic() - previous["firstObservedMonotonic"],
                            waitBasis="Conservative host monotonic elapsed since observing the actual STARTED event; no queue/session/policy reset",
                            fromEventCursor=offset, toEventCursor=len(self.events.events))
        gate = self.parked() if parked else None
        offset = self.events.cursor()
        self.device.start(category, quiet=True)
        request = self.events.wait(offset, lambda e: e["kind"] == "MVP_SPEECH_REQUEST" and e["characterId"] == case["characterId"], "fresh speech request")
        require(request["requestId"] not in self.requests, "Request identifier was reused")
        self.requests.add(request["requestId"])
        require(request["clipId"] == clip["clipId"] and request["identity"] == case["expectedIdentity"]
                and all(request[k] == clip[k] for k in ("characterId", "profileId", "audioSha256", "textSha256")), "Speech request source identity differs")
        target_status = "STARTED" if terminal is None else terminal
        event = self.events.wait(offset, lambda e: e["kind"] == "MVP_SPEECH" and e["requestId"] == request["requestId"]
                                 and e["status"] in {target_status, "REJECTED", "FAILED", "CANCELLED", "COMPLETED"}, "speech " + target_status)
        require(event["status"] == target_status and event.get("reason") == reason,
                "Unexpected speech result: " + str(event.get("status")) + "/" + str(event.get("reason")))
        group = self.speech_group(request["requestId"])
        expected = ["REJECTED"] if terminal == "REJECTED" else ["QUEUED", "STARTED"] + (["COMPLETED"] if terminal else [])
        require([e["status"] for e in group] == expected, "Speech status sequence differs")
        for value in group:
            require(value["mode"] == "LOCAL_FILE" and value["providerId"] == PROVIDER, "Speech escaped the local provider")
            if value["status"] != "REJECTED":
                require(value["profileId"] == clip["profileId"] and value["speakerId"] == clip["speakerId"], "Applied voice differs")
        if any(value["status"] == "STARTED" for value in group):
            self.text_last_started[text_key] = {
                "firstObservedMonotonic": self.events.started_observed_monotonic[request["requestId"]],
                "event": next(value for value in group if value["status"] == "STARTED"),
            }
        return {"request": request, "speech": group, "parkedGate": gate}

    def speech_group(self, request_id):
        return [e for e in self.events.events if e["kind"] == "MVP_SPEECH" and e["requestId"] == request_id]

    def cancellation(self, action, reason):
        self.restart()
        case = self.selected
        playing = self.speech(case, "common", terminal=None)
        offset = self.events.cursor()
        if action == "stop":
            self.device.start("stop")
        else:
            launched = self.device.run("shell", "am", "start", "--user", str(self.args.user),
                                       "-a", "android.settings.SETTINGS")
            require("Error:" not in launched and "Exception" not in launched, "Settings launch failed")
            background = self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE"
                                          and e["foreground"] is False, "fresh actual background gate")
            self.record("Android Settings backgrounds MVP", gate=background)
        terminal = self.events.wait(offset, lambda e: e["kind"] == "MVP_SPEECH"
                                    and e["requestId"] == playing["request"]["requestId"] and e["status"] in {"CANCELLED", "COMPLETED", "FAILED"}, reason)
        require(terminal["status"] == "CANCELLED" and terminal["reason"] == reason, "Cancellation differs")
        require([e["status"] for e in self.speech_group(terminal["requestId"])] == ["QUEUED", "STARTED", "CANCELLED"], "Cancellation sequence differs")
        offset = self.events.cursor()
        self.device.start()
        if action != "stop":
            self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and e["foreground"], "foreground return")
        observation = self.events.observe_silent(self.args.idle_seconds, action + " return", offset)
        repeat = self.speech(case, "common", terminal="REJECTED", reason="REPEATED_TEXT")
        self.record(action + " cancels and return does not replay", playing=playing, terminal=terminal,
                    returnObservation=observation, repeat=repeat)

    def console(self):
        with urlopen(self.args.console_url.rstrip("/") + "/vehicle/state", timeout=3) as response:
            data = response.read(1_000_001)
        require(len(data) <= 1_000_000, "Console response exceeded size limit")
        state = json.loads(data)
        require(state["browser"]["active"] and state["browser"]["clients"] >= 1
                and state["controls"]["emulator_active"] and state["gear"]["bridge_ready"]
                and state["controls"]["dds_ready"]["all"], "Official Console browser/DDS is not active")
        return state

    def drive_test(self):
        require(not self.args.qa_only, "Drive test cannot run in QA-only mode")
        state = self.console()
        require(state["gear"]["actual"]["value"] == "Park" and state["controls"]["speed_kph"] == 0, "Drive test must start parked")
        self.restart()
        case = max(self.bundle["characters"], key=lambda c: self.clips[c["clipIds"]["common"]]["durationMs"])
        if self.selected["caseId"] != case["caseId"]:
            self.select(case)
        emit(state="DRIVE_TEST_PREPARING", instruction="Keep official Console visible. Select Drive only after SELECT_DRIVE_NOW.")
        playing = self.speech(case, "common", terminal=None)
        offset = self.events.cursor()
        emit(state="SELECT_DRIVE_NOW", requestId=playing["request"]["requestId"], instruction="Operator: select D at zero speed in official Console. Do not accelerate.")
        terminal = self.events.wait(offset, lambda e: e["kind"] == "MVP_SPEECH" and e["requestId"] == playing["request"]["requestId"]
                                    and e["status"] in {"CANCELLED", "COMPLETED", "FAILED"}, "actual D cancellation", self.args.drive_timeout)
        require(terminal["status"] == "CANCELLED" and terminal["reason"] == "SPEECH_NOT_ALLOWED", "Speech did not cancel during D transition")
        state = self.console()
        require(state["gear"]["actual"]["value"] == "Drive" and state["controls"]["speed_kph"] == 0, "Cancellation was not observed in actual D/zero speed")
        (self.output / "console-drive.json").write_text(json.dumps(state, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
        rejected = self.speech(case, "common", terminal="REJECTED", reason="SPEECH_NOT_ALLOWED", parked=False)
        offset = self.events.cursor()
        emit(state="RETURN_TO_P_NOW", instruction="Operator: select Park in official Console; the script never changes vehicle state.")
        end = time.monotonic() + self.args.drive_timeout
        parked_state = None
        while time.monotonic() < end:
            self.events.pull()
            state = self.console()
            if state["gear"]["actual"]["value"] == "Park" and state["controls"]["speed_kph"] == 0:
                parked_state = state
                break
            time.sleep(0.3)
        require(parked_state is not None, "Timed out waiting for operator Park return")
        self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and e["source"] == CAR_SOURCE
                         and e["parked"] and e["visible"] and e["knownUX"] and not e["requiresDO"], "actual parked app return")
        observation = self.events.observe_silent(self.args.idle_seconds, "D/P return", offset)
        (self.output / "console-returned-park.json").write_text(json.dumps(parked_state, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
        self.record("operator actual D cancels, rejects, and P return is silent", playing=playing, terminal=terminal,
                    rejected=rejected, returnObservation=observation)

    def visual_qa(self):
        case = self.selected
        for dark in (False, True):
            self.device.start("theme", dark=dark)
            # Force a state change before NEUTRAL, even when NEUTRAL was already selected.
            self.device.start("emotion", emotion="JOYFUL")
            for emotion in EMOTIONS:
                offset = self.events.cursor()
                self.device.start("emotion", emotion=emotion)
                self.presented(offset, case, emotion=emotion)
                shot = self.device.screenshot("qa-" + ("dark" if dark else "light") + "-" + emotion.lower())
                self.screenshots.append({"caseId": case["caseId"], "emotion": emotion, "dark": dark, **shot})
        self.record("six expressions in light and dark captured", screenshots=self.screenshots[-12:])

    def native_size_qa(self):
        for dark in (False, True):
            self.device.start("theme", dark=dark)
            for mode in ("thumbnails", "expressions"):
                offset = self.events.cursor()
                self.device.start("qa", qa_mode=mode)
                event = self.events.wait(offset, lambda e: e["kind"] == "MVP_QA_PRESENTED"
                                         and e["mode"] == mode and e["dark"] == dark, "native-size QA presentation")
                expected = [c["characterId"] for c in self.bundle["characters"]] if mode == "thumbnails" else [self.selected["characterId"]] * 6
                require(event["sizesPx"] == [64, 128] and isinstance(event["density"], (int, float))
                        and event["density"] > 0 and event["characterIds"] == expected, "Native-size QA scene differs")
                shot = self.device.screenshot("qa-native-" + mode + "-" + ("dark" if dark else "light"))
                self.screenshots.append({"qaMode": mode, "dark": dark, "sizesPx": [64, 128], **shot})
                self.record("native-size " + mode + (" dark" if dark else " light"), presentation=event, screenshot=shot)
        self.device.start("experience")

    def extra_block(self):
        self.restart()
        case = self.selected
        playing = self.speech(case, "common", terminal=None)
        offset = self.events.cursor()
        self.device.start("force_block", blocked=True)
        terminal = self.events.wait(offset, lambda e: e["kind"] == "MVP_SPEECH"
                                    and e["requestId"] == playing["request"]["requestId"] and e["status"] in {"CANCELLED", "COMPLETED", "FAILED"}, "extra restriction cancellation")
        require(terminal["status"] == "CANCELLED" and terminal["reason"] == "SPEECH_NOT_ALLOWED", "Extra restriction did not cancel")
        blocked = self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and not e["visible"], "hidden extra restriction gate")
        screenshot = self.device.screenshot("extra-blocked")
        rejected = self.speech(case, "common", terminal="REJECTED", reason="SPEECH_NOT_ALLOWED", parked=False)
        offset = self.events.cursor()
        self.device.start("force_block", blocked=False)
        self.events.wait(offset, lambda e: e["kind"] == "MVP_GATE" and e["source"] == CAR_SOURCE
                         and e["parked"] and e["knownUX"] and not e["requiresDO"] and e["visible"], "extra block removal on actual Park")
        observation = self.events.observe_silent(self.args.idle_seconds, "extra block removal", offset)
        self.record("extra restriction cancels/rejects and removal never grants synthetic permission",
                    playing=playing, terminal=terminal, blocked=blocked, rejected=rejected, observation=observation, screenshot=screenshot)

    def boundaries(self):
        self.parked()
        offset = self.events.cursor()
        self.device.start("verify_boundaries")
        event = self.events.wait(offset, lambda e: e["kind"] == "MVP_BOUNDARY_TESTS", "fresh Android parser/store boundary checks")
        checks = event["checks"]
        require(isinstance(checks, list) and len(checks) == 10
                and event["total"] == event["passed"] == 10, "Expected ten successful Android boundary checks")
        names = [row["name"] for row in checks]
        require(all(isinstance(name, str) and 0 < len(name) <= 256 for name in names)
                and len(set(names)) == 10 and all(row["passed"] is True for row in checks),
                "Android boundary checks are missing, duplicated or failed")
        self.record("ten Android parser/store boundary checks", event=event)

    def run(self):
        self.preflight()
        self.boundaries()
        saved = None
        delivered = []
        for case in self.bundle["characters"]:
            presented = self.select(case)
            shot = self.device.screenshot("case-" + case["caseId"])
            self.screenshots.append({"caseId": case["caseId"], **shot})
            if self.args.qa_only:
                self.record("QA presentation " + case["caseId"], presented=presented, screenshot=shot)
                continue
            greeting = self.speech(case, "greeting")
            repeat = self.speech(case, "greeting", terminal="REJECTED", reason="REPEATED_TEXT")
            common = self.speech(case, "common")
            offset = self.events.cursor()
            self.device.start("reroute")
            reroute = self.events.wait(offset, lambda e: e["kind"] == "MVP_REROUTE", "reroute identity")
            require(reroute["characterId"] == case["characterId"] and reroute["identity"] == case["expectedIdentity"], "Reroute changed identity")
            offset = self.events.cursor()
            self.device.start("arrive")
            arrived = self.events.wait(offset, lambda e: e["kind"] == "MVP_ARRIVED", "arrival stage")
            require(arrived["characterId"] == case["characterId"] and arrived["identity"] == case["expectedIdentity"], "Arrival changed identity")
            self.presented(offset, case, stage="ARRIVED")
            arrival = self.speech(case, "arrival")
            delivered.extend(value["request"]["clipId"] for value in (greeting, common, arrival))
            offset = self.events.cursor()
            self.device.start("save")
            saved = self.events.wait(offset, lambda e: e["kind"] == "MVP_SAVED", "saved collection")
            require(saved["characterId"] == case["characterId"] and saved["identity"] == case["expectedIdentity"]
                    and 1 <= saved["collectedCount"] <= 8, "Saved collection differs")
            self.record("joined greeting/common/arrival/repeat/save " + case["caseId"], presented=presented, greeting=greeting,
                        common=common, repeat=repeat, reroute=reroute, arrival=arrival, saved=saved, screenshot=shot)
        if not self.args.qa_only:
            require(len(delivered) == len(set(delivered)) == 24 and set(delivered) == set(self.clips),
                    "Not all twenty-four bundled WAV clips completed")
            self.record("all twenty-four bundled local WAV clips completed", completedClipIds=sorted(delivered),
                        audioSha256={clip_id: self.clips[clip_id]["audioSha256"] for clip_id in sorted(delivered)})
            require(saved["collectedCount"] == 8, "All eight cases were not collected")
            selected = self.selected
            restored = self.restart()
            require(restored["characterId"] == selected["characterId"] and restored["identity"] == selected["expectedIdentity"]
                    and restored["stage"] == "ARRIVED" and restored["collectedCount"] == 8, "Selection/collection did not survive restart")
            self.record("all eight saved identities and final selection restore", restored=restored)
            common = self.speech(self.selected, "common")
            self.record("common clip completes", **common)
            self.cancellation("stop", "USER_CANCELLED")
            self.cancellation("background", "BACKGROUND")
            self.extra_block()
            if self.args.drive_test:
                self.drive_test()
        self.parked()
        self.visual_qa()
        self.native_size_qa()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--user", type=int, default=10)
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / ".local/journey-mvp/bundle")
    parser.add_argument("--output-dir", type=Path, required=True, help="New, non-existing evidence directory")
    parser.add_argument("--timeout", type=float, default=40, help="Each app-event wait, 5..120 seconds")
    parser.add_argument("--idle-seconds", type=float, default=2, help="No-replay observation, 1.25..15 seconds")
    parser.add_argument("--qa-only", action="store_true", help="Capture visuals only, without submitting any speech")
    parser.add_argument("--drive-test", action="store_true", help="Operator-controlled actual D/zero-speed/P test")
    parser.add_argument("--drive-timeout", type=float, default=60, help="Bounded operator D/P wait, 5..180 seconds")
    parser.add_argument("--console-url", default="http://127.0.0.1:8088", help="Read-only official Console state endpoint")
    args = parser.parse_args()
    if not (0 <= args.user <= 1000 and 5 <= args.timeout <= 120 and 1.25 <= args.idle_seconds <= 15
            and 5 <= args.drive_timeout <= 180):
        parser.error("Invalid user or timeout bounds")
    url = urlsplit(args.console_url)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
        parser.error("Console must be an unauthenticated http://127.0.0.1:<port> origin")
    if args.qa_only and args.drive_test:
        parser.error("--qa-only and --drive-test cannot be combined")
    output = args.output_dir.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.error("Evidence directory must be new: " + str(error))
    audit = None
    report = {"startedAt": now(), "status": "FAIL", "scope": "New emulator app-event and screenshot exercise; no model inference, PCM capture, listening or physical vehicle proof.",
              "notVerified": ["Screenshot pixels and visual quality", "Independent pixel measurement of the 64/128px QA scenes",
                              "PCM/audio content, audible latency or cancel-to-silence", "Human Korean listening", "Physical vehicle behavior"],
              "optionalAssetNegativePlan": [
                  "While the current Activity remains alive, remove one installed app-private WAV, request that clip, and require VOICE_FILE_MISSING without fallback. Restore exact bytes afterward. Cold launch may intentionally repair a missing file, so that is a different test.",
                  "While alive, alter one installed WAV byte, request that clip, and require VOICE_FILE_CORRUPT without fallback. Restore exact bytes afterward. Do not change bundled assets or the persistent binding ledger."],
              "assetNegativeTestsExecuted": False, "driveTestRequested": args.drive_test, "qaOnly": args.qa_only,
              "eventNamespace": NAMESPACE, "appStateNamespace": "journey-mvp-validation"}
    report["notVerified"].append("Missing/corrupt installed audio negative tests are a separate plan, not executed by this tool")
    if not args.drive_test:
        report["notVerified"].append("Actual D/zero-speed/P transition test was not requested")
    if args.qa_only:
        report["notVerified"].append("All speech, cancellation, collection and restart-after-save scenarios in QA-only mode")
    try:
        bundle, clips = read_bundle(args.bundle_dir.resolve())
        report.update(bundleId=bundle["bundleId"], bundleSha256=digest((args.bundle_dir / "bundle.json").read_bytes()))
        audit = RuntimeAudit(args, bundle, clips, output)
        audit.run()
        report["status"] = "PASS_QA_CAPTURE_ONLY" if args.qa_only else "PASS_APP_EVENTS_AND_SCREENSHOT_CAPTURE"
    except (VerificationError, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        report["error"] = str(error)
        emit(state="FAIL", reason=str(error))
        if args.drive_test:
            emit(state="CHECK_PARK_REQUIRED", instruction="Operator: verify official Console is Park at zero speed before ending the test.")
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
