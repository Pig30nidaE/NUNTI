"""Examples shared by live /docs and the checked-in OpenAPI artifact."""

import json
from pathlib import Path

from .fixtures import load_scenario


def add_examples(spec):
    values = load_scenario("10-report")["contracts"]
    values["EventBatch"] = {"schemaVersion": "1.0", "events": [values["DrivingEvent"]]}
    values["EmotionBatch"] = {"schemaVersion": "1.0", "emotions": [values["EmotionSnapshot"]]}
    # Telemetry examples come from the checked contract corpus (single source of truth).
    root = Path(__file__).resolve().parents[2] / "contracts/v1/examples"
    for name in ("SampleBatch", "ScoreBatch"):
        values[name] = json.loads((root / f"{name}.valid.json").read_text())
    values["TelemetrySample"] = values["SampleBatch"]["samples"][0]
    values["ScoreSnapshot"] = values["ScoreBatch"]["scores"][0]
    for name, value in values.items():
        if name in spec["components"]["schemas"]:
            spec["components"]["schemas"][name]["examples"] = [value]
    stamp = "2026-11-01T03:16:00Z"
    meta = {"requestId": "e3ac4ab7-4c33-4ef8-a77b-046fdf717066", "serverTime": stamp}
    receipt = {"id": "example-id", "status": "stored", "receivedAt": stamp}
    for path, operations in spec["paths"].items():
        if not path.startswith("/v1/"):
            continue
        for method, operation in operations.items():
            example = None
            if method in {"post", "put"}:
                batch_paths = ("/events", "/emotions", "/samples", "/scores")
                example = [receipt] if path.endswith(batch_paths) else receipt
            elif method == "get" and path.endswith("/report"):
                example = {
                    "value": values["TripReport"],
                    "receivedAt": stamp,
                    "unresolvedEvidenceEventIds": [],
                }
            elif method == "get" and path.endswith(("/events", "/emotions", "/samples", "/scores")):
                kind = path.rsplit("/", 1)[1]
                value = values[
                    {
                        "events": "DrivingEvent",
                        "emotions": "EmotionSnapshot",
                        "samples": "TelemetrySample",
                        "scores": "ScoreSnapshot",
                    }[kind]
                ]
                example = {"items": [{"value": value, "receivedAt": stamp}], "nextOffset": None}
            if example is not None:
                operation["responses"]["200"]["content"]["application/json"]["example"] = {
                    "data": example,
                    "meta": meta,
                }
            for code, response in operation["responses"].items():
                if int(code) >= 400 and "content" in response:
                    response["content"]["application/json"]["example"] = {
                        "error": {
                            "code": "request_rejected",
                            "message": "Request rejected",
                            "details": [],
                        },
                        "meta": meta,
                    }
    return spec
