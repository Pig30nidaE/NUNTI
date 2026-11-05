"""Exercise real HTTP, SQLite restart/claims, bytes and cost boundaries without a key."""

import base64
import json
import struct
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from nunti.api import create_app
from nunti.characters.media import inspect_png, inspect_wav, pcm_wav
from nunti.characters.models import canonical, sha
from nunti.characters.providers import ApiPipeline, FixturePipeline, b64
from nunti.characters.worker import GenerationWorker

from .conftest import TOKEN_A, TOKEN_B


def tiny_png(opaque=False):
    def chunk(kind, content):
        return (
            struct.pack(">I", len(content))
            + kind
            + content
            + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
        )

    rows = []
    for y in range(64):
        rows.append(
            b"\0"
            + b"".join(
                bytes((80, 170, 160, 255 if opaque or 12 <= x < 52 and 12 <= y < 52 else 0))
                for x in range(64)
            )
        )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


@pytest.fixture
def generation_settings(settings, tmp_path):
    png = tmp_path / "sample.png"
    png.write_bytes(tiny_png())
    clips = []
    for index, category in enumerate(("greeting", "common", "arrival", "greeting")):
        # Unit-test PCM fixture, explicitly not human speech or provider output.
        audio = pcm_wav(bytes([index, 0]) * 1200)
        path = tmp_path / f"source-{index}.wav"
        path.write_bytes(audio)
        clips.append(
            {
                "characterId": "original-a" if index < 3 else "original-b",
                "clipId": ("original-a" if index < 3 else "original-b") + "-" + category,
                "audioPath": path.name,
                "audioSha256": sha(audio),
                "text": ("초기 인사 샘플", "공통 샘플", "도착 샘플", "후속 시험 샘플")[index],
                "speakerId": "unit-test-fixture",
                "source": {"kind": "AUTHORED_TEST_PCM"},
            }
        )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"characters": [{"characterId": "original-a"}], "clips": clips}))
    return replace(
        settings, generation_mode="OFFLINE_FIXTURE", fixture_png=png, fixture_manifest=manifest
    )


def input_value(request_id=None):
    return {
        "requestId": request_id or str(uuid4()),
        "destination": {"name": "바다", "traits": "고요한 물빛"},
        "purpose": "휴식",
        "route": {"points": [[0.12, 0.8], [0.4, 0.2], [0.9, 0.6]]},
    }


def data(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def test_http_fixture_media_speech_restore_and_owner_isolation(generation_settings, sample):
    settings = generation_settings
    headers = {"Authorization": f"Bearer {TOKEN_A}"}
    value = input_value()
    with TestClient(create_app(settings), headers=headers) as client:
        capabilities = data(client.get("/v2/generation-capabilities"))
        assert capabilities["fixtureFollowupText"] == "후속 시험 샘플"
        assert capabilities["humanQualityApproved"] is False
        submitted = data(client.post("/v2/character-generations", json=value))
        assert submitted["state"] == "QUEUED"
        worker = GenerationWorker(client.app.state.character_store, settings)
        generated = worker.run_once()
        assert generated["state"] == "READY", generated
        artifact = generated["artifact"]
        assert artifact["mode"] == "OFFLINE_FIXTURE"
        assert artifact["inputCanonical"] == canonical(value)
        assert artifact["specHash"] == artifact["voiceManifest"]["clips"][0]["source"]["specSha256"]
        assert artifact["fixtureProvenance"]["kind"] == "PREEXISTING_MEDIA_NOT_NEW_GENERATION"
        assert len(artifact["voiceManifest"]["clips"]) == 3
        for clip in artifact["voiceManifest"]["clips"]:
            audio = client.get("/v2/assets/" + clip["audioSha256"])
            assert audio.status_code == 200
            assert sha(audio.content) == clip["audioSha256"]
            inspect_wav(audio.content)
            assert clip["speakerId"] == clip["source"]["voiceId"]
            assert clip["source"]["mediaOrigin"] == "OFFLINE_FIXTURE"
            assert clip["fixtureProvenance"]["speakerId"] == "unit-test-fixture"
        image_path = artifact["visual"]["asset"]["path"]
        assert client.get(image_path).content == settings.fixture_png.read_bytes()
        other = {"Authorization": f"Bearer {TOKEN_B}"}
        for path in (
            image_path,
            "/v2/jobs/" + value["requestId"],
            "/v2/characters/" + artifact["characterId"],
        ):
            assert client.get(path, headers=other).status_code == 404
            assert client.get(path, headers={"Authorization": ""}).status_code == 401
        assert data(client.post("/v2/character-generations", json=value)) == generated
        assert worker.run_once() is None
        conflict = value | {"purpose": "다른 목적"}
        assert client.post("/v2/character-generations", json=conflict).status_code == 409
        speech = {"requestId": str(uuid4()), "text": capabilities["fixtureFollowupText"]}
        path = "/v2/characters/" + artifact["characterId"]
        data(client.post(path + "/speech", json=speech))
        result = worker.run_once()
        assert result["state"] == "READY", result
        assert "artifact" not in result
        clip = result["speechManifest"]["clips"][0]
        assert clip["text"] == speech["text"]
        assert clip["source"] == artifact["voiceManifest"]["clips"][0]["source"]
        assert data(client.get(path)) == artifact
        # Independent v1 cleanup/deletion cannot erase a collectible.
        data(client.post("/v1/trips", json=sample("TripCreate")))
        data(client.delete("/v1/trips/trip-mock"))
        assert data(client.get(path)) == artifact
        assert data(client.post(path + "/speech", json=speech)) == result
    with TestClient(create_app(settings), headers=headers) as restarted:
        assert data(restarted.get(path)) == artifact
        assert data(restarted.get("/v2/jobs/" + value["requestId"])) == generated
        assert restarted.get(image_path).content == settings.fixture_png.read_bytes()


def test_missing_api_keys_and_unverified_prices_have_zero_network(generation_settings, monkeypatch):
    import nunti.characters.providers as providers

    calls = []
    monkeypatch.setattr(providers.Transport, "request", lambda *a, **k: calls.append((a, k)))
    settings = replace(generation_settings, generation_mode="API")
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN_A}"}) as client:
        value = input_value()
        data(client.post("/v2/character-generations", json=value))
        result = GenerationWorker(client.app.state.character_store, settings).run_once()
        assert result["state"] == "FAILED"
        assert result["error"] == "MISSING_PROVIDER_CREDENTIALS"
        with client.app.state.character_store.connect() as db:
            assert db.execute("SELECT count(*) FROM steps").fetchone()[0] == 0
    assert calls == []
    settings = replace(
        settings, openai_key="not-a-key", elevenlabs_key="not-a-key", google_key="not-a-key"
    )
    with pytest.raises(ValueError, match="ACCOUNT_PRICE_CONFIGURATION_REQUIRED"):
        ApiPipeline(settings)
    assert calls == []


def test_actual_sqlite_claim_exclusion_and_uncertain_call_is_never_replayed(generation_settings):
    settings = generation_settings
    with TestClient(create_app(settings)) as client:
        store = client.app.state.character_store
        value = input_value()
        store.submit("a", value, "API")
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda holder: store.claim(holder, now=1000), ("one", "two")))
        job = next(c for c in claims if c)
        assert sum(c is not None for c in claims) == 1
        store.begin_step(job, "external_voice", {"request": "stable"}, 1000)
        assert store.claim("restart", now=1301) is None
        result = store.get_job("a", value["requestId"])
        assert result["state"] == "RESULT_UNKNOWN"
        assert result["error"] == "PROVIDER_RESULT_UNKNOWN"
        assert store.claim("restart", now=2000) is None


def test_completed_steps_resume_without_repeating_provider_calls(generation_settings):
    settings = generation_settings
    with TestClient(create_app(settings)) as client:
        store = client.app.state.character_store
        value = input_value()
        store.submit("a", value, "OFFLINE_FIXTURE")
        job = store.claim("dead", now=1000)
        fixture = FixturePipeline(settings)
        for name, request, result in (
            ("preflight", {"providerId": fixture.provider_id}, fixture.preflight()),
            ("planning", value, fixture.plan(value)),
        ):
            store.begin_step(job, name, request, 0)
            store.finish_step(job, name, result)
        with store.transaction() as db:
            db.execute("UPDATE jobs SET lease_until=0")
            db.execute("UPDATE worker_lock SET expires=0")

        class CountFixture(FixturePipeline):
            def preflight(self):
                pytest.fail("Completed preflight must not be called again")

            def plan(self, value):
                pytest.fail("Completed planning must not be called again")

        result = GenerationWorker(store, settings, lambda mode: CountFixture(settings)).run_once()
        assert result["state"] == "READY", result


def test_budget_and_voice_slot_caps_are_atomic(generation_settings):
    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        store.job_cap = 200
        value = input_value()
        store.submit("a", value, "API")
        job = store.claim("one")
        store.begin_step(job, "image", {}, 150)
        store.finish_step(job, "image", {"receipt": "recorded"})
        assert store.begin_step(job, "image", {}, 150) == {"receipt": "recorded"}
        with pytest.raises(ValueError, match="BUDGET_CAP_REACHED"):
            store.begin_step(job, "voice", {}, 51)
        with pytest.raises(ValueError, match="PROVIDER_REQUEST_CHANGED"):
            store.begin_step(job, "image", {"changed": True}, 150)
        store.reserve_voice(job, "character-one", "provider", capacity=1)
        store.reserve_voice(job, "character-one", "provider", capacity=1)
        with pytest.raises(ValueError, match="VOICE_SLOT_CAP_REACHED"):
            store.reserve_voice(job, "character-two", "provider", capacity=1)


def test_media_tamper_and_saved_character_tamper_fail_closed(generation_settings):
    settings = generation_settings
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN_A}"}) as client:
        value = input_value()
        data(client.post("/v2/character-generations", json=value))
        worker = GenerationWorker(client.app.state.character_store, settings)
        result = worker.run_once()
        artifact = result["artifact"]
        store = client.app.state.character_store
        asset = store.media / artifact["visual"]["asset"]["sha256"]
        asset.write_bytes(asset.read_bytes()[:-1])
        assert client.get(artifact["visual"]["asset"]["path"]).status_code == 503
        with store.transaction() as db:
            changed = artifact | {"displayName": "몰래 바뀐 이름"}
            db.execute("UPDATE characters SET artifact_json=?", (canonical(changed),))
        assert client.get("/v2/characters/" + artifact["characterId"]).status_code == 503


@pytest.mark.parametrize(
    "change",
    [
        {"route": {"points": [[0, 0], [0, 0]]}},
        {"route": {"points": [[False, 0], [1, 1]]}},
        {"route": {"points": [[-1, 0], [1, 1]]}},
        {"route": {"points": [[0, 0, 1], [1, 1]]}},
        {"destination": {"name": "a" * 61, "traits": ""}},
        {"purpose": "😀" * 61},
        {"requestId": "not-a-uuid"},
        {"extra": "untrusted"},
    ],
)
def test_v2_input_rejection(generation_settings, change):
    with TestClient(
        create_app(generation_settings), headers={"Authorization": f"Bearer {TOKEN_A}"}
    ) as client:
        assert (
            client.post("/v2/character-generations", json=input_value() | change).status_code == 422
        )


def test_unknown_fixture_speech_does_not_pretend_to_synthesize(generation_settings):
    fixture = FixturePipeline(generation_settings)
    with pytest.raises(ValueError, match="FIXTURE_TEXT_UNAVAILABLE"):
        fixture.speak({"voiceId": "fixture-id"}, "완전히 새로운 임의의 문장")
    with pytest.raises(ValueError, match="TRANSPARENT_VISIBLE_CHARACTER_REQUIRED"):
        inspect_png(tiny_png(opaque=True))


class RecordingTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


def api_settings(settings, **kwargs):
    return replace(
        settings,
        generation_mode="API",
        openai_key="fake",
        elevenlabs_key="fake",
        google_key="fake",
        recraft_key="fake",
        generation_prices_verified=True,
        generation_step_ceilings={
            name: 10000
            for name in (
                "planning",
                "image_candidates",
                "voice_candidates",
                "selection",
                "save_voice",
                "speech",
                "remove_background",
            )
        },
        **kwargs,
    )


def test_eleven_design_save_then_followup_uses_same_voice_id(generation_settings):
    settings = api_settings(generation_settings)
    fixture = FixturePipeline(settings)
    concept = fixture.plan(input_value())
    transport = RecordingTransport(
        [
            {
                "previews": [
                    {"generated_voice_id": f"preview-{i}", "audio_base_64": b64(b"preview")}
                    for i in range(3)
                ]
            },
            {"voice_id": "persistent-voice-one"},
            bytes([1, 0]) * 1200,
            bytes([2, 0]) * 1200,
        ]
    )
    pipeline = ApiPipeline(settings, transport)
    candidates = pipeline.voice_candidates(input_value(), concept)
    voice = pipeline.save_voice("gen-test", concept, candidates["candidates"][1])
    first = pipeline.speak(voice, "첫 문장")
    second = pipeline.speak(voice, "새로운 문장")
    for call in transport.calls[-2:]:
        assert "/text-to-speech/persistent-voice-one?output_format=pcm_24000" in call[1]
        assert json.loads(call[2]["body"])["model_id"] == "eleven_v4"
    assert first["rawAudioSha256"] != second["rawAudioSha256"]
    inspect_wav(base64.b64decode(first["audio"]))
    assert json.loads(transport.calls[0][2]["body"])["model_id"] == "eleven_ttv_v3"
    assert json.loads(transport.calls[1][2]["body"])["generated_voice_id"] == "preview-1"


def test_flare_edit_conditions_on_style_and_actual_route(generation_settings):
    transport = RecordingTransport([{"data": [{"b64_json": b64(tiny_png())}] * 2}])
    pipeline = ApiPipeline(api_settings(generation_settings), transport)
    concept = FixturePipeline(generation_settings).plan(input_value())
    result = pipeline.images(input_value(), concept)
    assert len(result["candidates"]) == 2
    method, url, request = transport.calls[0]
    assert method == "POST" and url.endswith("/v1/images/edits")
    assert b"style-master.png" in request["body"] and b"journey-route.png" in request["body"]
    assert b"gpt-image-2.5-flare" in request["body"]
    assert b"transparent" in request["body"]


def test_google_rest_interaction_audio_steps_not_sdk_field(generation_settings):
    audio = pcm_wav(bytes([1, 0]) * 1200)
    transport = RecordingTransport(
        [
            {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {"type": "audio", "mime_type": "audio/wav", "data": b64(audio)}
                        ],
                    }
                ]
            }
        ]
    )
    pipeline = ApiPipeline(
        api_settings(generation_settings, generation_pipeline="GOOGLE_COMPARE"), transport
    )
    rendered = pipeline.speak({"voiceId": "google-fixed-id"}, "안녕")
    assert base64.b64decode(rendered["audio"]) == audio
    request = json.loads(transport.calls[0][2]["body"])
    assert request["generation_config"]["speech_config"] == [{"voice": "google-fixed-id"}]
    assert request["response_format"] == {"type": "audio"}


def test_partial_price_configuration_fails_before_any_transport(generation_settings):
    transport = RecordingTransport([])
    settings = replace(api_settings(generation_settings), generation_step_ceilings={"planning": 1})
    with pytest.raises(ValueError, match="ACCOUNT_PRICE_CONFIGURATION_REQUIRED"):
        ApiPipeline(settings, transport)
    assert transport.calls == []


def test_same_text_new_request_reuses_original_clip_and_does_not_call_provider(generation_settings):
    settings = generation_settings
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN_A}"}) as client:
        store = client.app.state.character_store
        value = input_value()
        data(client.post("/v2/character-generations", json=value))
        first = GenerationWorker(store, settings).run_once()
        assert first["jobId"] == first["requestId"] == value["requestId"]
        artifact = first["artifact"]
        path = "/v2/characters/" + artifact["characterId"] + "/speech"
        original = artifact["voiceManifest"]["clips"][0]
        data(client.post(path, json={"requestId": str(uuid4()), "text": original["text"]}))
        worker = GenerationWorker(
            store, settings, lambda mode: pytest.fail("Cached text cannot create a provider")
        )
        second = worker.run_once()
        assert second["speechManifest"]["clips"] == [original]
        assert second["cost"]["reservedMicros"] == 0
        fixture = FixturePipeline(settings)
        text = fixture.followup["metadata"]["text"]
        data(client.post(path, json={"requestId": str(uuid4()), "text": text}))
        third = GenerationWorker(store, settings).run_once()
        data(client.post(path, json={"requestId": str(uuid4()), "text": text}))
        fourth = worker.run_once()
        assert fourth["speechManifest"] == third["speechManifest"]
        assert data(client.get("/v2/characters/" + artifact["characterId"])) == artifact


def test_20_retained_voices_do_not_double_subtract_external_active_slots(generation_settings):
    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        for index in range(20):
            value = input_value()
            submitted = store.submit("a", value, "API")
            assert submitted["jobId"] == submitted["requestId"]
            # Account used already includes previously activated voices.
            store.reserve_voice(
                {"owner": "a"}, "character-" + str(index), "provider", capacity=30 - index
            )
            with store.transaction() as db:
                db.execute(
                    "UPDATE voices SET state='ACTIVE',voice_id=? WHERE character_id=?",
                    ("voice-" + str(index), "character-" + str(index)),
                )
        with store.connect() as db:
            assert (
                db.execute("SELECT count(*) FROM voices WHERE state='ACTIVE'").fetchone()[0] == 20
            )
        with pytest.raises(Exception) as exc:
            store.submit("a", input_value(), "API")
        assert getattr(exc.value, "code", None) == "initial_batch_limit"


def test_google_prebuilt_voices_do_not_consume_custom_voice_slots(generation_settings):
    inventory = {
        "voices": [{"type": "prebuilt", "id": "prebuilt-" + str(i)} for i in range(250)]
        + [{"type": "prompted", "id": "custom-one"}, {"type": "replicated", "id": "custom-two"}]
    }
    transport = RecordingTransport([inventory])
    pipeline = ApiPipeline(
        api_settings(generation_settings, generation_pipeline="GOOGLE_COMPARE"), transport
    )
    account = pipeline.preflight()
    assert account["voiceSlotsUsed"] == 2
    assert account["availableVoiceSlots"] == 198
    assert account["storedCandidatesPerCharacter"] == 1


def test_google_only_one_new_stored_voice_and_recraft_has_no_arbitrary_download(
    generation_settings,
):
    audio = pcm_wav(bytes([1, 0]) * 1200)
    transport = RecordingTransport(
        [
            {
                "id": "new-google-voice",
                "sample_audio": {"data": b64(audio), "mime_type": "audio/wav"},
            },
            {"image": {"b64_json": b64(tiny_png())}, "credits": 10},
        ]
    )
    pipeline = ApiPipeline(
        api_settings(generation_settings, generation_pipeline="GOOGLE_COMPARE"), transport
    )
    concept = FixturePipeline(generation_settings).plan(input_value())
    voices = pipeline.voice_candidates(input_value(), concept)
    assert len(voices["candidates"]) == 1
    assert (
        pipeline.save_voice("character-one", concept, voices["candidates"][0])["voiceId"]
        == "new-google-voice"
    )
    output = pipeline.prepare_image(tiny_png(opaque=True))
    inspect_png(base64.b64decode(output["data"]))
    assert len(transport.calls) == 2
    assert transport.calls[1][1] == "https://external.api.recraft.ai/v1/images/removeBackground"
    request = json.loads(transport.calls[1][2]["body"])
    assert request["response_format"] == "b64_json"
    assert request["image_url"].startswith("data:image/png;base64,")


def test_redirect_cannot_forward_provider_authorization(generation_settings, monkeypatch):
    import urllib.error

    import nunti.characters.providers as providers

    handlers = []

    class RedirectingResponse:
        def open(self, request, timeout):
            assert request.get_header("Authorization") == "Bearer fake"
            raise urllib.error.HTTPError(
                request.full_url, 302, "redirect", {"Location": "https://other.invalid/"}, None
            )

    def opener(*items):
        handlers.extend(items)
        return RedirectingResponse()

    monkeypatch.setattr(providers.urllib.request, "build_opener", opener)
    with pytest.raises(ValueError, match="PROVIDER_HTTP_302"):
        providers.Transport().request(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={"Authorization": "Bearer fake"},
            body=b"{}",
        )
    assert len(handlers) == 1 and isinstance(handlers[0], providers.NoRedirect)
    assert (
        handlers[0].redirect_request(None, None, 302, "redirect", {}, "https://other.invalid")
        is None
    )


def test_long_decoded_audio_is_rejected_instead_of_successfully_truncated(monkeypatch):
    # Authored 31-second decoded PCM; cannot use pcm_wav helper which correctly
    # rejects overlong material already at the boundary.
    import io
    import wave
    from types import SimpleNamespace

    import nunti.characters.media as media

    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 24000, 0, "NONE", "NONE"))
        wav.writeframes(bytes(31 * 24000 * 2))
    monkeypatch.setattr(
        media.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=output.getvalue()),
    )
    with pytest.raises(ValueError, match="INVALID_PCM_AUDIO"):
        media.normalize_audio(b"non-wav-compressed-fixture", "mp3", "/fixture/ffmpeg")


def test_cost_unknown_is_not_zero_and_fixture_is_really_zero(generation_settings):
    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        value = input_value()
        store.submit("a", value, "API")
        job = store.claim("one")
        store.begin_step(job, "image", {}, 15000)
        store.finish_step(job, "image", {"usage": "not enough to compute actual account billing"})
        cost = store.get_job("a", value["requestId"])["cost"]
        assert cost["actualMicros"] is None
        assert cost["reservedMicros"] == 15000
        assert cost["complete"] is False


def test_saved_voice_remains_usable_after_default_pipeline_changes(generation_settings):
    settings = generation_settings
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN_A}"}) as client:
        store = client.app.state.character_store
        data(client.post("/v2/character-generations", json=input_value()))
        generated = GenerationWorker(store, settings).run_once()
        artifact = generated["artifact"]
        fixture = FixturePipeline(settings)
        text = fixture.followup["metadata"]["text"]
        store.submit(
            "a",
            {"requestId": str(uuid4()), "text": text},
            "OFFLINE_FIXTURE",
            artifact["characterId"],
        )
        changed_default = replace(settings, generation_pipeline="GOOGLE_COMPARE")
        worker = GenerationWorker(store, changed_default)
        names = []
        original = worker._pipeline

        def recording(mode, pipeline_name=None, **kwargs):
            names.append(pipeline_name)
            return original(mode, pipeline_name, **kwargs)

        worker._pipeline = recording
        speech = worker.run_once()
        assert speech["state"] == "READY", speech
        assert names == ["OPENAI_ELEVEN"]
        assert (
            speech["speechManifest"]["clips"][0]["source"]
            == artifact["voiceManifest"]["clips"][0]["source"]
        )


def test_idle_worker_sigterm_exits_and_releases_global_lease(generation_settings):
    import os
    import subprocess
    import sys
    import time

    settings = generation_settings
    with TestClient(create_app(settings)) as client:
        store = client.app.state.character_store
        env = os.environ.copy()
        # This subprocess never gets real provider credentials.
        for key in ("OPENAI_API_KEY", "ELEVENLABS_API_KEY", "GOOGLE_API_KEY", "RECRAFT_API_TOKEN"):
            env.pop(key, None)
        env.update(
            NUNTI_AUTH_TOKENS=json.dumps({TOKEN_A: "a"}),
            NUNTI_DB_PATH=str(settings.db_path),
            NUNTI_GENERATION_MODE="OFFLINE_FIXTURE",
            NUNTI_FIXTURE_PNG=str(settings.fixture_png),
            NUNTI_FIXTURE_MANIFEST=str(settings.fixture_manifest),
            NUNTI_REQUIRE_HTTPS="false",
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "nunti.characters.worker"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            time.sleep(0.3)
            assert process.poll() is None
            process.terminate()
            assert process.wait(timeout=3) == 0
            with store.connect() as db:
                assert db.execute("SELECT count(*) FROM worker_lock").fetchone()[0] == 0
            assert store.claim("replacement") is None
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)


def test_v2_exported_schemas_match_authoritative_models():
    from pathlib import Path

    from nunti.characters import models

    directory = Path(__file__).resolve().parents[2] / "contracts/v2"
    for name in (
        "GenerationInput",
        "SpeechInput",
        "Concept",
        "DesignedVoiceSource",
        "VoiceManifest3",
        "CharacterArtifact",
        "JobView",
    ):
        schema = json.loads((directory / (name + ".schema.json")).read_text())
        schema.pop("$schema")
        schema.pop("$id")
        assert schema == getattr(models, name).model_json_schema()


def test_duplicate_planned_text_is_rejected_before_image_or_voice_work(generation_settings):
    from pydantic import ValidationError

    from nunti.characters.models import InitialTexts

    with pytest.raises(ValidationError, match="INITIAL_SPEECH_TEXTS_MUST_BE_DISTINCT"):
        InitialTexts(greeting=" 같은 본문 ", common="같은 본문", arrival="다른 본문")
    assert InitialTexts(greeting=" 첫 본문 ", common="둘째", arrival="셋째").greeting == "첫 본문"

    class DuplicatePlanningFixture(FixturePipeline):
        def plan(self, value):
            result = super().plan(value)
            result["texts"]["common"] = result["texts"]["greeting"]
            return result

        def images(self, value, concept):
            pytest.fail("Invalid planned text must fail before image generation")

        def voice_candidates(self, value, concept):
            pytest.fail("Invalid planned text must fail before voice generation")

    with TestClient(create_app(generation_settings)) as client:
        store = client.app.state.character_store
        store.submit("a", input_value(), "OFFLINE_FIXTURE")
        result = GenerationWorker(
            store, generation_settings, lambda mode: DuplicatePlanningFixture(generation_settings)
        ).run_once()
        assert result["state"] == "FAILED"
        with store.connect() as db:
            assert [row[0] for row in db.execute("SELECT name FROM steps ORDER BY name")] == [
                "planning",
                "preflight",
            ]


def test_critic_receives_actual_route_guide_separate_from_numbered_candidates(generation_settings):
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "imageIndex": 0,
                                    "voiceIndex": 0,
                                    "rationale": "Relative contract-test choice",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    transport = RecordingTransport([{"data": [{"b64_json": b64(tiny_png())}] * 2}, response])
    pipeline = ApiPipeline(api_settings(generation_settings), transport)
    concept = FixturePipeline(generation_settings).plan(input_value())
    images = pipeline.images(input_value(), concept)
    voices = {"candidates": [{"audio": b64(b"fixture-audio"), "mime": "audio/wav"}]}
    selection = pipeline.select(concept, images, voices)
    assert selection["humanApproved"] is False
    request = json.loads(transport.calls[1][2]["body"])
    parts = request["contents"][0]["parts"]
    index = next(
        i
        for i, part in enumerate(parts)
        if part.get("text", "").startswith("Actual journey route guide")
    )
    assert parts[index + 1]["inlineData"]["data"] == images["referenceRoutePng"]
    assert sha(base64.b64decode(images["referenceRoutePng"])) == images["referenceRouteHash"]
