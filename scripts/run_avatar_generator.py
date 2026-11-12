#!/usr/bin/env python3
"""Start the destination/route avatar generator and its actual parked Android host."""

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
from local_tools import ADB, SDK, gradle_env, gradle_flags  # noqa: E402  (이 컴퓨터의 JDK·SDK를 찾는다)
APK = WORK / "Nunti-Avatar-Generator-debug.apk"
LOCAL_AI = ROOT / ".local/avatar-quality-v4/local-image"


ENV_FILES = (ROOT / ".env.local", ROOT / ".env")  # 앞의 파일이 우선한다. 둘 다 git 에 올리지 않는다.


def env_file_value(name):
    """Read one value from the project's dotenv files without printing it."""
    for path in ENV_FILES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
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


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(
        path.with_suffix(".pending"), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600
    )
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    path.with_suffix(".pending").replace(path)
    path.chmod(0o600)


def config():
    path = WORK / "connection.json"
    if path.is_file():
        value = json.loads(path.read_text())
        if value.get("baseUrl") != BASE or len(value.get("token", "")) < 32:
            raise RuntimeError("기존 로컬 연결 파일이 올바르지 않습니다.")
        return value
    value = {"baseUrl": BASE, "token": secrets.token_urlsafe(36)}
    private_json(path, value)
    return value


def runtime():
    for path in (
        ROOT / ".worktrees/server/backend/.venv/bin/python",
        ROOT / "backend/.venv/bin/python",
    ):
        if (
            path.is_file()
            and subprocess.run(
                [str(path), "-c", "import fastapi, pydantic, uvicorn, PIL"],
                capture_output=True,
                check=False,
            ).returncode
            == 0
        ):
            return path
    raise RuntimeError(
        "backend의 Python 환경과 Pillow가 필요합니다. TESTING.ko.md의 환경 복원을 따라주세요."
    )


def request(configuration, path):
    req = urllib.request.Request(
        BASE + path, headers={"Authorization": "Bearer " + configuration["token"]}
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.loads(response.read(1_048_576)).get("data")


def stop():
    path = WORK / "server.pid"
    if not path.is_file():
        return
    pid = int(path.read_text().strip())
    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        text=True,
        capture_output=True,
        check=False,
    ).stdout
    if command.strip() and "nunti.avatar_studio.api:app" not in command:
        raise RuntimeError("PID가 다른 프로그램을 가리켜 자동 종료하지 않습니다.")
    if command.strip():
        os.kill(pid, signal.SIGTERM)
        for _ in range(40):
            if (
                subprocess.run(
                    ["ps", "-p", str(pid)], capture_output=True, check=False
                ).returncode
                != 0
            ):
                break
            time.sleep(0.1)
    path.unlink(missing_ok=True)


def server(configuration, allow_paid=False, local_ai=False, navigation_api=False, cloud_chat=False):
    binary = LOCAL_AI / "venv/bin/mflux-generate-flux2-edit"
    weights = LOCAL_AI / "model"
    if local_ai and (
        not binary.is_file()
        or not weights.is_dir()
        or not (weights / "transformer").is_dir()
    ):
        raise RuntimeError(
            "로컬 AI 모델 환경이 없습니다. docs/design/avatar-quality-v4/local-model-result.md의 준비 환경을 확인해 주세요."
        )
    try:
        current = request(configuration, "/v3/capabilities")
        if bool(current.get("imageApiPaidApproved", False)) != allow_paid:
            raise RuntimeError(
                "실행 중인 서버의 유료 승인 모드가 다릅니다. 의도한 옵션과 --restart-server로 다시 시작해 주세요."
            )
        if bool(current.get("localImageModelAvailable", False)) != local_ai:
            raise RuntimeError(
                "실행 중인 서버의 로컬 AI 모드가 다릅니다. --local-ai와 --restart-server로 다시 시작해 주세요."
            )
        if bool(current.get("routeApiAvailable", False)) != navigation_api:
            raise RuntimeError("실행 중인 서버의 경로 API 모드가 다릅니다. --navigation-api와 --restart-server로 다시 시작해 주세요.")
        if bool(current.get("conversationAvailable", False)) != cloud_chat:
            raise RuntimeError("실행 중인 서버의 대화 API 모드가 다릅니다. --cloud-chat와 --restart-server로 다시 시작해 주세요.")
        return current
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            "8768 포트에 다른 인증의 서버가 있습니다. --restart-server 또는 기존 실행을 확인해 주세요."
        ) from exc
    except (urllib.error.URLError, TimeoutError):
        pass
    env = dict(
        os.environ,
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONUNBUFFERED="1",
        NUNTI_STUDIO_TOKEN=configuration["token"],
        NUNTI_STUDIO_WORKSPACE=str(WORK),
        NUNTI_STUDIO_PAID_API_APPROVED="true" if allow_paid else "false",
        NUNTI_STUDIO_LOCAL_MODEL_ENABLED="true" if local_ai else "false",
        NUNTI_STUDIO_LOCAL_MODEL_BINARY=str(binary),
        NUNTI_STUDIO_LOCAL_MODEL_WEIGHTS=str(weights),
        NUNTI_STUDIO_LOCAL_MODEL_TIMEOUT_SECONDS="150",
        NUNTI_STUDIO_ROUTE_API_ENABLED="true" if navigation_api else "false",
        NUNTI_STUDIO_WARDROBE_ENABLED="true" if allow_paid else "false",
        NUNTI_STUDIO_CHAT_API_ENABLED="true" if cloud_chat else "false",
    )
    if cloud_chat and not env.get("NUNTI_STUDIO_CHAT_API_KEY"):
        chat_key = env_file_value("NUNTI_STUDIO_CHAT_API_KEY")
        if chat_key:
            env["NUNTI_STUDIO_CHAT_API_KEY"] = chat_key
    if (allow_paid or (cloud_chat and not env.get("NUNTI_STUDIO_CHAT_API_KEY"))) and not env.get("OPENAI_API_KEY"):
        key = env_file_value("OPENAI_API_KEY")
        legacy = ROOT / ".local/credentials/openai-api-key"  # 예전 위치. 이미 여기에 넣어 둔 PC도 그대로 쓴다.
        if not key and legacy.is_file():
            key = legacy.read_text().strip() or None
        if key:
            env["OPENAI_API_KEY"] = key
        elif allow_paid:
            print("OPENAI_API_KEY 가 .env.local / .env 에 없어 유료 이미지 생성은 꺼진 채로 시작합니다.")
    if cloud_chat and not (env.get("NUNTI_STUDIO_CHAT_API_KEY") or env.get("OPENAI_API_KEY")):
        raise RuntimeError("대화 API에 사용할 NUNTI_STUDIO_CHAT_API_KEY 또는 OPENAI_API_KEY를 설정해 주세요.")
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


def android(configuration):
    if not APK.is_file():
        raise RuntimeError("새 APK가 없습니다. --build를 붙여 실행해 주세요.")
    import run_route_birth

    serial = run_route_birth.emulator()
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
    # -g: 매니페스트의 런타임 권한(CAR_SPEED 등)을 설치 때 허용한다. 앱이 직접 묻지 않아, 없으면 주차 확인에서 막힌다.
    run(adb + ["install", "-r", "-g", "--user", user, APK], capture_output=True)
    command = (
        "run-as "
        + PACKAGE
        + " --user "
        + user
        + " sh -c "
        + shlex.quote(
            "umask 077; mkdir -p files; cat > files/avatar-studio-connection.json"
        )
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
        help="과금 API 사용을 명시적으로 승인한 뒤에만 지정합니다. 기본 실행은 유료 모드를 끕니다.",
    )
    parser.add_argument(
        "--local-ai",
        action="store_true",
        help="준비된 무료 로컬 이미지 모델을 연결합니다. 생성 화면에서 로컬 AI를 선택해 주세요.",
    )
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--navigation-api", action="store_true", help="사진 없이 공개 경로 API를 명시적으로 연결합니다. 현대 내비 경로와 별도 출처입니다.")
    parser.add_argument("--cloud-chat", action="store_true", help="주차 중 눈티 대화에 OpenAI API를 연결합니다.")
    parser.add_argument(
        "--show-code",
        action="store_true",
        help="브라우저 로그인용 로컬 연결 코드만 표시합니다. API 키가 아닙니다.",
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
    caps = server(configuration, allow_paid=args.paid_api, local_ai=args.local_ai,
                  navigation_api=args.navigation_api, cloud_chat=args.cloud_chat)
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
    if caps.get("localImageModelAvailable"):
        print(
            "무료 로컬 AI 연결됨: 기본 생성 방식입니다. 현재 Mac 기준 약 1분이 걸립니다."
        )
    if caps.get("voice", {}).get("available"):
        print("캐릭터별 로컬 TTS 연결됨: 첫 듣기에서 새 음성을 만들고 이후에는 같은 음성을 재생합니다.")
    if caps.get("conversationAvailable"):
        print("눈티 대화에 OpenAI API를 연결했습니다.")
    if caps.get("routeApiAvailable"):
        print("경로 API 연결됨: 내비 목적지 불러오기 → 경로 API로 길 불러오기 → 경로 확인 → 눈티 생성")
        print("안내: docs/design/avatar-v6/TESTING.ko.md")
    else:
        print("안내: docs/design/avatar-generator/TESTING.ko.md")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print("실행 실패: " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None
