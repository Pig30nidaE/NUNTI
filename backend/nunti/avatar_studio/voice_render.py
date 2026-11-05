"""Offline, immutable character voice assets using the existing pinned MLX cache.

The web process imports this module without importing MLX. A separate CLI process
owns Metal. One file lock serializes all voice jobs; image jobs must be scheduled
separately by the application to avoid GPU memory contention.
"""

from __future__ import annotations

import fcntl
import gc
import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import tempfile
import time
import uuid
import wave
from array import array
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .voice_design import canonical, validate_voice_plan

ROOT = Path(__file__).resolve().parents[3]
VOICE_MODEL_LOCK = ROOT / "prototypes/journey_voice_v3/model-lock.json"
BASE_MODEL_LOCK = ROOT / "prototypes/journey_voice_v3/identity/model-lock.json"
VOICE_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
VOICE_REVISION = "f90d617701d9f7f4ca499291e0b57f2b3c2fd2ee"
BASE_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
BASE_REVISION = "e7dd0585652209fa0d7783659aad4e8a324de11c"
PYTHON = ROOT / ".local/journey-voice-v3/venv/bin/python"
PROVIDER = "LOCAL_QWEN_VOICE_DESIGN"
SETTINGS = {"temperature": 0.7, "top_p": 0.95, "top_k": 50, "repetition_penalty": 1.05}
QUALITY_VERSION = "conversational-duration-and-bounded-retry-1"


def speech_duration_limits(text: str) -> tuple[int, int]:
    """Bound short companion utterances; this does not certify pronunciation."""
    letters = sum(character.isalnum() for character in text)
    return max(1000, letters * 40), min(40000, max(14000, letters * 420))


def validate_speech_duration(text: str, duration_ms: int) -> None:
    minimum, maximum = speech_duration_limits(text)
    if duration_ms < minimum:
        raise ValueError("VOICE_SPEECH_TOO_SHORT")
    if duration_ms > maximum:
        raise ValueError("VOICE_SPEECH_TOO_LONG")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _model_info(base=False):
    lock_path = BASE_MODEL_LOCK if base else VOICE_MODEL_LOCK
    lock = json.loads(lock_path.read_text())
    expected = (BASE_MODEL, BASE_REVISION) if base else (VOICE_MODEL, VOICE_REVISION)
    if (lock["modelId"], lock["revision"]) != expected:
        raise ValueError("VOICE_MODEL_PIN_CHANGED")
    cache = (
        ROOT / lock["cacheRelativePath"]
        if base
        else ROOT
        / ".local/journey-voice-v3/hf/hub"
        / ("models--" + VOICE_MODEL.replace("/", "--"))
        / "snapshots"
        / VOICE_REVISION
    )
    return lock, cache


def runtime_status() -> dict:
    """Cheap availability check; actual rendering verifies every model file hash."""
    try:
        _, cache = _model_info()
        available = PYTHON.is_file() and (cache / "config.json").is_file()
    except (OSError, KeyError, ValueError):
        available = False
    return {
        "available": available,
        "provider": PROVIDER,
        "modelId": VOICE_MODEL,
        "revision": VOICE_REVISION,
        "apiKeyRequired": False,
        "automaticPlayback": False,
    }


def voice_available() -> bool:
    return runtime_status()["available"]


def inspect_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as source:
        shape = (
            source.getframerate(),
            source.getnchannels(),
            source.getsampwidth(),
            source.getcomptype(),
        )
        if shape != (24000, 1, 2, "NONE"):
            raise ValueError("VOICE_WAV_FORMAT_INVALID")
        frames = source.getnframes()
        if not 2400 <= frames <= 24000 * 45:
            raise ValueError("VOICE_WAV_DURATION_INVALID")
        raw = source.readframes(frames)
    pcm = array("h", raw)
    if len(pcm) != frames or not any(pcm):
        raise ValueError("VOICE_WAV_EMPTY")
    if os.sys.byteorder != "little":
        pcm.byteswap()
    return {
        "sampleRateHz": 24000,
        "channels": 1,
        "sampleWidthBytes": 2,
        "frames": frames,
        "durationMs": round(frames / 24),
        "peakPcm": max(abs(n) for n in pcm),
        "fullScaleSamples": sum(n in (-32768, 32767) for n in pcm),
        "audioSha256": sha256(path),
        "bytes": path.stat().st_size,
    }


@contextmanager
def _gpu_lock():
    path = ROOT / ".local/avatar-quality-v4/local-image/inference.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        # A crashed worker releases flock automatically. Avoid an unbounded web job.
        end = time.monotonic() + 300
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= end:
                    raise TimeoutError("VOICE_GPU_BUSY") from exc
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class LocalVoiceRenderer:
    """Keep at most one pinned model in memory; requests reuse immutable PCM assets."""

    def __init__(self):
        self._model = None
        self._base = None

    def _load(self, base=False):
        if self._model is not None and self._base == base:
            return self._model
        import mlx.core as mx

        self._model = None
        gc.collect()
        mx.clear_cache()
        lock, cache = _model_info(base)
        for item in lock["files"]:
            path = cache / item["path"]
            if (
                not path.is_file()
                or path.stat().st_size != item["bytes"]
                or sha256(path) != item["sha256"]
            ):
                raise ValueError("VOICE_MODEL_FILE_CHANGED: " + item["path"])
        os.environ.update(
            {
                "HF_HUB_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "TOKENIZERS_PARALLELISM": "false",
            }
        )
        from mlx_audio.tts.utils import load_model

        self._model = load_model(str(cache))
        self._base = base
        if self._model.config.tts_model_type != ("base" if base else "voice_design"):
            raise ValueError("VOICE_MODEL_TYPE_CHANGED")
        return self._model

    def render(self, plan: dict, output_dir: Path, text: str | None = None) -> dict:
        validate_voice_plan(plan)
        text = plan["greeting"] if text is None else text
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > 180
            or any(ord(c) < 32 for c in text)
        ):
            raise ValueError("VOICE_TEXT_INVALID")
        # Lock includes cache inspection/publication: simultaneous equal jobs converge.
        with _gpu_lock():
            return self._render_locked(plan, Path(output_dir), text)

    def _render_locked(self, plan, output_dir, text):
        text_sha = hashlib.sha256(text.encode()).hexdigest()
        character_dir = output_dir / plan["profileId"]
        clip_dir = character_dir / text_sha
        audio = clip_dir / "audio.wav"
        metadata = clip_dir / "metadata.json"
        base = text != plan["greeting"]
        reference = None
        if base:
            # This is our own generated synthetic source, never uploaded human speech.
            reference = self._render_locked(plan, output_dir, plan["greeting"])
        expected = {
            "profileId": plan["profileId"],
            "text": text,
            "textSha256": text_sha,
            "planSha256": hashlib.sha256(canonical(plan).encode()).hexdigest(),
            "modelId": BASE_MODEL if base else VOICE_MODEL,
            "revision": BASE_REVISION if base else VOICE_REVISION,
            "referenceAudioSha256": reference["audioSha256"] if reference else None,
        }
        if clip_dir.exists():
            if not audio.is_file() or not metadata.is_file():
                raise ValueError("VOICE_CACHE_INCOMPLETE")
            record = json.loads(metadata.read_text())
            if any(record.get(k) != v for k, v in expected.items()):
                raise ValueError("VOICE_CACHE_BINDING_CHANGED")
            actual = inspect_wav(audio)
            if any(record.get(k) != v for k, v in actual.items()):
                raise ValueError("VOICE_CACHE_AUDIO_CHANGED")
            # An older completed asset is never silently replaced by a new voice.
            validate_speech_duration(text, actual["durationMs"])
            return {
                **record,
                "audioPath": str(audio.resolve()),
                "cacheHit": True,
                "qualityVersionCurrent": QUALITY_VERSION,
                "qualityChecksAppliedOnRead": [
                    "WAV_HASH",
                    "PCM_FORMAT",
                    "CONVERSATIONAL_DURATION_BOUND",
                ],
            }
        model = self._load(base)
        import mlx.core as mx
        import numpy as np
        import soundfile as sf

        character_dir.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix=".pending-", dir=character_dir))
        (temp / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        (temp / "attempts").mkdir()
        attempts = []
        started = time.monotonic()
        try:
            for attempt in range(3):
                generation_seed = (
                    plan["seed"]
                    if attempt == 0
                    else int(
                        hashlib.sha256(
                            f"{plan['profileId']}:{text_sha}:attempt:{attempt}".encode()
                        ).hexdigest()[:8],
                        16,
                    )
                )
                settings = {
                    **SETTINGS,
                    "temperature": round(0.7 - 0.1 * attempt, 2),
                    "repetition_penalty": round((1.5 if base else 1.05) + 0.1 * attempt, 2),
                    "max_tokens": math.ceil(speech_duration_limits(text)[1] / 80) + 1,
                }
                mx.random.seed(generation_seed)
                if base:
                    chunks = list(
                        model.generate(
                            text=text,
                            ref_audio=reference["audioPath"],
                            ref_text=plan["greeting"],
                            lang_code="Korean",
                            **settings,
                            stream=False,
                            verbose=False,
                        )
                    )
                else:
                    chunks = list(
                        model.generate_voice_design(
                            text=text,
                            instruct=plan["instruct"],
                            language="Korean",
                            **settings,
                            stream=False,
                            verbose=False,
                        )
                    )
                evidence = {"attempt": attempt + 1, "seed": generation_seed, "settings": settings}
                try:
                    if len(chunks) != 1 or chunks[0].sample_rate != 24000:
                        raise ValueError("VOICE_MODEL_OUTPUT_INVALID")
                    result = chunks[0]
                    samples = np.asarray(result.audio).reshape(-1)
                    if (
                        not samples.size
                        or not np.isfinite(samples).all()
                        or not np.max(np.abs(samples))
                    ):
                        raise ValueError("VOICE_MODEL_OUTPUT_SILENT")
                    candidate = temp / "attempts" / f"{attempt + 1:02d}.wav"
                    sf.write(candidate, samples, 24000, subtype="PCM_16")
                    evidence.update(
                        tokenCount=int(result.token_count),
                        audioSha256=sha256(candidate),
                        durationMs=round(samples.size / 24),
                        file=str(candidate.relative_to(temp)),
                    )
                    if not 0 < result.token_count < settings["max_tokens"]:
                        raise ValueError("VOICE_TOKEN_LIMIT_REACHED")
                    actual = inspect_wav(candidate)
                    validate_speech_duration(text, actual["durationMs"])
                except ValueError as exc:
                    evidence["rejectedReason"] = str(exc)
                    attempts.append(evidence)
                    (temp / "attempts.json").write_text(
                        json.dumps(attempts, ensure_ascii=False, indent=2) + "\n"
                    )
                    mx.clear_cache()
                    continue
                evidence["accepted"] = True
                attempts.append(evidence)
                shutil.copyfile(candidate, temp / "audio.wav")
                break
            else:
                rejected = character_dir / ("rejected-" + text_sha + "-" + uuid.uuid4().hex)
                temp.rename(rejected)
                raise ValueError(
                    "VOICE_QUALITY_RETRIES_EXHAUSTED: " + attempts[-1]["rejectedReason"]
                )
            record = {
                **expected,
                **actual,
                "provider": PROVIDER,
                "status": "READY",
                "newVoiceGenerated": True,
                "synthetic": True,
                "realPersonReference": False,
                "automaticPlayback": False,
                "humanListeningVerified": False,
                "speakerUniquenessVerified": False,
                "voiceIdentityAcrossTextsVerified": False,
                "method": "SYNTHETIC_REFERENCE_ICL" if base else "TEXT_TO_VOICE_DESIGN",
                "generationSeconds": round(time.monotonic() - started, 3),
                "tokenCount": int(result.token_count),
                "settings": settings,
                "seed": generation_seed,
                "planSeed": plan["seed"],
                "attempts": attempts,
                "qualityVersion": QUALITY_VERSION,
                "qualityChecks": [
                    "EOS_BEFORE_TOKEN_LIMIT",
                    "NON_SILENT_FINITE_PCM",
                    "CONVERSATIONAL_DURATION_BOUND",
                ],
                "postprocessing": "none; raw float waveform encoded as PCM16 WAV",
                "createdAt": datetime.now(UTC).isoformat(),
                "packages": {
                    n: importlib.metadata.version(n)
                    for n in ("mlx", "mlx-audio", "numpy", "soundfile")
                },
                "license": "Apache-2.0 model / MIT MLX-Audio",
                "role": plan["role"],
            }
            (temp / "metadata.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n"
            )
            temp.rename(clip_dir)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
        mx.clear_cache()
        return {**record, "audioPath": str(audio.resolve()), "cacheHit": False}


def render_voice(plan: dict, output_dir: Path, text: str | None = None) -> dict:
    return LocalVoiceRenderer().render(plan, output_dir, text)
