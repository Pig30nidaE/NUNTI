#!/usr/bin/env python3
"""Start the avatar generator with Python 3.9+ and a separate Python 3.12-3.14 backend."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/avatar-generator"
BASE = "http://127.0.0.1:8768"
PACKAGE = "ai.nunti.avatar.demo"
AVD = "Nunti_Restore_2_1"
from local_tools import ADB, SDK, avd_name, emulator_env, gradle_env, gradle_flags

APK = WORK / "Nunti-Avatar-Generator-debug.apk"
ENV_FILES = (ROOT / ".env.local", ROOT / ".env", ROOT / "backend/.env")


def env_file_value(name: str) -> str | None:
    """Read one value from the project's dotenv files without printing it."""
    val = os.getenv(name, "").strip()
    if val:
        return val
    for path in ENV_FILES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                if value:
                    return value
    return None


def run(arguments, **kwargs):
    return subprocess.run([str(x) for x in arguments], check=True, **kwargs)


def private_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    fd = os.open(pending, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    pending.replace(path)
    path.chmod(0o600)


def config() -> dict:
    path = WORK / "connection.json"
    if path.is_file():
        value = json.loads(path.read_text())
        if value.get("baseUrl") != BASE or len(value.get("token", "")) < 32:
            raise RuntimeError("기존 로컬 연결 파일이 올바르지 않습니다.")
        return value
    value = {"baseUrl": BASE, "token": secrets.token_urlsafe(36)}
    private_json(path, value)
    return value


def runtime() -> Path:
    for path in (
        ROOT / "backend/.venv/bin/python",
        ROOT / ".worktrees/server/backend/.venv/bin/python",
    ):
        if (
            path.is_file()
            and subprocess.run(
                [
                    str(path),
                    "-c",
                    (
                        "import sys\n"
                        "if not (3, 12) <= sys.version_info[:2] < (3, 15):\n"
                        "    raise SystemExit(1)\n"
                        "import fastapi, pydantic, uvicorn, PIL\n"
                    ),
                ],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        ):
            return path
    raise RuntimeError(
        "backend의 Python 3.12-3.14 가상환경(fastapi, pydantic, uvicorn, Pillow)이 필요합니다. "
        "cd backend && uv sync --frozen 으로 준비해 주세요."
    )


def request(configuration: dict, path: str):
    req = urllib.request.Request(
        BASE + path, headers={"Authorization": "Bearer " + configuration["token"]}
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.loads(response.read(1_048_576)).get("data")


def stop():
    pids: set[int] = set()
    path = WORK / "server.pid"
    if path.is_file():
        try:
            pids.add(int(path.read_text().strip()))
        except ValueError:
            pass
    try:
        out = subprocess.run(
            ["lsof", "-ti", "tcp:8768", "-sTCP:LISTEN"],
            text=True,
            capture_output=True,
            check=False,
        ).stdout
        for line in out.splitlines():
            if line.strip().isdigit():
                pids.add(int(line.strip()))
    except OSError:
        pass
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(40):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    path.unlink(missing_ok=True)


def server(configuration: dict) -> dict:
    api_key = env_file_value("OPENAI_API_KEY")
    chat_key = env_file_value("NUNTI_STUDIO_CHAT_API_KEY") or api_key
    try:
        current = request(configuration, "/v3/capabilities")
        if bool(api_key) and not current.get("wardrobeAvailable"):
            stop()
        else:
            return current
    except urllib.error.HTTPError:
        stop()
    except (urllib.error.URLError, TimeoutError):
        pass

    env = dict(
        os.environ,
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONUNBUFFERED="1",
        NUNTI_STUDIO_TOKEN=configuration["token"],
        NUNTI_STUDIO_WORKSPACE=str(WORK),
        NUNTI_STUDIO_PAID_API_APPROVED="true",
        NUNTI_STUDIO_WARDROBE_ENABLED="true",
        NUNTI_STUDIO_ROUTE_API_ENABLED="true",
        NUNTI_STUDIO_CHAT_API_ENABLED="true",
    )
    if api_key:
        env["OPENAI_API_KEY"] = api_key
    else:
        print(
            "안내: .env 파일에 OPENAI_API_KEY가 설정되어 있지 않습니다. 키를 설정한 뒤 실행해 주세요."
        )
    if chat_key:
        env["NUNTI_STUDIO_CHAT_API_KEY"] = chat_key

    with (WORK / "server.log").open("ab") as log:
        process = subprocess.Popen(
            [
                str(runtime()),
                "-m",
                "uvicorn",
                "nunti.avatar_studio.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8768",
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (WORK / "server.pid").write_text(str(process.pid) + "\n")
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError(
                "생성기가 종료됐습니다. .local/avatar-generator/server.log를 확인해 주세요."
            )
        try:
            return request(configuration, "/v3/capabilities")
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("로컬 생성기의 시작 시간이 초과됐습니다.")


def emulator() -> str:
    result = run([ADB, "devices"], text=True, capture_output=True).stdout
    devices = [
        line.split()[0] for line in result.splitlines()[1:] if len(line.split()) >= 2
    ]
    for serial in devices:
        if serial.startswith("emulator-"):
            name = run(
                [ADB, "-s", serial, "emu", "avd", "name"],
                text=True,
                capture_output=True,
            ).stdout
            if name.splitlines()[:1] == [AVD]:
                return serial
    running = [s for s in devices if s.startswith("emulator-")]
    if running:
        return running[0]
    port = next(p for p in range(5554, 5585, 2) if f"emulator-{p}" not in devices)
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / "launcher-emulator.log").open("ab") as log:
        subprocess.Popen(
            [
                str(SDK / "emulator/emulator"),
                "-avd",
                avd_name(AVD),
                "-port",
                str(port),
                "-no-snapshot-load",
                "-no-snapshot-save",
                "-no-boot-anim",
                "-memory",
                "8192",
                "-cores",
                "4",
            ],
            env=emulator_env(),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return f"emulator-{port}"


def build():
    env = gradle_env()
    with (WORK / "build.log").open("w") as log:
        run(
            [
                ROOT / "android/gradlew",
                *gradle_flags(),
                ":app:assembleDebug",
                ":app:assembleRelease",
                ":app:lintDebug",
            ],
            cwd=ROOT / "android",
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    shutil.copy2(ROOT / "android/build/app/outputs/apk/debug/app-debug.apk", APK)
    shutil.copy2(
        ROOT / "android/build/app/outputs/apk/release/app-release-unsigned.apk",
        WORK / "Nunti-Avatar-Generator-release-unsigned.apk",
    )


def apk_stale() -> bool:
    if not APK.is_file():
        return True
    apk_mtime = APK.stat().st_mtime
    for folder in (ROOT / "android/app/src", ROOT / "prototypes/avatar_generator"):
        for path in folder.rglob("*"):
            if path.is_file() and path.stat().st_mtime > apk_mtime:
                return True
    return False


def android(configuration: dict) -> dict:
    if apk_stale():
        print("변경된 코드를 반영하여 Android APK를 새로 빌드합니다…")
        build()
    serial = emulator()
    adb = [ADB, "-s", serial]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = subprocess.run(
            [str(x) for x in adb + ["shell", "getprop", "sys.boot_completed"]],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            break
        time.sleep(1)
    else:
        raise RuntimeError("Pleos 에뮬레이터 부팅이 완료되지 않았습니다.")
    user = run(
        adb + ["shell", "am", "get-current-user"], capture_output=True, text=True
    ).stdout.strip()
    if not user.isdigit():
        raise RuntimeError("Android 사용자를 확인하지 못했습니다.")
    run(adb + ["reverse", "tcp:8768", "tcp:8768"], capture_output=True)
    run(adb + ["forward", "tcp:8088", "tcp:8088"], capture_output=True)
    run(adb + ["install", "-r", "-g", "--user", user, APK], capture_output=True)
    command = f"run-as {PACKAGE} --user {user} sh -c " + shlex.quote(
        "umask 077; mkdir -p files; cat > files/avatar-studio-connection.json"
    )
    run(
        adb + ["shell", command],
        input=json.dumps(configuration).encode(),
        capture_output=True,
    )
    run(
        adb + ["shell", "am", "force-stop", "--user", user, PACKAGE],
        capture_output=True,
    )
    run(
        adb
        + [
            "shell",
            "am",
            "start",
            "-W",
            "--user",
            user,
            "-n",
            PACKAGE + "/ai.nunti.app.MainActivity",
        ],
        capture_output=True,
    )
    return {
        "serial": serial,
        "androidUser": int(user),
        "apk": str(APK),
        "sha256": hashlib.sha256(APK.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument(
        "--browser", action="store_true", help="Android 대신 브라우저를 엽니다."
    )
    parser.add_argument("--server-only", action="store_true")
    parser.add_argument("--restart-server", action="store_true")
    parser.add_argument(
        "--paid-api",
        action="store_true",
        default=True,
        help="OpenAI API 연결 (기본 활성)",
    )
    parser.add_argument(
        "--navigation-api",
        action="store_true",
        default=True,
        help="경로 API 연결 (기본 활성)",
    )
    parser.add_argument(
        "--cloud-chat",
        action="store_true",
        default=True,
        help="대화 API 연결 (기본 활성)",
    )
    parser.add_argument("--stop", action="store_true")
    parser.add_argument(
        "--show-code", action="store_true", help="브라우저 로그인용 로컬 연결 코드 표시"
    )
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    if args.stop:
        stop()
        print("로컬 눈티 생성기를 종료했습니다.")
        return
    configuration = config()
    if args.show_code:
        print(configuration["token"])
        return
    if args.build:
        build()
    if args.restart_server:
        stop()
    caps = server(configuration)
    if args.browser:
        webbrowser.open(BASE)
        print("눈티 생성기: " + BASE)
        print(
            "최초 연결 코드는 python3 scripts/run_avatar_generator.py --show-code 로 확인하세요."
        )
    elif not args.server_only:
        proof = android(configuration)
        proof.update(baseUrl=BASE, mode=caps.get("mode"), mediaCaptured=False)
        private_json(WORK / "delivery.json", proof)
        print("눈티 아바타 생성기를 실제 Android 앱에서 열었습니다.")
    else:
        print("눈티 생성기 준비 완료: " + BASE)
    if caps.get("wardrobeAvailable"):
        print("OpenAI 이미지 생성(Wardrobe API) 연결됨")
    if caps.get("conversationAvailable"):
        print("OpenAI 눈티 대화 API 연결됨")
    if caps.get("routeApiAvailable"):
        print("경로 API 연결됨")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print("실행 실패: " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
