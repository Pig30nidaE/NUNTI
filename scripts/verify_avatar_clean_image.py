#!/usr/bin/env python3
"""Two explicit loopback model probes; no paid API, retries, installation or recording."""

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local/avatar-quality-v5/model-http"
BASE = "http://127.0.0.1:8768"


def raw_request(config, path, body=None):
    headers = {"Authorization": "Bearer " + config["token"]}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        BASE + path,
        headers=headers,
        data=json.dumps(body, ensure_ascii=False).encode()
        if body is not None
        else None,
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read(12_000_001)


def api(config, path, body=None):
    return json.loads(raw_request(config, path, body))["data"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", choices=["coast", "garden"])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cases = {}
    examples = json.loads(
        (ROOT / "prototypes/avatar_generator/examples/index.json").read_text()
    )
    coast = {
        "destination": {
            "name": "강릉 안목해변",
            "traits": "푸른 바다, 맑은 파도와 커피 향",
        },
        "purpose": "주말에 바다를 보며 쉬기",
        "route": examples[0]["route"],
    }
    garden = {
        "destination": {"name": "작은 정원", "traits": "숲과 잎, 씨앗을 품은 정원"},
        "purpose": "정원 산책과 나들이",
        "route": {
            "points": [
                [0.85, 0.82],
                [0.72, 0.6],
                [0.79, 0.36],
                [0.51, 0.43],
                [0.3, 0.18],
                [0.12, 0.24],
            ],
            "inputOrigin": "TEST_ROUTE",
            "sourceLabel": "합성 여정 시험선",
            "confirmed": True,
        },
    }
    for name, value in [("coast", coast), ("garden", garden)]:
        value["requestId"] = str(
            uuid5(NAMESPACE_URL, "nunti/avatar-quality-v5/clean-" + name)
        )
        value["renderMode"] = "LOCAL_MODEL"
        cases[name] = value
        path = OUT / (name + "-input.json")
        if path.exists() and json.loads(path.read_text()) != value:
            raise RuntimeError("INPUT_CHANGED")
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    if not args.run:
        print(json.dumps({name: value["requestId"] for name, value in cases.items()}))
        return
    config = json.loads((ROOT / ".local/avatar-generator/connection.json").read_text())
    assert config["baseUrl"] == BASE
    caps = api(config, "/v3/capabilities")
    assert (
        caps["localImageModelAvailable"]
        and not caps["imageApiPaidApproved"]
        and not caps["imageApiAvailable"]
    )
    case = args.run
    output = OUT / case
    output.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic()
    try:
        artifact = api(config, "/v3/avatars", cases[case])
        (output / "artifact.json").write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
        )
        assert artifact["mediaOrigin"] == "LOCAL_MODEL"
        provider = artifact["provider"]
        assert provider["promptVersion"] == "local-clean-silhouette-3"
        assert provider["paidApiCalls"] == 0 and provider["offline"] is True
        assert provider["structureReferenceHasInteriorRoute"] is False
        assert provider["originalRouteImageSent"] is False
        assets = [
            ("character-rgba.png", artifact["visual"]),
            ("original-rgb.png", provider["originalRgb"]),
        ]
        assets += [(item["name"], item) for item in provider["referenceImages"]]
        for filename, item in assets:
            content = raw_request(config, item["path"])
            assert hashlib.sha256(content).hexdigest() == item["sha256"]
            (output / filename).write_bytes(content)
        with Image.open(output / "character-rgba.png") as image:
            assert image.mode == "RGBA" and image.size == (512, 512)
            assert image.getchannel("A").getextrema() == (0, 255)
        report = {
            "status": "PASS_LOCAL_HTTP_FUNCTIONAL",
            "case": case,
            "requestId": artifact["requestId"],
            "characterId": artifact["characterId"],
            "httpElapsedSeconds": round(time.monotonic() - start, 2),
            "modelElapsedSeconds": provider["elapsedSeconds"],
            "seed": provider["seed"],
            "modelCommit": provider["modelCommit"],
            "rgbaSha256": artifact["visual"]["sha256"],
            "rawSha256": provider["originalSha256"],
            "paidApiCalls": 0,
            "humanQualityApproved": False,
            "routeCorrespondenceVerified": False,
            "surfaceMarkingsVerified": False,
            "videoRecorded": False,
            "speakerRecorded": False,
        }
        (output / "verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        print(json.dumps(report, ensure_ascii=False))
    except Exception as error:
        (output / "failure.txt").write_text(str(error) + "\n")
        raise


if __name__ == "__main__":
    main()
