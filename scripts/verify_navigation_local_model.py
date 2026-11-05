#!/usr/bin/env python3
"""Generate one free local-model avatar from a saved API route, without device changes."""

import hashlib
import json
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local/navigation-integration/local-ai"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / ".local/avatar-generator/connection.json").read_text())

    def request(path, body=None):
        headers = {"Authorization": "Bearer " + config["token"]}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            config["baseUrl"] + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=200) as response:
            return response.read()

    caps = json.loads(request("/v3/capabilities"))["data"]
    assert caps["localImageModelAvailable"], "FREE_LOCAL_MODEL_REQUIRED"
    assert not caps["imageApiPaidApproved"], "PAID_MODE_MUST_STAY_OFF"
    plan = json.loads(
        (ROOT / ".local/navigation-integration/live/coast-plan.json").read_text()
    )
    fresh = json.loads(request("/v3/route-plans/" + plan["planId"]))["data"]
    assert fresh["geometry"] == plan["geometry"]
    assert not fresh["retrieval"]["externalRequestMade"]
    saved = OUT / "request.json"
    if saved.exists():
        body = json.loads(saved.read_text())
        assert body["route"]["apiPlanId"] == plan["planId"]
    else:
        body = {
            "requestId": str(uuid4()),
            "destination": {
                "name": plan["destination"]["name"],
                "traits": "푸른 바다, 파도와 커피 향",
            },
            "purpose": "바다를 보며 쉬기",
            "route": {**plan["route"], "confirmed": True},
            "renderMode": "LOCAL_MODEL",
        }
        saved.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n")
        saved.chmod(0o600)
    start = time.monotonic()
    artifact = json.loads(request("/v3/avatars", body))["data"]
    elapsed = round(time.monotonic() - start, 2)
    assert artifact["mediaOrigin"] == "LOCAL_MODEL"
    assert artifact["route"]["inputOrigin"] == "API_ROUTE"
    assert artifact["route"]["apiRoute"]["geometry"] == plan["geometry"]
    assert artifact["voice"]["newVoiceGenerated"] is False
    image = request(artifact["visual"]["path"])
    assert hashlib.sha256(image).hexdigest() == artifact["visual"]["sha256"]
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    (OUT / "artifact.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
    )
    (OUT / "avatar.png").write_bytes(image)
    proof = {
        "status": "PASS_API_ROUTE_TO_ACTUAL_LOCAL_MODEL_IMAGE",
        "characterId": artifact["characterId"],
        "planId": plan["planId"],
        "imageSha256": artifact["visual"]["sha256"],
        "imageHashVerified": True,
        "elapsedSeconds": elapsed,
        "provider": artifact.get("provider"),
        "sourceGeometryPreserved": True,
        "paidApiCalls": 0,
        "newVoiceGenerated": False,
        "deviceChanges": 0,
        "videoRecorded": False,
        "speakerRecorded": False,
        "humanQualityApproved": False,
    }
    (OUT / "verification.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {k: v for k, v in proof.items() if k != "provider"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
