#!/usr/bin/env python3
"""Collect v4 evidence and inspect the real saved AI PNG. Never generates or records media."""

import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/avatar-generator"
OUTPUT = ROOT / "docs/design/avatar-quality-v4/verification"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    suites = list(
        ET.parse(OUTPUT.parent / "backend-tests.xml").getroot().iter("testsuite")
    )
    assert suites and all(
        int(s.get("errors", 0)) == int(s.get("failures", 0)) == 0 for s in suites
    )
    reports = {}
    local_ai_ui = None
    for source, name, status in (
        (
            "browser-verification/verification.json",
            "browser",
            "PASS_AVATAR_GENERATOR_UI",
        ),
        (
            "native-verification/verification.json",
            "android",
            "PASS_AVATAR_GENERATOR_UI",
        ),
        (
            "input-edge-verification/verification.json",
            "input-edges",
            "PASS_AVATAR_INPUT_EDGES",
        ),
        (
            "local-ai-native-verification/verification.json",
            "local-ai-android",
            "PASS_LOCAL_MODEL_UI",
        ),
    ):
        value = json.loads((WORK / source).read_text())
        assert value["status"] == status and value["providerApiCalls"] == 0
        assert not value.get("videoRecorded", False) and not value.get(
            "speakerRecorded", False
        )
        for filename, expected in value.get("sourceSha256", {}).items():
            assert sha(ROOT / filename) == expected, (
                "Rerun UI verification after source changes: " + filename
            )
        shutil.copy2(WORK / source, OUTPUT / (name + ".json"))
        reports[name] = {"status": status, "checks": len(value["checks"])}
        if name == "local-ai-android":
            local_ai_ui = value
    motion_path = ROOT / ".local/avatar-quality-v4/motion-qa/verification.json"
    motion = json.loads(motion_path.read_text())
    assert motion["status"] == "PASS_FORMATION_PIXELS"
    assert motion["sourceSha256"] == sha(
        ROOT / "prototypes/avatar_generator/formation.js"
    )
    shutil.copy2(motion_path, OUTPUT / "motion.json")
    artifact = json.loads(
        (WORK / "local-ai-native-verification/artifact.json").read_text()
    )
    assert artifact["mediaOrigin"] == "LOCAL_MODEL"
    provider = artifact["provider"]
    assert provider["offline"] is True and provider["paidApiCalls"] == 0
    assert provider["adapterSha256"] == sha(
        ROOT / "backend/nunti/avatar_studio/local_model.py"
    )
    config = json.loads((WORK / "connection.json").read_text())
    owner = hashlib.sha256(config["token"].encode()).hexdigest()
    raw_path = WORK / "media" / owner / provider["originalRgb"]["sha256"]
    assert sha(raw_path) == provider["originalSha256"]
    with Image.open(raw_path) as raw_image:
        assert raw_image.mode == "RGB" and raw_image.size == (512, 512)
    image_path = WORK / "media" / owner / artifact["visual"]["sha256"]
    assert sha(image_path) == artifact["visual"]["sha256"]
    with Image.open(image_path) as image:
        assert image.mode == "RGBA" and image.size == (512, 512)
        alpha = image.getchannel("A")
        assert alpha.getextrema() == (0, 255)
        histogram = alpha.histogram()
        image_info = {
            "sha256": sha(image_path),
            "size": list(image.size),
            "transparentPixels": histogram[0],
            "opaquePixels": histogram[255],
        }
    assert artifact["design"]["formation"]["source"] == "MEASURED_ALPHA_BOUNDARY"
    assert (
        artifact["design"]["formation"]["mapping"]
        == "GEOMETRIC_PROJECTION_NOT_SEMANTIC"
    )
    shutil.copy2(image_path, OUTPUT / "preview-local-ai.png")
    shutil.copy2(
        WORK / "local-ai-native-verification/02-new-avatar.png",
        OUTPUT / "android-local-ai.png",
    )
    assert local_ai_ui is not None
    initial_failure = WORK / "local-ai-native-verification/first-attempt.json"
    if local_ai_ui.get("replayedRequestId") and initial_failure.is_file():
        shutil.copy2(
            initial_failure, OUTPUT / "local-ai-initial-assertion-failure.json"
        )
    result = {
        "status": "PASS_AVATAR_QUALITY_V4_FUNCTIONAL_DELIVERY",
        "scope": "Collected actual UI/model/geometry evidence and inspected saved PNG. Human final-art approval, exact AI route preservation and driving-habit effect are not verified.",
        "backendCasesIncludingSubtests": sum(int(s.get("tests", 0)) for s in suites),
        "surfaces": reports,
        "motionFixtures": len(motion["fixtures"]),
        "image": image_info,
        "localInference": {
            "model": provider["model"],
            "revision": provider["modelCommit"],
            "elapsedSeconds": provider["elapsedSeconds"],
            "steps": provider["steps"],
            "rawRgbSha256": provider["originalSha256"],
            "uiRetryUsedSavedRequest": bool(local_ai_ui.get("replayedRequestId")),
        },
        "providerApiCalls": 0,
        "paidApiApproved": False,
        "newVoiceGenerated": False,
        "renderingStyleHumanApproved": True,
        "finalGeneratedArtHumanApproved": False,
        "videoRecorded": False,
        "speakerRecorded": False,
    }
    (OUTPUT / "delivery.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
