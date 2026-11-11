"""Real bundled PNG composition, failure fallbacks and Studio end-to-end checks."""

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageChops

from nunti.avatar_studio import layered_render
from nunti.avatar_studio.api import Settings, create_app
from nunti.avatar_studio.models import Route, canonical, digest
from nunti.avatar_studio.variant_spec import LayeredAvatarSpec, VariantContext


@pytest.fixture(scope="module")
def shipped_bundle(tmp_path_factory):
    """A snapshot prevents deployment-art edits from sharing mutable test state."""
    target = tmp_path_factory.mktemp("actual-nunti-art") / "bundle"
    shutil.copytree(layered_render.ASSET_ROOT, target)
    return target


@pytest.fixture(autouse=True)
def local_only(shipped_bundle, monkeypatch):
    monkeypatch.setattr(layered_render, "ASSET_ROOT", shipped_bundle)

    def no_network(*args, **kwargs):
        raise AssertionError("Layer variants must work without network access")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(urllib.request, "urlopen", no_network)


def route_input():
    return Route.model_validate(
        {
            "points": [[0.1, 0.7], [0.4, 0.3], [0.8, 0.6]],
            "inputOrigin": "TEST_ROUTE",
            "sourceLabel": "MOCK visual matrix route",
            "confirmed": True,
        }
    )


def variant_context(**changes):
    return VariantContext.model_validate(
        {
            "routeId": "mock-layer-route",
            "seed": "test-37",
            "destinationCategory": "coast",
            "roadType": "rural",
            "userSelectedMood": "curious",
            "provenance": {
                "routeId": "mock",
                "destinationCategory": "mock",
                "roadType": "mock",
                "userSelectedMood": "mock",
            },
            **changes,
        }
    )


def open_png(content):
    image = Image.open(io.BytesIO(content))
    image.load()
    return image


def assert_same_pixels(left, right):
    assert left.mode == right.mode == "RGBA"
    assert left.size == right.size == (768, 768)
    assert ImageChops.difference(left, right).getbbox(alpha_only=False) is None


def test_all_nine_real_variants_reuse_core_and_are_repeatable(shipped_bundle):
    manifest = json.loads((shipped_bundle / "manifest.json").read_text())
    expected_core = {"core/" + name + ".png" for name in manifest["coreOrder"]}
    visual_hashes = set()
    for destination in ("coast", "mountain", "city"):
        for mood in ("calm", "curious", "adventurous"):
            context = variant_context(destinationCategory=destination, userSelectedMood=mood)
            png, design = layered_render.render_layered_avatar(context, route_input())
            repeat_png, repeat_design = layered_render.render_layered_avatar(context, route_input())
            assert png == repeat_png
            assert design == repeat_design
            spec = LayeredAvatarSpec.model_validate(design["avatarSpec"])
            assert spec.destinationMotif == destination and spec.expression == mood
            assert design["renderStatus"] == "COMPOSITED"
            assert design["imageSha256"] == digest(png)
            assert design["faceAnchors"] == manifest["fixedFaceAnchors"]
            assert expected_core.issubset(design["layerAssets"])
            for path, actual_sha in design["layerAssets"].items():
                assert actual_sha == manifest["files"][path]["sha256"]
                assert actual_sha == digest((shipped_bundle / path).read_bytes())
            assert [layer.path for layer in spec.layers[:6]] == [
                "core/" + name + ".png" for name in manifest["coreOrder"]
            ]
            image = open_png(png)
            assert image.size == (768, 768) and image.mode == "RGBA"
            assert image.getchannel("A").getextrema() == (0, 255)
            visual_hashes.add(digest(png))
    assert len(visual_hashes) == 9


def test_no_route_and_missing_context_use_exact_packaged_base_pixels(shipped_bundle):
    with Image.open(shipped_bundle / "base.png") as base:
        for context, route in (
            (None, None),
            (variant_context(), None),
            (VariantContext(), route_input()),
        ):
            png, design = layered_render.render_layered_avatar(context, route)
            assert_same_pixels(open_png(png), base)
            spec = LayeredAvatarSpec.model_validate(design["avatarSpec"])
            assert spec.expression == "base"
            assert spec.destinationMotif == spec.roadMotif == "none"
            if route is None:
                assert "MISSING_ROUTE" in spec.fallbackReasons


@pytest.mark.parametrize(
    "damage",
    [
        "missing-expression",
        "missing-core",
        "corrupt-layer",
        "missing-manifest",
        "corrupt-manifest",
        "unsupported-version",
        "wrong-canvas",
        "missing-face-anchors",
    ],
)
def test_damaged_active_bundle_returns_complete_bundled_base(
    damage,
    shipped_bundle,
    tmp_path,
):
    active = tmp_path / "damaged-active-bundle"
    shutil.copytree(shipped_bundle, active)
    manifest_file = active / "manifest.json"
    if damage == "missing-expression":
        (active / "expressions/curious.png").unlink()
    elif damage == "missing-core":
        (active / "core/head.png").unlink()
    elif damage == "corrupt-layer":
        (active / "destinations/coast.png").write_bytes(b"damaged PNG")
    elif damage == "missing-manifest":
        manifest_file.unlink()
    elif damage == "corrupt-manifest":
        manifest_file.write_text("not JSON")
    else:
        manifest = json.loads(manifest_file.read_text())
        if damage == "unsupported-version":
            manifest["assetVersion"] = "unavailable-future-version"
        elif damage == "wrong-canvas":
            manifest["canvas"] = [1024, 1024]
        elif damage == "missing-face-anchors":
            manifest.pop("fixedFaceAnchors")
        manifest_file.write_text(json.dumps(manifest))
    png, design = layered_render.render_layered_avatar(
        variant_context(),
        route_input(),
        asset_root=active,
    )
    assert design["renderStatus"] == "BASE_FALLBACK"
    spec = LayeredAvatarSpec.model_validate(design["avatarSpec"])
    assert spec.expression == "base" and spec.destinationMotif == spec.roadMotif == "none"
    assert spec.layers[0].path == "fallback/base.png"
    assert set(design["layerAssets"]) == {"fallback/base.png"}
    with Image.open(shipped_bundle / "fallback/base.png") as base:
        assert_same_pixels(open_png(png), base)


def test_day_night_change_display_metadata_without_recoloring_character():
    day, day_design = layered_render.render_layered_avatar(variant_context(), route_input())
    night, night_design = layered_render.render_layered_avatar(
        variant_context(displayMode="night"),
        route_input(),
    )
    assert day == night
    day_spec, night_spec = day_design["avatarSpec"], night_design["avatarSpec"]
    assert day_spec["displayMode"] == "day" and night_spec["displayMode"] == "night"
    assert day_spec["palette"]["background"] != night_spec["palette"]["background"]
    assert day_design["layerAssets"] == night_design["layerAssets"]
    assert day_spec["variantId"] != night_spec["variantId"]


@pytest.mark.parametrize("damage", ["missing", "corrupt", "unsupported"])
def test_default_root_manifest_failure_uses_independent_fallback_manifest(
    damage,
    shipped_bundle,
    tmp_path,
    monkeypatch,
):
    broken = tmp_path / "default-bundle"
    shutil.copytree(shipped_bundle, broken)
    main_manifest = broken / "manifest.json"
    if damage == "missing":
        main_manifest.unlink()
    elif damage == "corrupt":
        main_manifest.write_text("incomplete JSON")
    else:
        manifest = json.loads(main_manifest.read_text())
        manifest["assetVersion"] = "unsupported-version"
        main_manifest.write_text(json.dumps(manifest))
    monkeypatch.setattr(layered_render, "ASSET_ROOT", broken)
    png, design = layered_render.render_layered_avatar(variant_context(), route_input())
    assert design["renderStatus"] == "BASE_FALLBACK"
    assert design["avatarSpec"]["layers"] == [{"id": "fallback-base", "path": "fallback/base.png"}]
    fallback_manifest = json.loads((broken / "fallback/manifest.json").read_text())
    assert (
        design["layerAssets"]["fallback/base.png"]
        == fallback_manifest["files"]["base.png"]["sha256"]
    )
    with Image.open(broken / "fallback/base.png") as base:
        assert_same_pixels(open_png(png), base)


def test_damaged_active_and_fallback_assets_fail_without_inventing_replacement(
    shipped_bundle,
    tmp_path,
    monkeypatch,
):
    broken = tmp_path / "fully-broken-bundle"
    shutil.copytree(shipped_bundle, broken)
    (broken / "core/head.png").unlink()
    (broken / "fallback/base.png").write_bytes(b"corrupt fallback")
    monkeypatch.setattr(layered_render, "ASSET_ROOT", broken)
    with pytest.raises(layered_render.LayerAssetError):
        layered_render.render_layered_avatar(variant_context(), route_input())


def test_path_update_is_recorded_and_keeps_core_and_face_anchors():
    first, first_design = layered_render.render_layered_avatar(variant_context(), route_input())
    route = route_input().model_copy(update={"points": [[0.1, 0.2], [0.3, 0.7], [0.9, 0.4]]})
    changed, changed_design = layered_render.render_layered_avatar(variant_context(), route)
    assert first and changed
    first_spec, changed_spec = first_design["avatarSpec"], changed_design["avatarSpec"]
    assert first_spec["routeFingerprint"] != changed_spec["routeFingerprint"]
    assert first_spec["variantId"] != changed_spec["variantId"]
    assert first_spec["characterId"] == changed_spec["characterId"]
    assert first_spec["layers"][:6] == changed_spec["layers"][:6]
    assert first_design["faceAnchors"] == changed_design["faceAnchors"]
    # Three stripe alternatives do not promise a unique picture for every path.


def test_concurrent_rendering_does_not_change_shared_assets(shipped_bundle):
    before = {
        str(p.relative_to(shipped_bundle)): digest(p.read_bytes())
        for p in shipped_bundle.rglob("*.png")
    }
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(
            workers.map(
                lambda _: layered_render.render_layered_avatar(variant_context(), route_input()),
                range(8),
            )
        )
    assert all(png == results[0][0] and design == results[0][1] for png, design in results)
    after = {
        str(p.relative_to(shipped_bundle)): digest(p.read_bytes())
        for p in shipped_bundle.rglob("*.png")
    }
    assert after == before


def test_fresh_process_reproduces_pixels_and_spec(shipped_bundle):
    script = """
import hashlib, json, socket, sys
from pathlib import Path
from nunti.avatar_studio.layered_render import render_layered_avatar
from nunti.avatar_studio.models import Route, canonical
from nunti.avatar_studio.variant_spec import VariantContext
def offline(*args, **kwargs):
    raise AssertionError('network forbidden')
socket.create_connection = offline
context = VariantContext.model_validate_json(sys.argv[2])
route = Route.model_validate_json(sys.argv[3])
png, design = render_layered_avatar(context, route, asset_root=Path(sys.argv[1]))
spec_sha = hashlib.sha256(canonical(design['avatarSpec']).encode()).hexdigest()
print(json.dumps([hashlib.sha256(png).hexdigest(), spec_sha]))
"""
    context, route = variant_context(), route_input()
    png, design = layered_render.render_layered_avatar(context, route)
    command = [
        sys.executable,
        "-c",
        script,
        str(shipped_bundle),
        context.model_dump_json(),
        route.model_dump_json(),
    ]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    outputs = [
        subprocess.run(
            command, env=env, check=True, capture_output=True, text=True, timeout=30
        ).stdout
        for _ in range(2)
    ]
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0]) == [digest(png), digest(canonical(design["avatarSpec"]).encode())]


def test_actual_art_is_saved_and_served_with_avatar_spec_through_existing_api(tmp_path):
    config = Settings("actual-art-api-test-token-0123456789012345", tmp_path / "studio")
    value = {
        "requestId": str(uuid4()),
        "renderMode": "LOCAL_LAYERS",
        "destination": {"name": "실제 레이어 검토", "traits": "mock local fixture"},
        "route": route_input().model_dump(),
        "variantContext": variant_context().model_dump(),
    }
    with TestClient(
        create_app(config),
        base_url="http://127.0.0.1:8768",
        client=("127.0.0.1", 52100),
        headers={"Authorization": "Bearer " + config.token},
    ) as client:
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        png = client.get(result["visual"]["path"])
        sidecar = client.get(result["avatarSpec"]["path"])
        expected_png, expected_design = layered_render.render_layered_avatar(
            variant_context(), route_input()
        )
        assert png.content == expected_png
        assert digest(png.content) == result["visual"]["sha256"]
        assert sidecar.json() == expected_design["avatarSpec"]
        LayeredAvatarSpec.model_validate(sidecar.json())
        assert sidecar.json() == result["design"]["avatarSpec"]
        assert result["design"]["renderStatus"] == "COMPOSITED"
        assert "formation" not in result["design"]
        replay = client.post("/v3/avatars", json={**value, "requestId": str(uuid4())})
        assert replay.json()["data"]["visual"] == result["visual"]
        assert client.get("/v3/avatars/" + result["characterId"]).json()["data"] == result
