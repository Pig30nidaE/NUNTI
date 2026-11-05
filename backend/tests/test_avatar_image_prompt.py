"""Inspect real prompt/reference bytes without credentials, providers, downloads or inference."""

import io
import json
import math
from dataclasses import replace

import pytest
from PIL import Image

from nunti.avatar_studio.api import Settings
from nunti.avatar_studio.image_api import (
    image_request_references,
    render_api_image,
    route_landmarks,
    structure_reference,
)
from nunti.avatar_studio.models import digest
from nunti.avatar_studio.storage import StudioError


def config(tmp_path):
    return Settings(
        "prompt-test-token-not-an-api-key-1234567",
        tmp_path / "workspace",
        style_asset_dir=tmp_path / "styles",
    )


def inputs():
    value = {
        "requestId": "00000000-0000-4000-8000-000000000001",
        "destination": {"name": "작은 해변", "traits": "파도가 겹치는 해안"},
        "purpose": "가족과 휴식",
        "route": {"points": [[0.1, 0.8], [0.3, 0.3], [0.6, 0.6], [0.8, 0.1]]},
    }
    design = {
        "displayName": "물결 눈티",
        "personality": "조용하고 감싸는 동반자",
        "palette": ["#6aada5", "#d4e4ce", "#dfc392"],
        "visualIntent": {
            "destinationTheme": "COAST",
            "purposeMood": "REST",
            "renderingStyle": "MATTE_ILLUSTRATED_2_5D",
            "evidence": [
                {
                    "source": "USER_DECLARED_TRAITS",
                    "detail": "파도가 겹치는 해안",
                    "target": "mantle overlap",
                }
            ],
            "variationRole": "FINE_DETAILS_ONLY",
            "routeFeatures": {
                "landmarks": [
                    {
                        "arcFraction": 0.35,
                        "pointIndex": 1,
                        "sourcePoint": [0.3, 0.3],
                        "targetPoint": [0.45, 0.4],
                        "part": "mantle",
                        "selection": "LARGE_BEND",
                    }
                ]
            },
        },
        "formation": {
            "version": "route-volume-2",
            "contour": [
                [
                    0.5 + 0.3 * math.cos(i / 192 * 2 * math.pi),
                    0.5 + 0.35 * math.sin(i / 192 * 2 * math.pi),
                ]
                for i in range(192)
            ],
            "spine": [[0.25 + i / 95 * 0.5, 0.7 - i / 95 * 0.4] for i in range(96)],
            "faceCenter": [0.5, 0.45],
        },
    }
    return value, design


def test_prompt_uses_declared_evidence_and_separate_reference_roles(tmp_path):
    value, design = inputs()
    prompt, references, source = image_request_references(config(tmp_path), value, design)
    assert [name for name, _ in references] == [
        "structure-map.png",
        "style-board.png",
    ]
    assert source == "PROCEDURAL_MATERIAL_STUDY"
    assert "not an approved character concept" in prompt
    assert "does not imply human art approval" in prompt
    assert "not verified GPS" in prompt and "not a bend" in prompt
    assert "No glass, no refraction, no glossy specular highlights, no transparent body" in prompt
    assert "only the background outside the character is transparent" in prompt
    assert "palette changes do not fulfill structural personalization" in prompt
    assert "Never copy the route stroke" in prompt
    assert "Its image is deliberately not sent" in prompt
    assert "No route lines, route threads, scars" in prompt
    data = json.loads(prompt.split("USER DATA AND DESIGN INTERPRETATION", 1)[1].split("\n", 1)[1])
    assert data["userDeclaredDestination"] == value["destination"]
    assert data["userDeclaredPurpose"] == value["purpose"]
    assert data["renderingStyle"] == "MATTE_ILLUSTRATED_2_5D"
    assert data["styleAuthority"] == "LATEST_USER_FEEDBACK"
    assert data["visualInterpretation"]["evidence"][0]["source"] == "USER_DECLARED_TRAITS"
    assert data["landmarkCorrespondence"][0]["sourcePoint"] == [0.3, 0.3]
    assert data["landmarkCorrespondence"][0]["part"] == "mantle"
    assert data["correspondenceVerification"] == "PROPOSED_NOT_VERIFIED_IN_GENERATED_PIXELS"
    assert data["surfaceRouteMarking"] == "NONE"
    assert data["routeRole"] == "SILHOUETTE_AND_FORMATION_ONLY"
    assert data["originalRouteImageSent"] is False
    for _, content in references:
        with Image.open(io.BytesIO(content)) as image:
            assert image.format == "PNG" and image.size == (768, 768)
    repeated = image_request_references(config(tmp_path), value, design)
    assert repeated == (prompt, references, source)


def test_structure_image_has_no_route_thread_or_landmark_paint():
    value, design = inputs()
    before = structure_reference(value, design)
    design["formation"]["spine"] = [[0.2, 0.8], [0.5, 0.1], [0.8, 0.8]]
    design["visualIntent"]["routeFeatures"]["landmarks"][0]["targetPoint"] = [0.95, 0.95]
    assert before == structure_reference(value, design)
    with Image.open(io.BytesIO(before)) as image:
        # Geometry guides and labels cannot reach the final skin through this image.
        assert {color for _, color in image.getcolors()} == {
            (250, 250, 247),
            (139, 191, 185),
            (255, 243, 217),
            (48, 45, 43),
        }


def test_style_board_only_loads_configured_private_asset_dir(tmp_path):
    settings = config(tmp_path)
    settings.style_asset_dir.mkdir()
    approved_path = settings.style_asset_dir / "concept-a.png"
    stream = io.BytesIO()
    Image.new("RGBA", (64, 64), (80, 160, 150, 190)).save(stream, "PNG")
    approved_path.write_bytes(stream.getvalue())
    value, design = inputs()
    prompt, references, source = image_request_references(
        replace(settings, style_reference=approved_path), value, design
    )
    assert references[1][1] == stream.getvalue()
    assert source == "SERVER_CONFIGURED_STYLE_BOARD"
    assert str(approved_path) not in prompt
    assert digest(references[1][1]) == digest(approved_path.read_bytes())
    with pytest.raises(ValueError, match="STYLE_REFERENCE_OUTSIDE_ASSET_DIR"):
        replace(settings, style_reference=tmp_path / "outside.png")


def test_legacy_design_does_not_turn_old_finished_png_into_a_style_lock(tmp_path):
    value, design = inputs()
    design.pop("visualIntent")
    design.pop("formation")
    prompt, references, source = image_request_references(config(tmp_path), value, design)
    assert "LEGACY_PROPOSAL_ONLY" in prompt
    assert "BODY_FLOW_PROPOSAL" in prompt
    assert len(references) == 2 and source == "PROCEDURAL_MATERIAL_STUDY"
    value["route"]["points"] = [[0.1, 0.2], [0.8, 0.2]]
    landmarks = route_landmarks(value, design)
    assert landmarks[0]["selection"] == "FLOW_SAMPLE"


def test_paid_approval_guard_runs_before_transport_or_reference_read(tmp_path, monkeypatch):
    import nunti.avatar_studio.image_api as module

    def no_transport(*args):
        raise AssertionError("unapproved call reached transport")

    monkeypatch.setattr(module.urllib.request, "build_opener", no_transport)
    settings = replace(
        config(tmp_path),
        image_enabled=True,
        image_key="unit-test-not-a-key",
        image_prices_verified=True,
        image_reservation_micros=10_000,
    )
    value, design = inputs()
    with pytest.raises(StudioError, match="PAID_API_APPROVAL_REQUIRED"):
        render_api_image(settings, value, b"old-png-must-not-be-read", design)


def test_startup_does_not_even_read_provider_key_without_approval(monkeypatch, tmp_path):
    import nunti.avatar_studio.api as module

    queried = []

    def environment(name, default=None):
        queried.append(name)
        assert name != "OPENAI_API_KEY"
        return {
            "NUNTI_STUDIO_TOKEN": "env-test-token-not-an-api-key-1234567",
            "NUNTI_STUDIO_WORKSPACE": str(tmp_path),
            "NUNTI_STUDIO_IMAGE_API_ENABLED": "true",
            "NUNTI_STUDIO_PAID_API_APPROVED": "false",
        }.get(name, default)

    monkeypatch.setattr(module.os, "getenv", environment)
    settings = Settings.from_env()
    assert settings.image_key == "" and settings.image_available is False
    assert "OPENAI_API_KEY" not in queried


def test_missing_or_invalid_style_board_fails_without_paid_transport(tmp_path):
    settings = config(tmp_path)
    value, design = inputs()
    with pytest.raises(StudioError, match="INVALID_STYLE_REFERENCE"):
        image_request_references(
            replace(settings, style_reference=settings.style_asset_dir / "gone.png"), value, design
        )
