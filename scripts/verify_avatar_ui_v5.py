#!/usr/bin/env python3
"""Run the approved local v5 UI checks without paid APIs, new AI inference or recording."""

import argparse
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/avatar-quality-v5"
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def commands():
    artifact = json.loads((WORK / "model-http/coast/artifact.json").read_text())
    request_id = artifact["requestId"]
    if artifact["mediaOrigin"] != "LOCAL_MODEL" or str(UUID(request_id)) != request_id:
        raise ValueError("저장된 AI 해변 결과를 확인할 수 없습니다.")
    python = next(
        (
            p
            for p in (
                ROOT / ".worktrees/server/backend/.venv/bin/python",
                ROOT / "backend/.venv/bin/python",
            )
            if p.is_file()
        ),
        None,
    )
    if python is None:
        raise ValueError("서버 Python 환경이 없습니다.")
    return [
        [
            sys.executable,
            "scripts/run_avatar_generator.py",
            "--local-ai",
            "--restart-server",
        ],
        ["node", "scripts/verify_avatar_input_edges.mjs"],
        ["node", "scripts/verify_avatar_generator.mjs", "--qa-tag=v5"],
        [
            "node",
            "scripts/verify_avatar_generator.mjs",
            "--native",
            "--port=9224",
            "--qa-tag=v5",
        ],
        [
            "node",
            "scripts/verify_avatar_generator.mjs",
            "--native",
            "--port=9224",
            "--qa-tag=v5",
            "--local-ai",
            "--resume-request=" + request_id,
        ],
        [
            "node",
            "prototypes/avatar_generator/verify_formation.mjs",
            "--fixtures=.local/avatar-quality-v5/motion-fixtures",
            "--out=.local/avatar-quality-v5/motion-qa",
        ],
        [str(python), "scripts/verify_avatar_quality_v5.py"],
    ]


def chrome_ready():
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:9223/json/list", timeout=2
        ) as response:
            return any(target.get("type") == "page" for target in json.load(response))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="실제 로컬 검증을 실행합니다. 생략하면 명령만 표시합니다.",
    )
    args = parser.parse_args()
    steps = commands()
    if not args.run:
        for step in steps:
            print(shlex.join(step))
        return
    own_chrome = None
    try:
        if not chrome_ready():
            if not CHROME.is_file():
                raise ValueError("검증용 Google Chrome을 찾지 못했습니다.")
            profile = ROOT / ".local/avatar-generator/chrome-v5-manual-qa"
            own_chrome = subprocess.Popen(
                [
                    str(CHROME),
                    "--headless=new",
                    "--remote-debugging-port=9223",
                    "--remote-debugging-address=127.0.0.1",
                    "--user-data-dir=" + str(profile),
                    "--no-first-run",
                    "--no-default-browser-check",
                    "about:blank",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(80):
                if chrome_ready():
                    break
                if own_chrome.poll() is not None:
                    raise ValueError("검증용 Chrome이 종료됐습니다.")
                time.sleep(0.1)
            else:
                raise ValueError("검증용 Chrome의 시작 시간이 초과됐습니다.")
        for index, step in enumerate(steps, 1):
            print(f"[{index}/{len(steps)}] {shlex.join(step)}", flush=True)
            subprocess.run(step, cwd=ROOT, check=True)
        print(
            "로컬 화면 검증 완료. docs/design/avatar-quality-v5/verification/delivery.json을 확인하세요."
        )
    finally:
        if own_chrome is not None:
            own_chrome.terminate()
            try:
                own_chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                own_chrome.kill()
                own_chrome.wait(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("검증 중단: " + str(error), file=sys.stderr)
        raise SystemExit(1) from None
