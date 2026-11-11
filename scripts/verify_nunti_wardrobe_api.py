#!/usr/bin/env python3
"""Submit the skin matrix to Studio's paid wardrobe API and verify the returned PNGs."""

import argparse
import hashlib
import io
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import monotonic

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = Path(__file__).with_name("nunti_skin_scenarios.json")
ROUTE = {"points": [[.12, .8], [.25, .52], [.66, .62], [.88, .22]],
         "inputOrigin": "ROUTE_FILE", "sourceLabel": "QA 합성 경로", "confirmed": True}


def client():
    config = json.loads((ROOT / ".local/avatar-generator/connection.json").read_text())
    assert config["baseUrl"] == "http://127.0.0.1:8768"

    def request(path, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        query = urllib.request.Request(config["baseUrl"] + path, data=data, headers={
            "Authorization": "Bearer " + config["token"], "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(query, timeout=220 if data else 12) as response:
                body = response.read()
                return json.loads(body)["data"] if response.headers.get_content_type() == "application/json" else body
        except urllib.error.HTTPError as error:
            code = json.loads(error.read()).get("error", {}).get("code", "STUDIO_HTTP_ERROR")
            raise RuntimeError(f"{error.code} {code}") from None

    return request


def write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def wardrobe_payload(case):
    return {"destination": {"name": case["destination"], "traits": case["traits"]}, "purpose": case["purpose"],
            "scenery": case["scenery"], "road": case["road"], "mood": case["mood"],
            "route": ROUTE if case["route"] else None}


def verify(request, out, case):
    start = monotonic()
    payload = wardrobe_payload(case)
    artifact = request("/v3/wardrobe", payload)
    assert artifact["mediaOrigin"] == "OPENAI_WARDROBE"
    assert artifact["destination"] == payload["destination"] and artifact["purpose"] == payload["purpose"]
    assert artifact["design"]["wardrobe"]["mood"] == payload["mood"]
    provider = artifact["provider"]
    if artifact["design"]["wardrobe"]["look"] == "default":
        assert provider["usage"].get("output_tokens", 0) == 0
    else:
        assert provider["name"] == "openai" and provider["usage"]["output_tokens"] > 0
    visual = artifact["visual"]
    assert visual["path"] == "/v3/assets/" + visual["sha256"]
    content = request(visual["path"])
    assert hashlib.sha256(content).hexdigest() == visual["sha256"]
    with Image.open(io.BytesIO(content)) as image:
        assert image.format == "PNG" and image.mode == "RGBA" and image.size == (768, 768)
        alpha = image.getchannel("A")
        assert alpha.getextrema() == (0, 255)
        subject = alpha.point(lambda value: 255 if value >= 128 else 0).getbbox()
        assert subject is not None and subject[3] - subject[1] >= 384
    (out / (case["id"] + ".png")).write_bytes(content)
    write_json(out / (case["id"] + ".json"), artifact)
    return {"id": case["id"], "status": "GENERATED", "visualSha256": visual["sha256"],
            "alphaBounds": subject, "requestId": artifact["requestId"], "model": provider["model"],
            "version": provider["version"], "estimatedCostMicros": provider["estimatedCostMicros"],
            "seconds": round(monotonic() - start, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cases", nargs="+", help="Case IDs. Default is the complete matrix.")
    parser.add_argument("--workers", type=int, default=5, choices=range(1, 9))
    args = parser.parse_args()
    cases = json.loads(SCENARIOS.read_text())
    if args.cases:
        selected = set(args.cases)
        cases = [case for case in cases if case["id"] in selected]
        if len(cases) != len(selected):
            parser.error("Unknown case ID")
    args.output.mkdir(parents=True, exist_ok=True)
    request = client()
    assert request("/v3/capabilities")["wardrobeAvailable"]
    before = request("/v3/wardrobe/budget")
    rows = []
    print(json.dumps({"starting": len(cases), "budget": before}), flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(verify, request, args.output, case): case for case in cases}
        for result in as_completed(futures):
            case = futures[result]
            try:
                row = result.result()
            except (OSError, ValueError, KeyError, RuntimeError, AssertionError) as error:
                row = {"id": case["id"], "status": "FAILED", "error": str(error) or type(error).__name__}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    after = request("/v3/wardrobe/budget")
    rows.sort(key=lambda row: row["id"])
    write_json(args.output / "generation-run.json", {"before": before, "after": after, "rows": rows})
    print(json.dumps({"completed": sum(row["status"] == "GENERATED" for row in rows), "budget": after}), flush=True)
    return int(any(row["status"] == "FAILED" for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
