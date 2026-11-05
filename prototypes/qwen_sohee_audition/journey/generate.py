"""Reuse the pinned Sohee preset on one new text, with no audio reference or DSP."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
UPSTREAM = HERE.parent
SOURCE_METADATA = ROOT / "prototypes/voice_audition/commercial/elevenlabs-anna-journey.json"
os.environ["HF_HOME"] = str(ROOT / ".local/qwen-sohee-audition/hf")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def environment():
    return sorted([item.metadata["Name"], item.version] for item in importlib.metadata.distributions())


def protected_hashes():
    paths = list((UPSTREAM / "samples").glob("*")) + [UPSTREAM / "config.json", UPSTREAM / "model-lock.json", UPSTREAM / "source-refs.json", UPSTREAM / "environment-before.json", ROOT / "prototypes/journey_voice_v3/requirements.lock.txt"]
    return {str(p.relative_to(ROOT)): digest(p) for p in paths if p.is_file()}


def read_expected():
    config = json.loads((UPSTREAM / "config.json").read_text())
    lock = json.loads((UPSTREAM / "model-lock.json").read_text())
    source = json.loads(SOURCE_METADATA.read_text())
    assert hashlib.sha256(source["text"].encode()).hexdigest() == source["textSha256"]
    assert config["referenceAudio"] is None and config["speaker"] == "Sohee"
    specification = importlib.util.spec_from_file_location("original_sohee_generator", UPSTREAM / "generate.py")
    original = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(original)
    items = []
    for condition in config["conditions"]:
        fields = original.expected(condition["id"] + "-journey", {"id": "journey", "text": source["text"]}, condition, config, lock)
        fields.update({"auditionScope": "same-text journey comparison, not product acceptance", "sourceTextMetadataPath": str(SOURCE_METADATA.relative_to(ROOT)), "sourceAudioUsedAsModelInput": False, "referenceAudio": None})
        items.append(fields)
    return config, lock, source, original, items


def main():
    config, lock, source, original, items = read_expected()
    baseline_path = HERE / "baseline.json"
    baseline = {"protectedFiles": protected_hashes(), "packages": environment()}
    if baseline_path.exists():
        assert json.loads(baseline_path.read_text()) == baseline
    else:
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
    folder = HERE / "samples"
    folder.mkdir(exist_ok=True)
    pending = []
    for fields in items:
        wav = folder / fields["audioPath"]
        meta = wav.with_suffix(".json")
        if wav.exists() or meta.exists():
            if not (wav.exists() and meta.exists()):
                raise RuntimeError("Partial result requires inspection: " + fields["clipId"])
            original.validate(wav, json.loads(meta.read_text()), fields)
            print(json.dumps({"event": "cache-hit", "clipId": fields["clipId"]}), flush=True)
        else:
            pending.append((wav, fields))
    if not pending:
        print(json.dumps({"event": "all-cached", "modelLoaded": False}), flush=True)
        return
    for item in lock["files"]:
        assert digest(ROOT / lock["cacheRelativePath"] / item["path"]) == item["sha256"]
    refs = {"modelId": lock["modelId"], "revision": lock["revision"], "sourceModelId": lock["sourceModelId"], "sourceRevision": lock["sourceRevision"], "license": lock["license"], "modelLockPath": str((UPSTREAM / "model-lock.json").relative_to(ROOT)), "modelLockSha256": digest(UPSTREAM / "model-lock.json"), "sourceRefs": json.loads((UPSTREAM / "source-refs.json").read_text()), "sourceTextMetadataPath": str(SOURCE_METADATA.relative_to(ROOT)), "sourceTextMetadataSha256AtGeneration": digest(SOURCE_METADATA), "text": source["text"], "textSha256": source["textSha256"], "conditions": config["conditions"], "generation": config["generation"], "sourceAudioUsedAsModelInput": False, "referenceAudio": None, "newDownloads": 0, "environmentChanged": False}
    refs_path = HERE / "model-refs.json"
    if refs_path.exists():
        assert json.loads(refs_path.read_text()) == refs
    else:
        refs_path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n")
    import mlx.core as mx
    import numpy as np
    import soundfile as sf
    from mlx_audio.tts.utils import load_model
    print(json.dumps({"event": "loading", "modelId": lock["modelId"]}), flush=True)
    load_started = time.monotonic()
    model = load_model(str(ROOT / lock["cacheRelativePath"]))
    load_seconds = time.monotonic() - load_started
    assert model.config.tts_model_type == "custom_voice"
    assert model.config.talker_config.spk_id["sohee"] == lock["speakerId"]
    print(json.dumps({"event": "loaded", "seconds": load_seconds}), flush=True)
    for wav, fields in pending:
        settings = fields["generation"]
        mx.random.seed(settings["seed"])
        print(json.dumps({"event": "generating", "clipId": fields["clipId"]}), flush=True)
        started = time.monotonic()
        chunks = list(model.generate_custom_voice(text=fields["text"], speaker="Sohee", language="Korean", instruct=fields["instruct"], temperature=settings["temperature"], top_p=settings["topP"], top_k=settings["topK"], repetition_penalty=settings["repetitionPenalty"], max_tokens=settings["maxTokens"], stream=False, verbose=False))
        if not chunks:
            raise RuntimeError("No model output")
        values = np.concatenate([np.asarray(chunk.audio).reshape(-1) for chunk in chunks])
        if not values.size or not np.isfinite(values).all() or not np.max(np.abs(values)):
            raise RuntimeError("Invalid or silent waveform")
        with wav.open("xb") as output:
            sf.write(output, values, chunks[0].sample_rate, format="WAV", subtype="PCM_16")
        record = {**fields, "createdAt": datetime.now(timezone.utc).isoformat(), "audioSha256": digest(wav), "sampleRateHz": chunks[0].sample_rate, "channels": 1, "frames": int(values.size), "durationSeconds": values.size / chunks[0].sample_rate, "generationSeconds": time.monotonic() - started, "modelLoadSeconds": load_seconds, "rawFloatPeak": float(np.max(np.abs(values))), "samplesAtOrAboveFullScale": int(np.count_nonzero(np.abs(values) >= 1)), "peakMlxMemoryBytes": mx.get_peak_memory()}
        with wav.with_suffix(".json").open("x") as output:
            json.dump(record, output, ensure_ascii=False, indent=2)
            output.write("\n")
        print(json.dumps({"event": "generated", "clipId": fields["clipId"], "durationSeconds": record["durationSeconds"], "generationSeconds": record["generationSeconds"], "peakMlxMemoryBytes": record["peakMlxMemoryBytes"]}), flush=True)
        mx.clear_cache()
    assert baseline == {"protectedFiles": protected_hashes(), "packages": environment()}


if __name__ == "__main__":
    main()
