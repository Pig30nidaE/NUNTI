"""Pinned, offline Sohee synthesis. Inspecting identity never imports the GPU runtime."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import threading
import time
import wave

ROOT = Path(__file__).resolve().parents[2]
MODEL_LOCK = ROOT / "prototypes/qwen_sohee_audition/model-lock.json"
REQUIREMENTS_LOCK = ROOT / "prototypes/journey_voice_v3/requirements.lock.txt"
MODEL_LOCK_SHA256 = "0563bb1b7eeec13c116698e21c6cecb91c807f1e1e38bf35f802c7f6b211d0f1"
REQUIREMENTS_LOCK_SHA256 = "56e6df439bde9b9a26ba8d15b2f514e9c0e094a6ee4f05e3457080f90c2a7469"
QWEN_RUNTIME_SHA256 = "cf264ff51fa16c232cca5ded3ce052af6f4f1137d1371b86ba9f4e2a1a526f0a"
GENERATION = {"temperature": 0.7, "topP": 0.95, "topK": 50, "repetitionPenalty": 1.05, "maxTokens": 375}
MAX_TEXT_CHARACTERS = 100
MAX_DURATION_MS = 30000


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _canonical(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SoheeSynthesizer:
    """Use the existing 1.7B CustomVoice cache without downloads, references or DSP.

    ``identity``, ``fingerprint`` and ``model_loaded`` are read-only properties.
    Construct with the existing journey-voice-v3 Python environment. The caller
    prepares the output directory; render creates exactly one new WAV file.
    Calls on one instance are serialized because MLX sampling uses shared RNG.
    Use one instance in the orchestrator, not simultaneous GPU workers.
    """

    def __init__(self) -> None:
        if _sha256(MODEL_LOCK) != MODEL_LOCK_SHA256:
            raise ValueError("PINNED_MODEL_LOCK_CHANGED")
        if _sha256(REQUIREMENTS_LOCK) != REQUIREMENTS_LOCK_SHA256:
            raise ValueError("PINNED_REQUIREMENTS_LOCK_CHANGED")
        self._lock = json.loads(MODEL_LOCK.read_text())
        if (self._lock["modelId"], self._lock["revision"], self._lock["speaker"], self._lock["speakerId"], self._lock["languageId"]) != (
            "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
            "41d3337e8b7f2843a75841595fc14e4b9a7a4b96", "Sohee", 2864, 2064,
        ):
            raise ValueError("PINNED_MODEL_IDENTITY_CHANGED")
        package_pins = {}
        for line in REQUIREMENTS_LOCK.read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            name, expected_version = line.split("==", 1)
            actual = importlib.metadata.version(name)
            if actual != expected_version:
                raise ValueError(f"PINNED_RUNTIME_PACKAGE_CHANGED: {name}")
            package_pins[name] = actual
        distribution = importlib.metadata.distribution("mlx-audio")
        self._runtime_path = Path(distribution.locate_file("mlx_audio/tts/models/qwen3_tts/qwen3_tts.py"))
        if _sha256(self._runtime_path) != QWEN_RUNTIME_SHA256:
            raise ValueError("PINNED_QWEN_RUNTIME_CHANGED")
        self._identity = {
            "providerId": "qwen3-tts-sohee-local",
            "modelId": self._lock["modelId"], "revision": self._lock["revision"],
            "speaker": "Sohee", "speakerId": 2864,
            "language": "Korean", "languageId": 2064,
            "generation": dict(GENERATION),
            "defaults": {"maxTextCharacters": MAX_TEXT_CHARACTERS, "maxDurationMs": MAX_DURATION_MS, "sampleRateHz": 24000, "channels": 1, "sampleWidthBytes": 2, "referenceAudio": None, "postprocessing": "none; raw waveform only encoded as PCM16 WAV"},
            "modelLockSha256": MODEL_LOCK_SHA256,
            "runtimePin": {"requirementsLockSha256": REQUIREMENTS_LOCK_SHA256, "qwenCodeSha256": QWEN_RUNTIME_SHA256, "packages": package_pins},
        }
        self._fingerprint = hashlib.sha256(_canonical({"identity": self._identity, "adapterSha256": _sha256(Path(__file__))}).encode("utf-8")).hexdigest()
        self._model = None
        self._render_lock = threading.Lock()

    @property
    def identity(self) -> dict:
        """A detached identity dictionary; per-journey seed/direction are excluded."""
        return deepcopy(self._identity)

    @property
    def fingerprint(self) -> str:
        """SHA-256 of canonical identity plus this adapter's exact source hash."""
        return self._fingerprint

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    def _ensure_model(self) -> float:
        if self._model is not None:
            return 0.0
        if _sha256(MODEL_LOCK) != MODEL_LOCK_SHA256 or _sha256(self._runtime_path) != QWEN_RUNTIME_SHA256:
            raise ValueError("PIN_CHANGED_BEFORE_MODEL_LOAD")
        cache = ROOT / self._lock["cacheRelativePath"]
        for item in self._lock["files"]:
            path = cache / item["path"]
            if not path.is_file() or path.stat().st_size != item["bytes"] or _sha256(path) != item["sha256"]:
                raise ValueError("PINNED_MODEL_FILE_CHANGED: " + item["path"])
        os.environ["HF_HOME"] = str(ROOT / ".local/qwen-sohee-audition/hf")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        from mlx_audio.tts.utils import load_model
        started = time.monotonic()
        model = load_model(str(cache))
        if model.config.tts_model_type != "custom_voice" or model.config.talker_config.spk_id.get("sohee") != 2864 or model.sample_rate != 24000:
            raise ValueError("LOADED_MODEL_DOES_NOT_MATCH_SOHEE_PIN")
        self._model = model
        return time.monotonic() - started

    def render(self, text: str, direction: str, seed: int, output: Path) -> dict:
        """Create one new PCM16 WAV and return actual file and inference metadata.

        A reported 375-token limit or output longer than 30 seconds raises before
        writing. EOS is inferred from the pinned generation loop when the actual
        returned token_count is below the limit; no direct EOS event is claimed.
        """
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARACTERS:
            raise ValueError("TEXT_MUST_CONTAIN_1_TO_100_CHARACTERS")
        if not isinstance(direction, str):
            raise TypeError("DIRECTION_MUST_BE_A_STRING")
        if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("SEED_MUST_BE_AN_UNSIGNED_32_BIT_INTEGER")
        output = Path(output)
        if output.exists() or output.is_symlink():
            raise FileExistsError(output)
        if not output.parent.is_dir():
            raise FileNotFoundError("OUTPUT_DIRECTORY_MUST_ALREADY_EXIST: " + str(output.parent))
        with self._render_lock:
            # Recheck after waiting; a previous caller may have created the path.
            if output.exists() or output.is_symlink():
                raise FileExistsError(output)
            model_load_seconds = self._ensure_model()
            import mlx.core as mx
            import numpy as np
            import soundfile as sf
            mx.random.seed(seed)
            started = time.monotonic()
            settings = self._identity["generation"]
            results = list(self._model.generate_custom_voice(
                text=text, speaker="Sohee", language="Korean", instruct=direction,
                temperature=settings["temperature"], top_p=settings["topP"], top_k=settings["topK"],
                repetition_penalty=settings["repetitionPenalty"], max_tokens=settings["maxTokens"],
                stream=False, verbose=False,
            ))
            inference_seconds = time.monotonic() - started
            if len(results) != 1:
                raise RuntimeError("EXPECTED_ONE_NON_STREAMING_GENERATION_RESULT")
            result = results[0]
            token_count = int(result.token_count)
            if token_count <= 0:
                raise RuntimeError("NO_GENERATED_AUDIO_TOKENS")
            if token_count >= settings["maxTokens"]:
                raise RuntimeError(f"TOKEN_LIMIT_REACHED: {token_count}/{settings['maxTokens']}")
            samples = np.asarray(result.audio).reshape(-1)
            if result.sample_rate != 24000 or not samples.size or not np.isfinite(samples).all() or not np.max(np.abs(samples)):
                raise RuntimeError("INVALID_OR_SILENT_MODEL_WAVEFORM")
            if samples.size > 24000 * MAX_DURATION_MS // 1000:
                raise RuntimeError("AUDIO_EXCEEDS_30_SECOND_LIMIT")
            buffer = io.BytesIO()
            sf.write(buffer, samples, result.sample_rate, format="WAV", subtype="PCM_16")
            encoded = buffer.getvalue()
            with wave.open(io.BytesIO(encoded)) as wav:
                sample_rate, channels, width, frames = wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()
                pcm = np.frombuffer(wav.readframes(frames), dtype="<i2")
            if (sample_rate, channels, width, frames) != (24000, 1, 2, int(samples.size)):
                raise RuntimeError("ENCODED_WAV_FORMAT_MISMATCH")
            with output.open("xb") as target:
                target.write(encoded)
            audio_sha = _sha256(output)
            if audio_sha != hashlib.sha256(encoded).hexdigest():
                raise RuntimeError("WRITTEN_WAV_HASH_MISMATCH")
            mx.clear_cache()
            return {
                "sampleRateHz": sample_rate, "channels": channels, "sampleWidthBytes": width,
                "frames": frames, "durationMs": round(frames * 1000 / sample_rate), "audioSha256": audio_sha,
                "tokenCount": token_count,
                "termination": {"reason": "eos_inferred_from_reported_token_count_and_pinned_loop", "directEosObserved": False, "tokenLimitReached": False, "maxTokens": settings["maxTokens"]},
                "inferenceSeconds": inference_seconds, "modelLoadSeconds": model_load_seconds,
                "rawFloatPeak": float(np.max(np.abs(samples))), "rawSamplesAtOrAboveFullScale": int(np.count_nonzero(np.abs(samples) >= 1)),
                "pcmFullScaleSamples": int(np.count_nonzero((pcm == -32768) | (pcm == 32767))),
            }
