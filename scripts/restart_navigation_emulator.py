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
    args = parser.parse_args()
    if not args.run:
        print(
            json.dumps(
                {"status": "PREVIEW_ONLY", "command": COMMAND, "userdataWiped": False}
            )
        )
        return
    if adb("emu", "avd", "name").stdout.splitlines()[:1] != [AVD]:
        raise ValueError("EXACT_NUNTI_AVD_REQUIRED")
    WORK.mkdir(parents=True, exist_ok=True, mode=0o700)
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
    print(
        "기존 SDK 위치·아바타를 저장했습니다. 같은 AVD를 정상 종료합니다.", flush=True
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
            COMMAND,
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
    (WORK / "restart.json").write_text(
        json.dumps(
            {
                "status": "APP_RETURNED_AFTER_AUTHENTICATED_RESTART",
                "avd": AVD,
                "serial": SERIAL,
                "userdataWiped": False,
                "vehicleHardwarePropertiesChanged": False,
                "fullGpsStateBeforeRestartAvailable": False,
                "videoRecorded": False,
                "speakerRecorded": False,
            },
            indent=2,
        )
        + "\n"
    )
    print("인증된 GPS 조회 준비와 앱 복귀를 완료했습니다.", flush=True)


if __name__ == "__main__":
    main()
