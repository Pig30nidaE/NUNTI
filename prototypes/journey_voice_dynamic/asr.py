"""One local Whisper pass per dynamic WAV. Existing results are never overwritten."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD_ASR = ROOT / "prototypes/voice_audition/asr"
OUTPUT = HERE / "asr"
os.environ["HF_HOME"] = str(ROOT / ".local/voice-audition-asr/hf")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write("\n")


def compare(reference: str, hypothesis: str) -> dict:
    # Reuse the previously inspected, pure edit alignment. No ASR main is invoked.
    specification = importlib.util.spec_from_file_location("saved_asr_comparison", OLD_ASR / "transcribe.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.compare(reference, hypothesis)


def sources() -> list[dict]:
    values = []
    for path in sorted((HERE / "demo/characters").glob("*/character.json")):
        artifact = read(path)
        categories = {clip["cacheKey"]: category for category, clip in artifact["clips"].items()}
        for metadata_path in sorted((path.parent / "clips").glob("*/metadata.json")):
            record = read(metadata_path)
            audio = metadata_path.with_name("audio.wav")
            if sha(audio) != record["audioSha256"] or hashlib.sha256(record["text"].encode()).hexdigest() != record["textSha256"]:
                raise ValueError("Input WAV or original text hash disagrees")
            if record["referenceAudio"] is not None or record["postprocessing"] != "none":
                raise ValueError("Unexpected input provenance")
            category = categories.get(metadata_path.parent.name, "additional")
            values.append({"id": artifact["journeyId"] + "/" + category,
                           "characterId": artifact["characterId"], "category": category,
                           "file": str(audio.relative_to(ROOT)), "audioSha256": sha(audio),
                           "metadataFile": str(metadata_path.relative_to(ROOT)), "metadataSha256": sha(metadata_path),
                           "referenceText": record["text"], "referenceTextSha256": record["textSha256"],
                           "bindingId": record["bindingId"], "direction": record["direction"]})
    if len(values) != 13 or sum(value["category"] == "additional" for value in values) != 1:
        raise ValueError("Expected twelve planned clips and one additional-text WAV")
    if len({value["id"] for value in values}) != len(values):
        raise ValueError("ASR input identities must be unique")
    return values


def verify_results() -> dict:
    report = read(OUTPUT / "results.json")
    baseline = read(OUTPUT / "baseline.json")
    if len(report["results"]) != 13:
        raise ValueError("Incomplete one-pass ASR output")
    for entry in report["results"]:
        if sha(ROOT / entry["file"]) != entry["audioSha256"] or sha(ROOT / entry["metadataFile"]) != entry["metadataSha256"]:
            raise ValueError("Input artifact changed")
        if compare(entry["referenceText"], entry["recognizedText"]) != entry["comparison"]:
            raise ValueError("Stored text comparison changed")
    current = {path: sha(ROOT / path) for path in baseline["protectedFileHashes"]}
    if current != baseline["protectedFileHashes"]:
        raise ValueError("Prior ASR, input WAV, runtime, or model bytes changed")
    return {"status": "ACTUAL_THIRTEEN_WAV_ONE_PASS_ASR_AND_PROTECTED_HASHES_VERIFIED",
            "clips": 13, "protectedFilesUnchanged": len(current),
            "inputWavsAndMetadataUnchanged": True, "priorAsrResultsUnchanged": True,
            "comparisonRecomputed": True, "sourceTextUsedAsPrompt": False,
            "humanQualityApproved": False, "perceptualVoiceVariationVerified": False}


def run() -> None:
    OUTPUT.mkdir(exist_ok=True)
    if any((OUTPUT / name).exists() for name in ("results.json", "results.jsonl", "baseline.json", "input-manifest.json")):
        raise ValueError("Prior ASR attempt exists; inspect it or use --verify-only instead of repeating inference")
    inputs = sources()
    lock_path = OLD_ASR / "model-lock.json"
    lock = read(lock_path)
    model = Path(lock["localPath"])
    for item in lock["files"]:
        path = model / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            raise ValueError("Existing pinned ASR cache is unavailable or changed")
    protected = sorted(path for path in OLD_ASR.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    protected += [model / item["path"] for item in lock["files"]]
    protected += [ROOT / item[key] for item in inputs for key in ("file", "metadataFile")]
    packages_before = sorted((distribution.metadata["Name"], distribution.version) for distribution in importlib.metadata.distributions())
    write_new(OUTPUT / "baseline.json", {"protectedFileHashes": {str(path.relative_to(ROOT)): sha(path) for path in protected},
                                         "packagesBefore": packages_before})
    write_new(OUTPUT / "input-manifest.json", inputs)
    import mlx.core as mx
    import mlx_whisper
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    settings = {"language": "ko", "task": "transcribe", "temperature": 0.0,
                "condition_on_previous_text": False, "initial_prompt": None, "word_timestamps": False}
    results = []
    with (OUTPUT / "results.jsonl").open("x", encoding="utf-8") as incremental:
        for entry in inputs:
            audio, rate = sf.read(ROOT / entry["file"], dtype="float32", always_2d=True)
            mono = audio.mean(axis=1)
            factor = math.gcd(rate, 16000)
            waveform = resample_poly(mono, 16000 // factor, rate // factor).astype(np.float32)
            print(json.dumps({"event": "transcribing", "id": entry["id"]}), flush=True)
            started = time.monotonic()
            value = mlx_whisper.transcribe(waveform, path_or_hf_repo=str(model), verbose=None, **settings)
            record = {**entry, "recognizedText": value["text"], "recognizedLanguage": value["language"],
                      "sourceSampleRateHz": rate, "asrSampleRateHz": 16000,
                      "asrSeconds": time.monotonic() - started, "segments": value["segments"],
                      "comparison": compare(entry["referenceText"], value["text"])}
            results.append(record)
            incremental.write(json.dumps(record, ensure_ascii=False) + "\n")
            incremental.flush()
            print(json.dumps({"event": "transcribed", "id": entry["id"], "text": value["text"],
                              "cer": record["comparison"]["characterErrorRate"]}, ensure_ascii=False), flush=True)
    total_edits = sum(value["comparison"]["distance"] for value in results)
    total_characters = sum(value["comparison"]["referenceCharacters"] for value in results)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "modelId": lock["modelId"],
              "revision": lock["revision"], "modelLockSha256": sha(lock_path),
              "settings": settings, "decoder": "One greedy temperature-zero pass per source; no beam search or text prompt",
              "sourceTextUsedAsPrompt": False, "newModelDownloads": 0, "providerRequests": 0,
              "originalComparisonCodeSha256": sha(OLD_ASR / "transcribe.py"),
              "clips": len(results), "microCharacterErrorRate": total_edits / total_characters,
              "peakMlxMemoryBytes": mx.get_peak_memory(), "results": results,
              "doesNotProve": ["phonetic correctness", "naturalness", "cuteness", "perceptual speaker identity",
                               "that a discrepancy is a TTS error rather than an ASR error"]}
    write_new(OUTPUT / "results.json", report)
    packages_after = sorted((distribution.metadata["Name"], distribution.version) for distribution in importlib.metadata.distributions())
    if [list(item) for item in packages_after] != read(OUTPUT / "baseline.json")["packagesBefore"]:
        raise ValueError("ASR environment inventory changed")
    verification = verify_results()
    verification["packageInventoryUnchanged"] = True
    write_new(OUTPUT / "verification.json", verification)
    lines = ["# Dynamic journey voice transcription", "", "Each of the thirteen WAVs was transcribed once with the existing local Whisper-small cache. No source text was supplied as a prompt.", "",
             "| Source | Recognized Korean | Normalized CER |", "| --- | --- | ---: |"]
    for value in results:
        lines.append("| " + value["id"] + " | " + value["recognizedText"].replace("|", "\\|").strip() + " | " + format(value["comparison"]["characterErrorRate"] * 100, ".2f") + "% |")
    lines += ["", "CER removes whitespace and punctuation and compares NFC letters and numbers. ASR disagreements can be recognition errors. These results do not approve pronunciation, naturalness, cuteness, or distinct voice identity.", "",
              "All input WAVs, metadata, old ASR artifacts, model cache files, and package inventory were preserved. Full results and edit alignments are in results.json."]
    with (OUTPUT / "summary.md").open("x", encoding="utf-8") as target:
        target.write("\n".join(lines) + "\n")
    mx.clear_cache()
    print(json.dumps({"event": "complete", "clips": len(results), "microCER": report["microCharacterErrorRate"],
                      "protectedFiles": verification["protectedFilesUnchanged"]}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify_results(), ensure_ascii=False, indent=2))
    else:
        run()


if __name__ == "__main__":
    main()
