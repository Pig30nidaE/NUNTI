"""Turn the Fish Audio downloads in mp3/ into the app's score voice clips.

    python3 scripts/build_score_voice_clips.py

Each clip ID is found by a unique piece of its file name (Fish Audio names files after the text).
Output: Opus in .ogg (32 kbps mono, about a tenth of WAV), 150 ms of silence in front (car audio can clip the first syllable),
every clip brought to the same loudness. Written to android/feature/score/src/main/assets/score-voice/.
The app maps lines to these files in RecordedVoice.kt.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mp3"
OUT = ROOT / "android/feature/score/src/main/assets/score-voice"

# clip ID -> a piece of the file name that only that recording has
KEYS = {
    "greeting": "오늘도-같이-달려요",
    "brake-1": "깜짝이야",
    "brake-2": "놀랐잖아요",
    "brake-3": "심장-떨어지는",
    "accel-1": "조금만-천천히",
    "accel-2": "우왓",
    "curve-1": "커브-너무",
    "curve-2": "꺄악",
    "relief": "안심돼요",
    "verdict-unknown-1": "놓친-게",
    "verdict-great-1": "처음부터-끝까지",
    "verdict-great-2": "콧노래",
    "verdict-good-1": "대부분-편안해서",
    "verdict-good-2": "참-포근했어요",
    "verdict-fair-1": "콩닥콩닥",
    "verdict-fair-2": "그래도-emphasis몇-번은",
    "verdict-low-1": "바짝-긴장",
    "verdict-low-2": "계속-조마조마",
    "scene-recovered-1": "갈수록-차분",
    "scene-recovered-2": "편안하게-와-줘서",
    "scene-brakes-1": "심장이-쿵",
    "scene-brakes-2": "데굴-구",
    "scene-accel-1": "날아가는-줄",
    "scene-curves-1": "빙글빙글",
    "scene-smooth-1": "사르르-부드러웠어요",
    "scene-smooth-2": "창밖-구경",
    "checkin-cheer-1": "같이-와서-좋았어요",
    "checkin-cheer-2": "오늘도-수고했어요",
    "checkin-ask-trouble-1": "안-좋은-일-있나요",
    "checkin-ask-hurry-1": "많이-바빴나요",
    "pause-movement-1": "평가할-만큼-달리지",
    "pause-signals-1": "신호가-부족해서-평가를",
    "pause-saved-1": "잠깐-저장해",
}

TARGET = "I=-16:TP=-1.5:LRA=11"
PRE_ROLL_MS = 150


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def convert(src: Path, dst: Path):
    # Pass 1 measures loudness; pass 2 applies one linear gain so the clip's dynamics stay as recorded.
    measured = run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"loudnorm={TARGET}:print_format=json",
                    "-f", "null", "-"]).stderr
    m = json.loads(measured[measured.rindex("{"):measured.rindex("}") + 1])
    norm = (f"loudnorm={TARGET}:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(src), "-af", f"{norm},adelay={PRE_ROLL_MS},aresample=48000",
         "-ac", "1", "-c:a", "libopus", "-b:a", "32k", "-application", "voip", "-map_metadata", "-1", str(dst)])


def main() -> int:
    files = sorted(SRC.glob("*.mp3"))
    OUT.mkdir(parents=True, exist_ok=True)
    used = set()
    missing = []
    for clip, key in KEYS.items():
        hits = [f for f in files if key in f.name]
        if not hits:
            missing.append(clip)
            continue
        if len(hits) > 1:
            print(f"{clip}: '{key}' matches {len(hits)} files", file=sys.stderr)
            return 1
        used.add(hits[0])
        convert(hits[0], OUT / f"{clip}.ogg")
        print(f"{clip}.ogg  <-  {hits[0].name}")
    for f in files:
        if f not in used:
            print(f"not used (add a key): {f.name}")
    if missing:
        print("no recording yet: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
