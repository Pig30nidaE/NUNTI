#!/usr/bin/env python3
"""Collect the local image-provider key without echoing or logging it. Saved as OPENAI_API_KEY in .env.local."""
import getpass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".env.local"  # git 에 올리지 않는다 (.gitignore). run_avatar_generator.py 가 여기서 읽는다.


def main():
    print("NUNTI · OpenAI 이미지 생성 키 입력")
    print("입력한 키는 화면과 셸 기록에 표시되지 않습니다.")
    print("이 프로젝트의 .env.local 에만 저장됩니다. 앱 APK에는 포함되지 않습니다.")
    # 터미널이 붙여넣기 앞뒤에 넣는 표시(ESC[200~ … ESC[201~)와 따옴표를 걷어 낸다.
    key = getpass.getpass("OpenAI API key: ").replace("\x1b[200~", "").replace("\x1b[201~", "").strip().strip("'\"")
    if not key:
        raise SystemExit("입력된 키가 없습니다. 붙여 넣은 뒤 Enter 를 눌러 주세요. 저장하지 않았습니다.")
    if not key.startswith("sk-") or len(key) < 24 or any(c.isspace() or not c.isprintable() for c in key):
        # 키는 보여 주지 않고, 어디가 맞지 않는지만 알린다.
        why = ("sk- 로 시작하지 않음" if not key.startswith("sk-") else
               "너무 짧음" if len(key) < 24 else "공백이나 보이지 않는 문자가 섞임")
        raise SystemExit(f"키 형식을 확인해 주세요 ({why}, 길이 {len(key)}). 저장하지 않았습니다.")
    # 다른 설정 줄은 그대로 두고 OPENAI_API_KEY 줄만 바꾼다.
    lines = []
    if TARGET.is_file():
        lines = [line for line in TARGET.read_text(encoding="utf-8").splitlines()
                 if not line.strip().removeprefix("export ").lstrip().startswith("OPENAI_API_KEY=")]
    lines.append("OPENAI_API_KEY=" + key)
    fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print("키 저장 완료 (.env.local). 이미지 호출은 NUNTI의 30달러 한도 안에서 처리합니다.")
    input("이 창을 닫으려면 Enter를 누르세요.")


if __name__ == "__main__":
    main()
