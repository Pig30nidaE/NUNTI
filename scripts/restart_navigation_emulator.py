#!/usr/bin/env python3
"""Restart the existing Nunti AVD with authenticated local GPS control.

The default only prints the intended command. --run gracefully restarts this
specific AVD, keeps userdata, and returns through the existing app launcher.
"""

import argparse
import json
import os
import subprocess
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / ".local/pm-tools/sdk"
ADB = SDK / "platform-tools/adb"
SERIAL = "emulator-5554"
AVD = "Nunti_Restore_2_1"
WORK = ROOT / ".local/navigation-integration/replay/authenticated-restart"
COMMAND = [
    str(SDK / "emulator/emulator"),
    "-avd",
    AVD,
    "-port",
    "5554",
    "-no-snapshot-load",
    "-no-snapshot-save",
    "-no-boot-anim",
    "-memory",
    "4096",
    "-grpc",
    "8554",
    "-grpc-use-token",
]


def adb(*arguments, timeout=10, check=True):
    return subprocess.run(
        [str(ADB), "-s", SERIAL, *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--navigation-only", action="store_true", help="기존 내비·GPS 진단만 저장하고 내비 화면으로 복귀")
    args = parser.parse_args()
    if not args.run:
        print(
            json.dumps(
                {"status": "PREVIEW_ONLY", "command": COMMAND + (["-no-passive-gps"] if args.navigation_only else []), "userdataWiped": False}
            )
        )
        return
    if adb("emu", "avd", "name").stdout.splitlines()[:1] != [AVD]:
        raise ValueError("EXACT_NUNTI_AVD_REQUIRED")
    WORK.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.navigation_only:
        (WORK / "android-location-before.txt").write_text(adb("shell", "dumpsys", "location").stdout)
        (WORK / "native-activity-before.txt").write_text(adb("shell", "dumpsys", "activity", "activities").stdout)
        with urllib.request.urlopen("http://127.0.0.1:8088/vehicle/state", timeout=4) as response:
            original_console = json.load(response)
        (WORK / "console-before.json").write_text(json.dumps(original_console))
    else:
        capture_native_before()
    restart(args.navigation_only, original_console if args.navigation_only else None)


def capture_native_before():
    before = subprocess.run(
        [
            "node",
            str(ROOT / "scripts/navigation_native_command.mjs"),
            "--command=refresh",
            "--wait-ms=5000",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=40,
    )
    (WORK / "native-before-restart.json").write_bytes(before.stdout)
    if json.loads(before.stdout)["snapshot"].get("connected") is not True:
        raise ValueError("CONNECTED_NATIVE_BASELINE_REQUIRED")


def restart(navigation_only, original_console):
    print(
        "현재 위치 진단을 저장했습니다. 같은 AVD를 정상 종료합니다.", flush=True
    )
    adb("emu", "kill")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        devices = subprocess.run(
            [str(ADB), "devices"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
        if SERIAL + "\t" not in devices:
            break
        time.sleep(0.5)
    else:
        raise ValueError("EMULATOR_GRACEFUL_SHUTDOWN_NOT_CONFIRMED")
    environment = dict(
        os.environ,
        ANDROID_HOME=str(SDK),
        ANDROID_USER_HOME=str(ROOT / ".local/pm-tools/android-user"),
        ANDROID_AVD_HOME=str(ROOT / ".local/pm-tools/avd"),
    )
    with (WORK / "emulator.log").open("ab") as log:
        process = subprocess.Popen(
            COMMAND + (["-no-passive-gps"] if navigation_only else []),
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print("토큰 인증을 켜고 기존 userdata로 부팅합니다.", flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("EMULATOR_EXITED_DURING_BOOT")
        boot = adb("shell", "getprop", "sys.boot_completed", timeout=5, check=False)
        if boot.returncode == 0 and boot.stdout.strip() == "1":
            break
        time.sleep(1)
    else:
        raise ValueError("EMULATOR_BOOT_TIMEOUT")
    if navigation_only:
        adb("forward", "tcp:8088", "tcp:8088")
        adb("reverse", "tcp:8768", "tcp:8768")
        # Reconnect only after the official console reports that the DDS bridge is ready.
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8088/vehicle/state", timeout=3) as response:
                    state = json.load(response)
                if state.get("gear", {}).get("bridge_ready"): break
            except (OSError, ValueError): pass
            time.sleep(1)
        else:
            (WORK / "restart.json").write_text(json.dumps({"status":"RESTARTED_DDS_NOT_READY", "userdataWiped":False}))
            raise ValueError("RESTARTED_DDS_NOT_READY")
        controls = original_console["controls"]
        values = {"speed":controls["speed_kph"], "accelerator":controls["accelerator_pct"], "brake":controls["brake_pct"], "steering":controls["steering_deg"]}
        restore_errors = []
        for endpoint, params in [("gear", {"gear": original_console["gear"]["actual"]["value"]}), ("controls", values)]:
            try:
                request = urllib.request.Request("http://127.0.0.1:8088/vehicle/"+endpoint+"?"+urllib.parse.urlencode(params), method="PUT")
                with urllib.request.urlopen(request, timeout=4) as response: response.read()
            except (OSError, ValueError) as error:
                restore_errors.append(endpoint + ": " + str(error))
        console_restored = False
        try:
            with urllib.request.urlopen("http://127.0.0.1:8088/vehicle/state", timeout=4) as response:
                restored = json.load(response)
            (WORK / "console-restored.json").write_text(json.dumps(restored))
            console_restored = restored["gear"]["actual"]["value"] == original_console["gear"]["actual"]["value"] and all(
                restored["controls"][key] == controls[key] for key in ("speed_kph", "accelerator_pct", "brake_pct", "steering_deg")
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            restore_errors.append("readback: " + str(error))
        (WORK / "console-restoration.json").write_text(json.dumps({"restored":console_restored,"errors":restore_errors}))
        if not console_restored:
            (WORK / "restart.json").write_text(json.dumps({"status":"RESTARTED_CONSOLE_RESTORE_UNCONFIRMED", "userdataWiped":False,"restoreErrors":restore_errors}))
            raise ValueError("RESTARTED_CONSOLE_RESTORE_UNCONFIRMED")
        user = adb("shell", "am", "get-current-user").stdout.strip()
        adb("shell", "am", "start", "-W", "--user", user, "-n", "ai.umos.maps.android.navigation.app/.MainActivity")
    else:
        return_to_nunti()
    (WORK / "restart.json").write_text(json.dumps({"status":"AUTHENTICATED_RESTART_COMPLETED", "navigationOnly":navigation_only,
        "avd":AVD,"serial":SERIAL,"passiveGpsDisabledAtStartup":navigation_only,
        "userdataWiped":False,"videoRecorded":False,"speakerRecorded":False}, indent=2))
    print("인증된 GPS 조회 준비와 앱 복귀를 완료했습니다.", flush=True)


def return_to_nunti():
    subprocess.run(
        [
            "python3",
            str(ROOT / "scripts/run_avatar_generator.py"),
            "--local-ai",
            "--navigation-api",
        ],
        cwd=ROOT,
        check=True,
        timeout=90,
    )


if __name__ == "__main__":
    main()
