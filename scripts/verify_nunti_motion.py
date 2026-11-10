#!/usr/bin/env python3
"""Verify the debug native transformation on a real, parked Pleos emulator.

Uses the official Virtual Console's HTTP controls and restores the values read
at entry. It never overrides CarUxRestrictions or changes production app state.
Run only after the debug APK is installed and Console DDS is active.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADB = ROOT / ".local/pm-tools/sdk/platform-tools/adb"
PACKAGE = "ai.nunti.avatar.demo"
COMPONENT = PACKAGE + "/ai.nunti.app.transformation.TransformationPreviewActivity"
OUT = ROOT / "docs/redesign/birth-motion-v1/runtime"


class Probe:
    def __init__(self, serial="emulator-5554", continue_background=None):
        self.serial = serial
        self.user = self.adb("shell", "am", "get-current-user").stdout.strip()
        self.folder = OUT / time.strftime("run-%Y%m%dT%H%M%SZ", time.gmtime())
        self.folder.mkdir(parents=True, exist_ok=True)
        self.report = {
            "status": "RUNNING",
            "surface": "ACTUAL_PLEOS_NATIVE_CANVAS",
            "serial": serial,
            "user": self.user,
            "checks": [],
            "screenshots": [],
            "recordings": [],
            "restored": False,
            "paidApiCalls": 0,
        }
        self.baseline = self.console("/vehicle/state")
        if not self.baseline["gear"]["bridge_ready"]:
            raise RuntimeError("Official Virtual Console DDS must be ready")
        self.save("console-before.json", self.console_evidence(self.baseline))
        self.buttons = {}
        self.original_reduced = None
        if continue_background is not None:
            folder = Path(continue_background).resolve()
            if not folder.is_relative_to(OUT.resolve()):
                raise ValueError("Continuation must use this task's runtime directory")
            previous = json.loads((folder / "report.json").read_text())
            if not any(
                check["name"] == "park recovery does not autoplay" and check["passed"]
                for check in previous["checks"]
            ):
                raise ValueError(
                    "Continuation requires the earlier parked-recovery checks"
                )
            self.folder = folder
            self.save("report-initial-home-key-timeout.json", previous)
            self.report = previous
            self.report.pop("error", None)
            self.report["status"] = "RUNNING"
            self.report["continuation"] = (
                "Pleos HOME retained foreground; explicit navigation activity now exercises real onPause"
            )
            self.original_reduced = self.state().get("reducedMotion", False)

    def adb(self, *args, binary=False, check=True, timeout=12):
        return subprocess.run(
            [str(ADB), "-s", self.serial, *map(str, args)],
            capture_output=True,
            text=not binary,
            check=check,
            timeout=timeout,
        )

    def save(self, name, value):
        (self.folder / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )

    def console(self, path, values=None):
        url = "http://127.0.0.1:8088" + path
        if values is not None:
            url += "?" + urllib.parse.urlencode(values)
        request = urllib.request.Request(url, method="GET" if values is None else "PUT")
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    @staticmethod
    def console_evidence(value):
        return {key: value.get(key) for key in ("gear", "controls", "browser")}

    def state(self):
        raw = self.adb(
            "exec-out",
            "run-as",
            PACKAGE,
            "--user",
            self.user,
            "cat",
            "files/nunti-transformation-state.json",
            check=False,
        ).stdout
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def wait(self, predicate, timeout=15):
        end = time.monotonic() + timeout
        latest = {}
        while time.monotonic() < end:
            latest = self.state()
            if predicate(latest):
                return latest
            time.sleep(0.12)
        raise AssertionError("Native state timeout: " + json.dumps(latest))

    def launch(self, **extras):
        previous = self.state().get("playbackId")
        args = [
            "shell",
            "am",
            "start",
            "-W",
            "--user",
            self.user,
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "-n",
            COMPONENT,
        ]
        for key, value in extras.items():
            flag = (
                "--ez"
                if isinstance(value, bool)
                else "--el"
                if isinstance(value, int)
                else "--es"
            )
            args.extend(
                [
                    flag,
                    key,
                    str(value).lower() if isinstance(value, bool) else str(value),
                ]
            )
        self.adb(*args)
        return self.wait(
            lambda s: s.get("playbackId") != previous and s.get("sample"), timeout=20
        )

    def check(self, name, passed, evidence=None):
        self.report["checks"].append(
            {"name": name, "passed": bool(passed), "evidence": evidence}
        )
        if not passed:
            raise AssertionError(name)
        print("PASS " + name, flush=True)

    def screenshot(self, name):
        time.sleep(1.2)
        png = self.adb("exec-out", "screencap", "-p", binary=True).stdout
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        path = self.folder / (name + ".png")
        path.write_bytes(png)
        self.report["screenshots"].append(path.name)
        return path

    def read_buttons(self):
        self.adb("shell", "uiautomator", "dump", "/sdcard/nunti-motion-ui.xml")
        raw = self.adb("shell", "cat", "/sdcard/nunti-motion-ui.xml").stdout
        root = ET.fromstring(raw)
        self.buttons = {}
        for node in root.iter("node"):
            if (
                node.get("text")
                and node.get("enabled") == "true"
                and node.get("clickable") == "true"
            ):
                bounds = re.fullmatch(
                    r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", "")
                )
                if bounds:
                    x1, y1, x2, y2 = map(int, bounds.groups())
                    self.buttons[node.get("text")] = (
                        (x1 + x2) // 2,
                        (y1 + y2) // 2,
                        x2 - x1,
                        y2 - y1,
                    )
        (self.folder / "native-controls.xml").write_text(raw)
        return self.buttons

    def tap(self, text):
        if text not in self.buttons:
            self.read_buttons()
        if text not in self.buttons:
            raise AssertionError("Visible native control not found: " + text)
        x, y, _, _ = self.buttons[text]
        self.adb("shell", "input", "tap", str(x), str(y))

    def ready(self):
        return self.wait(
            lambda s: s.get("assetsReady") and s.get("gateAllowed"), timeout=20
        )

    def collect_frame(self, name):
        self.wait(lambda s: s.get("captureWritten") is True)
        for remote, suffix in [("frame", ""), ("final-reference", "-reference")]:
            raw = self.adb(
                "exec-out",
                "run-as",
                PACKAGE,
                "--user",
                self.user,
                "cat",
                "files/nunti-transformation-" + remote + ".png",
                binary=True,
            ).stdout
            assert raw.startswith(b"\x89PNG\r\n\x1a\n")
            (self.folder / (name + suffix + ".png")).write_bytes(raw)
        self.save(name + ".json", self.state())

    def movie(self, name, style):
        self.launch(sample="coast-curious", style=style, autoPlay=False)
        self.ready()
        self.read_buttons()
        remote = "/sdcard/" + name + ".mp4"
        recorder = subprocess.Popen(
            [
                str(ADB),
                "-s",
                self.serial,
                "shell",
                "screenrecord",
                "--size",
                "1920x1080",
                "--bit-rate",
                "8000000",
                "--time-limit",
                "7",
                remote,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(0.5)
            self.tap("변신 보기")
            self.wait(lambda s: s.get("animationRunning") is True)
            finished = self.wait(
                lambda s: s.get("stopReason") == "COMPLETED", timeout=10
            )
            self.save(name + "-state.json", finished)
            recorder.communicate(timeout=12)
            if recorder.returncode:
                raise AssertionError("Android screenrecord failed")
            self.adb("pull", remote, str(self.folder / (name + ".mp4")), timeout=15)
            self.adb("shell", "rm", remote)
            self.report["recordings"].append(name + ".mp4")
            self.check(
                name + " completes its 4000ms timeline",
                finished["elapsedMs"] == 4000 and not finished["animationRunning"],
                {
                    k: finished.get(k)
                    for k in (
                        "frameCount",
                        "meanFrameIntervalMs",
                        "maxFrameIntervalMs",
                        "targetFps",
                    )
                },
            )
            return finished
        finally:
            if recorder.poll() is None:
                recorder.terminate()
                recorder.communicate(timeout=5)

    def cases(self):
        self.park()
        self.launch(sample="coast-curious", style="LIGHT_TRAIL", autoPlay=False)
        state = self.ready()
        self.original_reduced = state["reducedMotion"]
        if self.original_reduced:
            self.read_buttons()
            self.tap("움직임 줄이기: 켜짐")
            self.wait(lambda s: not s.get("reducedMotion"))
        self.check(
            "actual parked Car service gate",
            state.get("gateSource") == "ACTUAL_CAR_SERVICE",
        )

        for moment in (0, 1000, 2200, 3000, 4000):
            self.launch(
                sample="coast-curious",
                style="LIGHT_TRAIL",
                seekMs=moment,
                readOnlyCapture=True,
                captureFrame=True,
            )
            state = self.wait(
                lambda s, moment=moment: (
                    s.get("captureWritten") and s.get("elapsedMs") == moment
                )
            )
            self.collect_frame(f"native-{moment:04d}")
            self.screenshot(f"screen-{moment:04d}")
            self.check(
                f"native capture {moment}ms uses real parked gate", state["gateAllowed"]
            )

        source = (
            ROOT / "docs/redesign/route-variants-v1/samples/coast-curious/character.png"
        )
        self.check(
            "final source equals approved generated PNG",
            state["finalSourceHash"] == hashlib.sha256(source.read_bytes()).hexdigest(),
        )
        self.adb("shell", "dumpsys", "gfxinfo", PACKAGE, "reset")
        self.movie("light-trail-preview", "LIGHT_TRAIL")
        self.movie("quiet-color-preview", "QUIET_COLOR")
        (self.folder / "gfxinfo.txt").write_text(
            self.adb("shell", "dumpsys", "gfxinfo", PACKAGE).stdout
        )
        (self.folder / "memory-after-playback.txt").write_text(
            self.adb("shell", "dumpsys", "meminfo", PACKAGE).stdout
        )

        self.launch(sample="coast-curious", style="LIGHT_TRAIL", autoPlay=False)
        self.ready()
        self.read_buttons()
        self.check(
            "native controls meet 56dp height",
            all(v[3] >= 56 for v in self.buttons.values()),
            self.buttons,
        )
        self.tap("변신 보기")
        self.wait(lambda s: s.get("animationRunning") and s.get("elapsedMs", 0) >= 450)
        self.tap("바로 보기")
        state = self.wait(lambda s: s.get("stopReason") == "SKIPPED")
        self.check(
            "skip resolves immediately to final",
            not state["animationRunning"] and state["elapsedMs"] == 4000,
        )
        self.screenshot("skip-final")

        self.read_buttons()
        self.tap("움직임 줄이기: 꺼짐")
        state = self.wait(lambda s: s.get("reducedMotion") is True)
        self.check(
            "reduced motion shows final without playback",
            not state["animationRunning"] and state["elapsedMs"] == 4000,
        )
        self.launch(sample="mountain-calm", style="LIGHT_TRAIL", autoPlay=True)
        state = self.ready()
        self.check(
            "reduced option persists across selection",
            state["reducedMotion"] and not state["animationRunning"],
        )
        self.screenshot("reduced-motion-final")
        self.read_buttons()
        self.tap("움직임 줄이기: 켜짐")
        self.wait(lambda s: not s.get("reducedMotion"))

        self.launch(sample="coast-curious", style="LIGHT_TRAIL", autoPlay=False)
        self.ready()
        self.read_buttons()
        self.tap("변신 보기")
        self.wait(lambda s: s.get("animationRunning") and s.get("elapsedMs", 0) >= 450)
        self.console("/vehicle/gear", {"gear": "Drive"})
        state = self.wait(
            lambda s: not s.get("gateAllowed") and not s.get("animationRunning")
        )
        self.save("restricted-state.json", state)
        self.console(
            "/vehicle/controls",
            {"speed": 20, "accelerator": 0, "brake": 0, "steering": 0},
        )
        self.check(
            "real D transition stops decoration",
            state["stopReason"] in ("RESTRICTED", "BACKGROUNDED"),
        )
        (self.folder / "restricted-ux.txt").write_text(
            self.adb(
                "shell",
                "dumpsys",
                "car_service",
                "--services",
                "CarUxRestrictionsManagerService",
            ).stdout
        )
        self.screenshot("driving-restricted")
        self.park()
        time.sleep(1)
        returned = self.state()
        self.check(
            "park recovery does not autoplay", not returned.get("animationRunning")
        )
        self.save("park-return-state.json", returned)
        self.remaining_cases()

    def remaining_cases(self):
        self.park()
        self.launch(sample="city-adventurous", style="QUIET_COLOR", autoPlay=False)
        self.ready()
        self.read_buttons()
        self.tap("변신 보기")
        self.wait(lambda s: s.get("animationRunning"))
        # Pleos HOME keeps the current multi-window app resumed. Switch to the
        # previously observed navigation activity to exercise an actual onPause.
        self.adb(
            "shell",
            "am",
            "start",
            "-W",
            "--user",
            self.user,
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "-n",
            "ai.umos.maps.android.navigation.app/.MainActivity",
        )
        state = self.wait(
            lambda s: not s.get("foreground") and not s.get("animationRunning")
        )
        self.check(
            "background interrupts and settles",
            state.get("stopReason") == "BACKGROUNDED",
        )
        self.save("background-state.json", state)

        self.launch(
            sample="city-adventurous",
            style="QUIET_COLOR",
            displayMode="night",
            seekMs=4000,
            readOnlyCapture=True,
            captureFrame=True,
        )
        self.wait(lambda s: s.get("captureWritten") and s.get("displayMode") == "night")
        self.collect_frame("night-final")
        self.screenshot("screen-night-final")
        self.check("night final remains static", not self.state()["animationRunning"])

        self.launch(
            sample="coast-curious",
            style="LIGHT_TRAIL",
            loadDelayMs=3000,
            autoPlay=False,
        )
        state = self.wait(lambda s: s.get("status") == "LOADING")
        self.check(
            "loading retains approved base",
            state["baseReady"] and not state["animationRunning"],
        )
        self.screenshot("loading-base")
        self.ready()
        self.launch(
            sample="coast-curious", simulateMissingAsset=True, captureFrame=True
        )
        state = self.wait(
            lambda s: s.get("status") == "FAILED" and s.get("captureWritten")
        )
        self.collect_frame("failure-base")
        self.screenshot("screen-failure-base")
        self.check(
            "missing asset shows complete base",
            state["baseReady"]
            and state["captureReference"] == "APPROVED_BASE"
            and not state["animationRunning"],
        )

        for category in ("coast", "mountain", "city"):
            for mood in ("calm", "curious", "adventurous"):
                sample = category + "-" + mood
                self.launch(
                    sample=sample, seekMs=4000, readOnlyCapture=True, captureFrame=True
                )
                state = self.wait(
                    lambda s, sample=sample: (
                        s.get("captureWritten") and s.get("sample") == sample
                    )
                )
                self.collect_frame("final-" + sample)
                source = (
                    ROOT
                    / "docs/redesign/route-variants-v1/samples"
                    / sample
                    / "character.png"
                )
                self.check(
                    sample + " final retains original PNG",
                    state["finalSourceHash"]
                    == hashlib.sha256(source.read_bytes()).hexdigest(),
                )

        self.launch(
            sample="coast-curious", style="LIGHT_TRAIL", seekMs=4000, autoPlay=False
        )
        self.ready()
        self.resize_case()
        self.screenshot("final-ready-to-review")
        self.report["status"] = "PASS"

    def resize_case(self):
        raw = self.adb("shell", "dumpsys", "activity", "activities").stdout
        match = re.search(
            r"\* Task\{[^\n]*#(\d+) type=standard[^\n]*ai\.nunti\.avatar\.demo[^\n]*\n\s+mBounds=Rect\((\d+), (\d+) - (\d+), (\d+)\)",
            raw,
        )
        if not match:
            raise AssertionError("Native app task bounds are unavailable")
        task, left, top, right, bottom = map(int, match.groups())
        narrow_right = left + min(830, right - left)
        try:
            self.adb(
                "shell", "am", "task", "resize", task, left, top, narrow_right, bottom
            )
            self.screenshot("resized-830px")
            raw = self.adb("shell", "dumpsys", "activity", "activities").stdout
            (self.folder / "resized-activity.txt").write_text(raw)
            self.read_buttons()
            self.save("resized-state.json", self.state())
            observed = f"mBounds=Rect({left}, {top} - {narrow_right}, {bottom})" in raw
            self.check(
                "native narrow task layout remains usable",
                observed and bool(self.buttons),
                {"width": narrow_right - left, "height": bottom - top},
            )
        finally:
            self.adb("shell", "am", "task", "resize", task, left, top, right, bottom)
            restored = self.adb("shell", "dumpsys", "activity", "activities").stdout
            (self.folder / "restored-activity.txt").write_text(restored)
            self.report["taskBoundsRestored"] = (
                f"mBounds=Rect({left}, {top} - {right}, {bottom})" in restored
            )
            if not self.report["taskBoundsRestored"]:
                raise AssertionError("Original app task bounds were not restored")

    def park(self):
        self.console(
            "/vehicle/controls",
            {
                "speed": 0,
                "accelerator": 0,
                "brake": 0,
                "steering": self.baseline["controls"]["steering_deg"],
            },
        )
        self.console("/vehicle/gear", {"gear": "Park"})

    def restore(self):
        controls = self.baseline["controls"]
        self.console(
            "/vehicle/controls",
            {
                "speed": controls["speed_kph"],
                "accelerator": controls["accelerator_pct"],
                "brake": controls["brake_pct"],
                "steering": controls["steering_deg"],
            },
        )
        self.console(
            "/vehicle/gear", {"gear": self.baseline["gear"]["actual"]["value"]}
        )
        value = self.console("/vehicle/state")
        self.save("console-restored.json", self.console_evidence(value))
        self.report["restored"] = value["gear"]["actual"]["value"] == self.baseline[
            "gear"
        ]["actual"]["value"] and all(
            value["controls"][key] == controls[key]
            for key in ("speed_kph", "accelerator_pct", "brake_pct", "steering_deg")
        )
        if not self.report["restored"]:
            raise AssertionError("Original Console values were not restored")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--continue-from-background", type=Path)
    args = parser.parse_args()
    if not args.run:
        print(
            json.dumps(
                {
                    "status": "PREVIEW",
                    "component": COMPONENT,
                    "requires": "installed debug APK + active official Virtual Console",
                }
            )
        )
        return
    probe = Probe(continue_background=args.continue_from_background)
    try:
        if args.continue_from_background:
            probe.remaining_cases()
        else:
            probe.cases()
    except Exception as error:
        probe.report["status"] = "FAIL"
        probe.report["error"] = str(error)
        probe.save("failure-state.json", probe.state())
        raise
    finally:
        try:
            probe.restore()
            if (
                probe.original_reduced is not None
                and probe.state().get("reducedMotion") != probe.original_reduced
            ):
                probe.launch(sample="coast-curious", autoPlay=False)
                probe.ready()
                probe.read_buttons()
                probe.tap(
                    "움직임 줄이기: "
                    + ("켜짐" if probe.state().get("reducedMotion") else "꺼짐")
                )
        finally:
            probe.save("report.json", probe.report)
            (OUT / "latest-run.json").write_text(
                json.dumps(
                    {"folder": str(probe.folder), "status": probe.report["status"]},
                    indent=2,
                )
                + "\n"
            )
    print(
        json.dumps(
            {
                "status": probe.report["status"],
                "checks": len(probe.report["checks"]),
                "folder": str(probe.folder),
                "restored": probe.report["restored"],
            }
        )
    )


if __name__ == "__main__":
    main()
