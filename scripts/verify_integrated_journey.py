#!/usr/bin/env python3
"""Verify the real Android journey flow and restore the initial Virtual Console values.

No recording, model generation, app termination, or GPS changes. Without --run,
this command only explains the test. Run after the APK and four feedback voices
have been prepared. A pre-existing active journey is never interrupted.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/integration-2026-11-05"
ADB = ROOT / ".local/pm-tools/sdk/platform-tools/adb"
PACKAGE = "ai.nunti.avatar.demo"
SERIAL = "emulator-5554"
CONSOLE = "http://127.0.0.1:8088"
MAIN = PACKAGE + "/ai.nunti.app.MainActivity"
REPORT = WORK / "runtime-verification.json"
CONTROL_KEYS = {
    "speed": "speed_kph",
    "accelerator": "accelerator_pct",
    "brake": "brake_pct",
    "steering": "steering_deg",
}


class VerificationFailure(RuntimeError):
    pass


class Probe:
    def __init__(self, character_id: str):
        self.character_id = character_id
        self.started = time.monotonic()
        # Leave 30 seconds of the 180-second bound for session cleanup and restoration.
        self.work_deadline = self.started + 150
        self.deadline = self.work_deadline
        self.folder = WORK / "runtime-runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        self.folder.mkdir(parents=True, mode=0o700)
        self.user = ""
        self.baseline: dict | None = None
        self.modified_console = False
        self.owned_ids: set[str] = set()
        self.pending_source: str | None = None
        self.previous_id: str | None = None
        self.log_start_seconds: float | None = None
        self.snapshots: list[dict] = []
        self.report = {
            "status": "RUNNING",
            "characterId": character_id,
            "surface": "ACTUAL_ANDROID_APP_AND_VIRTUAL_CONSOLE",
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "evidenceDirectory": str(self.folder),
            "checks": [],
            "failures": [],
            "restore": {"attempted": False, "matched": None},
            "navigationMapMovement": "NOT_TESTED",
            "audioEvidence": "ANDROID_MEDIA_PLAYER_LOGS_NOT_SPEAKER_RECORDING",
            "videoRecorded": False,
            "speakerRecorded": False,
            "paidApiCalls": 0,
            "newModelGenerations": 0,
        }

    def remaining(self, maximum: float = 10) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise VerificationFailure("검증 제한 시간을 초과했습니다.")
        return max(0.1, min(maximum, remaining))

    def run(self, args: list[str], *, timeout: float = 10, binary=False, check=True):
        result = subprocess.run(
            [str(x) for x in args], cwd=ROOT, capture_output=True,
            text=not binary, timeout=self.remaining(timeout), check=False,
        )
        if check and result.returncode:
            error = result.stderr if not binary else result.stderr.decode(errors="replace")
            raise VerificationFailure(f"명령 실패 ({result.returncode}): {args[0]}: {error[-1000:]}")
        return result

    def adb(self, *args: str, **kwargs):
        return self.run([str(ADB), "-s", SERIAL, *args], **kwargs)

    def save(self, name: str, value):
        path = self.folder / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        return path

    def check(self, name: str, condition: bool, evidence=None):
        self.report["checks"].append({"name": name, "passed": bool(condition), "evidence": evidence})
        if not condition:
            raise VerificationFailure(name)
        print("PASS " + name, flush=True)

    def console(self, path: str, *, values: dict | None = None):
        url = CONSOLE + path
        if values is not None:
            url += "?" + urllib.parse.urlencode(values)
        request = urllib.request.Request(url, method="PUT" if values is not None else "GET")
        with urllib.request.urlopen(request, timeout=self.remaining(4)) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise VerificationFailure("Console 응답이 너무 큽니다.")
            return json.loads(raw) if raw else {}

    def controls(self, *, speed: float, accelerator=0, brake=0, steering=None):
        if steering is None:
            steering = self.baseline["controls"]["steering_deg"]
        self.modified_console = True
        self.console("/vehicle/controls", values={
            "speed": speed, "accelerator": accelerator, "brake": brake, "steering": steering,
        })

    def park(self):
        self.controls(speed=0)
        self.console("/vehicle/gear", values={"gear": "Park"})

    def snapshot(self):
        result = self.adb("exec-out", "run-as", PACKAGE, "--user", self.user,
                          "cat", "files/journeys/latest.json", check=False, timeout=5)
        # adb exec-out can return zero even when the remote cat writes its error to stdout.
        if "No such file" in result.stderr or "No such file" in result.stdout:
            return None
        if result.returncode:
            raise VerificationFailure("앱 여정 기록을 읽지 못했습니다: " + result.stderr[-500:])
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise VerificationFailure("앱 여정 기록이 JSON 객체가 아닙니다.")
        self.snapshots.append(value)
        if (self.pending_source and value.get("characterId") == self.character_id
                and value.get("source") == self.pending_source
                and value.get("sessionId") != self.previous_id):
            self.owned_ids.add(value["sessionId"])
        return value

    def service_running(self):
        raw = self.adb("shell", "dumpsys", "activity", "services", PACKAGE, timeout=5).stdout
        return any("ServiceRecord{" in line and "JourneyService" in line for line in raw.splitlines())

    def wait(self, description, predicate, *, timeout=60, interval=1):
        end = min(time.monotonic() + timeout, self.deadline)
        while time.monotonic() < end:
            value = predicate()
            if value:
                return value
            time.sleep(min(interval, max(0, end - time.monotonic())))
        raise VerificationFailure("시간 초과: " + description)

    def wait_snapshot(self, description, predicate, *, timeout=60, interval=5):
        def observe():
            value = self.snapshot()
            return value if value and predicate(value) else None
        return self.wait(description, observe, timeout=timeout, interval=interval)

    def main_activity(self):
        self.adb("shell", "am", "start", "-W", "--user", self.user,
                 "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER",
                 "-f", "0x10200000", "-n", MAIN, timeout=10)

    def foreground(self, name: str):
        raw = self.adb("shell", "dumpsys", "activity", "activities", timeout=5).stdout
        resumed = [line.strip() for line in raw.splitlines()
                   if "mResumedActivity" in line or "topResumedActivity" in line]
        return any(name in line for line in resumed), resumed

    def ui(self, label: str):
        self.adb("shell", "uiautomator", "dump", "/sdcard/nunti-journey-verification.xml", timeout=8)
        raw = self.adb("shell", "cat", "/sdcard/nunti-journey-verification.xml", timeout=5).stdout
        (self.folder / f"{label}.xml").write_text(raw)
        return ET.fromstring(raw)

    def tap(self, text: str, label: str):
        def find():
            visible, _ = self.foreground("JourneyActivity")
            if not visible:
                return None
            root = self.ui(label)
            for node in root.iter("node"):
                if (node.get("package") == PACKAGE and node.get("text") == text
                        and node.get("enabled") == "true" and node.get("clickable") == "true"):
                    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
                    if match:
                        left, top, right, bottom = map(int, match.groups())
                        if right > left and bottom > top:
                            return ((left + right) // 2, (top + bottom) // 2)
            return None
        x, y = self.wait(text + " 실제 버튼", find, timeout=15, interval=.5)
        self.adb("shell", "input", "tap", str(x), str(y), timeout=5)

    def screenshot(self, label: str):
        png = self.adb("exec-out", "screencap", "-p", binary=True, timeout=5).stdout
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise VerificationFailure("정지 화면을 PNG로 받지 못했습니다.")
        path = self.folder / f"{label}.png"
        path.write_bytes(png)
        return str(path)

    def start(self, source: str):
        previous = self.snapshot()
        self.previous_id = previous.get("sessionId") if previous else None
        self.pending_source = source
        self.main_activity()
        self.wait("생성 화면", lambda: self.foreground("AvatarStudioActivity")[0], timeout=10, interval=.5)
        args = ["node", "scripts/start_journey_verification.mjs", "--character=" + self.character_id]
        if source == "LIVE":
            args.append("--live")
        result = self.run(args, timeout=25)
        (self.folder / f"{source.lower()}-start-button.json").write_text(result.stdout)
        snapshot = self.wait_snapshot(source + " 여정 시작", lambda value:
            value.get("sessionId") in self.owned_ids and value.get("source") == source
            and value.get("state") == "ACTIVE", timeout=25, interval=1)
        self.pending_source = None
        self.save(source.lower() + "-started.json", snapshot)
        self.check(source + " 같은 아바타로 시작", snapshot.get("characterId") == self.character_id,
                   {"sessionId": snapshot["sessionId"], "characterId": snapshot["characterId"]})
        self.check(source + " 주차 승인 상태", snapshot.get("canFinish") is True)
        return snapshot

    def finish(self, snapshot: dict, label: str):
        session_id = snapshot["sessionId"]
        self.main_activity()
        self.wait_snapshot("주차 후 종료 허용", lambda value:
            value.get("sessionId") == session_id and value.get("canFinish") is True,
            timeout=15, interval=1)
        self.tap("여정 마치기", label + "-finish-button")
        final = self.wait_snapshot("최종 리포트 저장", lambda value:
            value.get("sessionId") == session_id and value.get("state") == "FINISHED",
            timeout=10, interval=1)
        self.save(label + "-finished.json", final)
        self.check(label + " 같은 세션 종료·리포트 저장",
                   final.get("characterId") == self.character_id and isinstance(final.get("items"), list),
                   {"sessionId": session_id, "total": final.get("total"), "coverage": final.get("coverage")})
        self.report.setdefault("screenshots", []).append(self.screenshot(label + "-report"))
        self.wait("종료 음성 후 여정 서비스 종료", lambda: not self.service_running(), timeout=15, interval=1)
        return final

    def execute(self):
        self.baseline = self.console("/vehicle/state")
        self.save("console-before.json", self.baseline)
        self.user = self.adb("shell", "am", "get-current-user", timeout=5).stdout.strip()
        self.check("Android 현재 사용자 확인", bool(re.fullmatch(r"\d+", self.user)))
        old = self.snapshot()
        self.check("기존 진행 여정 없음", not (old and old.get("state") == "ACTIVE") and not self.service_running(),
                   {"existingState": old.get("state") if old else None})
        self.check("Console 차량 신호 브리지 준비",
                   self.baseline.get("gear", {}).get("bridge_ready") is True
                   and self.baseline.get("controls", {}).get("emulator_active") is True)
        self.log_start_seconds = float(self.adb("shell", "date", "+%s", timeout=5).stdout.strip())
        self.park()
        demo = self.start("DEMO")
        completed = self.wait_snapshot("시연 480초 전체 입력", lambda value:
            value.get("sessionId") == demo["sessionId"] and value.get("sampleCount", 0) >= 481
            and value.get("elapsedMs", 0) >= 480_000, timeout=60)
        self.check("DEMO 전체 481 표본 평가", completed.get("total") is not None and bool(completed.get("events")),
                   {"sampleCount": completed["sampleCount"], "elapsedMs": completed["elapsedMs"],
                    "total": completed.get("total"), "emotion": completed.get("emotion")})
        self.finish(completed, "demo")

        live = self.start("LIVE")
        self.check("LIVE 새 세션 분리", live["sessionId"] != demo["sessionId"])
        self.console("/vehicle/gear", values={"gear": "Drive"})
        self.controls(speed=30)
        driving_since = time.monotonic()
        live = self.wait_snapshot("Console D·30km/h 실제 수신", lambda value:
            value.get("sessionId") == live["sessionId"] and value.get("gear") == "D"
            and isinstance(value.get("speedKmh"), (int, float))
            and abs(value["speedKmh"] - 30) <= 2 and value.get("canFinish") is False
            and time.monotonic() - driving_since >= 15, timeout=35)
        self.save("live-driving.json", live)
        self.check("LIVE 실제 속도·기어 수신 및 주행 게이트", True,
                   {"speedKmh": live["speedKmh"], "gear": live["gear"], "sampleCount": live["sampleCount"]})
        self.tap("내비 열기", "live-navigation-button")
        def navigation_foreground():
            visible, resumed = self.foreground("ai.umos.maps.android.navigation.app")
            return resumed if visible else None
        nav = self.wait("현대 내비 전면", navigation_foreground, timeout=10, interval=1)
        self.check("내비 화면 전환", True, nav)
        nav_started = time.monotonic()
        before = live["sampleCount"]
        advanced = self.wait_snapshot("내비 전면에서 10초 이상 샘플링", lambda value:
            value.get("sessionId") == live["sessionId"] and value.get("state") == "ACTIVE"
            and time.monotonic() - nav_started >= 10 and value.get("sampleCount", 0) >= before + 5,
            timeout=20)
        self.save("live-navigation-background.json", advanced)
        self.check("내비 전면에서도 같은 여정 기록 유지", True,
                   {"before": before, "after": advanced["sampleCount"], "sessionId": live["sessionId"]})
        self.park()
        parked = self.wait_snapshot("실제 P·정차 수신", lambda value:
            value.get("sessionId") == live["sessionId"] and value.get("gear") == "P"
            and isinstance(value.get("speedKmh"), (int, float)) and abs(value["speedKmh"]) <= .1
            and value.get("canFinish") is True, timeout=15, interval=1)
        final = self.finish(parked, "live")
        self.check("LIVE 수신 표본으로 점수 계산", final.get("total") is not None and final.get("coverage", 0) > 0,
                   {"total": final.get("total"), "coverage": final.get("coverage")})

    def cleanup(self):
        self.deadline = self.started + 180
        try:
            if self.modified_console:
                current = self.snapshot()
                if current and current.get("sessionId") in self.owned_ids and current.get("state") == "ACTIVE":
                    self.park()
                    self.finish(current, "cleanup")
        except Exception as exc:
            self.report["failures"].append("시험 여정 정리 실패: " + str(exc))
        finally:
            if self.modified_console and self.baseline:
                self.report["restore"]["attempted"] = True
                try:
                    original = self.baseline["controls"]
                    gear = self.baseline["gear"]["actual"]["value"]
                    self.controls(speed=0, steering=original["steering_deg"])
                    self.console("/vehicle/gear", values={"gear": gear})
                    self.controls(**{key: original[value] for key, value in CONTROL_KEYS.items()})
                    def restored():
                        value = self.console("/vehicle/state")
                        equal = value["gear"]["actual"]["value"] == gear and all(
                            math.isclose(float(value["controls"][field]), float(original[field]), abs_tol=.01)
                            for field in CONTROL_KEYS.values())
                        return value if equal else None
                    observed = self.wait("Console 초기값 복원", restored, timeout=5, interval=.5)
                    self.save("console-restored.json", observed)
                    self.report["restore"].update(matched=True, gear=gear,
                        controls={field: original[field] for field in CONTROL_KEYS.values()})
                except Exception as exc:
                    self.report["restore"].update(matched=False, error=str(exc))
                    self.report["failures"].append("Console 원복 실패: " + str(exc))

    def collect_logs(self):
        if self.log_start_seconds is None:
            return
        raw = self.adb("logcat", "-d", "-v", "epoch", "NuntiJourney:I", "*:S", timeout=5).stdout
        lines = []
        for line in raw.splitlines():
            match = re.match(r"\s*(\d+\.\d+)\s", line)
            if match and float(match.group(1)) >= self.log_start_seconds:
                lines.append(line)
        (self.folder / "journey-logcat.txt").write_text("\n".join(lines) + "\n")
        started = [line for line in lines if "JOURNEY_VOICE_STARTED" in line and self.character_id in line]
        completed = [line for line in lines if "JOURNEY_VOICE_COMPLETED" in line]
        starts_by_kind = sorted({re.search(r"kind=(\w+)", line).group(1) for line in started})
        completed_by_kind = sorted({re.search(r"kind=(\w+)", line).group(1) for line in completed})
        self.report["voicePlayback"] = {"startedKinds": starts_by_kind, "completedKinds": completed_by_kind,
                                         "startedCount": len(started), "completedCount": len(completed)}
        self.check("선택한 아바타의 감정 음원 실제 재생", bool(set(starts_by_kind) & {"WORRY", "RELIEF", "JOY"})
                   and bool(set(completed_by_kind) & {"WORRY", "RELIEF", "JOY"}), self.report["voicePlayback"])

    def write_report(self):
        self.report["elapsedSeconds"] = round(time.monotonic() - self.started, 2)
        self.report["sessionIds"] = sorted(self.owned_ids)
        self.report["status"] = "PASS" if not self.report["failures"] else "FAIL"
        self.save("observed-snapshots.json", self.snapshots)
        self.save("runtime-verification.json", self.report)
        REPORT.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"status": self.report["status"], "checks": len(self.report["checks"]),
                          "report": str(REPORT), "restored": self.report["restore"]["matched"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="실제 앱과 Console 값을 조작해 검증")
    parser.add_argument("--character", help="이미 보관한 아바타 ID. 생략하면 selected-avatar.json 사용")
    args = parser.parse_args()
    if not args.run:
        print("실행 대기: python3 scripts/verify_integrated_journey.py --run\n"
              "준비된 APK·서버·감정 음원으로 시연 → 실시간 Console → 내비 전면 → 종료 리포트를 시험합니다.\n"
              "기존 진행 여정이 있으면 중단합니다. 시험 뒤 Console 초기값을 복원하며 녹화·합성·앱 종료는 하지 않습니다.")
        return 0
    character_id = args.character
    if character_id is None:
        character_id = json.loads((WORK / "selected-avatar.json").read_text())["characterId"]
    if not re.fullmatch(r"nunti-[0-9a-f-]{36}", character_id):
        parser.error("올바른 저장 아바타 ID가 필요합니다.")
    probe = Probe(character_id)
    try:
        probe.execute()
    except (Exception, KeyboardInterrupt) as exc:
        probe.report["failures"].append(str(exc) or "사용자 중단")
    finally:
        probe.cleanup()
        try:
            probe.collect_logs()
        except Exception as exc:
            probe.report["failures"].append("음성 재생 로그 검증: " + str(exc))
        probe.write_report()
    return 0 if probe.report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
