"""Generate new lines from one immutable, selected synthetic voice reference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import time
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / ".local/journey-voice-v3-identity"
REFERENCE = HERE.parent / "samples/round-smile-hello.wav"
TEXTS = {
    "comfort": "천천히 가도 괜찮아. 나는 네 옆에 있을게.",
    "arrival": "와, 도착했다! 여기서 어떤 기억을 만나게 될까?",
}
os.environ["HF_HOME"] = str(CACHE / "hf")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def exclusive_json(path: Path, value: object) -> None:
    with path.open("x") as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write("\n")


def environment() -> dict:
    names = ["mlx-audio", "mlx", "transformers", "numpy", "soundfile"]
    package_versions = {name: importlib.metadata.version(name) for name in names}
    distribution = importlib.metadata.distribution("mlx-audio")
    runtime_file = Path(distribution.locate_file("mlx_audio/tts/models/qwen3_tts/qwen3_tts.py"))
    return {"packages": package_versions, "qwenMlxRuntimeSha256": digest(runtime_file)}


def load_binding(reference: Path, reference_text: str | None, temperature: float) -> dict:
    lock_path = HERE / "model-lock.json"
    lock = json.loads(lock_path.read_text())
    original = json.loads(REFERENCE.with_suffix(".json").read_text())
    reference_sha = digest(reference)
    if reference_sha != original["audioSha256"]:
        raise ValueError("REFERENCE_CHANGED: selected synthetic reference hash disagrees")
    selected_text = original["text"] if reference_text is None else reference_text
    spec = {
        "schemaVersion": 1, "previewId": "nunti-round-smile-preview-v3",
        "scope": "voice preview only; no production or v2 binding replacement",
        "baseModel": {"modelId": lock["modelId"], "revision": lock["revision"],
                      "upstreamModelId": lock["upstreamModelId"],
                      "upstreamRevision": lock["upstreamRevision"],
                      "modelLockSha256": digest(lock_path)},
        "reference": {
            "sourcePath": str(REFERENCE.relative_to(ROOT)),
            "audioSha256": reference_sha, "text": selected_text,
            "textSha256": hashlib.sha256(selected_text.encode()).hexdigest(),
            "voiceDesignModelId": original["modelId"],
            "voiceDesignRevision": original["revision"],
            "voiceDesignMetadataSha256": digest(REFERENCE.with_suffix(".json")),
            "synthetic": True, "realPersonReference": False,
        },
        "generation": {"seed": 20261102, "temperature": temperature, "topP": 0.95,
                       "topK": 50, "repetitionPenalty": 1.5, "maxTokens": 375,
                       "language": "Korean", "mode": "reference audio and exact transcript ICL"},
        "runtime": environment(),
        "postprocessing": "none; raw model waveform only encoded as PCM16 WAV",
    }
    identity_sha = hashlib.sha256(canonical(spec)).hexdigest()
    candidate = {"bindingId": "qvi-" + identity_sha[:32], "bindingSha256": identity_sha, "binding": spec}
    binding_path = HERE / "binding.json"
    if binding_path.exists():
        if json.loads(binding_path.read_text()) != candidate:
            raise ValueError("BINDING_CHANGED: reference, transcript, model, runtime or settings differ")
    else:
        if selected_text != original["text"]:
            raise ValueError("REFERENCE_TEXT_CHANGED: selected reference requires its exact transcript")
        exclusive_json(binding_path, candidate)
    frozen_reference = HERE / "reference.wav"
    if not frozen_reference.exists():
        with frozen_reference.open("xb") as target, reference.open("rb") as source:
            shutil.copyfileobj(source, target)
    if digest(frozen_reference) != reference_sha:
        raise ValueError("FROZEN_REFERENCE_CHANGED")
    return candidate


def expected_provenance(clip_id: str, text: str, binding: dict) -> dict:
    """Derive every repeated identity field from the authoritative binding."""
    spec = binding["binding"]
    reference = spec["reference"]
    return {
        "clipId": clip_id, "previewId": spec["previewId"],
        "bindingId": binding["bindingId"], "bindingSha256": binding["bindingSha256"],
        "baseModelId": spec["baseModel"]["modelId"],
        "baseRevision": spec["baseModel"]["revision"],
        "voiceDesignModelId": reference["voiceDesignModelId"],
        "voiceDesignRevision": reference["voiceDesignRevision"],
        "referenceAudioSha256": reference["audioSha256"], "referenceText": reference["text"],
        "text": text, "textSha256": hashlib.sha256(text.encode()).hexdigest(),
        "audioPath": clip_id + ".wav", "generation": spec["generation"],
        "postprocessing": spec["postprocessing"],
        "device": "Apple Silicon Metal via MLX",
        "humanListeningVerified": False, "voiceIdentityAcrossTextsVerified": False,
    }


def validate_cached_metadata(clip_id: str, text: str, binding: dict, audio: Path, record: dict) -> None:
    for field, expected in expected_provenance(clip_id, text, binding).items():
        if record.get(field) != expected:
            raise ValueError(f"CACHED_PROVENANCE_CHANGED: {clip_id}.{field}")
    if record.get("audioSha256") != digest(audio):
        raise ValueError("CACHED_AUDIO_CHANGED: " + clip_id)
    with wave.open(str(audio), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 24000, "NONE"):
            raise ValueError("CACHED_AUDIO_FORMAT_CHANGED: " + clip_id)
        actual = {"channels": source.getnchannels(), "sampleRateHz": source.getframerate(),
                  "frames": source.getnframes(),
                  "durationSeconds": source.getnframes() / source.getframerate()}
    for field, expected in actual.items():
        if record.get(field) != expected:
            raise ValueError(f"CACHED_AUDIO_METADATA_CHANGED: {clip_id}.{field}")


def cached(clip_id: str, text: str, binding: dict) -> bool:
    audio = HERE / "samples" / (clip_id + ".wav")
    metadata = audio.with_suffix(".json")
    if not audio.exists() and not metadata.exists():
        return False
    if not (audio.exists() and metadata.exists()):
        raise ValueError("PARTIAL_RESULT: refusing to overwrite " + clip_id)
    record = json.loads(metadata.read_text())
    validate_cached_metadata(clip_id, text, binding, audio, record)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--reference-text")
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()
    binding = load_binding(args.reference, args.reference_text, args.temperature)
    todo = []
    for clip_id, text in TEXTS.items():
        if cached(clip_id, text, binding):
            print(json.dumps({"event": "cache-hit", "clipId": clip_id,
                              "bindingId": binding["bindingId"]}), flush=True)
        else:
            todo.append((clip_id, text))
    if not todo:
        print(json.dumps({"event": "all-cached", "modelLoaded": False}), flush=True)
        return
    lock = json.loads((HERE / "model-lock.json").read_text())
    for item in lock["files"]:
        if digest(ROOT / lock["cacheRelativePath"] / item["path"]) != item["sha256"]:
            raise ValueError("MODEL_FILE_CHANGED: " + item["path"])
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model
    start = time.perf_counter()
    print(json.dumps({"event": "loading", "modelId": lock["modelId"]}), flush=True)
    model = load_model(str(ROOT / lock["cacheRelativePath"]))
    load_seconds = time.perf_counter() - start
    print(json.dumps({"event": "loaded", "seconds": load_seconds,
                      "tokenizerHasEncoder": model.speech_tokenizer.has_encoder}), flush=True)
    if not model.speech_tokenizer.has_encoder:
        raise ValueError("Reference ICL requires the speech tokenizer encoder")
    (HERE / "samples").mkdir(exist_ok=True)
    settings = binding["binding"]["generation"]
    for clip_id, text in todo:
        mx.random.seed(settings["seed"])
        started = time.perf_counter()
        print(json.dumps({"event": "generating", "clipId": clip_id}, ensure_ascii=False), flush=True)
        chunks = list(model.generate(
            text=text, ref_audio=str(HERE / "reference.wav"),
            ref_text=binding["binding"]["reference"]["text"], lang_code=settings["language"],
            temperature=settings["temperature"], top_p=settings["topP"], top_k=settings["topK"],
            repetition_penalty=settings["repetitionPenalty"], max_tokens=settings["maxTokens"],
            verbose=False, stream=False,
        ))
        if not chunks:
            raise ValueError("No Base model output")
        samples = np.concatenate([np.asarray(chunk.audio).reshape(-1) for chunk in chunks])
        generation_seconds = time.perf_counter() - started
        if not samples.size or not np.isfinite(samples).all() or not np.max(np.abs(samples)):
            raise ValueError("Invalid or silent waveform")
        audio = HERE / "samples" / (clip_id + ".wav")
        with audio.open("xb") as target:
            sf.write(target, samples, chunks[0].sample_rate, format="WAV", subtype="PCM_16")
        record = {
            **expected_provenance(clip_id, text, binding),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "audioSha256": digest(audio), "sampleRateHz": chunks[0].sample_rate,
            "channels": 1, "frames": int(samples.size), "durationSeconds": samples.size / chunks[0].sample_rate,
            "generationSeconds": generation_seconds, "modelLoadSeconds": load_seconds,
            "rawFloatPeak": float(np.max(np.abs(samples))),
            "samplesAtOrAboveFullScale": int(np.count_nonzero(np.abs(samples) >= 1)),
            "peakMlxMemoryBytes": mx.get_peak_memory(),
        }
        exclusive_json(audio.with_suffix(".json"), record)
        print(json.dumps({"event": "generated", "clipId": clip_id,
                          "durationSeconds": record["durationSeconds"],
                          "generationSeconds": generation_seconds,
                          "peakMlxMemoryBytes": record["peakMlxMemoryBytes"]}), flush=True)
        mx.clear_cache()


if __name__ == "__main__":
    main()
