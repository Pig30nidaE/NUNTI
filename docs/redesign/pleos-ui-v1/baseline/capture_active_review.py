"""Capture a silent review journey using a saved image and restore persisted state.

Requires the connected emulator, existing offline Studio, and the exact original
latest.json backup alongside this file. It never generates images or audio.
"""

import hashlib
import json
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
ADB = ROOT / ".local/pm-tools/sdk/platform-tools/adb"
PACKAGE = "ai.nunti.avatar.demo"
USER = "10"
CHARACTER = "nunti-bb48e374-03bd-4b14-b34c-733cc93f395b"


def adb(*args, binary=False, input_bytes=None):
    result = subprocess.run(
        [str(ADB), "-s", "emulator-5554", *map(str, args)],
        input=input_bytes,
        capture_output=True,
        check=True,
        timeout=15,
    )
    return result.stdout if binary else result.stdout.decode()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def state():
    return json.loads(
        adb(
            "exec-out",
            "run-as",
            PACKAGE,
            "--user",
            USER,
            "cat",
            "files/journeys/latest.json",
        )
    )


def wait(predicate, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = state()
        if predicate(value):
            return value
        time.sleep(0.25)
    raise RuntimeError("Journey state timeout")


def ui(name):
    adb("shell", "uiautomator", "dump", "/sdcard/nunti-ui-baseline.xml")
    raw = adb("shell", "cat", "/sdcard/nunti-ui-baseline.xml")
    (OUT / (name + ".xml")).write_text(raw)
    return ET.fromstring(raw)


def tap(text, name):
    for node in ui(name).iter("node"):
        if node.get("text") == text and node.get("enabled") == "true":
            bounds = re.fullmatch(
                r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", "")
            )
            if bounds:
                left, top, right, bottom = map(int, bounds.groups())
                adb("shell", "input", "tap", (left + right) // 2, (top + bottom) // 2)
                return
    raise RuntimeError("Button missing: " + text)


def capture(name):
    # Vehicle gate changes precede the visible compositor transition.
    ui(name)
    time.sleep(1.2)
    (OUT / (name + ".png")).write_bytes(adb("exec-out", "screencap", "-p", binary=True))
    save(name + ".json", state())
    (OUT / (name + "-activity.txt")).write_text(
        adb("shell", "dumpsys", "activity", "activities")
    )
    (OUT / (name + "-car-ux.txt")).write_text(
        adb(
            "shell",
            "dumpsys",
            "car_service",
            "--services",
            "CarUxRestrictionsManagerService",
        )
    )


def console(path, values=None, method=None):
    url = "http://127.0.0.1:8088" + path
    if values:
        url += "?" + urllib.parse.urlencode(values)
    request = urllib.request.Request(url, method=method or ("PUT" if values else "GET"))
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


original = (OUT / "existing-last-journey-original.json").read_bytes()
assert state()["state"] != "ACTIVE", "Preserve any pre-existing active journey"
assert json.loads(original)["sessionId"] == state()["sessionId"]
baseline = console("/vehicle/state")
client = "nunti-ui-active-" + str(uuid.uuid4())
stop = threading.Event()
owned = None


def heartbeat():
    while not stop.is_set():
        try:
            console("/browser/session", {"client": client}, "POST")
        except OSError:
            pass
        stop.wait(1)


thread = threading.Thread(target=heartbeat)
thread.start()
try:
    for _ in range(50):
        if console("/vehicle/state")["gear"]["bridge_ready"]:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError("Console DDS unavailable")
    adb(
        "shell",
        "am",
        "start",
        "-W",
        "--user",
        USER,
        "-n",
        PACKAGE + "/ai.nunti.app.MainActivity",
    )
    subprocess.run(
        [
            "node",
            "scripts/start_journey_verification.mjs",
            "--character=" + CHARACTER,
            "--live",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
        timeout=30,
    )
    started = wait(
        lambda s: s.get("state") == "ACTIVE" and s.get("characterId") == CHARACTER
    )
    owned = started["sessionId"]
    assert started.get("voices") == {}, (
        "This review must have no playable greeting or feedback audio"
    )
    tap("음성 끄기", "review-mute-control")
    wait(lambda s: s.get("muted") is True)
    capture("production-active-parked")
    console(
        "/vehicle/controls", {"speed": 30, "accelerator": 0, "brake": 0, "steering": 0}
    )
    console("/vehicle/gear", {"gear": "Drive"})
    wait(
        lambda s: (
            s.get("gear") == "D"
            and s.get("speedKmh", 0) >= 29
            and not s.get("canFinish")
        )
    )
    capture("production-driving-active")
    console(
        "/vehicle/controls", {"speed": 0, "accelerator": 0, "brake": 0, "steering": 0}
    )
    console("/vehicle/gear", {"gear": "Park"})
    wait(lambda s: s.get("canFinish") is True)
    tap("여정 마치기", "review-finish-control")
    wait(lambda s: s.get("state") == "FINISHED")
    capture("production-post-trip-review")
finally:
    controls = baseline["controls"]
    console(
        "/vehicle/controls",
        {
            "speed": controls["speed_kph"],
            "accelerator": controls["accelerator_pct"],
            "brake": controls["brake_pct"],
            "steering": controls["steering_deg"],
        },
    )
    console("/vehicle/gear", {"gear": baseline["gear"]["actual"]["value"]})
    # The official Console activation can also reset climate power.
    console("/vehicle/hvac", {"power": int(baseline["hvac"]["power_on"])})
    current = state()
    if owned and current.get("sessionId") == owned and current.get("state") == "ACTIVE":
        wait(lambda s: s.get("canFinish") is True)
        tap("여정 마치기", "review-cleanup-finish-control")
        wait(lambda s: s.get("state") == "FINISHED")
    if owned:
        save("review-session-final.json", state())
        # This test owned the sole active session and has finished it. Clear only
        # app memory so JourneyRuntime.current cannot shadow the restored report.
        adb("shell", "am", "force-stop", "--user", USER, PACKAGE)
        adb(
            "exec-in",
            "run-as",
            PACKAGE,
            "--user",
            USER,
            "sh",
            "-c",
            "cat > files/journeys/latest.json",
            input_bytes=original,
        )
    restored = adb(
        "exec-out",
        "run-as",
        PACKAGE,
        "--user",
        USER,
        "cat",
        "files/journeys/latest.json",
        binary=True,
    )
    assert restored == original
    time.sleep(0.5)
    stop.set()
    thread.join()
    console("/browser/session", {"client": client, "closing": 1}, "POST")
    after = console("/vehicle/state")
    save(
        "active-review-restoration.json",
        {
            "reviewSessionId": owned,
            "latestBytesRestored": restored == original,
            "latestSha256": hashlib.sha256(restored).hexdigest(),
            "gear": after["gear"]["actual"]["value"],
            "controls": {
                key: after["controls"][key]
                for key in ("speed_kph", "accelerator_pct", "brake_pct", "steering_deg")
            },
            "browser": after["browser"],
            "hvacPowerRestored": after["hvac"]["power_on"]
            == baseline["hvac"]["power_on"],
            "paidApiCalls": 0,
            "modelGenerations": 0,
        },
    )
    adb(
        "shell",
        "am",
        "start",
        "-W",
        "--user",
        USER,
        "-n",
        PACKAGE + "/ai.nunti.app.transformation.TransformationPreviewActivity",
        "--es",
        "sample",
        "coast-curious",
        "--es",
        "style",
        "LIGHT_TRAIL",
        "--es",
        "displayMode",
        "day",
        "--el",
        "seekMs",
        "4000",
        "--ez",
        "readOnlyCapture",
        "false",
        "--ez",
        "autoPlay",
        "false",
    )
    print(
        json.dumps(
            {
                "reviewSessionId": owned,
                "latestRestored": True,
                "gear": after["gear"]["actual"]["value"],
            }
        )
    )
