"""Audition real Korean V3 output without pitch, speed, or denoise effects."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / ".local/chatterbox-audition"
LOCK = json.loads((HERE / "model-lock.json").read_text())
TEXTS = {
    "hello": "안녕하세요. 오늘의 여행도 함께할게요.",
    "comfort": "천천히 가도 괜찮아. 나는 네 옆에 있을게.",
}
SEED = 20261102


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["mps", "cpu"], default="mps")
    parser.add_argument("--conditions", choices=["builtin", "qwen-reference", "both"], default="both")
    args = parser.parse_args()
    os.environ.setdefault("HF_HOME", str(CACHE / "hf"))
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("PKUSEG_HOME", str(CACHE / "pkuseg"))
    # Upstream's Cangjie helper asks for "main" even with from_local().
    # Bind that private offline cache reference to the same pinned model revision.
    hf_repo = CACHE / "hf/hub/models--ResembleAI--chatterbox"
    snapshot = hf_repo / "snapshots" / LOCK["modelRevision"]
    snapshot.mkdir(parents=True, exist_ok=True)
    (hf_repo / "refs").mkdir(exist_ok=True)
    (hf_repo / "refs/main").write_text(LOCK["modelRevision"])
    cangjie = snapshot / "Cangjie5_TC.json"
    if not cangjie.exists():
        cangjie.symlink_to(CACHE / "model/Cangjie5_TC.json")

    import numpy as np
    import soundfile as sf
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS, punc_norm

    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS requested but unavailable; do not silently change device")
    sample_dir = HERE / "samples"
    sample_dir.mkdir(exist_ok=True)
    reference = ROOT / "prototypes/journey_voice_v3/samples/round-smile-hello.wav"
    reference_meta = reference.with_suffix(".json")
    if args.conditions != "builtin":
        reference_info = json.loads(reference_meta.read_text())
        if file_hash(reference) != reference_info["audioSha256"]:
            raise ValueError("Qwen synthetic reference hash mismatch")

    start = time.perf_counter()
    print("LOADING", args.device, flush=True)
    model = ChatterboxMultilingualTTS.from_local(CACHE / "model", device=args.device, t3_model="v3")
    if args.device == "mps":
        torch.mps.synchronize()
    load_seconds = time.perf_counter() - start
    print("LOADED", round(load_seconds, 3), flush=True)
    packages = {name: importlib.metadata.version(name) for name in [
        "chatterbox-tts", "torch", "torchaudio", "transformers", "numpy",
        "soundfile", "resemble-perth", "safetensors", "librosa",
    ]}
    summary = {
        "schemaVersion": 1, "modelId": LOCK["modelId"],
        "modelRevision": LOCK["modelRevision"], "codeRevision": LOCK["codeRevision"],
        "variant": LOCK["variant"], "device": args.device,
        "platform": platform.platform(), "machine": platform.machine(),
        "python": platform.python_version(), "packages": packages,
        "modelLoadSeconds": load_seconds, "clips": [],
        "humanListeningVerified": False, "voiceIdentityAcrossTextsVerified": False,
        "postprocessing": "none; raw watermarked model waveform only encoded as PCM16 WAV",
        "watermark": "official PerThImplicitWatermarker applied by upstream generate",
    }
    conditions = ["builtin", "qwen-reference"] if args.conditions == "both" else [args.conditions]
    for condition in conditions:
        for text_id, text in TEXTS.items():
            clip_id = condition + "-" + text_id
            target = sample_dir / (clip_id + ".wav")
            meta_path = target.with_suffix(".json")
            if target.exists() or meta_path.exists():
                raise FileExistsError(f"Refusing to overwrite evidence: {target}")
            random.seed(SEED)
            np.random.seed(SEED)
            torch.manual_seed(SEED)
            if args.device == "mps":
                torch.mps.manual_seed(SEED)
            kwargs = {
                "language_id": "ko", "exaggeration": 0.4, "cfg_weight": 0.5,
                "temperature": 0.8, "repetition_penalty": 1.2, "min_p": 0.05, "top_p": 1.0,
            }
            if condition == "qwen-reference":
                kwargs["audio_prompt_path"] = str(reference)
            print("GENERATING", clip_id, flush=True)
            generation_start = time.perf_counter()
            wav = model.generate(text, **kwargs)
            if args.device == "mps":
                torch.mps.synchronize()
            generation_seconds = time.perf_counter() - generation_start
            samples = wav.squeeze(0).detach().cpu().numpy()
            if not np.isfinite(samples).all() or not samples.size:
                raise ValueError("Empty or non-finite generated waveform")
            sf.write(target, samples, model.sr, subtype="PCM_16")
            metadata = {
                "clipId": clip_id, "createdAt": datetime.now(timezone.utc).isoformat(),
                "modelId": LOCK["modelId"], "modelRevision": LOCK["modelRevision"],
                "codeRevision": LOCK["codeRevision"], "variant": LOCK["variant"],
                "condition": condition, "text": text,
                "textSha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "upstreamNormalizedText": punc_norm(text), "languageId": "ko",
                "generation": {"seed": SEED, **{k: v for k, v in kwargs.items() if k != "audio_prompt_path"}},
                "generationSeconds": generation_seconds, "device": args.device,
                "audioPath": target.name, "audioSha256": file_hash(target),
                "sampleRateHz": model.sr, "channels": 1, "frames": int(samples.size),
                "durationSeconds": samples.size / model.sr,
                "rawFloatPeak": float(np.max(np.abs(samples))),
                "rawFloatRms": float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))),
                "samplesAtOrAboveFullScale": int(np.count_nonzero(np.abs(samples) >= 1)),
                "packages": packages, "postprocessing": summary["postprocessing"],
                "humanListeningVerified": False, "voiceIdentityAcrossTextsVerified": False,
            }
            if condition == "qwen-reference":
                metadata["syntheticReference"] = {
                    "path": str(reference.relative_to(ROOT)), "audioSha256": file_hash(reference),
                    "metadataSha256": file_hash(reference_meta),
                    "modelId": reference_info["modelId"], "modelRevision": reference_info["revision"],
                    "text": reference_info["text"], "instruct": reference_info["instruct"],
                    "realPersonReference": False,
                }
            if args.device == "mps":
                metadata["mpsCurrentAllocatedBytes"] = torch.mps.current_allocated_memory()
                metadata["mpsDriverAllocatedBytes"] = torch.mps.driver_allocated_memory()
            write_json(meta_path, metadata)
            summary["clips"].append({"clipId": clip_id, "metadataPath": str(meta_path.relative_to(HERE)),
                                     "audioSha256": metadata["audioSha256"],
                                     "durationSeconds": metadata["durationSeconds"],
                                     "generationSeconds": generation_seconds})
            write_json(HERE / "runtime-summary.json", summary)
            print("SAVED", clip_id, metadata["durationSeconds"], generation_seconds, flush=True)
    print("FINISHED", len(summary["clips"]), flush=True)


if __name__ == "__main__":
    main()
