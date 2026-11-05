#!/usr/bin/env python3
"""Bind journey characters to a finite local Korean voice catalog and synthesize WAV."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_STATE = ROOT / ".local/journey-voice/state"
DEFAULT_MODELS = ROOT / ".local/journey-voice/models"
PROVIDER = "supertonic3-local-catalog"
LOCALE = "ko-KR"


class VoiceError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VoiceError(f"Unreadable JSON: {path}: {exc}") from exc


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".voice-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate_text(text):
    if not isinstance(text, str) or not text.strip():
        raise VoiceError("Text must contain speech.")
    if len(text) > 100:
        raise VoiceError("Prototype accepts at most 100 characters and 30 seconds.")
    if not re.fullmatch(r"[가-힣ㄱ-ㅎㅏ-ㅣA-Za-z0-9 \t\n.,!?;:'\"()%\-]+", text):
        raise VoiceError("Unsupported character. This prototype accepts Korean, ASCII letters/digits, whitespace and basic punctuation; nothing is silently removed.")
    return text


def validate_recipe(recipe):
    if not isinstance(recipe, dict):
        raise VoiceError("Recipe must be an object.")
    for key in ("characterId", "journeyId"):
        if not isinstance(recipe.get(key), str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", recipe[key]):
            raise VoiceError(f"Invalid {key}.")
    return recipe


def validate_binding(binding):
    if not isinstance(binding, dict) or "bindingId" not in binding:
        raise VoiceError("Corrupt persisted binding.")
    body = {k: v for k, v in binding.items() if k != "bindingId"}
    if binding["bindingId"] != "vb-" + sha(canonical(body))[:32]:
        raise VoiceError("Persisted binding digest mismatch.")
    if binding.get("providerId") != PROVIDER or binding.get("locale") != LOCALE:
        raise VoiceError("Persisted binding provider/locale unsupported.")
    return binding


def bind_recipe(recipe, state_dir=DEFAULT_STATE, catalog=None):
    recipe = validate_recipe(recipe)
    catalog = catalog if catalog is not None else read_json(HERE / "catalog.json")
    lock = read_json(HERE / "model-lock.json")
    state_dir = Path(state_dir)
    ledger_path = state_dir / "bindings.json"
    with file_lock(state_dir / "bindings.lock"):
        ledger = read_json(ledger_path) if ledger_path.exists() else {"schemaVersion": 1, "bindings": {}}
        if ledger.get("schemaVersion") != 1 or not isinstance(ledger.get("bindings"), dict):
            raise VoiceError("Unsupported or corrupt binding ledger.")
        previous = ledger["bindings"].get(recipe["characterId"])
        if previous:
            validate_binding(previous)
            if previous["journeyId"] != recipe["journeyId"]:
                raise VoiceError("Character already belongs to another journey.")
            return previous
        intent = recipe.get("voiceIntent", {})
        requested = intent.get("requested", {}) if isinstance(intent, dict) else {}
        affect = requested.get("affect") if isinstance(requested, dict) else None
        preset = catalog.get("profiles", {}).get(affect)
        if preset is None:
            raise VoiceError(f"UNBOUND_INTENT: no catalog candidate for affect {affect!r}.")
        body = {
            "schemaVersion": 1, "providerId": PROVIDER, "locale": LOCALE,
            "characterId": recipe["characterId"], "journeyId": recipe["journeyId"],
            "voiceIdentityKey": intent.get("identityKey"), "profileId": preset["profileId"],
            "speakerId": preset["speakerId"], "preset": {"speed": preset["speed"], "steps": preset["steps"]},
            "catalogId": catalog["catalogId"], "catalogSha256": sha(canonical(catalog)),
            "sourceModelRevision": lock["revision"], "sourceRevision": lock["sourceRevision"],
            "assignmentReason": affect, "qualityStatus": "LISTENING_CANDIDATE_UNEVALUATED",
            "emotionControl": "NOT_IMPLEMENTED_CASTING_INTENT_ONLY"
        }
        binding = dict(body, bindingId="vb-" + sha(canonical(body))[:32])
        ledger["bindings"][recipe["characterId"]] = binding
        atomic_write(ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
        return binding


class LocalSynthesizer:
    def __init__(self, model_dir=DEFAULT_MODELS):
        self.model_dir = Path(model_dir)
        self.lock = read_json(HERE / "model-lock.json")
        self._engine = None
        self.runtime = {
            "python": sys.version.split()[0],
            "onnxruntime": importlib.metadata.version("onnxruntime"),
            "numpy": importlib.metadata.version("numpy"),
            "executionProvider": "CPUExecutionProvider", "intraOpThreads": 2, "interOpThreads": 1,
            "platform": sys.platform,
        }
        from download_models import verify_file
        self.asset_hashes = {}
        for entry in self.lock["files"]:
            try:
                self.asset_hashes[entry["path"]] = verify_file(self.model_dir / entry["path"], entry)
            except (OSError, ValueError) as exc:
                raise VoiceError(f"Model missing or modified. Run download_models.py: {exc}") from exc
        if sha((HERE / "vendor/supertonic_helper.py").read_bytes()) != self.lock["helperSha256"]:
            raise VoiceError("Vendored helper differs from reviewed pinned source.")
        self.fingerprint = sha(canonical({"runtime": self.runtime, "modelFiles": self.asset_hashes, "helper": self.lock["helperSha256"], "adapterSha256": sha(Path(__file__).read_bytes())}))

    def _load(self):
        if self._engine is not None:
            return
        import onnxruntime as ort
        from vendor import supertonic_helper as helper
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        opts.inter_op_num_threads = 1
        directory = str(self.model_dir / "onnx")
        sessions = helper.load_onnx_all(directory, opts, ["CPUExecutionProvider"])
        self._engine = helper.TextToSpeech(helper.load_cfgs(directory), helper.load_text_processor(directory), *sessions)
        original_sample = self._engine.sample_noisy_latent

        def bounded_sample(duration):
            if not all(math.isfinite(float(d)) and 0 < float(d) <= 30 for d in duration):
                raise VoiceError("Predicted duration exceeds 30-second prototype limit.")
            return original_sample(duration)

        self._engine.sample_noisy_latent = bounded_sample

    def render(self, text, binding, output):
        import numpy as np
        from vendor import supertonic_helper as helper
        self._load()
        speaker = binding["speakerId"]
        path = "voice_styles/" + speaker + ".json"
        if path not in self.asset_hashes:
            raise VoiceError("Bound speaker unavailable. No default speaker substitution.")
        style = helper.load_voice_style([str(self.model_dir / path)])
        model_text = self._engine.text_processor._preprocess_text(text, "ko")
        seed = int(sha(text.encode("utf-8") + canonical(binding))[:8], 16)
        np.random.seed(seed)
        start = time.monotonic()
        audio, duration = self._engine._infer([text], ["ko"], style, binding["preset"]["steps"], binding["preset"]["speed"])
        elapsed = time.monotonic() - start
        sample_rate = self._engine.sample_rate
        samples = audio[0, :int(sample_rate * float(duration[0]))]
        if not np.all(np.isfinite(samples)) or len(samples) == 0 or np.max(np.abs(samples)) < 0.0001:
            raise VoiceError("Synthesizer returned empty, silent or nonfinite audio.")
        pcm = (np.clip(samples, -1, 1) * 32767).round().astype("<i2")
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm.tobytes())
        return {
            "sampleRateHz": sample_rate, "channels": 1, "sampleWidthBytes": 2,
            "durationMs": round(len(samples) * 1000 / sample_rate),
            "inferenceSeconds": round(elapsed, 6), "noiseSeed": seed,
            "upstreamNormalizedModelText": model_text,
            "upstreamTextNormalization": "NFKD, whitespace and punctuation normalization, ko language tags; original text retained separately",
            "peakAmplitude": round(float(np.max(np.abs(samples))), 6),
            "rmsAmplitude": round(float(np.sqrt(np.mean(samples ** 2))), 6),
            "audibleQualityAssessed": False,
        }


def synthesize(recipe, text, state_dir=DEFAULT_STATE, model_dir=DEFAULT_MODELS, engine=None):
    text = validate_text(text)
    binding = bind_recipe(recipe, state_dir)
    engine = engine if engine is not None else LocalSynthesizer(model_dir)
    lock = read_json(HERE / "model-lock.json")
    if binding["sourceModelRevision"] != lock["revision"] or binding["sourceRevision"] != lock["sourceRevision"]:
        raise VoiceError("Persisted voice model revision unavailable. No migration or speaker fallback.")
    text_hash = sha(text.encode("utf-8"))
    cache_key = sha(canonical({"binding": binding, "textSha256": text_hash, "engineFingerprint": engine.fingerprint}))
    cache_dir = Path(state_dir) / "audio-cache"
    audio_path = cache_dir / (cache_key + ".wav")
    metadata_path = cache_dir / (cache_key + ".json")
    with file_lock(cache_dir / (cache_key + ".lock")):
        if metadata_path.exists():
            result = read_json(metadata_path)
            if result.get("cacheKey") != cache_key or result.get("textSha256") != text_hash or result.get("text") != text or result.get("bindingId") != binding["bindingId"]:
                raise VoiceError("Corrupt audio cache metadata.")
            if not audio_path.exists() or sha(audio_path.read_bytes()) != result.get("audioSha256"):
                raise VoiceError("Cached audio missing or hash mismatch. Refusing silent regeneration.")
            return audio_path, result, True
        if audio_path.exists():
            raise VoiceError("Orphan cached audio without provenance. Refusing overwrite.")
        temporary = cache_dir / (cache_key + ".generating.wav")
        try:
            metrics = engine.render(text, binding, temporary)
            result = {
                "schemaVersion": 1, "providerId": PROVIDER, "characterId": binding["characterId"],
                "journeyId": binding["journeyId"], "bindingId": binding["bindingId"],
                "profileId": binding["profileId"], "speakerId": binding["speakerId"], "locale": LOCALE,
                "text": text, "textSha256": text_hash, "cacheKey": cache_key,
                "audioSha256": sha(temporary.read_bytes()), "binding": binding,
                "sourceModelRevision": lock["revision"], "sourceRevision": lock["sourceRevision"],
                "sourceModelRepository": lock["repository"], "sourceModelFileSha256": engine.asset_hashes,
                "sourceHelperSha256": lock["helperSha256"], "runtime": engine.runtime,
                "engineFingerprint": engine.fingerprint, "preset": binding["preset"],
                "reproducibility": "Saved WAV bytes and hashes are authoritative. Seed does not guarantee identical fresh synthesis across runtimes.",
                **metrics,
            }
            os.replace(temporary, audio_path)
            atomic_write(metadata_path, json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
        finally:
            temporary.unlink(missing_ok=True)
        return audio_path, result, False


def load_recipe(path, index=0):
    data = read_json(path)
    if isinstance(data, dict) and "recipes" in data:
        try:
            return validate_recipe(data["recipes"][index])
        except (IndexError, TypeError) as exc:
            raise VoiceError("Invalid recipe index.") from exc
    if index != 0:
        raise VoiceError("Recipe index is only available for a recipes array.")
    return validate_recipe(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--recipe-index", type=int, default=0)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--bind-only", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--text")
    group.add_argument("--text-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        recipe = load_recipe(args.recipe, args.recipe_index)
        if args.bind_only:
            result = bind_recipe(recipe, args.state_dir)
        else:
            if args.text is None and args.text_file is None:
                raise VoiceError("Supply --text or --text-file, or use --bind-only.")
            text = args.text if args.text is not None else args.text_file.read_bytes().decode("utf-8")
            cached_audio, result, hit = synthesize(recipe, text, args.state_dir, args.model_dir)
            if args.output:
                atomic_write(args.output, cached_audio.read_bytes())
                atomic_write(args.output.with_suffix(".json"), json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
            result = dict(result, cacheHit=hit, audioPath=str(args.output or cached_audio))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (VoiceError, OSError, UnicodeError, importlib.metadata.PackageNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
