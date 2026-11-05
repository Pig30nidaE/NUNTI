"""Offline adapter boundary tests use tiny fake executables, never MLX/model inference."""

import base64
import fcntl
import io
import json
import os
import sys
import types
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from nunti.avatar_studio import api, local_model
from nunti.avatar_studio.api import Settings
from nunti.avatar_studio.illustration import render_avatar
from nunti.avatar_studio.local_model import LocalModelResult
from nunti.avatar_studio.models import canonical, digest
from nunti.avatar_studio.storage import StudioError
from tests.test_avatar_studio import TOKEN, client_for, fake_render, input_value


def png(mode="RGB", size=(512, 512)):
    image = Image.new(mode, size, "#faf9f4")
    if mode == "RGBA":
        image = Image.new(mode, size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 80, 390, 440), fill="#b8cdb8")
    return local_model.png_bytes(image)


def proposal():
    design = fake_render()[1]
    design.update(
        visualIntent={"destinationTheme": "garden"},
        formation={
            "contour": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            "spine": [[0.3, 0.7], [0.7, 0.3]],
            "faceCenter": [0.5, 0.5],
        },
    )
    return design


@pytest.fixture
def local_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ROOT", tmp_path)
    monkeypatch.setattr(local_model, "ROOT", tmp_path)
    style = tmp_path / "style.png"
    style.write_bytes(png("RGBA"))
    monkeypatch.setattr(local_model, "STYLE", style)
    weights = tmp_path / "weights"
    weights.mkdir()
    (weights / "checkpoint").write_bytes(b"fake")
    manifest = {
        "repo": local_model.MODEL,
        "revision": local_model.REVISION,
        "gated": False,
        "private": False,
        "bytes": 4,
        "files": [{"path": "checkpoint", "size": 4}],
    }
    (tmp_path / "model-manifest.json").write_text(canonical(manifest))
    binary = tmp_path / "mflux-fake"
    binary.write_text("#!/bin/sh\nexit 1\n")
    binary.chmod(0o700)
    return Settings(
        TOKEN,
        tmp_path / "studio",
        local_model_enabled=True,
        local_model_binary=binary,
        local_model_weights=weights,
    )


def fake_binary(settings, content=None, body=None):
    raw = content if content is not None else png()
    program = body or (
        "import base64,json,os,pathlib,sys\n"
        "p=pathlib.Path(sys.argv[sys.argv.index('--output')+1])\n"
        f"p.write_bytes(base64.b64decode({base64.b64encode(raw).decode()!r}))\n"
        "p.with_suffix('.env.json').write_text(json.dumps(dict(os.environ)))\n"
    )
    settings.local_model_binary.write_text(f"#!{sys.executable}\n" + program)


def stub_cutout(monkeypatch):
    def cut(raw, points):
        return (
            png("RGBA"),
            {
                "version": "route-volume-2",
                "source": "MEASURED_ALPHA_BOUNDARY",
                "mapping": "GEOMETRIC_PROJECTION_NOT_SEMANTIC",
                "faceCenter": None,
            },
            {"version": "test-only", "originalSha256": digest(raw)},
        )

    monkeypatch.setitem(
        sys.modules,
        "nunti.avatar_studio.matte_cutout",
        types.SimpleNamespace(cutout_matte_rgb=cut, MatteCutoutError=StudioError),
    )


def test_default_is_disabled_and_paid_gate_independent(tmp_path):
    settings = Settings(TOKEN, tmp_path)
    with client_for(settings) as client:
        caps = client.get("/v3/capabilities").json()["data"]
        assert caps["localImageModelAvailable"] is False
        assert caps["localImageModelInfo"]["offline"] is True
        assert caps["localImageModelInfo"]["paidApiCalls"] == 0
        value = {**input_value(), "renderMode": "LOCAL_MODEL"}
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LOCAL_MODEL_NOT_CONFIGURED"
        assert client.get("/v3/avatars").json()["data"] == []


def test_config_path_escape_and_manifest_change_rejected(local_settings, tmp_path):
    with pytest.raises(ValueError, match="OUTSIDE_WORKSPACE"):
        replace(local_settings, local_model_binary=tmp_path.parent / "outside")
    assert local_settings.local_model_available is True
    (local_settings.local_model_weights / "checkpoint").write_bytes(b"changed")
    assert local_settings.local_model_available is False
    with pytest.raises(StudioError, match="MANIFEST_INVALID"):
        local_model.local_model_manifest(local_settings)


def test_references_have_no_inset_and_face_is_explicit(local_settings):
    value = input_value()
    prompt, refs = local_model.references_and_prompt(value, proposal())
    assert len(refs) == 2
    assert "two separate visible dark eyes" in prompt
    assert "behind the face" in prompt
    assert "cream face patch" in prompt
    assert "gray is geometry only" in prompt
    assert "Remove construction lines" in prompt
    assert "Do not draw the route on the character" in prompt
    assert "pristine" in prompt and "scars" in prompt and "body stripes" in prompt
    assert '"routeRole":"SILHOUETTE_AND_FORMATION_ONLY"' in prompt
    assert '"surfaceRouteMarking":"NONE"' in prompt
    assert '"pastelPalette":["#2878a0"]' in prompt
    with Image.open(io.BytesIO(refs[1][1])) as image:
        # Only silhouette and face anchors are painted. No route inset in the corner.
        assert image.getpixel((12, 480)) == (250, 249, 244)
        assert image.getpixel((12, 12)) == (250, 249, 244)
        assert image.getpixel((256, 256)) == (255, 243, 217)
        assert image.getpixel((232, 250)) == (48, 45, 43)
        assert image.getpixel((280, 250)) == (48, 45, 43)
        assert image.getpixel((150, 150)) == (87, 150, 181)


def test_character_references_keep_structure_first_and_verified_two_stage_face_resize(
    local_settings, monkeypatch
):
    style_path = (
        Path(__file__).resolve().parents[2]
        / "docs/design/avatar-v6/assets/style-face-technique.png"
    )
    monkeypatch.setattr(local_model, "STYLE", style_path)
    value = input_value()
    _, design = render_avatar(value["route"]["points"], "서울역", "", "출장", "reference-order")
    _, references = local_model.references_and_prompt(value, design)
    assert [name for name, _ in references] == ["structure-reference.png", "style-reference.png"]
    with Image.open(io.BytesIO(references[0][1])) as structure:
        assert structure.mode == "RGB"
        assert structure.size == (512, 512)
    with Image.open(style_path) as source:
        rgba = source.convert("RGBA")
        original = Image.alpha_composite(
            Image.new("RGBA", rgba.size, (255, 255, 250, 255)), rgba
        ).convert("RGB")
    expected = original.copy()
    expected.thumbnail((512, 512), Image.Resampling.LANCZOS)
    expected.thumbnail((256, 256), Image.Resampling.LANCZOS)
    direct = original.copy()
    direct.thumbnail((256, 256), Image.Resampling.LANCZOS)
    assert direct.tobytes() != expected.tobytes(), (
        "The reference fixture must detect resize changes"
    )
    with Image.open(io.BytesIO(references[1][1])) as style:
        assert style.mode == "RGB"
        assert style.size == (256, 256)
        assert style.tobytes() == expected.tobytes()


def test_semantic_character_subprocess_uses_four_steps_512_output_and_actual_cutout(local_settings):
    # Only ML inference is replaced. Run the real subprocess adapter, persistence,
    # output validation and flat-border cutout against a controlled RGB image.
    fake_binary(local_settings)
    value = input_value()
    value["destination"] = {"name": "을왕리", "traits": ""}
    value["purpose"] = "수영"
    _, design = render_avatar(value["route"]["points"], "을왕리", "", "수영", "adapter-contract")
    run = local_settings.workspace / "semantic-run"
    result = local_model.render_local_image(local_settings, value, design, run)
    metadata = result.metadata
    assert metadata["promptVersion"] == "local-journey-character-7"
    assert metadata["steps"] == 4
    command = metadata["command"]
    assert command[command.index("--steps") + 1] == "4"
    assert command[command.index("--width") + 1] == "512"
    assert command[command.index("--height") + 1] == "512"
    assert [Path(path).name for path in command[command.index("--image-paths") + 1 :]] == [
        "structure-reference.png",
        "style-reference.png",
    ]
    assert metadata["referenceImages"] == [
        {"name": name, "sha256": digest(content)} for name, content in result.references
    ]
    sent_prompt = Path(command[command.index("--prompt-file") + 1]).read_text()
    assert sent_prompt == local_model.references_and_prompt(value, design)[0]
    assert "(1) the specified clothes; (2) the activity object" in sent_prompt
    prop = design["characterPlan"]["prop"]["descriptionEn"]
    assert f"(2) the activity object, {prop}" in sent_prompt
    assert (
        "(3) the destination-shaped bag, a prominent scalloped shell-shaped beach bag"
        in sent_prompt
    )
    assert (
        "background stays empty even for night, mountain, garden or beach destinations"
        in sent_prompt
    )
    assert metadata["promptSha256"] == digest((run / "prompt.txt").read_bytes())
    assert result.raw_png == (run / "original-rgb.png").read_bytes() == png()
    with Image.open(io.BytesIO(result.png)) as rgba, Image.open(io.BytesIO(result.raw_png)) as rgb:
        assert rgba.mode == "RGBA" and rgba.size == (512, 512)
        assert rgba.convert("RGB").tobytes() == rgb.tobytes()
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((256, 256))[3] == 255
    proof = metadata["cutout"]
    assert proof["version"] == "flat-border-cutout-2"
    assert proof["rgbChannelsPreserved"] is True
    assert proof["cropApplied"] is False
    assert proof["originalSha256"] == digest(result.raw_png)
    assert proof["rgbaSha256"] == digest(result.png)
    assert proof["removedGroundShadows"] == []
    assert result.formation["source"] == "MEASURED_ALPHA_BOUNDARY"
    assert result.formation["faceCenterVerified"] is False


def test_interior_route_cannot_become_a_skin_mark_in_model_reference(local_settings):
    design = proposal()
    _, before = local_model.references_and_prompt(input_value(), design)
    design["formation"]["spine"] = [[0.25, 0.75], [0.75, 0.75], [0.3, 0.25]]
    _, after = local_model.references_and_prompt(input_value(), design)
    # Animation geometry is retained in design, but it is absent from model-visible pixels.
    assert before[1][1] == after[1][1]
    with Image.open(io.BytesIO(before[1][1])) as image:
        assert image.getpixel((170, 350)) == image.getpixel((200, 350))


def test_face_anchor_must_fit_inside_body(local_settings):
    design = proposal()
    design["formation"]["faceCenter"] = [0.02, 0.02]
    with pytest.raises(StudioError, match="FACE_ANCHOR_OUTSIDE_BODY"):
        local_model.references_and_prompt(input_value(), design)


def test_real_subprocess_offline_env_raw_refs_and_metadata_preserved(local_settings, monkeypatch):
    fake_binary(local_settings)
    stub_cutout(monkeypatch)
    for key in ["OPENAI_API_KEY", "HF_TOKEN", "AWS_SECRET_ACCESS_KEY", "NUNTI_STUDIO_TOKEN"]:
        monkeypatch.setenv(key, "must-not-reach-child")
    run = local_settings.workspace / "run"
    value = input_value()
    result = local_model.render_local_image(local_settings, value, proposal(), run)
    assert result.raw_png == (run / "original-rgb.png").read_bytes() == png()
    env = json.loads((run / "original-rgb.env.json").read_text())
    assert not any(
        k in env
        for k in ["OPENAI_API_KEY", "HF_TOKEN", "AWS_SECRET_ACCESS_KEY", "NUNTI_STUDIO_TOKEN"]
    )
    assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"
    assert env["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1"
    assert Path(env["HOME"]).is_relative_to(run)
    assert result.metadata["modelCommit"] == local_model.REVISION
    assert result.metadata["originalSha256"] == digest(png())
    assert result.metadata["paidApiCalls"] == 0
    assert result.metadata["faceVisibilityVerified"] is False
    assert result.metadata["routeCorrespondenceVerified"] is False
    assert result.metadata["structureReferenceHasInteriorRoute"] is False
    assert result.metadata["surfaceRouteMarkingIntent"] == "NONE"
    assert result.metadata["surfaceMarkingsVerified"] is False
    for name, content in result.references:
        assert (run / name).read_bytes() == content


def test_parallel_inference_is_rejected_before_child(local_settings, monkeypatch):
    lock_path = local_settings.local_model_weights.parent / "inference.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(StudioError, match="LOCAL_MODEL_BUSY"):
            local_model.render_local_image(
                local_settings, input_value(), proposal(), local_settings.workspace / "run"
            )
    assert not (local_settings.workspace / "run").exists()


def test_http_gpu_busy_releases_request_for_identical_retry(local_settings, monkeypatch):
    stub_cutout(monkeypatch)
    fake_binary(
        local_settings,
        body=(
            "import base64,pathlib,sys\n"
            "p=pathlib.Path(sys.argv[sys.argv.index('--output')+1])\n"
            f"p.write_bytes(base64.b64decode({base64.b64encode(png()).decode()!r}))\n"
            "with (p.parent/'worker-count').open('a') as count:count.write('1')\n"
        ),
    )

    def render_proposal(*args):
        return fake_render()[0], proposal()

    value = {**input_value(), "renderMode": "LOCAL_MODEL"}
    lock_path = local_settings.local_model_weights.parent / "inference.lock"
    with client_for(local_settings, renderer=render_proposal) as client:
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            busy = client.post("/v3/avatars", json=value)
        assert busy.status_code == 409
        assert busy.json()["error"]["code"] == "LOCAL_MODEL_BUSY"
        assert client.get("/v3/avatars").json()["data"] == []
        assert not list(local_settings.workspace.rglob("worker-count"))

        # The exact requestId and input succeed after the actual GPU file lock is released.
        retry = client.post("/v3/avatars", json=value)
        assert retry.status_code == 200
        artifact = retry.json()["data"]
        assert artifact["requestId"] == value["requestId"]
        assert artifact["mediaOrigin"] == "LOCAL_MODEL"
        restored = client.post("/v3/avatars", json=value)
        assert restored.status_code == 200
        assert restored.json()["data"] == artifact
        workers = list(local_settings.workspace.rglob("worker-count"))
        assert len(workers) == 1 and workers[0].read_text() == "1"


@pytest.mark.parametrize("content", [b"broken", png("RGBA"), png(size=(256, 256))])
def test_invalid_child_output_never_ready(local_settings, content):
    fake_binary(local_settings, content)
    run = local_settings.workspace / "run"
    with pytest.raises(StudioError, match="INVALID_OUTPUT"):
        local_model.render_local_image(local_settings, input_value(), proposal(), run)
    assert json.loads((run / "metadata.json").read_text())["status"] == "FAILED"
    assert (run / "original-rgb.png").read_bytes() == content


def test_timeout_kills_process_and_releases_inference_lock(local_settings):
    fake_binary(
        local_settings,
        body=(
            "import os,pathlib,time\n"
            "pathlib.Path('child.pid').write_text(str(os.getpid()))\ntime.sleep(20)\n"
        ),
    )
    local_settings.local_model_timeout = 1
    run = local_settings.workspace / "run"
    with pytest.raises(StudioError, match="LOCAL_MODEL_TIMEOUT"):
        local_model.render_local_image(local_settings, input_value(), proposal(), run)
    pid = int((run / "child.pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    with (local_settings.local_model_weights.parent / "inference.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_http_local_model_result_reuse_restore_and_owner_scoped_raw(local_settings):
    calls = []
    metadata = {"modelCommit": local_model.REVISION, "paidApiCalls": 0, "seed": 12}
    formation = {
        "source": "MEASURED_ALPHA_BOUNDARY",
        "mapping": "GEOMETRIC_PROJECTION_NOT_SEMANTIC",
        "faceCenter": None,
    }

    def render(settings, value, design, run):
        calls.append(value["requestId"])
        return LocalModelResult(png("RGBA"), png(), [("structure.png", png())], metadata, formation)

    value = {**input_value(), "renderMode": "LOCAL_MODEL"}
    with client_for(local_settings, renderer=fake_render, local_renderer=render) as client:
        assert client.get("/v3/capabilities").json()["data"]["localImageModelAvailable"] is True
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 200
        artifact = response.json()["data"]
        assert artifact["mediaOrigin"] == "LOCAL_MODEL"
        assert artifact["visual"]["width"] == artifact["visual"]["height"] == 512
        assert artifact["design"]["formation"] == formation
        assert artifact["formationStatus"] == "MEASURED_ALPHA_GEOMETRY"
        assert artifact["motifsVerification"] == "PROPOSED_NOT_VERIFIED_IN_LOCAL_MODEL_IMAGE"
        assert client.get(artifact["provider"]["originalRgb"]["path"]).content == png()
        assert client.post("/v3/avatars", json=value).json()["data"] == artifact
        assert calls == [value["requestId"]]
        assert client.post("/v3/avatars", json={**value, "purpose": "changed"}).status_code == 409
        path = artifact["provider"]["originalRgb"]["path"]
    # Disable model after restart. Immutable collection still works without regeneration.
    with client_for(
        replace(local_settings, local_model_enabled=False), local_renderer=render
    ) as client:
        assert client.get("/v3/avatars").json()["data"] == [artifact]
        assert client.post("/v3/avatars", json=value).json()["data"] == artifact
        assert client.get(path).content == png()
    with client_for(replace(local_settings, token=TOKEN + "other")) as other:
        assert other.get(path).status_code == 404
