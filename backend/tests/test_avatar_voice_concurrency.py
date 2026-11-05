"""Two real request threads and an inherited file lock, using only a fake PCM worker."""

import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from nunti.avatar_studio import voice_service
from nunti.avatar_studio.models import digest
from nunti.avatar_studio.storage import StudioError, StudioStore
from tests.test_avatar_voice_service import WORKER


def test_concurrent_same_character_runs_one_worker_and_restores_same_voice(tmp_path, monkeypatch):
    worker_root = tmp_path / "worker"
    (worker_root / "scripts").mkdir(parents=True)
    # The first worker stays inside the production flock until the test releases it.
    # File rendezvous avoids relying on which request thread the scheduler runs first.
    worker = WORKER.replace(
        "folder=Path(a.output);path=folder/'audio.wav'",
        "folder=Path(a.output);path=folder/'audio.wav'\n"
        "import time\n"
        "(folder/'started').write_text('1')\n"
        "deadline=time.monotonic()+10\n"
        "while not (folder/'release').exists():\n"
        " if time.monotonic()>deadline:raise TimeoutError('test worker rendezvous')\n"
        " time.sleep(.01)",
    )
    (worker_root / "scripts/voice_render_studio.py").write_text(worker)
    monkeypatch.setattr(voice_service, "ROOT", worker_root)
    monkeypatch.setattr(voice_service, "PYTHON", sys.executable)
    monkeypatch.setattr(voice_service, "voice_available", lambda: True)

    store = StudioStore(tmp_path / "store")
    owner = "test-owner"
    artifact = {
        "characterId": "nunti-concurrent-test",
        "voice": {"plan": {"greeting": "안녕, 나는 시험 눈티야."}},
    }
    folder = store.root / "voice-runs" / owner / artifact["characterId"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(voice_service.generate_voice, store, owner, artifact)
        try:
            deadline = time.monotonic() + 5
            while not (folder / "started").is_file():
                if first.done():
                    first.result()  # Surface worker failures instead of timing out in the test.
                if time.monotonic() > deadline:
                    raise TimeoutError("first fake PCM worker did not start")
                time.sleep(0.01)
            second = executor.submit(voice_service.generate_voice, store, owner, artifact)
            with pytest.raises(StudioError, match="VOICE_IN_PROGRESS") as rejected:
                second.result(timeout=3)
            assert rejected.value.status == 409
        finally:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "release").touch()
        generated = first.result(timeout=5)

    assert generated["provider"] == "TEST_PCM_WORKER"
    assert (folder / "worker-count").read_text() == "1"
    assert store.voice(owner, artifact["characterId"]) == generated
    content, mime = store.asset(owner, generated["audio"]["sha256"])
    assert mime == "audio/wav" and digest(content) == generated["audio"]["sha256"]

    # A new store instance exercises persisted restoration after the request has completed.
    restored = voice_service.generate_voice(StudioStore(store.root), owner, artifact)
    assert restored == generated
    assert (folder / "worker-count").read_text() == "1"
