from types import SimpleNamespace

import pytest

from nunti.avatar_studio.models import digest
from nunti.avatar_studio.storage import StudioError, StudioStore
from nunti.avatar_studio.wardrobe import (
    CAP_MICROS,
    LEGACY_VERSION,
    REFERENCE,
    RESERVE_MICROS,
    WardrobeInput,
    brief,
    budget,
    build_prompt,
    create,
    wardrobe_claim,
)


def test_same_brief_is_cached_without_second_paid_call(tmp_path):
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")
    calls = []

    def render(key, prompt):
        calls.append(prompt)
        return b"fake-png", {}, 100_000

    value = WardrobeInput(destination={"name": "서울"}, purpose="면접", mood="calm")
    first = create(settings, store, "owner", value, render)
    second = create(settings, store, "owner", value, render)
    assert first == second and len(calls) == 1
    assert first["design"]["wardrobe"]["look"] == "personal"
    assert budget(store)["reservedUsd"] == RESERVE_MICROS / 1_000_000


def test_budget_refuses_before_provider_and_failure_keeps_reservation(tmp_path):
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")

    def failed(*args):
        raise StudioError("WARDROBE_RESULT_UNKNOWN")

    value = WardrobeInput(destination={"name": "서울"}, purpose="면접")
    with pytest.raises(StudioError):
        create(settings, store, "owner", value, failed)
    assert budget(store)["reservedUsd"] == RESERVE_MICROS / 1_000_000
    with store.connect() as db:
        db.execute("UPDATE requests SET reserved_micros=?", (CAP_MICROS,))
    with pytest.raises(StudioError, match="IMAGE_API_BUDGET_REACHED"):
        create(
            settings,
            store,
            "owner",
            WardrobeInput(destination={"name": "병원"}, purpose="외래 진료"),
            lambda *a: pytest.fail("must not spend"),
        )


def test_undecided_destination_keeps_base_character_without_paid_call(tmp_path):
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")
    value = WardrobeInput(destination={"name": "아직 미정"})
    artifact = create(
        settings, store, "owner", value, lambda *a: pytest.fail("must not call image provider")
    )
    assert artifact["design"]["wardrobe"]["look"] == "default"
    assert artifact["displayName"] == "기본 눈티"
    assert budget(store)["calls"] == 0


@pytest.mark.parametrize(
    "purpose",
    [
        "도자기 공방에서 첫 접시를 빚으러",
        "친구의 독립영화 첫 상영을 보러",
        "병원 진료가 아니라 로비에서 열리는 작은 사진 전시를 보러",
    ],
)
def test_freeform_context_and_explicit_mood_affect_versioned_brief(purpose):
    value = WardrobeInput(destination={"name": "서울"}, purpose=purpose, mood="calm")
    _, seed, result = brief(value)
    assert result["id"] == "personal"
    assert purpose in build_prompt(value, seed, result)
    assert seed != brief(value.model_copy(update={"mood": "curious"}))[1]


def test_legacy_purchase_reuses_original_character(tmp_path):
    store = StudioStore(tmp_path)
    value = WardrobeInput(destination={"name": "서울"}, purpose="면접")
    raw = value.model_dump(exclude_none=True)
    claim = wardrobe_claim(raw, LEGACY_VERSION, digest(REFERENCE.read_bytes()))
    store.claim("owner", claim, reserved=2_000_000, cap=CAP_MICROS)
    character = {
        "characterId": "nunti-" + claim["requestId"],
        "design": {"wardrobe": {"look": "formal"}},
    }
    store.complete("owner", claim["requestId"], character)
    assert (
        create(
            SimpleNamespace(wardrobe_available=True),
            store,
            "owner",
            value,
            lambda *_: pytest.fail("must reuse a purchased wardrobe"),
        )
        == character
    )
    assert budget(store)["calls"] == 1


def test_changed_api_route_is_rejected_before_paid_reservation(tmp_path):
    from nunti.avatar_studio.models import canonical, digest
    from nunti.avatar_studio.route_api import PlanStore

    store = StudioStore(tmp_path)
    plan = {"destination": {"name": "회사"}, "routePoints": [[0.1, 0.2], [0.8, 0.9]]}
    plan["planId"] = digest(canonical(plan).encode())
    PlanStore(store).put("owner", plan)
    route = {
        "confirmed": True,
        "inputOrigin": "API_ROUTE",
        "sourceLabel": "시험 경로",
        "apiPlanId": plan["planId"],
        "points": [[0.1, 0.1], [0.9, 0.9]],
    }
    value = WardrobeInput(
        destination={"name": plan["destination"]["name"]}, purpose="면접", route=route
    )
    with pytest.raises(StudioError, match="API_ROUTE_POINTS_MISMATCH"):
        create(
            SimpleNamespace(wardrobe_available=True, image_key="test"),
            store,
            "owner",
            value,
            lambda *args: pytest.fail("Changed route must not call a paid model"),
        )
    assert budget(store)["reservedUsd"] == 0


def test_shared_rig_exports_bound_textures_and_reuses_cached_bundle(tmp_path):
    import json

    store = StudioStore(tmp_path)
    value = WardrobeInput(
        destination={"name": "서울"}, purpose="전시 관람", animationRig="nunti-rig-1"
    )
    settings = SimpleNamespace(
        wardrobe_available=True, image_key="test", companion_rig_enabled=True
    )
    calls = []

    def renderer(key, prompt):
        calls.append(prompt)
        assert "ANIMATION REGISTRATION TAKES PRIORITY" in prompt
        return REFERENCE.read_bytes(), {}, 100_000

    artifact = create(settings, store, "owner", value, renderer)
    assert create(settings, store, "owner", value, renderer) == artifact
    assert len(calls) == 1
    rig = artifact["design"]["animationRig"]
    assert rig["textureSha256"] == artifact["visual"]["sha256"]
    payload, mime = store.asset("owner", rig["manifest"]["sha256"])
    definition = json.loads(payload)
    assert mime == "application/json"
    assert set(definition["parts"]) >= {
        "head",
        "torso",
        "leftArm",
        "rightArm",
        "leftLeg",
        "rightLeg",
        "leftEye",
        "rightEye",
        "mouth",
    }
    for part in definition["parts"].values():
        data, kind = store.asset("owner", part["sha256"])
        assert digest(data) == part["sha256"] and kind == "image/png"
    with pytest.raises(StudioError, match="ASSET_NOT_FOUND"):
        store.asset("other-owner", rig["manifest"]["sha256"])


def test_shared_rig_rejects_unregistered_image_without_repeating_paid_request(tmp_path):
    import io

    from PIL import Image

    store = StudioStore(tmp_path)
    value = WardrobeInput(destination={"name": "서울"}, animationRig="nunti-rig-1")
    output = io.BytesIO()
    Image.new("RGBA", (768, 768), "red").save(output, "PNG")
    calls = []

    def renderer(key, prompt):
        calls.append(prompt)
        return output.getvalue(), {}, 100_000

    for _ in range(2):
        with pytest.raises(StudioError, match="COMPANION_RIG_ALIGNMENT"):
            create(
                SimpleNamespace(
                    wardrobe_available=True, image_key="test", companion_rig_enabled=True
                ),
                store,
                "owner",
                value,
                renderer,
            )
    assert len(calls) == 1
    assert store.avatars("owner") == []
    assert budget(store)["reservedUsd"] == RESERVE_MICROS / 1_000_000


def test_shared_rig_rejects_missing_eyes_even_when_body_registration_matches(tmp_path):
    import io

    from PIL import Image, ImageDraw

    image = Image.open(REFERENCE).convert("RGBA")
    paint = ImageDraw.Draw(image)
    for rectangle in ((260, 220, 366, 323), (413, 220, 516, 323)):
        paint.rectangle(rectangle, fill=(255, 216, 194, 255))
    output = io.BytesIO()
    image.save(output, "PNG")
    value = WardrobeInput(destination={"name": "서울"}, animationRig="nunti-rig-1")
    with pytest.raises(StudioError, match="COMPANION_RIG_ALIGNMENT"):
        create(
            SimpleNamespace(wardrobe_available=True, image_key="test", companion_rig_enabled=True),
            StudioStore(tmp_path),
            "owner",
            value,
            lambda *_: (output.getvalue(), {}, 100_000),
        )


def test_rig_director_cannot_reintroduce_free_pose_or_held_props(monkeypatch):
    from urllib.error import URLError

    from nunti.avatar_studio import wardrobe

    value = WardrobeInput(destination={"name": "해변"}, animationRig="nunti-rig-1")
    _, seed, look = brief(value)
    prompt = build_prompt(value, seed, look)
    requests = []

    class OfflineOpener:
        def open(self, request, timeout):
            requests.append(request.data.decode("utf-8", errors="replace"))
            raise URLError("offline test")

    monkeypatch.setattr(
        wardrobe,
        "research_destination_brief",
        lambda *_: {
            "destinationVibe": "coast",
            "colorPalette": "coral and aqua",
            "outfitAndFootwear": "linen jacket",
            "poseAndProp": "HOLD_A_CUP",
            "headAndExpression": "CLOSE_BOTH_EYES",
        },
    )
    monkeypatch.setattr(wardrobe.urllib.request, "build_opener", lambda *_: OfflineOpener())
    with pytest.raises(StudioError, match="WARDROBE_RESULT_UNKNOWN"):
        wardrobe.render("test", prompt)
    assert len(requests) == 1
    assert "ANIMATION REGISTRATION TAKES PRIORITY" in requests[0]
    assert "HOLD_A_CUP" not in requests[0] and "CLOSE_BOTH_EYES" not in requests[0]
    assert "coral and aqua" in requests[0]


def test_invalid_paid_response_is_retained_for_local_diagnosis_without_retry(tmp_path, monkeypatch):
    import io

    from nunti.avatar_studio import wardrobe

    raw = b'{"data":[{"unexpected":"provider-format"}]}'
    calls = []

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return io.BytesIO(raw)

    monkeypatch.setattr(wardrobe.urllib.request, "build_opener", lambda *_: Opener())
    value = WardrobeInput(destination={"name": "쿠팡 서울 1센터"}, purpose="아르바이트")
    store = StudioStore(tmp_path)
    settings = SimpleNamespace(wardrobe_available=True, image_key="test")
    for _ in range(2):
        with pytest.raises(StudioError, match="WARDROBE_INVALID_RESPONSE"):
            create(settings, store, "owner", value, wardrobe.render)
    assert len(calls) == 1
    claim = wardrobe_claim(
        value.model_dump(exclude_none=True), wardrobe.VERSION, digest(REFERENCE.read_bytes())
    )
    assert store.provider_response("owner", claim["requestId"]) == raw
    with pytest.raises(StudioError, match="PROVIDER_RESPONSE_NOT_FOUND"):
        store.provider_response("other-owner", claim["requestId"])
    assert budget(store)["calls"] == 1


@pytest.mark.parametrize(
    ("size", "color", "expected"),
    [
        ((512, 512), (0, 0, 0, 0), "WARDROBE_IMAGE_SIZE"),
        ((1024, 1024), (240, 220, 200, 255), "WARDROBE_ALPHA_MISSING"),
    ],
)
def test_provider_image_validation_keeps_its_specific_error(monkeypatch, size, color, expected):
    import base64
    import io
    import json

    from PIL import Image

    from nunti.avatar_studio import wardrobe

    image = io.BytesIO()
    Image.new("RGBA", size, color).save(image, "PNG")
    raw = json.dumps({"data": [{"b64_json": base64.b64encode(image.getvalue()).decode()}]}).encode()
    opener = SimpleNamespace(open=lambda *args, **kwargs: io.BytesIO(raw))
    monkeypatch.setattr(wardrobe.urllib.request, "build_opener", lambda *_: opener)
    with pytest.raises(StudioError, match=expected):
        wardrobe.render("test", "offline wardrobe validation")


@pytest.mark.parametrize("payload", [None, {"data": []}, {"data": [None]}])
def test_malformed_provider_envelopes_fail_explicitly_without_leaking_payload(
    monkeypatch, caplog, payload
):
    import io
    import json

    from nunti.avatar_studio import wardrobe

    raw = json.dumps(payload).encode()
    opener = SimpleNamespace(open=lambda *args, **kwargs: io.BytesIO(raw))
    monkeypatch.setattr(wardrobe.urllib.request, "build_opener", lambda *_: opener)
    with pytest.raises(StudioError, match="WARDROBE_INVALID_RESPONSE"):
        wardrobe.render("test-key-never-log", "private prompt never log")
    assert "stage=image_payload" in caplog.text
    assert "test-key-never-log" not in caplog.text and "private prompt" not in caplog.text


def test_corrupt_image_is_distinguished_from_unknown_transport_outcome(monkeypatch, caplog):
    import base64
    import io
    import json

    from nunti.avatar_studio import wardrobe

    raw = json.dumps(
        {"data": [{"b64_json": base64.b64encode(b"private-invalid-image").decode()}]}
    ).encode()
    opener = SimpleNamespace(open=lambda *args, **kwargs: io.BytesIO(raw))
    monkeypatch.setattr(wardrobe.urllib.request, "build_opener", lambda *_: opener)
    with pytest.raises(StudioError, match="WARDROBE_INVALID_RESPONSE"):
        wardrobe.render("test", "offline image validation")
    assert "stage=image" in caplog.text
    assert "private-invalid-image" not in caplog.text


def test_documented_gpt_image_response_is_saved_at_the_existing_output_size(monkeypatch):
    import base64
    import io
    import json

    from PIL import Image

    from nunti.avatar_studio import wardrobe

    image = io.BytesIO()
    with Image.open(REFERENCE) as source:
        source.resize((1024, 1024)).save(image, "PNG")
    usage = {"input_tokens_details": {"text_tokens": 10, "image_tokens": 20}, "output_tokens": 30}
    raw = json.dumps(
        {
            "data": [
                {
                    "b64_json": base64.b64encode(image.getvalue()).decode(),
                    "generation_id": "test-generation",
                }
            ],
            "usage": usage,
        }
    ).encode()
    opener = SimpleNamespace(open=lambda *args, **kwargs: io.BytesIO(raw))
    monkeypatch.setattr(wardrobe.urllib.request, "build_opener", lambda *_: opener)
    value = WardrobeInput(destination={"name": "쿠팡 서울 1센터"}, purpose="아르바이트")
    _, seed, look = brief(value)
    content, reported, estimate = wardrobe.render("test", build_prompt(value, seed, look))
    with Image.open(io.BytesIO(content)) as output:
        assert output.size == (768, 768) and output.mode == "RGBA"
    assert reported == usage and estimate == 1110
