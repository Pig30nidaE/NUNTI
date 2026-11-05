"""Real subprocess/file/HTTP lifecycle with a synthetic PCM worker, never a TTS model."""

import sys
from dataclasses import replace

import pytest

from nunti.avatar_studio import voice_service
from nunti.avatar_studio.api import Settings
from nunti.avatar_studio.models import digest
from tests.test_avatar_studio import OTHER_TOKEN, TOKEN, client_for, fake_render, input_value

WORKER = """
import argparse,json,wave,math,struct,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--plan');p.add_argument('--output');a=p.parse_args()
folder=Path(a.output);path=folder/'audio.wav'
with wave.open(str(path),'wb') as w:
 w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
 w.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(i*.1))) for i in range(4800)))
with (folder/'worker-count').open('a') as count:count.write('1')
print(json.dumps({'audioPath':str(path),'audioSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
'provider':'TEST_PCM_WORKER','modelId':'TEST_ONLY'}))
"""


@pytest.fixture
def settings(tmp_path):
    return Settings(TOKEN, tmp_path / "studio")


@pytest.fixture
def worker(tmp_path, monkeypatch):
    folder = tmp_path / "worker"
    (folder / "scripts").mkdir(parents=True)
    (folder / "scripts/voice_render_studio.py").write_text(WORKER)
    monkeypatch.setattr(voice_service, "ROOT", folder)
    monkeypatch.setattr(voice_service, "PYTHON", sys.executable)
    monkeypatch.setattr(voice_service, "voice_available", lambda: True)


def test_first_voice_saved_replayed_and_merged_without_changing_image(settings, worker):
    data = input_value()
    with client_for(settings, renderer=fake_render) as client:
        a = client.post("/v3/avatars", json=data).json()["data"]
        url = "/v3/avatars/" + a["characterId"]
        voice = client.post(url + "/voice", json={}).json()["data"]
        assert voice["status"] == "READY" and voice["newVoiceGenerated"]
        assert voice["audio"]["durationMs"] == 200
        wav = client.get(voice["audio"]["path"])
        assert wav.headers["content-type"] == "audio/wav"
        assert digest(wav.content) == voice["audio"]["sha256"]
        assert client.post(url + "/voice", json={}).json()["data"] == voice
        restored = client.get(url).json()["data"]
        assert restored["voice"] == voice
        assert restored["visual"] == a["visual"]
        assert client.post("/v3/avatars", json=data).json()["data"] == restored
        assert client.get("/v3/avatars").json()["data"][0] == restored
    with client_for(settings) as restarted:
        assert restarted.get(url).json()["data"] == restored
        assert restarted.post(url + "/voice", json={}).json()["data"] == voice
    counts = list(settings.workspace.rglob("worker-count"))
    assert len(counts) == 1 and counts[0].read_text() == "1"
    with client_for(replace(settings, token=OTHER_TOKEN)) as other:
        assert other.post(url + "/voice", json={}).status_code == 404
        assert other.get(voice["audio"]["path"]).status_code == 404


def test_changed_saved_voice_is_not_silently_regenerated(settings, worker):
    with client_for(settings, renderer=fake_render) as client:
        a = client.post("/v3/avatars", json=input_value()).json()["data"]
        url = "/v3/avatars/" + a["characterId"] + "/voice"
        voice = client.post(url, json={}).json()["data"]
        media = settings.workspace / "media" / settings.owner / voice["audio"]["sha256"]
        media.write_bytes(b"tampered")
        assert client.post(url, json={}).status_code == 409
        assert list(settings.workspace.rglob("worker-count"))[0].read_text() == "1"


def test_unavailable_voice_preserves_ready_visual(settings, monkeypatch):
    monkeypatch.setattr(voice_service, "voice_available", lambda: False)
    with client_for(settings, renderer=fake_render) as client:
        a = client.post("/v3/avatars", json=input_value()).json()["data"]
        url = "/v3/avatars/" + a["characterId"]
        response = client.post(url + "/voice", json={})
        assert response.status_code == 409
        assert client.get(url).json()["data"] == a
        assert client.get(a["visual"]["path"]).status_code == 200
