#!/usr/bin/env python3
"""Capture one generated MVP voice from the authenticated emulator speaker stream."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_character_voice_runtime import Recording
from verify_catalog_pcm import compare
from verify_android_mvp import RuntimeAudit, read_bundle, emit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--user", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, default=ROOT / ".local/journey-mvp/bundle")
    parser.add_argument("--record-python", default=str(ROOT / ".local/voice-runtime/venv/bin/python"))
    args = parser.parse_args()
    args.timeout = 40
    args.idle_seconds = 2
    args.qa_only = False
    args.output_dir.mkdir(parents=True, exist_ok=False)
    bundle, clips = read_bundle(args.bundle_dir)
    audit = RuntimeAudit(args, bundle, clips, args.output_dir)
    report = {"status": "FAIL", "scope": "One authenticated guest speaker PCM capture, no microphone or human quality judgment"}
    recording = None
    try:
        audit.preflight()
        case = next(c for c in bundle["characters"] if c["caseId"] == "05-forest-visit")
        audit.select(case)
        clip = clips[case["clipIds"]["common"]]
        recording = Recording(args, clip)
        playback = audit.speech(case, "common")
        capture = recording.finish()
        recording = None
        captured_path = Path(capture["captureSummary"]["wav"])
        comparisons = []
        for control in bundle["characters"]:
            source = clips[control["clipIds"]["common"]]
            measurement = compare(args.bundle_dir / "voice" / source["audioPath"], captured_path, True)
            comparisons.append({"characterId": control["characterId"], "clipId": source["clipId"],
                "expected": source["clipId"] == clip["clipId"], "measurement": measurement})
        report.update(status="CAPTURED_AUTHENTICATED_PCM_AND_MEASURED", bundleId=bundle["bundleId"],
            playback=playback, capture=capture, comparisons=comparisons, humanListeningPerformed=False,
            speechQualityApproved=False, uniqueSpeakerIdentityProven=False,
            interpretation="Temporal waveform/energy measurements with seven same-text controls, no calibrated pass threshold or unique attribution verdict")
        emit(state="CAPTURED", clipId=clip["clipId"], controls=7)
    finally:
        if recording is not None:
            recording.abort()
        audit.events.pull()
        report["checks"] = audit.results
        (args.output_dir / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
