"""Real v3 HTTP/SQLite/Wardrobe/media checks; all provider paths are explicitly fake."""

import base64
import io
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
    return Settings(
        TOKEN,
        tmp_path / "studio",
        paid_api_approved=True,
        wardrobe_enabled=True,
        image_key="unit-test-not-a-key",
    )


def fake_wardrobe(key, prompt):
    image = Image.new("RGBA", (768, 768), (40, 120, 160, 255))
    result = io.BytesIO()
    image.save(result, "PNG")
    return result.getvalue(), {"input_tokens": 10, "output_tokens": 10}, 1000


def client_for(settings, **kwargs):
    kwargs.setdefault("wardrobe_renderer", fake_wardrobe)
    return TestClient(
        create_app(settings, **kwargs),
        base_url=ORIGIN,
        client=("127.0.0.1", 52100),
        headers={"Authorization": "Bearer " + settings.token},
    )


def test_auth_session_csrf_and_loopback(settings):
    with client_for(settings) as client:
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


def test_capabilities_reflect_wardrobe_api_mode(settings):
    with client_for(settings) as client:
        value = client.get("/v3/capabilities").json()["data"]
        assert value["mode"] == "OPENAI_WARDROBE"
        assert value["wardrobeAvailable"] is True
        assert value["voice"]["mode"] == "DEVICE_SPEECH"
        assert value["voice"]["automaticPlayback"] is False
        assert value["habitImprovementEffectVerified"] is False


def test_wardrobe_idempotency_and_restart(settings):
    value = input_value()
    with client_for(settings) as client:
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 200, response.text
        first = response.json()["data"]
        assert first["mediaOrigin"] == "OPENAI_WARDROBE"
        assert first["voice"]["provider"] == "DEVICE_SPEECH"
        assert first["visual"]["width"] == first["visual"]["height"] == 768
        media = client.get(first["visual"]["path"])
        assert digest(media.content) == first["visual"]["sha256"]
        assert client.post("/v3/avatars", json=value).json()["data"] == first
    with client_for(settings) as restored:
        assert restored.get("/v3/avatars/" + first["characterId"]).json()["data"] == first
        assert len(restored.get("/v3/avatars").json()["data"]) == 1
        assert restored.get(first["visual"]["path"]).content == media.content


def test_other_owner_cannot_restore_media_or_extraction(settings):
    def extract(content):
        return {"points": [[0.1, 0.2], [0.8, 0.7]], "confidence": 0.8, "warnings": []}

    source = fake_wardrobe(None, None)[0]
    with client_for(settings, extractor=extract) as client:
        first = client.post("/v3/avatars", json=input_value()).json()["data"]
        extracted = client.post(
            "/v3/route-extractions", json={"imageBase64": base64.b64encode(source).decode()}
        ).json()["data"]
    with client_for(replace(settings, token=OTHER_TOKEN)) as other:
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
    else:
        value["drivingScore"] = 99

    def no_render(*args):
        raise AssertionError("invalid input reached renderer")

    with client_for(settings, wardrobe_renderer=no_render) as client:
        assert client.post("/v3/avatars", json=value).status_code == 422


def test_source_retained_with_confirmed_correction(settings):
    source = fake_wardrobe(None, None)[0]
    points = [[0.1, 0.2], [0.4, 0.5], [0.8, 0.7]]

    def extract(content):
        return {"points": points, "confidence": 0.72, "warnings": ["CONFIRM_ROUTE"]}

    with client_for(settings, extractor=extract) as client:
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


def test_corrupt_input_and_saved_media_fail_closed(settings):
    with client_for(settings) as client:
        assert (
            client.post("/v3/route-extractions", json={"imageBase64": "X" * 32}).status_code == 400
        )
        artifact = client.post("/v3/avatars", json=input_value()).json()["data"]
        path = settings.workspace / "media" / settings.owner / artifact["visual"]["sha256"]
        path.write_bytes(b"tampered")
        assert client.get(artifact["visual"]["path"]).status_code == 409


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

    source = fake_wardrobe(None, None)[0]
    with client_for(settings, extractor=ambiguous) as client:
        response = client.post(
            "/v3/route-extractions",
            json={"imageBase64": base64.b64encode(source).decode(), "colorHint": "blue"},
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


def test_store_recovery_marks_pending_requests_unknown(settings):
    pending = input_value()
    store = StudioStore(settings.workspace)
    store.claim(settings.owner, pending)
    recovered = StudioStore(settings.workspace)
    with pytest.raises(StudioError, match="RESULT_UNKNOWN"):
        recovered.claim(settings.owner, pending)


def test_settings_from_env_auto_loads_dotenv_openai_api_key(tmp_path, monkeypatch):
    import nunti.avatar_studio.api as studio_api

    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENAI_API_KEY=sk-test-dotenv-key-value\n", encoding="utf-8")
    monkeypatch.setattr(studio_api, "ENV_FILES", (dotenv,))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("NUNTI_STUDIO_WORKSPACE", str(tmp_path / "workspace"))
    loaded = Settings.from_env()
    assert loaded.paid_api_approved is True
    assert loaded.wardrobe_enabled is True
    assert loaded.wardrobe_available is True
    assert loaded.chat_available is True
    assert loaded.route_api_enabled is True
