#!/usr/bin/env python3
"""Submit three real route inputs to the running offline bridge; record actual WAVs."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import time
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from generator import canonical, digest


def call(url, body=None):
    data = canonical(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.read()


def record(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("EVIDENCE_ALREADY_EXISTS_DIFFERENT_CONTENT")
    else:
        path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    parser.add_argument("--output", type=Path, default=HERE / "synthesis-01")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = [
        {"destination": {"name": "속초 영금정", "traits": "반투명 푸른 파도, 시원한 바닷바람"}, "purpose": "바다를 보며 휴식", "route": {"points": [[.07, .55], [.2, .4], [.38, .48], [.58, .35], [.76, .42], [.94, .27]]}},
        {"destination": {"name": "대관령 양떼목장", "traits": "초록 산길, 부드러운 이끼와 구름"}, "purpose": "산책과 느긋한 휴식", "route": {"points": [[.39, .93], [.65, .76], [.3, .6], [.65, .45], [.31, .28], [.55, .08]]}},
        {"destination": {"name": "성수 서울숲", "traits": "따뜻한 햇살, 도시의 초록 숲과 작은 전시"}, "purpose": "친구와 전시 관람", "route": {"points": [[.18, .8], [.13, .35], [.32, .1], [.72, .15], [.9, .4], [.78, .79], [.43, .9], [.18, .8]]}},
    ]
    started = time.monotonic()
    requests = []
    for index, case in enumerate(cases, 1):
        path = args.output / f"case-{index}-request.json"
        if path.exists():
            request = json.loads(path.read_text())
        else:
            request = {"requestId": str(uuid.uuid4()), **case}
            record(path, request)
        status, body = call(args.url + "/v1/journeys", request)
        response = json.loads(body)
        record(args.output / f"case-{index}-submitted.json", {"httpStatus": status, "response": response})
        assert response["state"] in ("GENERATING", "READY")
        assert response["artifact"]["inputSha256"] == digest(json.loads(response["artifact"]["inputCanonical"]))
        requests.append(request)
        print(canonical({"case": index, "requestId": request["requestId"], "submittedState": response["state"]}), flush=True)
    pending = set(range(3))
    health_samples = []
    while pending:
        if time.monotonic() - started > 1800:
            raise TimeoutError("SYNTHESIS_TIMEOUT")
        begin = time.monotonic()
        status, health = call(args.url + "/health")
        health_samples.append({"status": status, "seconds": time.monotonic() - begin, "body": json.loads(health)})
        for index in sorted(pending):
            _, data = call(args.url + "/v1/journeys/" + requests[index]["requestId"])
            response = json.loads(data)
            if response["state"] == "FAILED":
                record(args.output / f"case-{index + 1}-failed.json", response)
                raise RuntimeError("ACTUAL_SYNTHESIS_FAILED_" + str(index + 1))
            if response["state"] == "READY":
                record(args.output / f"case-{index + 1}-ready.json", response)
                for clip in response["artifact"]["voiceManifest"]["clips"]:
                    _, audio = call(args.url + "/v1/journeys/" + requests[index]["requestId"] + "/audio/" + clip["audioPath"])
                    assert hashlib.sha256(audio).hexdigest() == clip["audioSha256"]
                    output = args.output / clip["audioPath"]
                    if not output.exists():
                        output.write_bytes(audio)
                    else:
                        assert output.read_bytes() == audio
                print(canonical({"case": index + 1, "requestId": requests[index]["requestId"], "state": "READY", "clips": 3}), flush=True)
                pending.remove(index)
        if pending:
            time.sleep(1)
    ready = [json.loads((args.output / f"case-{i}-ready.json").read_text())["artifact"] for i in (1, 2, 3)]
    pairs = []
    for (a, x), (b, y) in itertools.combinations(enumerate(ready, 1), 2):
        rmse = math.sqrt(sum((p[k] - q[k]) ** 2 for p, q in zip(x["visual"]["outline"], y["visual"]["outline"]) for k in (0, 1)) / 144)
        pairs.append({"cases": [a, b], "outlineCoordinateRmse": rmse})
    report = {"status": "THREE_FRESH_INPUTS_NINE_REAL_OFFLINE_WAVS_READY", "requests": [r["requestId"] for r in requests], "actualClipCount": 9,
              "elapsedSeconds": time.monotonic() - started, "healthSamples": len(health_samples), "maximumHealthLatencySeconds": max(v["seconds"] for v in health_samples),
              "outlinePairMeasurements": pairs, "limits": "Geometry measurements are not human cuteness or naturalness approval. One Sohee speaker with delivery variations."}
    record(args.output / "health-observations.json", health_samples)
    record(args.output / "synthesis-result.json", report)
    print(canonical(report), flush=True)


if __name__ == "__main__":
    main()
