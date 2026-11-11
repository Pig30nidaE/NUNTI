"""Bridge the lightweight web process to the offline, GPU-owning voice worker."""

import fcntl
import json
import os
import subprocess
import tempfile
import wave

from .local_model import stop_child
from .models import canonical, digest
from .storage import StudioError
from .voice_render import PYTHON, ROOT, inspect_wav, voice_available

FEEDBACK_TEXTS = {
    "NEUTRAL": "함께 살펴보고 있어요.",
    "WORRY": "앗, 조금 걱정돼요. 천천히 가요.",
    "RELIEF": "휴, 이제 좀 안심돼요.",
    "JOY": "오늘 편안하게 달려서 좋았어요!",
}
VOICE_TIMEOUT_SECONDS = 360


def _run_voice_worker(folder, plan, lock, text=None):
    plan_file = folder / "plan.json"
    plan_file.write_text(canonical(plan))
    env = {
        key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "TMPDIR", "LANG"}
    }
    env.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
        HF_HUB_DISABLE_TELEMETRY="1",
    )
    command = [
        str(PYTHON),
        str(ROOT / "scripts/voice_render_studio.py"),
        "--plan",
        str(plan_file),
        "--output",
        str(folder),
    ]
    if text is not None:
        command.extend(["--text", text])
    with (folder / "worker.log").open("wb") as log:
        child = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=log,
            start_new_session=True,
            pass_fds=(lock.fileno(),),
        )
        try:
            output, _ = child.communicate(timeout=VOICE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            stop_child(child)
            raise StudioError("LOCAL_VOICE_TIMEOUT", 504) from exc
        except BaseException:
            stop_child(child)
            raise
    if child.returncode:
        raise StudioError("LOCAL_VOICE_FAILED", 502)
    try:
        result = json.loads(output)
        path = (folder / result["audioPath"]).resolve()
        if not path.is_relative_to(folder.resolve()):
            raise ValueError("voice outside run")
        evidence = inspect_wav(path)
        content = path.read_bytes()
        if digest(content) != result["audioSha256"]:
            raise ValueError("voice hash mismatch")
    except (OSError, EOFError, ValueError, KeyError, TypeError, wave.Error) as exc:
        raise StudioError("LOCAL_VOICE_INVALID_OUTPUT", 502) from exc
    return result, evidence, content


def generate_voice(store, owner, artifact):
    existing = store.voice(owner, artifact["characterId"])
    if existing:
        # Check the immutable asset still exists and has the recorded hash.
        store.asset(owner, existing["audio"]["sha256"])
        return existing
    if not voice_available():
        raise StudioError("LOCAL_VOICE_NOT_CONFIGURED", 409)
    plan = artifact["voice"].get("plan")
    if plan is None:
        from .voice_design import build_voice_design

        plan = build_voice_design(artifact, artifact["design"])
    folder = store.root / "voice-runs" / owner / artifact["characterId"]
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (folder / "request.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StudioError("VOICE_IN_PROGRESS", 409) from exc
        existing = store.voice(owner, artifact["characterId"])
        if existing:
            return existing
        result, evidence, content = _run_voice_worker(folder, plan, lock)
        sha = store.put_asset(owner, content, "audio/wav")
        voice = {
            **artifact["voice"],
            "plan": plan,
            "status": "READY",
            "provider": result["provider"],
            "newVoiceGenerated": True,
            "automaticPlayback": False,
            "audio": {
                "path": "/v3/assets/" + sha,
                "sha256": sha,
                "mimeType": "audio/wav",
                "durationMs": evidence["durationMs"],
                "sampleRateHz": evidence["sampleRateHz"],
            },
            "model": result.get("modelId"),
            "greeting": plan["greeting"],
            "humanQualityApproved": False,
        }
        store.put_voice(owner, artifact["characterId"], voice)
        return voice


def _feedback_file(store, owner, artifact, kind):
    if kind not in FEEDBACK_TEXTS:
        raise StudioError("FEEDBACK_KIND_INVALID", 400)
    return store.root / "voice-runs" / owner / artifact["characterId"] / f"feedback-{kind}.json"


def _feedback_binding(store, owner, artifact, kind):
    voice = store.voice(owner, artifact["characterId"])
    if not voice or voice.get("status") != "READY" or not voice.get("plan"):
        raise StudioError("VOICE_REFERENCE_REQUIRED", 409)
    plan = voice["plan"]
    if artifact["voice"].get("plan") != plan:
        raise StudioError("VOICE_IDENTITY_CONFLICT", 409)
    store.asset(owner, voice["audio"]["sha256"])
    return plan, {
        "characterId": artifact["characterId"],
        "kind": kind,
        "text": FEEDBACK_TEXTS[kind],
        "profileId": plan["profileId"],
        "planSha256": digest(canonical(plan).encode()),
        "referenceAudioSha256": voice["audio"]["sha256"],
    }


def get_feedback_voice(store, owner, artifact, kind):
    """Read an owner-scoped clip without starting a worker or repairing stored media."""
    path = _feedback_file(store, owner, artifact, kind)
    if not path.exists():
        raise StudioError("FEEDBACK_VOICE_NOT_FOUND", 404)
    _, binding = _feedback_binding(store, owner, artifact, kind)
    try:
        saved = json.loads(path.read_text())
        if any(saved.get(key) != value for key, value in binding.items()):
            raise ValueError("feedback identity changed")
        audio = saved["audio"]
        if audio["path"] != "/v3/assets/" + audio["sha256"]:
            raise ValueError("feedback asset path changed")
        _, mime = store.asset(owner, audio["sha256"])
        if mime != "audio/wav" or audio["mimeType"] != mime or saved["status"] != "READY":
            raise ValueError("feedback asset type changed")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # A completed clip must never be regenerated after corruption or tampering.
        raise StudioError("SAVED_FEEDBACK_VOICE_CHANGED", 409) from exc
    return saved


def generate_feedback_voice(store, owner, artifact, kind):
    """Generate one fixed driving line using the character's existing synthetic greeting."""
    metadata = _feedback_file(store, owner, artifact, kind)
    if metadata.exists():
        return get_feedback_voice(store, owner, artifact, kind)
    plan, binding = _feedback_binding(store, owner, artifact, kind)
    if not voice_available():
        raise StudioError("LOCAL_VOICE_NOT_CONFIGURED", 409)
    folder = metadata.parent
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (folder / "request.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StudioError("VOICE_IN_PROGRESS", 409) from exc
        if metadata.exists():
            return get_feedback_voice(store, owner, artifact, kind)
        # The worker reuses this exact directory for its synthetic reference. A missing
        # greeting must not cause its recursive renderer to invent a replacement voice.
        reference_dir = folder / plan["profileId"] / digest(plan["greeting"].encode())
        try:
            reference = json.loads((reference_dir / "metadata.json").read_text())
            if (
                digest((reference_dir / "audio.wav").read_bytes())
                != binding["referenceAudioSha256"]
                or reference["audioSha256"] != binding["referenceAudioSha256"]
                or reference["planSha256"] != binding["planSha256"]
                or reference["profileId"] != binding["profileId"]
                or reference["text"] != plan["greeting"]
            ):
                raise ValueError("synthetic reference changed")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise StudioError("VOICE_REFERENCE_CACHE_INVALID", 409) from exc
        result, evidence, content = _run_voice_worker(folder, plan, lock, binding["text"])
        expected = {
            key: binding[key]
            for key in (
                "text",
                "profileId",
                "planSha256",
                "referenceAudioSha256",
            )
        }
        if (
            any(result.get(key) != value for key, value in expected.items())
            or not isinstance(result.get("provider"), str)
            or not isinstance(result.get("modelId"), str)
        ):
            raise StudioError("LOCAL_VOICE_INVALID_OUTPUT", 502)
        sha = store.put_asset(owner, content, "audio/wav")
        saved = {
            **binding,
            "status": "READY",
            "provider": result["provider"],
            "model": result["modelId"],
            "automaticPlayback": False,
            "humanQualityApproved": False,
            "audio": {
                "path": "/v3/assets/" + sha,
                "sha256": sha,
                "mimeType": "audio/wav",
                "durationMs": evidence["durationMs"],
                "sampleRateHz": evidence["sampleRateHz"],
            },
        }
        fd, name = tempfile.mkstemp(dir=folder, prefix=".feedback-")
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(canonical(saved))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, metadata)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return saved
