"""Turn the Fish Audio downloads in mp3/ into the app's score voice clips.

    python3 prototypes/fish_voice/build_clips.py

Each clip ID is found by a unique piece of its file name (Fish Audio names files after the text).
Output: Opus in .ogg (32 kbps mono, about a tenth of WAV), 150 ms of silence in front (car audio can clip the first syllable),
every clip brought to the same loudness. Written to android/feature/score/src/main/assets/score-voice/.
The app maps lines to these files in RecordedVoice.kt.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "mp3"
OUT = ROOT / "android/feature/score/src/main/assets/score-voice"

# clip ID -> a piece of the file name that only that recording has
KEYS = {
    "brake-1": "깜짝이야",
    "brake-2": "놀랐잖아요",
    "brake-3": "심장-떨어지는",
    "accel-1": "우왓",
    "accel-2": "출발이-엄청",
    "curve-1": "꺄악",
    "curve-2": "커브-너무",
    "relief": "안심돼요",
    "verdict-unknown-1": "놓친-게",
    "verdict-great-1": "처음부터-끝까지",
    "verdict-good-1": "대부분-편안해서",
    "verdict-fair-1": "콩닥콩닥",
    "verdict-low-1": "바짝-긴장",
    "scene-recovered-1": "갈수록-차분",
    "scene-brakes-1": "심장이-쿵",
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
