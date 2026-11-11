"""The new layer mode reuses Studio persistence without changing legacy requests."""

import io
import socket
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from nunti.avatar_studio.api import Settings, create_app
from nunti.avatar_studio.models import AvatarInput, Route, digest
from nunti.avatar_studio.variant_spec import VariantContext, build_avatar_spec

ORIGIN = "http://127.0.0.1:8768"
TOKEN = "layered-studio-test-token-0123456789012345"


def route_input():
    return {
        "points": [[0.1, 0.7], [0.4, 0.3], [0.8, 0.6]],
        "inputOrigin": "ROUTE_FILE",
        "sourceLabel": "로컬 검토 경로",
        "confirmed": True,
    }


def input_value():
    return {
        "requestId": str(uuid4()),
        "destination": {"name": "바다", "traits": "사용자가 고른 목적지"},
        "purpose": "쉬기",
        "route": route_input(),
        "renderMode": "LOCAL_LAYERS",
        "variantContext": {
            "routeId": "review-route-1",
            "seed": "seed-4",
            "destinationCategory": "coast",
            "roadType": "highway",
            "userSelectedMood": "curious",
        },
    }


def isolated_renderer(context, route):
    """Exercise the real mapper and HTTP storage independently of the art package."""
    spec = build_avatar_spec(context, route)
    color = tuple(bytes.fromhex(digest(spec["variantId"].encode()))[:3]) + (255,)
    image = Image.new("RGBA", (768, 768))
    image.paste(color, (128, 64, 640, 704))
    data = io.BytesIO()
    image.save(data, "PNG")
    return data.getvalue(), {
        "displayName": "눈티",
        "personality": "같은 기본 눈티의 여행 표현",
        "palette": list(spec["palette"].values()),
        "motifs": [
            {"label": "레이어", "source": "로컬", "target": "장식", "detail": "공통 자산 선택"}
        ],
        "voice": {"description": "기존 음성 계획 유지", "rate": 1.0, "pitch": 1.0},
        "avatarSpec": spec,
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


def test_layered_http_is_stable_across_request_ids_and_persists_sidecar(settings, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Layer rendering must not call inference, legacy rendering or a network"
        )

    monkeypatch.setattr(socket, "create_connection", forbidden)
    with client_for(
        settings,
        layered_renderer=isolated_renderer,
        renderer=forbidden,
        api_renderer=forbidden,
        local_renderer=forbidden,
    ) as client:
        value = input_value()
        first_response = client.post("/v3/avatars", json=value)
        assert first_response.status_code == 200, first_response.text
        first = first_response.json()["data"]
        assert first["mediaOrigin"] == "LOCAL_LAYERS"
        assert first["formationStatus"] == "STATIC_LAYER_COMPOSITE"
        assert "formation" not in first["design"]
        assert first["voice"]["status"] == "PLANNED"
        assert first["voice"]["automaticPlayback"] is False
        assert client.post("/v3/avatars", json=value).json()["data"] == first
        second = client.post("/v3/avatars", json={**value, "requestId": str(uuid4())}).json()[
            "data"
        ]
        assert second["characterId"] != first["characterId"]
        assert second["visual"] == first["visual"]
        assert second["design"]["avatarSpec"] == first["design"]["avatarSpec"]
        png = client.get(first["visual"]["path"])
        assert digest(png.content) == first["visual"]["sha256"]
        spec = client.get(first["avatarSpec"]["path"])
        assert spec.headers["content-type"].startswith("application/json")
        assert spec.json() == first["design"]["avatarSpec"]
        assert digest(spec.content) == first["avatarSpec"]["sha256"]
        conflict = {**value, "variantContext": {**value["variantContext"], "seed": "changed"}}
        assert client.post("/v3/avatars", json=conflict).status_code == 409
    with client_for(settings, layered_renderer=forbidden) as restored:
        assert restored.get("/v3/avatars/" + first["characterId"]).json()["data"] == first
        assert restored.get(first["visual"]["path"]).content == png.content
        assert restored.get(first["avatarSpec"]["path"]).content == spec.content


def test_missing_route_only_works_for_explicit_layer_mode(settings):
    value = input_value()
    value.pop("route")
    with client_for(settings, layered_renderer=isolated_renderer) as client:
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["route"] is None
        spec = result["design"]["avatarSpec"]
        assert spec["expression"] == "base"
        assert spec["destinationMotif"] == spec["roadMotif"] == "none"
        assert "MISSING_ROUTE" in spec["fallbackReasons"]
        for mode in ("LOCAL_RENDER", "IMAGE_API", "LOCAL_MODEL"):
            legacy = {**value, "renderMode": mode}
            legacy.pop("variantContext")
            assert client.post("/v3/avatars", json=legacy).status_code == 422


def test_layer_context_does_not_silently_change_legacy_rendering():
    value = input_value()
    value["renderMode"] = "LOCAL_RENDER"
    with pytest.raises(ValidationError, match="VARIANT_CONTEXT_REQUIRES_LOCAL_LAYERS"):
        AvatarInput.model_validate(value)
    value.pop("variantContext")
    before = dict(value)
    assert AvatarInput.model_validate(value).model_dump(exclude_none=True) == before


def test_matrix_uses_identical_core_and_one_motif_per_slot():
    route = Route.model_validate(route_input())
    combinations = []
    for destination in ("coast", "mountain", "city"):
        for mood in ("calm", "curious", "adventurous"):
            context = VariantContext(destinationCategory=destination, userSelectedMood=mood)
            spec = build_avatar_spec(context, route)
            assert spec == build_avatar_spec(context, route)
            assert spec["destinationMotif"] == destination
            assert spec["expression"] == mood
            assert spec["motion"] == "none"
            assert spec["layers"][:6] == [
                {"id": "core-" + p, "path": "core/" + p + ".png"}
                for p in ("body", "head", "sprout", "scarf", "bag", "badge")
            ]
            assert sum(layer["id"].startswith("destination-") for layer in spec["layers"]) == 1
            assert sum(layer["id"].startswith("expression-") for layer in spec["layers"]) == 1
            assert all(
                ".." not in layer["path"] and not layer["path"].startswith("/")
                for layer in spec["layers"]
            )
            combinations.append(spec["variantId"])
    assert len(set(combinations)) == 9


def test_missing_fields_and_unsupported_categories_have_documented_fallbacks():
    route = Route.model_validate(route_input())
    missing = build_avatar_spec(VariantContext(), route)
    assert missing["expression"] == "base"
    assert missing["destinationMotif"] == missing["roadMotif"] == "none"
    assert set(missing["fallbackReasons"]) == {
        "MISSING_MOOD",
        "UNKNOWN_DESTINATION",
        "UNKNOWN_ROAD_TYPE",
    }
    unsupported = build_avatar_spec(
        VariantContext(destinationCategory="nature", userSelectedMood="bright"),
        route,
    )
    assert unsupported["expression"] == "base" and unsupported["destinationMotif"] == "none"
    assert "UNSUPPORTED_DESTINATION" in unsupported["fallbackReasons"]
    assert "UNSUPPORTED_MOOD" in unsupported["fallbackReasons"]


def test_input_labels_cannot_fabricate_sdk_fields_or_driver_mood():
    route = Route.model_validate(route_input())
    spec = build_avatar_spec(
        VariantContext(
            destinationCategory="coast",
            roadType="urban",
            userSelectedMood="calm",
            provenance={
                "destinationCategory": "direct-sdk",
                "roadType": "direct-sdk",
                "userSelectedMood": "app-derived",
            },
        ),
        route,
    )
    assert spec["destinationMotif"] == spec["roadMotif"] == "none"
    assert spec["expression"] == "base"
    assert "direct-sdk" not in spec["provenance"].values()
    assert "MOOD_NOT_USER_SELECTED" in spec["fallbackReasons"]
    mock = build_avatar_spec(
        VariantContext(
            destinationCategory="coast",
            userSelectedMood="curious",
            provenance={"destinationCategory": "mock", "userSelectedMood": "mock"},
        ),
        route,
    )
    assert mock["provenance"]["destinationCategory"] == "mock"
    assert mock["provenance"]["userSelectedMood"] == "mock"


@pytest.mark.parametrize("source", ["app-derived", "mock", "user-selected", "unknown"])
def test_app_or_mock_route_identifiers_keep_their_declared_provenance(source):
    spec = build_avatar_spec(
        VariantContext(routeId="application-route-hash", provenance={"routeId": source}),
        Route.model_validate(route_input()),
    )
    assert spec["provenance"]["routeId"] == source


def test_route_identifier_cannot_claim_verified_sdk_origin():
    spec = build_avatar_spec(
        VariantContext(routeId="application-route-hash", provenance={"routeId": "direct-sdk"}),
        Route.model_validate(route_input()),
    )
    assert spec["provenance"]["routeId"] == "app-derived"
    assert "ROUTE_ID_SDK_PROVENANCE_NOT_VERIFIED" in spec["fallbackReasons"]


def test_synthetic_route_revision_keeps_mock_provenance():
    spec = build_avatar_spec(
        VariantContext(routeRevision=2, provenance={"routeRevision": "mock"}),
        Route.model_validate(route_input()),
    )
    assert spec["provenance"]["routeRevision"] == "mock"
    sdk_claim = build_avatar_spec(
        VariantContext(routeRevision=2, provenance={"routeRevision": "direct-sdk"}),
        Route.model_validate(route_input()),
    )
    assert sdk_claim["provenance"]["routeRevision"] == "app-derived"
    assert "ROUTE_REVISION_SDK_PROVENANCE_NOT_VERIFIED" in sdk_claim["fallbackReasons"]


@pytest.mark.parametrize(
    "category,accent",
    [
        ("coast", "#5595B0"),
        ("mountain", "#709260"),
        ("city", "#9780B1"),
    ],
)
def test_spec_accent_matches_exported_motif_palette(category, accent):
    spec = build_avatar_spec(
        VariantContext(destinationCategory=category),
        Route.model_validate(route_input()),
    )
    assert spec["palette"]["accent"] == accent


def test_path_revision_seed_and_day_night_are_explicit_mapping_inputs():
    route = Route.model_validate(route_input())
    context = VariantContext(routeId="same-route", roadType="rural", seed="a")
    first = build_avatar_spec(context, route)
    reroute = Route.model_validate(
        {**route_input(), "points": [[0.1, 0.2], [0.4, 0.7], [0.9, 0.3]]}
    )
    changed = build_avatar_spec(context, reroute)
    assert changed["routeFingerprint"] != first["routeFingerprint"]
    assert changed["variantId"] != first["variantId"]
    assert changed["characterId"] == first["characterId"]
    assert changed["layers"][:6] == first["layers"][:6]
    night = build_avatar_spec(context.model_copy(update={"displayMode": "night"}), route)
    assert night["layers"] == first["layers"]
    assert night["palette"]["background"] != first["palette"]["background"]
    assert night["variantId"] != first["variantId"]
    assert (
        build_avatar_spec(context.model_copy(update={"seed": "b"}), route)["variantId"]
        != first["variantId"]
    )
    assert (
        build_avatar_spec(context.model_copy(update={"routeRevision": 2}), route)["variantId"]
        != first["variantId"]
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"destinationCategory": "../../private"},
        {"roadType": "trunk"},
        {"seed": True},
        {"mappingVersion": "future-unavailable"},
        {"routeRevision": 0},
        {"provenance": {"vehicleStress": "direct-sdk"}},
        {"baseAsset": "/private/file"},
    ],
)
def test_invalid_or_unsupported_boundary_values_are_rejected(patch):
    with pytest.raises(ValidationError):
        VariantContext.model_validate(patch)


def test_capabilities_advertises_opt_in_without_changing_default(settings):
    with client_for(settings) as client:
        capabilities = client.get("/v3/capabilities").json()["data"]
        assert capabilities["mode"] == "LOCAL_RENDER"
        assert capabilities["layeredRenderAvailable"] is True
        assert capabilities["layeredRenderInfo"]["motion"] == "none"
        assert capabilities["layeredRenderInfo"]["paidApiCalls"] == 0
