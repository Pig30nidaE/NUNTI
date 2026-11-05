"""Bridge the lightweight web process to the offline, GPU-owning voice worker."""

import fcntl
import json
import os
import subprocess
import wave

from .local_model import stop_child
from .models import canonical, digest
from .storage import StudioError
from .voice_render import PYTHON, ROOT, inspect_wav, voice_available


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
        plan_file = folder / "plan.json"
        plan_file.write_text(canonical(plan))
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "HOME", "TMPDIR", "LANG"}
        }
        env.update(
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
            HF_HUB_DISABLE_TELEMETRY="1",
        )
        with (folder / "worker.log").open("wb") as log:
            child = subprocess.Popen(
                [
                    str(PYTHON),
                    str(ROOT / "scripts/voice_render_studio.py"),
                    "--plan",
                    str(plan_file),
                    "--output",
                    str(folder),
                ],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=log,
                start_new_session=True,
                pass_fds=(lock.fileno(),),
            )
            try:
                output, _ = child.communicate(timeout=360)
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
        except (OSError, ValueError, KeyError, TypeError, wave.Error) as exc:
            raise StudioError("LOCAL_VOICE_INVALID_OUTPUT", 502) from exc
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
