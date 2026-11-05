#!/usr/bin/env python3
"""Transcribe only the twelve new MVP WAVs once using the existing local ASR cache."""
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
import unicodedata
import wave

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORKSPACE = ROOT / ".local/journey-mvp"
OUTPUT = HERE / "asr"
OLD_ASR = ROOT / "prototypes/voice_audition/asr"
DYNAMIC_ASR = ROOT / "prototypes/journey_voice_dynamic/asr"
os.environ["HF_HOME"] = str(ROOT / ".local/voice-audition-asr/hf")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_new(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write("\n")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def require(condition, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compare(reference: str, hypothesis: str) -> dict:
    specification = importlib.util.spec_from_file_location("saved_asr_comparison", OLD_ASR / "transcribe.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.compare(reference, hypothesis)


def word_difference(reference: str, hypothesis: str) -> dict:
    """Whitespace-delimited Korean eojeol alignment; spacing is not normalized away."""
    def words(value):
        return [word for raw in unicodedata.normalize("NFC", value).split()
                if (word := "".join(char for char in raw if char.isalnum()))]
    left, right = words(reference), words(hypothesis)
    matrix = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) + 1):
        matrix[i][0] = i
    for j in range(len(right) + 1):
        matrix[0][j] = j
    for i, expected in enumerate(left, 1):
        for j, observed in enumerate(right, 1):
            matrix[i][j] = min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1,
                               matrix[i - 1][j - 1] + (expected != observed))
    i, j, edits = len(left), len(right), []
    while i or j:
        if i and j and left[i - 1] == right[j - 1] and matrix[i][j] == matrix[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif i and j and matrix[i][j] == matrix[i - 1][j - 1] + 1:
            edits.append({"type": "substitution", "reference": left[i - 1], "hypothesis": right[j - 1]})
            i, j = i - 1, j - 1
        elif i and matrix[i][j] == matrix[i - 1][j] + 1:
            edits.append({"type": "deletion", "reference": left[i - 1], "hypothesis": ""})
            i -= 1
        else:
            edits.append({"type": "insertion", "reference": "", "hypothesis": right[j - 1]})
            j -= 1
    return {"method": "NFC alphanumeric eojeol separated by whitespace; spacing differences count",
            "referenceWords": left, "hypothesisWords": right,
            "distance": matrix[-1][-1], "edits": list(reversed(edits))}


def inputs() -> tuple[list[dict], list[Path]]:
    bundle_path = WORKSPACE / "bundle/bundle.json"
    manifest_path = WORKSPACE / "bundle/voice/manifest.json"
    bundle, manifest = read(bundle_path), read(manifest_path)
    require(digest(bundle) == read(WORKSPACE / "bundle-receipt.json")["bundleSha256"], "Bundle receipt mismatch")
    require(len(bundle["characters"]) == len(manifest["characters"]) == 8 and len(manifest["clips"]) == 24,
            "Expected eight characters and twenty-four bundled WAVs")
    clips = {item["clipId"]: item for item in manifest["clips"]}
    require(len(clips) == 24, "Duplicate manifest clip IDs")
    prior = read(DYNAMIC_ASR / "results.json")
    old = {(item["characterId"], item["category"]): item for item in prior["results"]}
    new_cases = {item["caseId"]: item for item in read(HERE / "cases/index.json")["cases"]
                 if item["origin"] == "NEW_MVP_GENERATION"}
    require(set(new_cases) == {"05-forest-visit", "06-lake-errand", "07-city-commute", "08-unplanned"},
            "Unexpected new case selection")
    selected, reused = [], []
    for entry in bundle["characters"]:
        directory = WORKSPACE / "state/characters" / entry["characterId"]
        artifact, plan = read(directory / "character.json"), read(directory / "plan.json")
        require(plan["planSha256"] == entry["sourcePlanSha256"] == artifact["planSha256"] ==
                digest({key: value for key, value in plan.items() if key != "planSha256"}), "Plan digest mismatch")
        binding = plan["voice"]
        require(binding == artifact["voiceBinding"] and binding["bindingId"] == entry["bindingId"], "Voice binding mismatch")
        require(set(entry["clipIds"]) == {"greeting", "arrival", "common"}, "Unexpected planned clip categories")
        for category, clip_id in entry["clipIds"].items():
            clip = clips[clip_id]
            audio = WORKSPACE / "bundle/voice" / clip["audioPath"]
            require(audio.resolve().parent == manifest_path.parent.resolve(), "Unexpected bundled WAV path")
            original = directory / artifact["clips"][category]["audioPath"]
            metadata_path = original.with_name("metadata.json")
            metadata = read(metadata_path)
            text = plan["utterances"][category]
            text_sha = hashlib.sha256(text.encode()).hexdigest()
            require(sha(audio) == sha(original) == clip["audioSha256"] == metadata["audioSha256"], "WAV hash mismatch")
            require(text == clip["text"] == metadata["text"] and text_sha == clip["textSha256"] == metadata["textSha256"],
                    "Original text mismatch")
            require(metadata["referenceAudio"] is None and metadata["postprocessing"] == "none", "Unexpected reference or DSP")
            require(metadata["bindingId"] == binding["bindingId"] == clip["source"]["bindingId"] and
                    metadata["direction"] == binding["direction"] and
                    hashlib.sha256(binding["direction"].encode()).hexdigest() == clip["source"]["directionSha256"],
                    "Direction or binding mismatch")
            with wave.open(str(audio), "rb") as wav:
                actual = {"sampleRateHz": wav.getframerate(), "channels": wav.getnchannels(),
                          "sampleWidthBytes": wav.getsampwidth(), "frames": wav.getnframes()}
                pcm = wav.readframes(wav.getnframes())
                require(wav.getcomptype() == "NONE" and len(pcm) == actual["frames"] * actual["channels"] * actual["sampleWidthBytes"],
                        "Incomplete PCM WAV")
            require(all(clip[key] == metadata[key] == value for key, value in actual.items()), "WAV header mismatch")
            require(actual["sampleRateHz"] == 24000 and actual["channels"] == 1 and actual["sampleWidthBytes"] == 2,
                    "Unexpected input PCM format")
            if entry["caseId"] not in new_cases:
                previous = old[(entry["characterId"], category)]
                require(previous["audioSha256"] == clip["audioSha256"] and previous["referenceText"] == text,
                        "Reused clip does not match previously transcribed source")
                reused.append(clip_id)
                continue
            require((entry["characterId"], category) not in old, "Refusing duplicate ASR of prior character")
            require(entry["journeyId"] == new_cases[entry["caseId"]]["journeyId"], "New case journey mismatch")
            selected.append({"id": entry["caseId"] + "/" + category, "caseId": entry["caseId"],
                             "purpose": entry["visual"]["purpose"], "category": category,
                             "characterId": entry["characterId"], "journeyId": entry["journeyId"],
                             "displayName": entry["displayName"], "clipId": clip_id,
                             "file": relative(audio), "sourceFile": relative(original),
                             "audioSha256": sha(audio), "metadataFile": relative(metadata_path),
                             "metadataSha256": sha(metadata_path), "referenceText": text,
                             "referenceTextSha256": text_sha, "bindingId": binding["bindingId"],
                             "direction": binding["direction"], "actualWavHeader": actual})
    require(len(selected) == len(reused) == 12 and len({item["id"] for item in selected}) == 12,
            "Expected exactly twelve new and twelve reused clips")
    require({item["purpose"] for item in selected} == {"visit", "errand", "commute", "unspecified"}, "Unexpected purpose set")
    protected = [path for base in (WORKSPACE / "bundle", WORKSPACE / "state", OLD_ASR, DYNAMIC_ASR)
                 for path in base.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name != ".lock"]
    protected += [WORKSPACE / "bundle-receipt.json", HERE / "cases/index.json", Path(__file__).resolve(),
                  ROOT / "prototypes/journey_voice_dynamic/asr.py"]
    return sorted(selected, key=lambda item: item["id"]), sorted(set(protected))


def packages() -> list[list[str]]:
    return sorted([distribution.metadata["Name"], distribution.version]
                  for distribution in importlib.metadata.distributions())


def verify_results(check_packages: bool = False) -> dict:
    baseline, report = read(OUTPUT / "baseline.json"), read(OUTPUT / "results.json")
    current_inputs, _ = inputs()
    require(current_inputs == read(OUTPUT / "input-manifest.json"), "Input selection changed")
    require(len(report["results"]) == 12 and len({entry["id"] for entry in report["results"]}) == 12,
            "Incomplete or duplicate output")
    for expected, result in zip(current_inputs, report["results"]):
        require(all(result.get(key) == value for key, value in expected.items()), "Stored source provenance changed")
        require(compare(result["referenceText"], result["recognizedText"]) == result["comparison"], "Character alignment changed")
        require(word_difference(result["referenceText"], result["recognizedText"]) == result["wordDifferences"], "Word alignment changed")
    current = {path: sha(ROOT / path) for path in baseline["protectedFileHashes"]}
    require(current == baseline["protectedFileHashes"], "Input, bundle, old results or model cache changed")
    if check_packages:
        require(packages() == baseline["packagesBefore"], "ASR package inventory changed")
    return {"status": "FILE_INTEGRITY_AND_TWELVE_NEW_MVP_WAV_ONE_PASS_ASR_VERIFIED",
            "clips": 12, "newCharacters": 4, "priorClipsNotRetranscribed": 12,
            "protectedFilesUnchanged": len(current), "bundleAndStateUnchanged": True,
            "priorAsrAndModelCacheUnchanged": True, "comparisonRecomputed": True,
            "sourceTextUsedAsPrompt": False, "newModelDownloads": 0, "providerRequests": 0,
            "humanQualityApproved": False, "packageInventoryComparedNow": check_packages}


def run() -> None:
    OUTPUT.mkdir(exist_ok=True)
    require(not any((OUTPUT / name).exists() for name in ("baseline.json", "input-manifest.json", "results.jsonl", "results.json")),
            "Prior attempt exists; inspect it or use --verify-only rather than repeat inference")
    selected, protected = inputs()
    lock_path = OLD_ASR / "model-lock.json"
    lock = read(lock_path)
    model = Path(lock["localPath"])
    require(lock["modelId"] == "mlx-community/whisper-small-mlx" and
            lock["revision"] == "45f3915923c7a79a5a5b5a7d909d39aeb0e5630e", "Unexpected ASR model identity")
    for item in lock["files"]:
        path = model / item["path"]
        require(path.is_file() and path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], "Pinned ASR cache mismatch")
        protected.append(path)
    write_new(OUTPUT / "baseline.json", {"createdAt": datetime.now(timezone.utc).isoformat(),
                                         "protectedFileHashes": {relative(path): sha(path) for path in sorted(set(protected))},
                                         "packagesBefore": packages()})
    write_new(OUTPUT / "input-manifest.json", selected)
    import mlx.core as mx
    import mlx_whisper
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    settings = {"language": "ko", "task": "transcribe", "temperature": 0.0,
                "condition_on_previous_text": False, "initial_prompt": None, "word_timestamps": False}
    results = []
    with (OUTPUT / "results.jsonl").open("x", encoding="utf-8") as incremental:
        for entry in selected:
            audio, rate = sf.read(ROOT / entry["file"], dtype="float32", always_2d=True)
            factor = math.gcd(rate, 16000)
            waveform = resample_poly(audio.mean(axis=1), 16000 // factor, rate // factor).astype(np.float32)
            print(json.dumps({"event": "transcribing", "id": entry["id"]}), flush=True)
            started = time.monotonic()
            value = mlx_whisper.transcribe(waveform, path_or_hf_repo=str(model), verbose=None, **settings)
            result = {**entry, "recognizedText": value["text"], "recognizedLanguage": value["language"],
                      "asrSampleRateHz": 16000, "asrSeconds": time.monotonic() - started,
                      "segments": value["segments"], "comparison": compare(entry["referenceText"], value["text"]),
                      "wordDifferences": word_difference(entry["referenceText"], value["text"])}
            results.append(result)
            incremental.write(json.dumps(result, ensure_ascii=False) + "\n")
            incremental.flush()
            print(json.dumps({"event": "transcribed", "id": entry["id"], "text": value["text"],
                              "cer": result["comparison"]["characterErrorRate"]}, ensure_ascii=False), flush=True)
    total_edits = sum(result["comparison"]["distance"] for result in results)
    total_characters = sum(result["comparison"]["referenceCharacters"] for result in results)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "modelId": lock["modelId"],
              "revision": lock["revision"], "modelLockSha256": sha(lock_path), "settings": settings,
              "decoder": "One greedy temperature-zero pass per new WAV; no source text prompt or beam search",
              "sourceTextUsedAsPrompt": False, "newModelDownloads": 0, "providerRequests": 0,
              "priorClipsNotRetranscribed": 12, "clips": len(results), "characterEdits": total_edits,
              "referenceCharacters": total_characters, "microCharacterErrorRate": total_edits / total_characters,
              "peakMlxMemoryBytes": mx.get_peak_memory(), "results": results,
              "doesNotProve": ["TTS pronunciation error rather than ASR error", "naturalness", "cuteness",
                               "perceptually unique voices", "driving benefit"]}
    write_new(OUTPUT / "results.json", report)
    verification = verify_results(check_packages=True)
    write_new(OUTPUT / "verification.json", verification)
    lines = ["# 새 MVP 음원 전사 결과", "", "기존 로컬 Whisper-small 캐시로 새 4캐릭터의 12WAV만 각각 한 번 전사했다. 원문 prompt는 주지 않았고 기존 12개는 재전사하지 않았다.", "",
             "| 사례·대사 | 원문 | 인식 결과 | 정규화 CER |", "| --- | --- | --- | ---: |"]
    for result in results:
        cells = [result["id"], result["referenceText"], result["recognizedText"].strip(),
                 format(result["comparison"]["characterErrorRate"] * 100, ".2f") + "%"]
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    lines += ["", "문자 CER은 NFC로 정규화한 문자·숫자를 비교하며 공백과 문장부호를 제외한다. 어절별 차이는 results.json의 wordDifferences에 기록했다. 어절 비교에는 띄어쓰기 차이도 포함된다.", "",
              "ASR 차이는 발음 불량을 확정하지 않는다. 발음·자연스러움·귀여움·화자 고유성은 사람 청취로 별도 판단한다.", "",
              "입력 WAV·metadata·bundle·기존 ASR 결과·모델 캐시의 해시와 설치 패키지 목록은 실행 전후 동일했다."]
    with (OUTPUT / "summary.md").open("x", encoding="utf-8") as target:
        target.write("\n".join(lines) + "\n")
    mx.clear_cache()
    print(json.dumps({"event": "complete", "clips": len(results), "microCER": report["microCharacterErrorRate"],
                      "protectedFiles": verification["protectedFilesUnchanged"]}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--check-packages", action="store_true", help="Compare current interpreter package inventory to the recorded ASR venv")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify_results(args.check_packages), ensure_ascii=False, indent=2))
    else:
        run()


if __name__ == "__main__":
    main()
