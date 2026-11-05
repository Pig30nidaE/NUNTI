#!/usr/bin/env python3
"""Build/install/open the offline Nunti MVP with existing local tools. Never clears app data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/journey-mvp"
SDK = ROOT / ".local/pm-tools/sdk"
ADB = SDK / "platform-tools/adb"
APK = WORK / "Nunti-Journey-MVP-debug.apk"
PACKAGE = "ai.nunti.avatar.demo"
ACTIVITY = PACKAGE + "/ai.nunti.app.journey.JourneyMvpActivity"
AVD = "Nunti_Restore_2_1"


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_apk_assets(apk, bundle):
    with zipfile.ZipFile(apk) as archive:
        expected = {"assets/journey-mvp/" + str(p.relative_to(bundle)): p for p in bundle.rglob("*") if p.is_file()}
        actual = {name for name in archive.namelist() if name.startswith("assets/journey-mvp/")}
        if actual != set(expected) or any(archive.read(name) != path.read_bytes() for name, path in expected.items()):
            raise ValueError("APK와 현재 생성 번들이 다릅니다. --build로 다시 빌드하세요.")


def build(bundle):
    destination = ROOT / "android/app/src/debug/assets/journey-mvp"
    if destination.exists():
        old = json.loads((destination / "bundle.json").read_text())
        current = {item["characterId"]: item for item in json.loads((bundle / "bundle.json").read_text())["characters"]}
        if any(current.get(item["characterId"]) != item for item in old["characters"]):
            raise ValueError("기존 앱 캐릭터를 변경하거나 제거하는 번들은 전달하지 않습니다.")
    shutil.copytree(bundle, destination, dirs_exist_ok=True)
    env = dict(os.environ, JAVA_HOME=str(ROOT / ".local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home"),
        ANDROID_HOME=str(SDK), ANDROID_USER_HOME=str(ROOT / ".worktrees/tts/.local/android-user"),
        GRADLE_USER_HOME=str(ROOT / ".worktrees/tts/.local/gradle-user"))
    print("기존 로컬 도구로 Debug 앱을 오프라인 빌드합니다.", flush=True)
    with (WORK / "launcher-build.log").open("w") as log:
        run([ROOT / "android/gradlew", "--offline", "--no-daemon", ":app:assembleDebug"], cwd=ROOT / "android", env=env, stdout=log, stderr=subprocess.STDOUT)
    built = ROOT / "android/build/app/outputs/apk/debug/app-debug.apk"
    verify_apk_assets(built, bundle)
    shutil.copy2(built, APK)
    (WORK / "delivered-apk.json").write_text(json.dumps({"apk": str(APK), "sha256": sha(APK),
        "bundleId": json.loads((bundle / "bundle.json").read_text())["bundleId"]}, ensure_ascii=False, indent=2) + "\n")


def find_emulator():
    result = run([ADB, "devices"], capture_output=True, text=True).stdout
    devices = [line.split()[0] for line in result.splitlines()[1:] if len(line.split()) >= 2]
    for serial in devices:
        if not serial.startswith("emulator-"):
            continue
        name = subprocess.run([str(ADB), "-s", serial, "emu", "avd", "name"], capture_output=True, text=True)
        if name.returncode == 0 and name.stdout.splitlines()[:1] == [AVD]:
            return serial
    port = next(port for port in range(5554, 5585, 2) if "emulator-" + str(port) not in devices)
    env = dict(os.environ, ANDROID_HOME=str(SDK), ANDROID_USER_HOME=str(ROOT / ".local/pm-tools/android-user"),
        ANDROID_AVD_HOME=str(ROOT / ".local/pm-tools/avd"))
    with (WORK / "launcher-emulator.log").open("a") as log:
        subprocess.Popen([str(SDK / "emulator/emulator"), "-avd", AVD, "-port", str(port),
            "-no-snapshot-load", "-no-snapshot-save", "-no-boot-anim", "-memory", "4096"], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return "emulator-" + str(port)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="기존 로컬 의존성으로 APK 재빌드")
    parser.add_argument("--input", type=Path, help="새 여정 JSON을 로컬에서 실제 생성하고 APK 갱신")
    parser.add_argument("--label")
    parser.add_argument("--summary")
    parser.add_argument("--check", action="store_true", help="APK/번들 정합성만 검사하고 실행하지 않음")
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    bundle = WORK / "bundle"
    if args.input:
        command = [ROOT / ".local/journey-voice-v3/venv/bin/python", ROOT / "prototypes/journey_mvp/worker.py", "generate", "--input", args.input.resolve()]
        if args.label:
            command += ["--label", args.label]
        if args.summary:
            command += ["--summary", args.summary]
        print("새 여정을 기존 로컬 모델로 생성합니다. API와 계정을 사용하지 않습니다.", flush=True)
        run(command, cwd=ROOT)
    if not bundle.is_dir():
        raise ValueError("생성 번들이 없습니다. prototypes/journey_mvp/README.md의 worker 초기 생성을 실행하세요.")
    if args.build or args.input or not APK.exists():
        build(bundle)
    verify_apk_assets(APK, bundle)
    print("APK와 생성 번들의 모든 파일이 일치합니다.", flush=True)
    if args.check:
        return 0
    if not ADB.is_file():
        raise ValueError("이 로컬의 Android 도구를 찾지 못했습니다. 설치나 다운로드를 자동 실행하지 않습니다.")
    serial = find_emulator()
    print("기존 Pleos 에뮬레이터 부팅을 기다립니다.", flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        ready = subprocess.run([str(ADB), "-s", serial, "shell", "getprop", "sys.boot_completed"], capture_output=True, text=True)
        if ready.returncode == 0 and ready.stdout.strip() == "1":
            break
        time.sleep(2)
    else:
        raise TimeoutError("에뮬레이터 부팅이 완료되지 않았습니다. launcher-emulator.log를 확인하세요.")
    user = run([ADB, "-s", serial, "shell", "am", "get-current-user"], capture_output=True, text=True).stdout.strip()
    if not user.isdigit():
        raise ValueError("에뮬레이터의 현재 사용자를 확인하지 못했습니다.")
    run([ADB, "-s", serial, "install", "-r", "--user", user, APK])
    run([ADB, "-s", serial, "shell", "am", "force-stop", "--user", user, PACKAGE])
    run([ADB, "-s", serial, "shell", "am", "start", "--user", user, "-W", "-n", ACTIVITY])
    print("\nNunti 여정 MVP가 열렸습니다.\n여행 선택 → 음성 시험 시작 → 인사 듣기 → 도착했어요 → 도착 대사 → 동반자 보관 순서로 시험하세요.\n차량이 P이고 속도가 0일 때만 화면과 음성이 허용됩니다. 앱을 다시 열어 보관과 같은 동반자가 유지되는지도 확인하세요.\n기존 앱 데이터는 삭제하지 않았습니다.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TimeoutError, subprocess.CalledProcessError) as error:
        print("실행 실패: " + str(error), file=sys.stderr)
        raise SystemExit(1)
