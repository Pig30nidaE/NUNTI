"""Real v3 HTTP/SQLite/render/media checks; all provider paths are explicitly fake."""

import base64
import io
import json
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from nunti.avatar_studio.api import COOKIE, ROOT, Settings, create_app
from nunti.avatar_studio.models import digest
from nunti.avatar_studio.storage import StudioError, StudioStore

TOKEN = "studio-unit-test-token-a-0123456789012345"
OTHER_TOKEN = "studio-unit-test-token-b-0123456789012345"
ORIGIN = "http://127.0.0.1:8768"


def input_value():
    return {
        "requestId": str(uuid4()),
        "destination": {"name": "작은 바다", "traits": "푸른 물빛"},
        "purpose": "가족과 쉬기",
        "route": {
            "points": [[0.1, 0.7], [0.4, 0.3], [0.8, 0.6]],
            "inputOrigin": "ROUTE_FILE",
            "sourceLabel": "시험 경로 좌표",
            "confirmed": True,
        },
    }


@pytest.fixture
def settings(tmp_path):
    return Settings(TOKEN, tmp_path / "studio")


def client_for(settings, **kwargs):
    return TestClient(
        create_app(settings, **kwargs),
        base_url=ORIGIN,
        client=("127.0.0.1", 52100),
        headers={"Authorization": "Bearer " + settings.token},
    )


def fake_render(*args):
    image = Image.new("RGBA", (768, 768), (40, 120, 160, 100))
    image.putpixel((0, 0), (0, 0, 0, 0))
    result = io.BytesIO()
    image.save(result, "PNG")
    return result.getvalue(), {
        "displayName": "시험 눈티",
        "personality": "조용한 동반자",
        "palette": ["#2878a0"],
        "motifs": [
            {
                "label": "경로",
                "source": "입력선",
                "target": "내부 무늬",
                "detail": "입력선 시험 모티브",
            }
        ],
        "voice": {"description": "기존 기기 화자 시험", "rate": 1.0, "pitch": 1.0},
    }


def test_auth_session_csrf_and_loopback(settings):
    with client_for(settings, renderer=fake_render) as client:
        assert client.get("/v3/capabilities", headers={"Authorization": "wrong"}).status_code == 401
        assert client.get("/v3/capabilities", headers={"Host": "evil.test:8768"}).status_code == 403
        assert (
            client.get("/v3/capabilities", headers={"Origin": "http://evil.test"}).status_code
            == 403
        )
        assert (
            client.post(
                "/session", json={"token": TOKEN}, headers={"Origin": "http://evil.test"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/session", content="token=" + TOKEN, headers={"Content-Type": "text/plain"}
            ).status_code
            == 415
        )
        assert client.post("/session", json={"token": "가" * 35}).status_code == 401
        response = client.post("/session", json={"token": TOKEN}, headers={"Origin": ORIGIN})
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        client.headers.pop("Authorization")
        assert COOKIE in client.cookies
        assert client.get("/v3/capabilities").status_code == 200
        assert client.post("/v3/avatars", json=input_value()).status_code == 403
        assert (
            client.post("/v3/avatars", json=input_value(), headers={"Origin": ORIGIN}).status_code
            == 200
        )


def test_capabilities_separate_generated_voice_and_local_render(settings):
    with client_for(settings) as client:
        value = client.get("/v3/capabilities").json()["data"]
        assert value["mode"] == "LOCAL_RENDER" and value["imageApiAvailable"] is False
        assert value["voice"]["mode"] == "LOCAL_VOICE_DESIGN"
        assert value["voice"]["newVoiceGenerated"] is True
        assert value["voice"]["automaticPlayback"] is False
        assert value["voice"]["blocksVisualReady"] is False
        assert value["habitImprovementEffectVerified"] is False


def test_real_render_idempotency_new_journey_and_restart(settings):
    value = input_value()
    with client_for(settings) as client:
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 200, response.text
        first = response.json()["data"]
        assert first["mediaOrigin"] == "LOCAL_RENDER"
        assert first["voice"]["provider"] == "LOCAL_QWEN_VOICE_DESIGN"
        assert first["voice"]["status"] == "PLANNED"
        assert first["voice"]["newVoiceGenerated"] is False
        assert "audio" not in first["voice"]
        assert first["visual"]["width"] == first["visual"]["height"] == 768
        media = client.get(first["visual"]["path"])
        assert digest(media.content) == first["visual"]["sha256"]
        with Image.open(io.BytesIO(media.content)) as image:
            assert image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255
        assert client.post("/v3/avatars", json=value).json()["data"] == first
        conflict = {**value, "purpose": "다른 목적"}
        assert client.post("/v3/avatars", json=conflict).status_code == 409
        second = client.post("/v3/avatars", json={**value, "requestId": str(uuid4())}).json()[
            "data"
        ]
        assert second["visual"]["sha256"] != first["visual"]["sha256"]
        changed = input_value()
        changed["destination"] = {"name": "초록 숲", "traits": "푸른 나뭇잎"}
        changed["route"]["points"] = [[0.2, 0.2], [0.25, 0.8], [0.7, 0.7], [0.8, 0.1]]
        third = client.post("/v3/avatars", json=changed).json()["data"]
        assert third["visual"]["sha256"] != first["visual"]["sha256"]
        assert third["design"]["motifs"] != first["design"]["motifs"]
    with client_for(settings) as restored:
        assert restored.get("/v3/avatars/" + first["characterId"]).json()["data"] == first
        assert len(restored.get("/v3/avatars").json()["data"]) == 3
        assert restored.get(first["visual"]["path"]).content == media.content


def test_other_owner_cannot_restore_media_or_extraction(settings):
    def extract(content):
        return {"points": [[0.1, 0.2], [0.8, 0.7]], "confidence": 0.8, "warnings": []}

    source = fake_render()[0]
    with client_for(settings, renderer=fake_render, extractor=extract) as client:
        first = client.post("/v3/avatars", json=input_value()).json()["data"]
        extracted = client.post(
            "/v3/route-extractions", json={"imageBase64": base64.b64encode(source).decode()}
        ).json()["data"]
    with client_for(replace(settings, token=OTHER_TOKEN), renderer=fake_render) as other:
        assert other.get("/v3/avatars").json()["data"] == []
        assert other.get("/v3/avatars/" + first["characterId"]).status_code == 404
        assert other.get(first["visual"]["path"]).status_code == 404
        value = input_value()
        value["route"].update(
            inputOrigin="NAVIGATION_SCREENSHOT", extractionId=extracted["extractionId"]
        )
        assert other.post("/v3/avatars", json=value).status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        "unconfirmed",
        "numeric-confirmed",
        "empty",
        "bool-point",
        "outside",
        "screenshot-no-source",
        "unknown-field",
        "bad-uuid",
    ],
)
def test_reject_invalid_inputs_before_render(settings, change):
    value = input_value()
    if change == "unconfirmed":
        value["route"]["confirmed"] = False
    elif change == "numeric-confirmed":
        value["route"]["confirmed"] = 1
    elif change == "empty":
        value["route"]["points"] = [[0.2, 0.2], [0.2, 0.2]]
    elif change == "bool-point":
        value["route"]["points"][0][0] = True
    elif change == "outside":
        value["route"]["points"][0][0] = 1.1
    elif change == "screenshot-no-source":
        value["route"]["inputOrigin"] = "NAVIGATION_SCREENSHOT"
    elif change == "unknown-field":
        value["drivingScore"] = 99
    else:
        value["requestId"] = "unsafe-id"

    def no_render(*args):
        raise AssertionError("invalid input reached renderer")

    with client_for(settings, renderer=no_render) as client:
        assert client.post("/v3/avatars", json=value).status_code == 422


def test_source_retained_with_confirmed_correction(settings):
    source = fake_render()[0]
    points = [[0.1, 0.2], [0.4, 0.5], [0.8, 0.7]]

    def extract(content):
        return {"points": points, "confidence": 0.72, "warnings": ["CONFIRM_ROUTE"]}

    with client_for(settings, renderer=fake_render, extractor=extract) as client:
        response = client.post(
            "/v3/route-extractions", json={"imageBase64": base64.b64encode(source).decode()}
        )
        assert response.status_code == 200
        original = response.json()["data"]
        assert original["requiresConfirmation"] is True and original["gpsVerified"] is False
        assert client.get(original["imagePath"]).content == source
        value = input_value()
        value["route"].update(
            inputOrigin="NAVIGATION_SCREENSHOT", extractionId=original["extractionId"]
        )
        result = client.post("/v3/avatars", json=value).json()["data"]
        assert result["route"]["sourceImageSha256"] == digest(source)
        assert result["route"]["extractedPoints"] == points
        assert result["route"]["points"] == value["route"]["points"]
        assert result["route"]["userCorrected"] is True


def test_corrupt_input_output_and_saved_media_fail_closed(settings):
    with client_for(settings, renderer=lambda *args: (b"broken", fake_render()[1])) as client:
        assert (
            client.post("/v3/route-extractions", json={"imageBase64": "X" * 32}).status_code == 400
        )
        assert client.post("/v3/avatars", json=input_value()).status_code == 400
        assert client.get("/v3/avatars").json()["data"] == []
    with client_for(settings, renderer=fake_render) as client:
        artifact = client.post("/v3/avatars", json=input_value()).json()["data"]
        path = settings.workspace / "media" / settings.owner / artifact["visual"]["sha256"]
        path.write_bytes(b"tampered")
        assert client.get(artifact["visual"]["path"]).status_code == 409


def test_examples_actual_navigation_extraction_and_render(settings):
    with client_for(settings) as client:
        examples = client.get("/v3/examples").json()["data"]
        assert len(examples) >= 3
        for example in examples[:3]:
            source = client.get(example["imagePath"])
            extracted = client.post(
                "/v3/route-extractions",
                json={"imageBase64": base64.b64encode(source.content).decode()},
            )
            assert extracted.status_code == 200, extracted.text
            proposal = extracted.json()["data"]
            value = {
                "requestId": str(uuid4()),
                "destination": example["destination"],
                "purpose": example["purpose"],
                "route": {
                    "points": proposal["points"],
                    "inputOrigin": "NAVIGATION_SCREENSHOT",
                    "sourceLabel": example["title"],
                    "confirmed": True,
                    "extractionId": proposal["extractionId"],
                },
            }
            response = client.post("/v3/avatars", json=value)
            assert response.status_code == 200, response.text
            assert response.json()["data"]["route"]["sourceImageSha256"] == digest(source.content)


def test_image_api_disabled_no_paid_call_and_budget_reuse(settings):
    calls = []

    def fake_api(config, value, local, design):
        calls.append(value["requestId"])
        return local, {"provider": "TEST_DOUBLE_NOT_LIVE", "actualCostMicros": None}

    value = {**input_value(), "renderMode": "IMAGE_API"}
    with client_for(settings, renderer=fake_render, api_renderer=fake_api) as client:
        assert client.post("/v3/avatars", json=value).status_code == 403
        assert calls == []
    configured = replace(
        settings,
        image_enabled=True,
        paid_api_approved=True,
        image_key="unit-test-not-a-key",
        image_prices_verified=True,
        image_reservation_micros=100_000,
        image_total_cap_micros=100_000,
    )
    with client_for(configured, renderer=fake_render, api_renderer=fake_api) as client:
        first = client.post("/v3/avatars", json=value).json()["data"]
        assert client.post("/v3/avatars", json=value).json()["data"] == first
        assert len(calls) == 1
        assert (
            client.post("/v3/avatars", json={**value, "requestId": str(uuid4())}).status_code == 409
        )
        assert len(calls) == 1
    with client_for(settings, renderer=fake_render, api_renderer=fake_api) as client:
        assert client.post("/v3/avatars", json=value).json()["data"] == first
        assert len(calls) == 1


def test_uncertain_api_and_restart_do_not_repeat_paid_operation(settings):
    configured = replace(
        settings,
        image_enabled=True,
        paid_api_approved=True,
        image_key="unit-test-not-a-key",
        image_prices_verified=True,
        image_reservation_micros=10_000,
    )
    calls = []

    def uncertain(*args):
        calls.append(True)
        raise StudioError("IMAGE_API_RESULT_UNKNOWN", 502)

    value = {**input_value(), "renderMode": "IMAGE_API"}
    with client_for(configured, renderer=fake_render, api_renderer=uncertain) as client:
        assert client.post("/v3/avatars", json=value).status_code == 502
        assert client.post("/v3/avatars", json=value).status_code == 409
        assert len(calls) == 1
    with client_for(configured, renderer=fake_render, api_renderer=uncertain) as client:
        assert client.post("/v3/avatars", json=value).status_code == 409
        assert len(calls) == 1
    pending = input_value()
    store = StudioStore(settings.workspace)
    store.claim(settings.owner, pending)
    recovered = StudioStore(settings.workspace)
    with pytest.raises(StudioError, match="RESULT_UNKNOWN"):
        recovered.claim(settings.owner, pending)


def test_public_static_does_not_expose_source_examples(settings):
    assert ROOT.is_dir()
    with client_for(settings) as client:
        assert client.get("/examples/index.json").status_code == 404
        assert client.get("/../IMPLEMENTATION-CONTRACT.md").status_code == 404


def test_ambiguous_route_and_color_hint_boundary(settings):
    received = []

    def ambiguous(content, color_hint=None):
        received.append(color_hint)
        raise ValueError("MULTIPLE_ROUTES_AMBIGUOUS")

    with client_for(settings, extractor=ambiguous) as client:
        response = client.post(
            "/v3/route-extractions",
            json={"imageBase64": base64.b64encode(fake_render()[0]).decode(), "colorHint": "blue"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "MULTIPLE_ROUTES_AMBIGUOUS"
        assert received == ["blue"]
        assert client.get("/v3/avatars").json()["data"] == []


def test_exif_source_keeps_original_bytes_and_oriented_dimensions(settings):
    image = Image.new("RGB", (400, 200), "white")
    exif = Image.Exif()
    exif[274] = 6
    output = io.BytesIO()
    image.save(output, "JPEG", exif=exif)
    original = output.getvalue()

    def extract(content):
        return {"points": [[0.1, 0.2], [0.8, 0.7]], "confidence": 0.7, "warnings": []}

    with client_for(settings, extractor=extract) as client:
        value = client.post(
            "/v3/route-extractions", json={"imageBase64": base64.b64encode(original).decode()}
        ).json()["data"]
        assert (value["imageWidth"], value["imageHeight"]) == (200, 400)
        assert value["imageSha256"] == digest(original)
        assert client.get(value["imagePath"]).content == original


def test_concurrent_duplicate_does_not_start_second_generation(settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()
    calls = []

    def slow_render(*args):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return fake_render()

    value = input_value()
    with client_for(settings, renderer=slow_render) as client, ThreadPoolExecutor(2) as pool:
        first = pool.submit(client.post, "/v3/avatars", json=value)
        assert entered.wait(5)
        try:
            duplicate = client.post("/v3/avatars", json=value)
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "REQUEST_IN_PROGRESS"
        finally:
            release.set()
        assert first.result().status_code == 200
        assert len(calls) == 1
        assert client.post("/v3/avatars", json=value).status_code == 200
        assert len(calls) == 1


def test_single_key_image_adapter_uses_real_multipart_and_one_post(settings, monkeypatch):
    from nunti.avatar_studio import image_api

    png = fake_render()[0]
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return json.dumps(
                {
                    "data": [{"b64_json": base64.b64encode(png).decode()}],
                    "usage": {"fixtureOnly": True},
                }
            ).encode()

    class FakeTransport:
        def open(self, request, timeout):
            calls.append(request)
            return FakeResponse()

    monkeypatch.setattr(image_api.urllib.request, "build_opener", lambda *args: FakeTransport())
    configured = replace(
        settings,
        image_enabled=True,
        paid_api_approved=True,
        image_key="unit-test-not-a-key",
        image_prices_verified=True,
        image_reservation_micros=10_000,
    )
    value = {**input_value(), "renderMode": "IMAGE_API"}
    with client_for(configured, renderer=fake_render) as client:
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 200, response.text
        artifact = response.json()["data"]
        assert artifact["mediaOrigin"] == "PROVIDER_GENERATED"
        assert artifact["provider"]["actualCostMicros"] is None
        assert artifact["motifsVerification"] == "PROPOSED_NOT_VERIFIED_IN_API_IMAGE"
        assert client.post("/v3/avatars", json=value).json()["data"] == artifact
    assert len(calls) == 1
    sent = calls[0]
    assert sent.full_url == "https://api.openai.com/v1/images/edits"
    assert sent.get_method() == "POST"
    assert b"structure-map.png" in sent.data and b"style-board.png" in sent.data
    assert b"confirmed-route.png" not in sent.data
    assert b"style-board.png" in sent.data and b"design-reference.png" not in sent.data
    assert configured.image_model.encode() in sent.data


def test_existing_key_flags_cannot_skip_explicit_paid_approval(settings):
    configured = replace(
        settings,
        image_enabled=True,
        image_key="unit-test-not-a-key",
        image_prices_verified=True,
        image_reservation_micros=10_000,
    )

    def never_call(*args):
        raise AssertionError("unapproved request reached model adapter")

    with client_for(configured, renderer=never_call, api_renderer=never_call) as client:
        capability = client.get("/v3/capabilities").json()["data"]
        assert capability["imageApiAvailable"] is False
        assert capability["imageApiPaidApprovalRequired"] is True
        response = client.post("/v3/avatars", json={**input_value(), "renderMode": "IMAGE_API"})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PAID_API_APPROVAL_REQUIRED"
        with client.app.state.store.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0


def test_provider_geometry_is_not_misrepresented_as_local_formation(settings):
    def render(*args):
        png, design = fake_render()
        design["formation"] = {"version": "route-volume-2", "privateTestReference": True}
        design["visualIntent"] = {"destinationTheme": "USER_DECLARED_COAST"}
        return png, design

    def api_render(config, value, local, design):
        return local, {"provider": "TEST_DOUBLE_NOT_LIVE", "actualCostMicros": None}

    configured = replace(
        settings,
        image_enabled=True,
        paid_api_approved=True,
        image_key="unit-test-not-a-key",
        image_prices_verified=True,
        image_reservation_micros=10_000,
    )
    with client_for(configured, renderer=render, api_renderer=api_render) as client:
        result = client.post("/v3/avatars", json={**input_value(), "renderMode": "IMAGE_API"})
        assert result.status_code == 200
        artifact = result.json()["data"]
        assert "formation" not in artifact["design"]
        assert artifact["formationStatus"] == "API_GEOMETRY_NOT_VERIFIED"
        assert artifact["motifsVerification"] == "PROPOSED_NOT_VERIFIED_IN_API_IMAGE"
        local = client.post("/v3/avatars", json=input_value()).json()["data"]
        assert local["design"]["formation"]["version"] == "route-volume-2"
