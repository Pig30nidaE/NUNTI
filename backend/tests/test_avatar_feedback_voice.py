"""Feedback voice HTTP, identity and process checks with a synthetic PCM worker only."""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from nunti.avatar_studio import voice_service
from nunti.avatar_studio.api import Settings
from nunti.avatar_studio.models import digest
from nunti.avatar_studio.storage import StudioError
from tests.test_avatar_studio import OTHER_TOKEN, TOKEN, client_for, fake_render, input_value

WORKER = r"""
import argparse,hashlib,json,math,struct,time,wave
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--plan');p.add_argument('--output');p.add_argument('--text')
a=p.parse_args();folder=Path(a.output);plan=json.loads(Path(a.plan).read_text())
text=a.text or plan['greeting'];sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
if a.text:
 (folder/'started').touch()
 if (folder/'hold').exists():
  end=time.monotonic()+10
  while not (folder/'release').exists():
   if time.monotonic()>end:raise TimeoutError('fake worker rendezvous')
   time.sleep(.01)
clip=folder/plan['profileId']/sha(text.encode());clip.mkdir(parents=True,exist_ok=True)
audio=clip/'audio.wav';meta=clip/'metadata.json'
if not meta.exists():
 with wave.open(str(audio),'wb') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
  frequency=.05+int(sha(text.encode())[:2],16)/10000
  w.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(i*frequency))) for i in range(48000)))
 ref=folder/plan['profileId']/sha(plan['greeting'].encode())/'audio.wav'
 record={'audioSha256':sha(audio.read_bytes()),'provider':'TEST_PCM_WORKER',
 'modelId':'TEST_ONLY','profileId':plan['profileId'],'text':text,
 'planSha256':sha(canonical(plan).encode()),
 'referenceAudioSha256':sha(ref.read_bytes()) if a.text else None}
 meta.write_text(canonical(record))
 with (folder/'synthesis-count').open('a') as count:count.write(text+'\n')
record=json.loads(meta.read_text());record['audioPath']=str(audio)
mode=(folder/'test-mode').read_text() if (folder/'test-mode').exists() else ''
if mode=='reference':record['referenceAudioSha256']='0'*64
if mode=='profile':record['profileId']='wrong-profile'
if mode=='text':record['text']='wrong text'
if mode=='plan':record['planSha256']='0'*64
if mode=='hash':record['audioSha256']='0'*64
if mode=='path':record['audioPath']=str(folder.parent/'outside.wav')
if mode=='pcm':audio.write_bytes(b'bad wav');record['audioSha256']=sha(audio.read_bytes())
print(json.dumps(record,ensure_ascii=False),flush=True)
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


def create_character(client, settings):
    original = client.post("/v3/avatars", json=input_value()).json()["data"]
    url = "/v3/avatars/" + original["characterId"]
    greeting_response = client.post(url + "/voice", json={})
    assert greeting_response.status_code == 200, greeting_response.text
    artifact = client.get(url).json()["data"]
    folder = settings.workspace / "voice-runs" / settings.owner / original["characterId"]
    return artifact, url, folder


def test_all_kinds_persist_with_same_reference_and_preserve_character(
    settings, worker, monkeypatch
):
    with client_for(settings, renderer=fake_render) as client:
        artifact, url, folder = create_character(client, settings)
        clips = {}
        for kind, text in voice_service.FEEDBACK_TEXTS.items():
            endpoint = url + "/feedback-voice/" + kind
            assert client.get(endpoint).status_code == 404
            response = client.post(endpoint, json={})
            assert response.status_code == 200, response.text
            clip = clips[kind] = response.json()["data"]
            assert clip["kind"] == kind and clip["text"] == text
            assert clip["profileId"] == artifact["voice"]["plan"]["profileId"]
            assert clip["referenceAudioSha256"] == artifact["voice"]["audio"]["sha256"]
            assert clip["audio"]["durationMs"] == 2000
            assert not clip["automaticPlayback"] and not clip["humanQualityApproved"]
            audio = client.get(clip["audio"]["path"])
            assert audio.headers["content-type"] == "audio/wav"
            assert digest(audio.content) == clip["audio"]["sha256"]
            assert client.get(endpoint).json()["data"] == clip
            assert client.post(endpoint, json={}).json()["data"] == clip
        assert client.get(url).json()["data"] == artifact
        assert client.get("/v3/avatars").json()["data"] == [artifact]
    assert len((folder / "synthesis-count").read_text().splitlines()) == 5
    # Stored clips remain usable without the inference environment, after a new app starts.
    monkeypatch.setattr(voice_service, "voice_available", lambda: False)
    with client_for(settings) as restarted:
        for kind, clip in clips.items():
            endpoint = url + "/feedback-voice/" + kind
            assert restarted.get(endpoint).json()["data"] == clip
            assert restarted.post(endpoint, json={}).json()["data"] == clip
    with client_for(replace(settings, token=OTHER_TOKEN)) as other:
        assert other.get(url + "/feedback-voice/JOY").status_code == 404
        assert other.post(url + "/feedback-voice/JOY", json={}).status_code == 404
        assert other.get(clips["JOY"]["audio"]["path"]).status_code == 404


def test_missing_reference_cache_only_get_and_input_guards(settings, worker):
    with client_for(settings, renderer=fake_render) as client:
        artifact = client.post("/v3/avatars", json=input_value()).json()["data"]
        url = "/v3/avatars/" + artifact["characterId"] + "/feedback-voice/"
        assert client.get(url + "NEUTRAL").status_code == 404
        response = client.post(url + "NEUTRAL", json={})
        assert response.status_code == 409 and "VOICE_REFERENCE_REQUIRED" in response.text
        for kind in ["unknown", "joy", "%2E%2E"]:
            assert client.get(url + kind).status_code == 400
            assert client.post(url + kind, json={}).status_code == 400
        assert client.get(url + "JOY", headers={"Authorization": "bad"}).status_code == 401
        assert (
            client.post(url + "JOY", json={}, headers={"Authorization": "bad"}).status_code == 401
        )
        assert client.get("/v3/avatars/nope/feedback-voice/JOY").status_code == 404
    assert not list(settings.workspace.rglob("synthesis-count"))


@pytest.mark.parametrize("mode", ["reference", "profile", "text", "plan", "hash", "path", "pcm"])
def test_worker_output_cannot_change_binding_or_publish_invalid_audio(settings, worker, mode):
    with client_for(settings, renderer=fake_render) as client:
        artifact, url, folder = create_character(client, settings)
        (folder / "test-mode").write_text(mode)
        response = client.post(url + "/feedback-voice/WORRY", json={})
        assert response.status_code == 502 and "LOCAL_VOICE_INVALID_OUTPUT" in response.text
        assert client.get(url + "/feedback-voice/WORRY").status_code == 404
        assert client.get(url).json()["data"] == artifact


@pytest.mark.parametrize("part", ["asset", "metadata", "reference"])
def test_tampered_media_or_binding_is_not_regenerated(settings, worker, part):
    with client_for(settings, renderer=fake_render) as client:
        artifact, url, folder = create_character(client, settings)
        endpoint = url + "/feedback-voice/JOY"
        clip = client.post(endpoint, json={}).json()["data"]
        if part == "asset":
            (settings.workspace / "media" / settings.owner / clip["audio"]["sha256"]).write_bytes(
                b"x"
            )
        elif part == "metadata":
            saved = folder / "feedback-JOY.json"
            data = json.loads(saved.read_text())
            data["text"] = "changed"
            saved.write_text(json.dumps(data))
        else:
            sha = artifact["voice"]["audio"]["sha256"]
            (settings.workspace / "media" / settings.owner / sha).write_bytes(b"x")
        assert client.get(endpoint).status_code == 409
        assert client.post(endpoint, json={}).status_code == 409
        assert len((folder / "synthesis-count").read_text().splitlines()) == 2


def test_missing_synthetic_reference_never_regenerates_greeting(settings, worker):
    with client_for(settings, renderer=fake_render) as client:
        artifact, url, folder = create_character(client, settings)
        plan = artifact["voice"]["plan"]
        reference = folder / plan["profileId"] / digest(plan["greeting"].encode()) / "audio.wav"
        reference.unlink()
        response = client.post(url + "/feedback-voice/RELIEF", json={})
        assert response.status_code == 409 and "VOICE_REFERENCE_CACHE_INVALID" in response.text
        assert client.get(url).json()["data"] == artifact
        assert len((folder / "synthesis-count").read_text().splitlines()) == 1


def test_concurrent_kinds_share_character_lock_and_timeout_releases_it(
    settings, worker, monkeypatch
):
    with client_for(settings, renderer=fake_render) as client:
        artifact, _, folder = create_character(client, settings)
        store = client.app.state.store
        (folder / "hold").touch()
        monkeypatch.setattr(voice_service, "VOICE_TIMEOUT_SECONDS", 1)
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                voice_service.generate_feedback_voice,
                store,
                settings.owner,
                artifact,
                "NEUTRAL",
            )
            deadline = time.monotonic() + 5
            while not (folder / "started").exists():
                if first.done():
                    first.result()
                if time.monotonic() > deadline:
                    raise TimeoutError("fake worker did not start")
                time.sleep(0.01)
            with pytest.raises(StudioError, match="VOICE_IN_PROGRESS"):
                voice_service.generate_feedback_voice(store, settings.owner, artifact, "JOY")
            with pytest.raises(StudioError, match="LOCAL_VOICE_TIMEOUT"):
                first.result(timeout=4)
        (folder / "release").touch()
        monkeypatch.setattr(voice_service, "VOICE_TIMEOUT_SECONDS", 5)
        clip = voice_service.generate_feedback_voice(store, settings.owner, artifact, "NEUTRAL")
        assert clip["kind"] == "NEUTRAL"
        assert len((folder / "synthesis-count").read_text().splitlines()) == 2


def test_retry_after_unpublished_metadata_reuses_worker_clip(settings, worker):
    with client_for(settings, renderer=fake_render) as client:
        artifact, url, folder = create_character(client, settings)
        endpoint = url + "/feedback-voice/RELIEF"
        clip = client.post(endpoint, json={}).json()["data"]
        (folder / "feedback-RELIEF.json").unlink()
        assert client.get(endpoint).status_code == 404
        assert client.post(endpoint, json={}).json()["data"] == clip
        assert len((folder / "synthesis-count").read_text().splitlines()) == 2
        assert client.get(url).json()["data"] == artifact
