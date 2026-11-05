"""Generate native Korean VoiceDesign comparisons, without pitch or speed processing."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TOOLS = ROOT / ".local/journey-voice-v3"
os.environ["HF_HOME"] = str(TOOLS / "hf")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

parser = argparse.ArgumentParser()
parser.add_argument("--style", choices=["round-smile", "bright-pebble", "soft-moss"])
parser.add_argument("--sentence", choices=["hello", "comfort"])
args = parser.parse_args()
config = json.loads((HERE / "styles.json").read_text())
lock = json.loads((HERE / "model-lock.json").read_text())
out = HERE / "samples"
out.mkdir(exist_ok=True)

model = None
for style in config["styles"]:
    if args.style and args.style != style["id"]:
        continue
    for sentence in config["sentences"]:
        if args.sentence and args.sentence != sentence["id"]:
            continue
        clip_id = f'{style["id"]}-{sentence["id"]}'
        wav = out / f"{clip_id}.wav"
        metadata = out / f"{clip_id}.json"
        if wav.exists() or metadata.exists():
            if not (wav.exists() and metadata.exists()):
                raise SystemExit(f"Partial prior result, inspect it before retry: {clip_id}")
            old = json.loads(metadata.read_text())
            if hashlib.sha256(wav.read_bytes()).hexdigest() != old["audioSha256"] or old["text"] != sentence["text"] or old["instruct"] != style["instruct"] or old["generation"] != config["generation"] or old["modelId"] != lock["modelId"] or old["revision"] != lock["revision"] or old["postprocessing"] != config["postprocessing"]:
                raise SystemExit(f"Existing immutable result disagrees: {clip_id}")
            print(json.dumps({"event": "cache-hit", "clipId": clip_id}), flush=True)
            continue
        if model is None:
            import mlx.core as mx
            import numpy as np
            import soundfile as sf
            from mlx_audio.tts.utils import load_model

            print(json.dumps({"event": "loading", "model": lock["modelId"], "revision": lock["revision"]}), flush=True)
            load_start = time.monotonic()
            model = load_model(lock["localPath"])
            print(json.dumps({"event": "loaded", "seconds": time.monotonic() - load_start}), flush=True)
        print(json.dumps({"event": "generating", "clipId": clip_id, "text": sentence["text"]}, ensure_ascii=False), flush=True)
        generation = config["generation"]
        mx.random.seed(generation["seed"])
        started = time.monotonic()
        chunks = list(model.generate_voice_design(text=sentence["text"], instruct=style["instruct"], language=config["language"], temperature=generation["temperature"], top_p=generation["topP"], top_k=generation["topK"], repetition_penalty=generation["repetitionPenalty"], max_tokens=generation["maxTokens"], verbose=False, stream=False))
        if not chunks:
            raise RuntimeError("No model output")
        audio = np.concatenate([np.asarray(chunk.audio).reshape(-1) for chunk in chunks])
        rate = chunks[0].sample_rate
        if not np.isfinite(audio).all() or not audio.size or np.max(np.abs(audio)) == 0:
            raise RuntimeError("Invalid or silent model waveform")
        sf.write(wav, audio, rate, subtype="PCM_16")
        record = {"clipId": clip_id, "createdAt": datetime.now(timezone.utc).isoformat(), "label": style["label"], "text": sentence["text"], "textSha256": hashlib.sha256(sentence["text"].encode()).hexdigest(), "instruct": style["instruct"], "modelId": lock["modelId"], "revision": lock["revision"], "language": config["language"], "generation": generation, "postprocessing": config["postprocessing"], "audioPath": wav.name, "audioSha256": hashlib.sha256(wav.read_bytes()).hexdigest(), "sampleRateHz": rate, "channels": 1, "frames": int(audio.size), "durationSeconds": audio.size / rate, "generationSeconds": time.monotonic() - started, "rawFloatPeak": float(np.max(np.abs(audio))), "peakMemoryBytes": mx.get_peak_memory(), "packages": {name: importlib.metadata.version(name) for name in ["mlx-audio", "mlx", "transformers", "numpy", "soundfile"]}, "humanListeningVerified": False, "voiceIdentityAcrossTextsVerified": False}
        metadata.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"event": "generated", "clipId": clip_id, "duration": record["durationSeconds"], "generationSeconds": record["generationSeconds"], "peakMemoryBytes": record["peakMemoryBytes"]}), flush=True)
        mx.clear_cache()
