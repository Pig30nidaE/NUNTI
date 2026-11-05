#!/usr/bin/env python3
"""Collect v5 real model and Canvas evidence; missing UI runs stay explicitly pending."""

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/avatar-quality-v5"
OUT = ROOT / "docs/design/avatar-quality-v5/verification"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    suites = list(
        ET.parse(OUT.parent / "backend-tests.xml").getroot().iter("testsuite")
    )
    assert suites and all(
        int(s.get("failures", 0)) == int(s.get("errors", 0)) == 0 for s in suites
    )
    renderer = read(WORK / "illustration/validation.json")
    assert renderer["status"] == "PASS_CLEAN_SURFACE_RENDERER"
    for name, expected in renderer["sourceHashes"].items():
        assert sha(ROOT / name) == expected, name
    assert all(
        c["surfaceRouteMarking"] == "NONE" and c["metadataThreadPainted"] is False
        for c in renderer["cases"]
    )
    canvas = read(WORK / "motion-qa/verification.json")
    geometry = read(WORK / "motion-qa/geometry-verification.json")
    assert canvas["status"] == "PASS_FORMATION_PIXELS"
    assert geometry["status"] == "PASS_FORMATION_GEOMETRY"
    for value in (canvas, geometry):
        assert value["sourceSha256"] == sha(
            ROOT / "prototypes/avatar_generator/formation.js"
        )
    model = read(WORK / "model-http/runtime-result.json")
    for name, expected in model["sourceSha256"].items():
        assert sha(ROOT / name) == expected, name
    artifact = read(WORK / "model-http/coast/artifact.json")
    assert artifact["mediaOrigin"] == "LOCAL_MODEL"
    assert artifact["design"]["visualIntent"]["surfaceRouteMarking"] == "NONE"
    assert artifact["design"]["routeThread"]["renderedOnSurface"] is False
    provider = artifact["provider"]
    assert provider["adapterSha256"] == sha(
        ROOT / "backend/nunti/avatar_studio/local_model.py"
    )
    assert provider["styleSourceSha256"] == sha(
        OUT.parent / "assets/style-clean-master.png"
    )
    assert provider["offline"] is True and provider["paidApiCalls"] == 0
    image_path = WORK / "model-http/coast/character-rgba.png"
    assert sha(image_path) == artifact["visual"]["sha256"]
    with Image.open(image_path) as image:
        assert image.mode == "RGBA" and image.size == (512, 512)
        assert image.getchannel("A").getextrema() == (0, 255)
    raw = WORK / "model-http/coast/original-rgb.png"
    assert sha(raw) == model["coast"]["rawSha256"]
    ui = {}
    for name, relative in (
        ("input-edges", "input-edge-verification"),
        ("chrome", "v5-browser-verification"),
        ("android", "v5-native-verification"),
        ("android-ai", "v5-local-ai-native-verification"),
    ):
        path = ROOT / ".local/avatar-generator" / relative / "verification.json"
        if path.is_file():
            value = read(path)
            assert value["status"].startswith("PASS_")
            assert value["providerApiCalls"] == 0
            assert not any(
                value.get(k, False)
                for k in ("videoRecorded", "speakerRecorded", "recordings")
            )
            for source, expected in value["sourceSha256"].items():
                assert sha(ROOT / source) == expected, source
            ui[name] = {"status": value["status"], "checks": len(value["checks"])}
            shutil.copy2(path, OUT / (name + ".json"))
        else:
            ui[name] = {
                "status": "NOT_EXECUTED_PENDING_APPROVAL"
                if name == "android-ai"
                else "NOT_EXECUTED_APPROVAL_REVIEW_FAILURE",
                "checks": 0,
            }
    for source, target in (
        ("illustration/validation.json", "renderer.json"),
        ("motion-qa/verification.json", "canvas.json"),
        ("motion-qa/geometry-verification.json", "geometry.json"),
        ("motion-qa/new-ai-static-verification.json", "new-ai-static.json"),
        ("model-http/runtime-result.json", "model.json"),
        ("motion-qa/effect-comparison.png", "effects.png"),
        ("illustration/after-comparison.png", "fast-illustrations.png"),
    ):
        shutil.copy2(WORK / source, OUT / target)
    shutil.copy2(image_path, OUT / "coast.png")
    native_preview = (
        ROOT
        / ".local/avatar-generator/v5-local-ai-native-verification/02-new-avatar.png"
    )
    if native_preview.is_file():
        shutil.copy2(native_preview, OUT / "android-coast.png")
    result = {
        "status": "IMPLEMENTED_AND_MODEL_CANVAS_VERIFIED_UI_PENDING"
        if any(v["checks"] == 0 for v in ui.values())
        else "PASS_CLEAN_AVATAR_FUNCTIONAL_DELIVERY",
        "backendCasesIncludingSubtests": sum(int(s.get("tests", 0)) for s in suites),
        "cleanRendererCases": len(renderer["cases"]),
        "actualLocalInferenceCalls": model["actualLocalInferenceCalls"],
        "modelElapsedSeconds": model["coast"]["modelElapsedSeconds"],
        "actualCanvasFixtures": len(canvas["fixtures"]),
        "actualCanvasPoses": sum(len(f["poses"]) for f in canvas["fixtures"]),
        "newAiCanvasVerified": any(
            f["imageSha256"] == artifact["visual"]["sha256"] and len(f["poses"]) == 5
            for f in canvas["fixtures"]
        ),
        "pureGeometryFrames": geometry["frames"],
        "effectSamples": geometry["effectSamples"],
        "ui": ui,
        "rgbaSha256": sha(image_path),
        "paidApiCalls": 0,
        "finalHumanQualityApproved": False,
        "exactAiRoutePreservationVerified": False,
        "videoRecorded": False,
        "speakerRecorded": False,
    }
    (OUT / "delivery.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
