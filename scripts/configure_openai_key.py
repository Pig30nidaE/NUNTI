#!/usr/bin/env python3
"""Collect the local image-provider key without echoing or logging it."""
import getpass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".local/credentials/openai-api-key"


def main():
    print("NUNTI · OpenAI 이미지 생성 키 입력")
    print("입력한 키는 화면과 셸 기록에 표시되지 않습니다.")
    print("이 프로젝트의 로컬 파일에만 저장됩니다. 앱 APK에는 포함되지 않습니다.")
    key = getpass.getpass("OpenAI API key: ").strip()
    if not key.startswith("sk-") or len(key) < 24 or any(c.isspace() for c in key):
        raise SystemExit("키 형식을 확인해 주세요. 저장하지 않았습니다.")
    TARGET.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(key + "\n")
    print("키 저장 완료. 이미지 호출은 NUNTI의 30달러 한도 안에서 처리합니다.")
    input("이 창을 닫으려면 Enter를 누르세요.")


if __name__ == "__main__":
    main()
