"""Audition only the native Korean preset, without voice design or reference cloning."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / ".local/qwen-sohee-audition"
os.environ["HF_HOME"] = str(CACHE / "hf")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def expected(clip_id: str, sentence: dict, condition: dict, config: dict, lock: dict) -> dict:
    names = ["mlx-audio", "mlx", "transformers", "numpy", "soundfile"]
    runtime_path = Path(importlib.metadata.distribution("mlx-audio").locate_file("mlx_audio/tts/models/qwen3_tts/qwen3_tts.py"))
    return {"clipId": clip_id, "text": sentence["text"],
            "textSha256": hashlib.sha256(sentence["text"].encode()).hexdigest(),
            "condition": condition["id"], "instruct": condition["instruct"],
            "modelId": lock["modelId"], "revision": lock["revision"],
            "modelLockSha256": digest(HERE / "model-lock.json"),
            "configSha256": digest(HERE / "config.json"),
            "speaker": config["speaker"], "speakerId": lock["speakerId"],
            "language": config["language"], "languageId": lock["languageId"],
            "referenceAudio": None, "mode": "native CustomVoice preset; no VoiceDesign or Base",
            "generation": config["generation"], "postprocessing": config["postprocessing"],
            "audioPath": clip_id + ".wav", "humanListeningVerified": False,
            "productQualityApproved": False, "device": "Apple Silicon Metal via MLX",
            "runtimePackages": {name: importlib.metadata.version(name) for name in names},
            "runtimeSourceSha256": digest(runtime_path)}


def validate(audio: Path, record: dict, fields: dict) -> None:
    for key, value in fields.items():
        if record.get(key) != value:
            raise ValueError("CACHED_PROVENANCE_CHANGED: " + key)
    if digest(audio) != record.get("audioSha256"):
        raise ValueError("CACHED_AUDIO_CHANGED")
    with wave.open(str(audio), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 24000):
            raise ValueError("CACHED_AUDIO_FORMAT_CHANGED")
        facts = {"sampleRateHz": source.getframerate(), "channels": source.getnchannels(),
                 "frames": source.getnframes(), "durationSeconds": source.getnframes() / source.getframerate()}
    for key, value in facts.items():
        if record.get(key) != value:
            raise ValueError("CACHED_AUDIO_METADATA_CHANGED: " + key)


def main() -> None:
    config = json.loads((HERE / "config.json").read_text())
    lock = json.loads((HERE / "model-lock.json").read_text())
    assert config["referenceAudio"] is None
    todo = []
    for condition in config["conditions"]:
        for sentence in config["sentences"]:
            clip_id = condition["id"] + "-" + sentence["id"]
            fields = expected(clip_id, sentence, condition, config, lock)
            audio = HERE / "samples" / (clip_id + ".wav")
            metadata = audio.with_suffix(".json")
            if audio.exists() or metadata.exists():
                if not (audio.exists() and metadata.exists()):
                    raise ValueError("PARTIAL_RESULT: " + clip_id)
                validate(audio, json.loads(metadata.read_text()), fields)
                print(json.dumps({"event": "cache-hit", "clipId": clip_id}), flush=True)
            else:
                todo.append((audio, fields))
    if not todo:
        print(json.dumps({"event": "all-cached", "modelLoaded": False}), flush=True)
        return
    for item in lock["files"]:
        if digest(ROOT / lock["cacheRelativePath"] / item["path"]) != item["sha256"]:
            raise ValueError("MODEL_FILE_CHANGED: " + item["path"])
    inventory = sorted([item.metadata["Name"], item.version] for item in importlib.metadata.distributions())
    baseline = {"packages": inventory, "existingRequirementsLockSha256": digest(ROOT / "prototypes/journey_voice_v3/requirements.lock.txt")}
    baseline_path = HERE / "environment-before.json"
    if baseline_path.exists():
        assert json.loads(baseline_path.read_text()) == baseline
    else:
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model
    print(json.dumps({"event": "loading", "modelId": lock["modelId"]}), flush=True)
    started = time.perf_counter()
    model = load_model(str(ROOT / lock["cacheRelativePath"]))
    load_seconds = time.perf_counter() - started
    assert model.config.tts_model_type == "custom_voice"
    assert "sohee" in [speaker.lower() for speaker in model.supported_speakers]
    assert model.config.talker_config.spk_id["sohee"] == lock["speakerId"]
    print(json.dumps({"event": "loaded", "seconds": load_seconds,
                      "speaker": "Sohee", "speakerId": lock["speakerId"],
                      "supportedSpeakers": model.supported_speakers}), flush=True)
    (HERE / "samples").mkdir(exist_ok=True)
    for audio, fields in todo:
        settings = fields["generation"]
        mx.random.seed(settings["seed"])
        print(json.dumps({"event": "generating", "clipId": fields["clipId"]}), flush=True)
        started = time.perf_counter()
        chunks = list(model.generate_custom_voice(
            text=fields["text"], speaker="Sohee", language="Korean", instruct=fields["instruct"],
            temperature=settings["temperature"], top_p=settings["topP"], top_k=settings["topK"],
            repetition_penalty=settings["repetitionPenalty"], max_tokens=settings["maxTokens"],
            stream=False, verbose=False,
        ))
        if not chunks:
            raise ValueError("No preset output")
        samples = np.concatenate([np.asarray(chunk.audio).reshape(-1) for chunk in chunks])
        generation_seconds = time.perf_counter() - started
        if not samples.size or not np.isfinite(samples).all() or not np.max(np.abs(samples)):
            raise ValueError("Invalid or silent model waveform")
        with audio.open("xb") as target:
            sf.write(target, samples, chunks[0].sample_rate, format="WAV", subtype="PCM_16")
        record = {**fields, "createdAt": datetime.now(timezone.utc).isoformat(),
                  "audioSha256": digest(audio), "sampleRateHz": chunks[0].sample_rate,
                  "channels": 1, "frames": int(samples.size),
                  "durationSeconds": samples.size / chunks[0].sample_rate,
                  "generationSeconds": generation_seconds, "modelLoadSeconds": load_seconds,
                  "rawFloatPeak": float(np.max(np.abs(samples))),
                  "samplesAtOrAboveFullScale": int(np.count_nonzero(np.abs(samples) >= 1)),
                  "peakMlxMemoryBytes": mx.get_peak_memory()}
        with audio.with_suffix(".json").open("x") as target:
            json.dump(record, target, ensure_ascii=False, indent=2)
            target.write("\n")
        print(json.dumps({"event": "generated", "clipId": fields["clipId"],
                          "durationSeconds": record["durationSeconds"],
                          "generationSeconds": generation_seconds,
                          "peakMlxMemoryBytes": record["peakMlxMemoryBytes"]}), flush=True)
        mx.clear_cache()


if __name__ == "__main__":
    main()
