import json

import httpx
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from nunti.demo_outbox import DemoOutbox
from nunti.fixtures import load_scenario, scenario_names
from nunti.models import CONTRACTS

from .conftest import ROOT


@pytest.mark.parametrize("name", scenario_names())
def test_mock_end_to_end(client, tmp_path, name):
    fixture = load_scenario(name)
    assert fixture["mock"] is True
    speech = fixture["contracts"]["SpeechRequest"]
    emotion = fixture["contracts"]["EmotionSnapshot"]
    assert speech["emotionId"] == emotion["emotionId"]
    assert speech["emotion"] == emotion["emotion"]
    assert speech["text"] == fixture["contracts"]["TripReport"]["finalText"]
    models = {model.__name__: model for model in CONTRACTS}
    for model_name, value in fixture["contracts"].items():
        models[model_name].model_validate(value)
        schema = json.loads((ROOT / "contracts/v1" / f"{model_name}.schema.json").read_text())
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    outbox_path = tmp_path / "outbox.sqlite3"
    outbox = DemoOutbox(outbox_path, consent=True)
    for index, step in enumerate(fixture["steps"]):
        if step["method"] == "GET":
            assert client.get(step["path"]).status_code == step["expectedStatus"]
            continue
        outbox.enqueue(str(index), step["method"], step["path"], step["body"])
        fault = [step.get("transportFault")]

        def sender(method, path, fault=fault, expected=step["expectedStatus"], **kwargs):
            if fault[0] == "before_send":
                raise httpx.ConnectError("simulated offline")
            result = client.request(method, path, **kwargs)
            assert result.status_code == expected, result.text
            if fault[0] == "after_commit":
                raise httpx.ReadError("simulated lost acknowledgment")
            return result

        if fault[0]:
            assert outbox.pump_once(sender, at=1000) == "retry"
            assert outbox.pending_count() == 1
            outbox = DemoOutbox(outbox_path, consent=True)  # Client process restart.
            fault[0] = None
        assert outbox.pump_once(sender, at=2000) == "acknowledged"
    path = "/v1/trips/" + fixture["contracts"]["TripCreate"]["tripId"]
    summary = client.get(path).json()["data"]
    assert summary["eventCount"] == (2 if name == "07-recovery" else 1)
    assert summary["emotionCount"] == (2 if name == "07-recovery" else 1)
    assert summary["reportAvailable"]
    report = client.get(path + "/report").json()["data"]["value"]
    assert report["finalText"] == fixture["contracts"]["TripReport"]["finalText"]
    assert outbox.pending_count() == 0


def test_outbox_consent_backoff_and_conflict(tmp_path):
    box = DemoOutbox(tmp_path / "outbox.sqlite3")
    assert not box.enqueue("key", "POST", "/v1/trips", {})
    assert box.pump_once(None) == "disabled"
    box.consent = True
    assert box.enqueue("key", "POST", "/v1/trips", {})
    assert box.enqueue("key", "POST", "/v1/trips", {})
    with pytest.raises(ValueError):
        box.enqueue("key", "POST", "/v1/trips", {"different": True})
    assert box.pump_once(lambda *a, **k: httpx.Response(503), at=0) == "retry"
    assert box.pump_once(None, at=0.5) == "waiting"
    assert box.pump_once(lambda *a, **k: httpx.Response(409), at=1) == "blocked"
    assert box.pump_once(None, at=100) == "blocked"
    assert box.pending_count() == 1
    box.revoke_consent()
    assert box.pending_count() == 0
