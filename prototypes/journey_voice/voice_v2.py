#!/usr/bin/env python3
"""Versioned small-character audition. Does not alter v1 bindings or samples."""
import argparse
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import wave
from download_models import verify_file
from voice_cli import HERE, ROOT, DEFAULT_MODELS, PROVIDER, LOCALE, VoiceError, LocalSynthesizer, atomic_write, canonical, file_lock, load_recipe, read_json, sha, synthesize, validate_binding, validate_recipe, validate_text

STATE_V2 = ROOT / ".local/journey-voice/state-v2"
os.environ.setdefault("NUMBA_CACHE_DIR", str(ROOT / ".local/journey-voice/numba-cache"))
os.environ.setdefault("LIBROSA_CACHE_DIR", str(ROOT / ".local/journey-voice/librosa-cache"))


def bind_v2(recipe, state_dir=STATE_V2):
    recipe = validate_recipe(recipe)
    state_dir = Path(state_dir)
    if state_dir.resolve() == (ROOT / ".local/journey-voice/state").resolve():
        raise VoiceError("v2 must use a separate state directory from v1.")
    catalog = read_json(HERE / "catalog-v2.json")
    lock = read_json(HERE / "model-lock-v2.json")
    path = state_dir / "bindings.json"
    with file_lock(state_dir / "bindings.lock"):
        ledger = read_json(path) if path.exists() else {"schemaVersion": 1, "bindings": {}}
        if ledger.get("schemaVersion") != 1 or not isinstance(ledger.get("bindings"), dict):
            raise VoiceError("Unsupported/corrupt v2 ledger.")
        previous = ledger["bindings"].get(recipe["characterId"])
        if previous:
            validate_binding(previous)
            if previous["journeyId"] != recipe["journeyId"]:
                raise VoiceError("Character already belongs to another journey.")
            if previous.get("candidateVersion") != 2:
                raise VoiceError("Existing binding belongs to another experiment version. No rebinding.")
            return previous
        affect = recipe.get("voiceIntent", {}).get("requested", {}).get("affect")
        preset = catalog["profiles"].get(affect)
        if preset is None:
            raise VoiceError(f"UNBOUND_INTENT: {affect!r}")
        body = {
            "schemaVersion": 1, "candidateVersion": 2, "providerId": PROVIDER, "locale": LOCALE,
            "characterId": recipe["characterId"], "journeyId": recipe["journeyId"],
            "voiceIdentityKey": recipe.get("voiceIntent", {}).get("identityKey"),
            "profileId": preset["profileId"], "speakerId": preset["speakerId"],
            "preset": {"speed": preset["speed"], "steps": preset["steps"]},
            "postprocess": copy.deepcopy(catalog["postprocess"]),
            "catalogId": catalog["catalogId"], "catalogSha256": sha(canonical(catalog)),
            "sourceModelRevision": lock["revision"], "sourceRevision": lock["sourceRevision"],
            "assignmentReason": affect, "qualityStatus": "LISTENING_CANDIDATE_UNEVALUATED",
            "emotionControl": "NOT_IMPLEMENTED_CASTING_INTENT_ONLY",
        }
        binding = dict(body, bindingId="vb-" + sha(canonical(body))[:32])
        ledger["bindings"][recipe["characterId"]] = binding
        atomic_write(path, json.dumps(ledger, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
        return binding


def read_pcm(path):
    import numpy as np
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise VoiceError("Pitch comparison requires mono PCM16.")
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2").astype(np.float32) / 32768, handle.getframerate()


def write_pcm(path, samples, sr):
    import numpy as np
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes((np.clip(samples, -1, 1) * 32767).round().astype("<i2").tobytes())


def signal_metrics(samples, sr):
    import numpy as np
    frame = max(1, int(sr * 0.01))
    energies = [float(np.sqrt(np.mean(samples[i:i+frame] ** 2))) for i in range(0, len(samples), frame)]
    threshold = max(0.002, max(energies) * 0.03)
    active = [i for i, value in enumerate(energies) if value > threshold]
    return {
        "peakAmplitude": round(float(np.max(np.abs(samples))), 6),
        "rmsAmplitude": round(float(np.sqrt(np.mean(samples ** 2))), 6),
        "fullScaleClippedSampleCount": int(np.sum(np.abs(samples) >= 0.999)),
        "firstEnergyAboveThresholdMs": active[0] * 10 if active else None,
        "energyThreshold": round(threshold, 6),
        "interpretation": "Signal measurements only. Onset does not establish first-syllable correctness or human audibility.",
    }


class SynthesizerV2(LocalSynthesizer):
    def __init__(self, model_dir=DEFAULT_MODELS):
        self.model_dir = Path(model_dir)
        self.lock = read_json(HERE / "model-lock-v2.json")
        self._engine = None
        self.runtime = {
            "python": sys.version.split()[0], "onnxruntime": importlib.metadata.version("onnxruntime"),
            "numpy": importlib.metadata.version("numpy"), "librosa": importlib.metadata.version("librosa"),
            "soxr": importlib.metadata.version("soxr"), "executionProvider": "CPUExecutionProvider",
            "intraOpThreads": 2, "interOpThreads": 1, "platform": sys.platform,
        }
        self.asset_hashes = {entry["path"]: verify_file(self.model_dir / entry["path"], entry) for entry in self.lock["files"]}
        if sha((HERE / "vendor/supertonic_helper.py").read_bytes()) != self.lock["helperSha256"]:
            raise VoiceError("Vendored upstream helper changed.")
        self.fingerprint = sha(canonical({"runtime": self.runtime, "modelFiles": self.asset_hashes, "helper": self.lock["helperSha256"], "adapterSha256": sha(Path(__file__).read_bytes()), "coreSha256": sha((HERE / "voice_cli.py").read_bytes())}))

    def render(self, text, binding, output):
        import librosa
        import numpy as np
        settings = binding.get("postprocess")
        if binding.get("candidateVersion") != 2 or not settings:
            raise VoiceError("v2 requires its versioned binding and explicit DSP settings.")
        if settings["type"] != "duration_preserving_pitch_shift" or settings["version"] != self.runtime["librosa"]:
            raise VoiceError("Bound DSP is unavailable. No fallback or silent migration.")
        raw_path = output.with_name(output.name.replace(".generating.wav", ".source.wav"))
        if raw_path.exists():
            raise VoiceError("Orphan raw source already exists. Refusing silent regeneration.")
        base = super().render(text, binding, raw_path)
        raw, sr = read_pcm(raw_path)
        shifted = librosa.effects.pitch_shift(raw, sr=sr, n_steps=settings["semitones"], bins_per_octave=12, res_type=settings["resampler"], scale=False, n_fft=settings["nFft"], hop_length=settings["hopLength"])
        if len(shifted) != len(raw) or not np.all(np.isfinite(shifted)):
            raise VoiceError("Pitch transform changed length or returned nonfinite audio.")
        peak = float(np.max(np.abs(shifted)))
        gain = min(1.0, settings["maxPeak"] / max(peak, 1e-9))
        shifted = shifted * gain
        write_pcm(output, shifted, sr)
        actual, _ = read_pcm(output)
        return {
            **base, "postprocess": settings, "postprocessGain": round(gain, 8),
            "sourceRawAudioCacheName": raw_path.name, "sourceRawAudioSha256": sha(raw_path.read_bytes()),
            "sourceRawSignalMetrics": signal_metrics(raw, sr), "outputSignalMetrics": signal_metrics(actual, sr),
            "peakAmplitude": round(float(np.max(np.abs(actual))), 6),
            "rmsAmplitude": round(float(np.sqrt(np.mean(actual ** 2))), 6),
            "frameCountPreserved": len(actual) == len(raw),
            "subjectiveCutenessAssessed": False, "koreanIntelligibilityAssessed": False,
            "firstSyllableListeningAssessed": False, "dspArtifactsListeningAssessed": False,
        }


def synthesize_v2(recipe, text, state_dir=STATE_V2, engine=None):
    validate_text(text)
    bind_v2(recipe, state_dir)
    engine = engine if engine is not None else SynthesizerV2()
    return synthesize(recipe, text, state_dir=state_dir, engine=engine)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--recipe-index", type=int, default=0)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--text-file", type=Path)
    parser.add_argument("--state-dir", type=Path, default=STATE_V2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    recipe = load_recipe(args.recipe, args.recipe_index)
    text = args.text if args.text is not None else args.text_file.read_bytes().decode("utf-8")
    audio, metadata, hit = synthesize_v2(recipe, text, args.state_dir)
    atomic_write(args.output, audio.read_bytes())
    atomic_write(args.output.with_suffix(".json"), json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    print(json.dumps(dict(metadata, cacheHit=hit, audioPath=str(args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
