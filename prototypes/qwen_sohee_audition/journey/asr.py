"""One fixed Whisper-small pass on each of the two new journey WAVs."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "prototypes/voice_audition/asr"))
from transcribe import compare, normalize
os.environ["HF_HOME"] = str(ROOT / ".local/voice-audition-asr/hf")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "asr-results.json"
    if output.exists() or (HERE / "asr-results.jsonl").exists():
        raise SystemExit("Prior ASR exists; inspect it instead of rerunning inference")
    lock = json.loads((ROOT / "prototypes/voice_audition/asr/model-lock.json").read_text())
    sources = []
    for wav in sorted((HERE / "samples").glob("*.wav")):
        record = json.loads(wav.with_suffix(".json").read_text())
        assert digest(wav) == record["audioSha256"]
        sources.append({"clipId": record["clipId"], "audioPath": str(wav.relative_to(HERE)), "audioSha256": record["audioSha256"], "metadataSha256": digest(wav.with_suffix(".json")), "referenceText": record["text"]})
    assert len(sources) == 2
    import mlx.core as mx
    import mlx_whisper
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    settings = {"language": "ko", "task": "transcribe", "temperature": 0.0, "condition_on_previous_text": False, "initial_prompt": None, "word_timestamps": False}
    results = []
    for source in sources:
        wav = HERE / source["audioPath"]
        samples, rate = sf.read(wav, dtype="float32", always_2d=True)
        divisor = math.gcd(rate, 16000)
        audio = resample_poly(samples.mean(axis=1), 16000 // divisor, rate // divisor).astype(np.float32)
        print(json.dumps({"event": "transcribing", "clipId": source["clipId"]}), flush=True)
        started = time.monotonic()
        actual = mlx_whisper.transcribe(audio, path_or_hf_repo=lock["localPath"], verbose=None, **settings)
        comparison = compare(source["referenceText"], actual["text"])
        expected_phrases = [normalize(p) for p in re.split(r"[.!?]+", source["referenceText"]) if normalize(p)]
        normalized = normalize(actual["text"])
        phrase_checks = [{"normalizedExpectedPhrase": p, "recognizedOccurrences": normalized.count(p), "expectedOccurrences": normalize(source["referenceText"]).count(p)} for p in expected_phrases]
        result = {**source, "transcript": actual["text"], "segments": actual["segments"], "asrSeconds": time.monotonic() - started, "comparison": comparison, "asrRecognizedFullEnding": normalized.endswith(normalize("오늘 만난 풍경은 내가 간직할게")), "phraseChecks": phrase_checks, "repeatedPhraseCandidate": any(p["recognizedOccurrences"] > p["expectedOccurrences"] for p in phrase_checks)}
        assert digest(wav) == source["audioSha256"]
        assert digest(wav.with_suffix(".json")) == source["metadataSha256"]
        results.append(result)
        with (HERE / "asr-results.jsonl").open("a") as target:
            target.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(json.dumps({"event": "transcribed", "clipId": source["clipId"], "transcript": actual["text"], "cer": comparison["characterErrorRate"], "asrRecognizedFullEnding": result["asrRecognizedFullEnding"]}, ensure_ascii=False), flush=True)
    report = {"createdAt": datetime.now(timezone.utc).isoformat(), "modelId": lock["modelId"], "revision": lock["revision"], "decoder": "greedy", "settings": settings, "modelReusedWithoutDownload": True, "passesPerAudio": 1, "peakMlxMemoryBytes": mx.get_peak_memory(), "packages": {p: importlib.metadata.version(p) for p in ["mlx-whisper", "mlx", "numpy", "scipy", "soundfile"]}, "sourceFilesUnchanged": True, "limits": ["ASR does not establish naturalness, cuteness or product acceptance.", "ASR can misrecognize or infer missing speech; a recognized ending is not human verification against audible cutoff.", "Reference text is only used after transcription, not as a prompt.", "Phrase occurrence checks compare orthographic text and may flag ASR mistakes."], "results": results}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"event": "complete", "clips": len(results)}), flush=True)


if __name__ == "__main__":
    main()
