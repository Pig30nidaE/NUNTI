#!/usr/bin/env python3
"""Check scenario voice plans and optionally synthesize every one with one local model.

Input: JSON array (or {"cases": [...]}) of {"id", "input", "design"} objects.
Each entry may instead supply a stored "voicePlan". --synthesize creates new WAVs;
without it only planning is verified, and the report says so explicitly.
"""

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from nunti.avatar_studio.voice_design import (
    build_voice_design,
    canonical,
    validate_voice_plan,
)
from nunti.avatar_studio.voice_render import (
    LocalVoiceRenderer,
    inspect_wav,
    validate_speech_duration,
)


def seed_accepted_cache(plan, source, destination):
    """Copy validated QA assets into a new run; preserve the entire original run."""
    text_sha = hashlib.sha256(plan["greeting"].encode()).hexdigest()
    source_clip = source / "audio" / plan["profileId"] / text_sha
    target = destination / "audio" / plan["profileId"] / text_sha
    if target.exists() or not source_clip.exists():
        return None
    record = json.loads((source_clip / "metadata.json").read_text())
    if (
        record["profileId"] != plan["profileId"]
        or record["text"] != plan["greeting"]
        or record["planSha256"] != hashlib.sha256(canonical(plan).encode()).hexdigest()
    ):
        raise ValueError("SEED_CACHE_BINDING_CHANGED")
    actual = inspect_wav(source_clip / "audio.wav")
    if any(record.get(k) != v for k, v in actual.items()):
        raise ValueError("SEED_CACHE_AUDIO_CHANGED")
    try:
        validate_speech_duration(plan["greeting"], actual["durationMs"])
    except ValueError as exc:
        return {"copied": False, "source": str(source_clip), "reason": str(exc)}
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".copy-", dir=target.parent))
    try:
        shutil.copytree(source_clip, temp, dirs_exist_ok=True)
        temp.rename(target)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return {
        "copied": True,
        "source": str(source_clip),
        "audioSha256": actual["audioSha256"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--synthesize", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--seed-cache",
        type=Path,
        help="Preserve prior run and reuse only valid immutable WAVs",
    )
    args = parser.parse_args()
    source = json.loads(args.cases.read_text())
    cases = (source["cases"] if isinstance(source, dict) else source)[: args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    renderer = LocalVoiceRenderer()
    results = []
    started = time.monotonic()
    for index, case in enumerate(cases):
        plan = case.get("voicePlan") or build_voice_design(
            case["input"], case.get("design")
        )
        validate_voice_plan(plan)
        result = {"id": case.get("id", str(index)), "voicePlan": plan, "audio": None}
        if args.synthesize:
            if args.seed_cache:
                result["priorRun"] = seed_accepted_cache(
                    plan, args.seed_cache, args.output
                )
            try:
                with redirect_stdout(sys.stderr):
                    result["audio"] = renderer.render(plan, args.output / "audio")
            except (ValueError, RuntimeError, TimeoutError) as exc:
                result["error"] = str(exc)
        results.append(result)
        # Preserve resumable progress even if a later synthesis fails.
        (args.output / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n"
        )
        print(
            json.dumps(
                {
                    "completed": len(results),
                    "total": len(cases),
                    "id": result["id"],
                    "synthesized": result["audio"] is not None,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    audio = [r["audio"] for r in results if r["audio"]]
    failed = [r["id"] for r in results if "error" in r]
    report = {
        "status": "FAIL" if failed else "PASS",
        "cases": len(results),
        "actualWavs": len(audio),
        "failedCases": failed,
        "uniqueVoiceBindings": len({r["voicePlan"]["profileId"] for r in results}),
        "uniqueSeeds": len({r["voicePlan"]["seed"] for r in results}),
        "roles": sorted({r["voicePlan"]["role"] for r in results}),
        "roleCounts": dict(Counter(r["voicePlan"]["role"] for r in results)),
        "uniqueWavHashes": len({r["audioSha256"] for r in audio}),
        "clippedWavs": sum(r["fullScaleSamples"] > 0 for r in audio),
        "durationRangeMs": [
            min((r["durationMs"] for r in audio), default=0),
            max((r["durationMs"] for r in audio), default=0),
        ],
        "totalAudioSeconds": round(sum(r["durationMs"] for r in audio) / 1000, 3),
        "elapsedSeconds": round(time.monotonic() - started, 2),
        "humanListeningVerified": False,
        "perceptuallyUniqueSpeakersVerified": False,
        "scope": "Actual WAV synthesis and file inspection"
        if args.synthesize
        else "Voice plans only; no synthesis",
    }
    (args.output / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
