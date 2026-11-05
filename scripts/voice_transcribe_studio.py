#!/usr/bin/env python3
"""One-pass local Korean ASR of generated WAVs, with no reference text prompt.

ASR disagreement is an inspection cue. It cannot certify pleasantness, perceived
age, speaker uniqueness, or which system made a pronunciation/transcription error.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from nunti.avatar_studio.voice_render import _gpu_lock, sha256


def compare(expected, recognized):
    a = re.sub(r"[^\w]", "", expected.casefold())
    b = re.sub(r"[^\w]", "", recognized.casefold())
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        next_row = [i]
        for j, y in enumerate(b, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (x != y)))
        row = next_row
    return {
        "edits": row[-1],
        "referenceCharacters": len(a),
        "characterErrorRate": row[-1] / max(1, len(a)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, required=True, help="voice_verify_studio results.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = json.loads(args.results.read_text())
    lock = json.loads(
        (ROOT / "prototypes/voice_audition/asr/model-lock.json").read_text()
    )
    cache = Path(lock["localPath"])
    for item in lock["files"]:
        if sha256(cache / item["path"]) != item["sha256"]:
            raise ValueError("ASR_MODEL_CHANGED")
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    import mlx_whisper
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    settings = {
        "language": "ko",
        "task": "transcribe",
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "initial_prompt": None,
        "word_timestamps": False,
    }
    results = []
    for index, item in enumerate(item for item in source if item.get("audio")):
        audio = item["audio"]
        path = Path(audio["audioPath"])
        if sha256(path) != audio["audioSha256"]:
            raise ValueError("ASR_INPUT_CHANGED")
        result_file = args.output / (audio["audioSha256"] + ".json")
        if result_file.exists():
            result = json.loads(result_file.read_text())
            if (
                result["audioSha256"] != audio["audioSha256"]
                or result["text"] != audio["text"]
            ):
                raise ValueError("ASR_CACHE_INPUT_CHANGED")
        else:
            samples, rate = sf.read(path, dtype="float32", always_2d=True)
            factor = math.gcd(rate, 16000)
            samples = resample_poly(
                samples.mean(axis=1), 16000 // factor, rate // factor
            ).astype(np.float32)
            started = time.monotonic()
            with _gpu_lock():
                value = mlx_whisper.transcribe(
                    samples, path_or_hf_repo=str(cache), verbose=None, **settings
                )
            result = {
                "id": item["id"],
                "audioSha256": audio["audioSha256"],
                "text": audio["text"],
                "recognizedText": value["text"],
                "comparison": compare(audio["text"], value["text"]),
                "seconds": round(time.monotonic() - started, 3),
                "modelId": lock["modelId"],
                "revision": lock["revision"],
                "sourceTextUsedAsPrompt": False,
                "settings": settings,
            }
            result_file.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            )
        results.append(result)
        print(
            json.dumps(
                {
                    "completed": index + 1,
                    "id": item["id"],
                    "text": result["recognizedText"],
                    "cer": result["comparison"]["characterErrorRate"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    report = {
        "clips": len(results),
        "sourceTextUsedAsPrompt": False,
        "exactAfterWhitespaceAndPunctuation": sum(
            r["comparison"]["edits"] == 0 for r in results
        ),
        "microCharacterErrorRate": sum(r["comparison"]["edits"] for r in results)
        / max(1, sum(r["comparison"]["referenceCharacters"] for r in results)),
        "reviewThreshold": 0.15,
        "needsListeningReview": [
            {
                "id": r["id"],
                "referenceText": r["text"],
                "recognizedText": r["recognizedText"],
                "characterErrorRate": r["comparison"]["characterErrorRate"],
            }
            for r in results
            if r["comparison"]["characterErrorRate"] > 0.15
        ],
        "interpretation": "ASR discrepancies are review cues, not confirmed TTS pronunciation failures.",
        "humanListeningVerified": False,
        "results": results,
    }
    (args.output / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
