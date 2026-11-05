"""One independent ASR pass on immutable audition or identity WAV files."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import time
import unicodedata

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / ".local/voice-audition-asr"
os.environ["HF_HOME"] = str(TOOLS / "hf")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"


def normalize(text):
    """NFC Unicode letters/numbers only: remove punctuation/whitespace, keep words unchanged."""
    return "".join(c for c in unicodedata.normalize("NFC", text) if c.isalnum())


def compare(reference, hypothesis):
    """Unit-cost Levenshtein distance and a deterministic minimum-cost alignment."""
    reference, hypothesis = normalize(reference), normalize(hypothesis)
    rows = [[0] * (len(hypothesis) + 1) for _ in range(len(reference) + 1)]
    for i in range(len(reference) + 1):
        rows[i][0] = i
    for j in range(len(hypothesis) + 1):
        rows[0][j] = j
    for i in range(1, len(reference) + 1):
        for j in range(1, len(hypothesis) + 1):
            rows[i][j] = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + (reference[i - 1] != hypothesis[j - 1]))
    edits = []
    i, j = len(reference), len(hypothesis)
    while i or j:
        if i and j and reference[i - 1] == hypothesis[j - 1] and rows[i][j] == rows[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif i and j and rows[i][j] == rows[i - 1][j - 1] + 1:
            edits.append({"type": "substitution", "referenceOffset": i - 1, "reference": reference[i - 1], "hypothesis": hypothesis[j - 1]})
            i, j = i - 1, j - 1
        elif i and rows[i][j] == rows[i - 1][j] + 1:
            edits.append({"type": "deletion", "referenceOffset": i - 1, "reference": reference[i - 1], "hypothesis": ""})
            i -= 1
        else:
            edits.append({"type": "insertion", "referenceOffset": i, "reference": "", "hypothesis": hypothesis[j - 1]})
            j -= 1
    distance = rows[-1][-1]
    return {"normalizedReference": reference, "normalizedHypothesis": hypothesis, "referenceCharacters": len(reference), "distance": distance, "characterErrorRate": distance / len(reference), "editAlignment": list(reversed(edits)), "needsHumanListening": distance > 0, "omissionCandidate": any(e["type"] == "deletion" for e in edits), "distortionCandidate": any(e["type"] in ["substitution", "insertion"] for e in edits)}


def main():
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--identity", action="store_true", help="Transcribe only the two new Base identity samples into separate files.")
    selection.add_argument("--round2", action="store_true", help="Transcribe four Sohee WAVs and one provided public ElevenLabs demo MP3.")
    selection.add_argument("--stella", action="store_true", help="Transcribe only the additional official Stella public-demo MP3.")
    args = parser.parse_args()
    prefix = "stella-" if args.stella else "round2-" if args.round2 else "identity-" if args.identity else ""
    expected_count = 1 if args.stella else 5 if args.round2 else 2 if args.identity else 10
    groups = [] if args.stella else [("qwen-sohee", "prototypes/qwen_sohee_audition/samples")] if args.round2 else [("qwen-base", "prototypes/journey_voice_v3/identity/samples")] if args.identity else [("qwen", "prototypes/journey_voice_v3/samples"), ("chatterbox", "prototypes/chatterbox_audition/samples")]
    if (HERE / f"{prefix}results.json").exists() or (HERE / f"{prefix}results.jsonl").exists():
        raise SystemExit("Prior ASR results exist. Inspect them rather than silently repeating inference.")
    inputs = []
    for group, folder in groups:
        for wav in sorted((ROOT / folder).glob("*.wav")):
            if args.identity and wav.stem not in ["comfort", "arrival"]:
                continue
            metadata = json.loads(wav.with_suffix(".json").read_text())
            assert hashlib.sha256(wav.read_bytes()).hexdigest() == metadata["audioSha256"]
            inputs.append({"id": f'{group}/{wav.stem}', "path": str(wav.relative_to(ROOT)), "sha256": metadata["audioSha256"], "referenceText": metadata["text"], "referenceMetadataSha256": hashlib.sha256(wav.with_suffix(".json").read_bytes()).hexdigest()})
    if args.round2:
        mp3 = ROOT / "prototypes/voice_audition/commercial/elevenlabs-anna-common-arrival.mp3"
        inputs.append({"id": "elevenlabs-public-demo/anna-common-arrival", "path": str(mp3.relative_to(ROOT)), "sha256": hashlib.sha256(mp3.read_bytes()).hexdigest(), "referenceText": "안녕하세요. 오늘의 여행도 함께할게요. 와, 도착했다! 여기서 어떤 기억을 만나게 될까?", "referenceMetadataSha256": None, "sourceContext": {"vendor": "ElevenLabs", "voiceLabel": "Anna", "modelId": None, "sourceTextOrigin": "PM-provided exact text entered in the official anonymous public UI demo", "acquisition": "PM-provided actual file from the official UI download button", "limitations": "Public anonymous demo; exact model ID, revision and synthesis parameters are not exposed. Do not label this as any specific ElevenLabs model version."}})
    if args.stella:
        mp3 = ROOT / "prototypes/voice_audition/commercial/elevenlabs-stella-common-arrival.mp3"
        metadata = json.loads(mp3.with_suffix(".json").read_text())
        assert hashlib.sha256(mp3.read_bytes()).hexdigest() == metadata["audioSha256"]
        assert hashlib.sha256(metadata["text"].encode()).hexdigest() == metadata["textSha256"]
        inputs.append({"id": "elevenlabs-public-demo/stella-common-arrival", "path": str(mp3.relative_to(ROOT)), "sha256": metadata["audioSha256"], "referenceText": metadata["text"], "referenceMetadataSha256": hashlib.sha256(mp3.with_suffix(".json").read_bytes()).hexdigest(), "sourceContext": {"vendor": "ElevenLabs", "voiceLabel": metadata["voiceName"], "modelId": metadata["modelId"], "sourceUrl": metadata["sourceUrl"], "acquisition": metadata["access"], "limitations": metadata["modelIdDisclosure"]}})
    assert len(inputs) == expected_count
    (HERE / f"{prefix}input-manifest.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n")
    lock = json.loads((HERE / "model-lock.json").read_text())
    import mlx.core as mx
    import mlx_whisper
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    settings = {"language": "ko", "task": "transcribe", "temperature": 0.0, "condition_on_previous_text": False, "initial_prompt": None, "word_timestamps": False}
    results = []
    for source in inputs:
        wav = ROOT / source["path"]
        values, sample_rate = sf.read(wav, dtype="float32", always_2d=True)
        audio = values.mean(axis=1)
        divisor = math.gcd(sample_rate, 16000)
        audio = resample_poly(audio, 16000 // divisor, sample_rate // divisor).astype(np.float32)
        print(json.dumps({"event": "transcribing", "id": source["id"]}), flush=True)
        start = time.monotonic()
        result = mlx_whisper.transcribe(audio, path_or_hf_repo=lock["localPath"], verbose=None, **settings)
        record = {**source, "recognizedText": result["text"], "recognizedLanguage": result["language"], "asrSeconds": time.monotonic() - start, "sourceSampleRateHz": sample_rate, "asrSampleRateHz": 16000, "comparison": compare(source["referenceText"], result["text"]), "segments": result["segments"]}
        assert hashlib.sha256(wav.read_bytes()).hexdigest() == source["sha256"]
        results.append(record)
        with (HERE / f"{prefix}results.jsonl").open("a") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps({"event": "transcribed", "id": source["id"], "text": result["text"], "cer": record["comparison"]["characterErrorRate"]}, ensure_ascii=False), flush=True)
    total_chars = sum(r["comparison"]["referenceCharacters"] for r in results)
    total_distance = sum(r["comparison"]["distance"] for r in results)
    report = {"schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(), "purpose": "Auxiliary independent transcription, not ground-truth speech quality", "modelId": lock["modelId"], "revision": lock["revision"], "decoder": "greedy at temperature 0; beam search is not implemented by mlx-whisper 0.4.3", "settings": settings, "normalization": "NFC letters and numbers only; punctuation and whitespace removed. No synonym, phonetic or grammar correction.", "originalWavFilesModified": False, "clips": len(results), "flaggedClips": sum(r["comparison"]["needsHumanListening"] for r in results), "microCharacterErrorRate": total_distance / total_chars, "peakMlxMemoryBytes": mx.get_peak_memory(), "packages": {p: importlib.metadata.version(p) for p in ["mlx-whisper", "mlx", "numpy", "scipy", "soundfile"]}, "limitations": ["ASR is fallible; discrepancies may be recognition errors rather than TTS errors.", "CER is orthographic character disagreement after stated normalization, not verified phonetic pronunciation error.", "Exact ASR text does not prove accurate pronunciation, naturalness, cuteness or stable speaker identity.", "Source transcript is only used after transcription for comparison; no reference text is supplied as ASR prompt.", f"All {expected_count} files were transcribed once with one model and one fixed decoding configuration."], "results": results}
    (HERE / f"{prefix}results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"event": "complete", "clips": len(results), "flagged": report["flaggedClips"], "microCER": report["microCharacterErrorRate"]}), flush=True)


if __name__ == "__main__":
    main()
