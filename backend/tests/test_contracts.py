import json

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from nunti.models import CONTRACTS, RouteSnapshot, SpeechRequest, TripCreate

from .conftest import ROOT


@pytest.mark.parametrize("model", CONTRACTS)
@pytest.mark.parametrize("variant", ["valid", "missing", "invalid"])
def test_shared_contract_corpus(model, variant):
    schema = json.loads((ROOT / "contracts/v1" / f"{model.__name__}.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    value = json.loads(
        (ROOT / "contracts/v1/examples" / f"{model.__name__}.{variant}.json").read_text()
    )
    if variant == "valid":
        validator.validate(value)
        model.model_validate(value)
    else:
        assert list(validator.iter_errors(value))
        with pytest.raises(ValidationError):
            model.model_validate(value)


@pytest.mark.parametrize("model", CONTRACTS)
def test_schema_does_not_drift(model):
    actual = json.loads((ROOT / "contracts/v1" / f"{model.__name__}.schema.json").read_text())
    for key in ("$schema", "$id", "examples"):
        actual.pop(key)
    assert actual == model.model_json_schema()


@pytest.mark.parametrize("consent", [False, 1, "true", None])
def test_consent_must_be_boolean_true(sample, consent):
    value = sample("TripCreate")
    value["syncConsent"] = consent
    with pytest.raises(ValidationError):
        TripCreate.model_validate(value)


def test_cross_field_invariants(sample):
    route = sample("RouteSnapshot")
    route["roadTypeRatios"] = {"urban": 0.8, "highway": 0.8}
    with pytest.raises(ValidationError):
        RouteSnapshot.model_validate(route)
    speech = sample("SpeechRequest")
    speech["expiresAt"] = speech["requestedAt"]
    with pytest.raises(ValidationError):
        SpeechRequest.model_validate(speech)


def test_highway_option_does_not_create_measured_features(sample):
    route = sample("RouteSnapshot")
    route.pop("roadTypeRatios")
    route["routeOption"] = "HIGHWAY"
    assert RouteSnapshot.model_validate(route).roadTypeRatios is None


def test_examples_connect_avatar_emotion_report_and_speech(sample):
    avatar, emotion, report, speech, voice = (
        sample(name)
        for name in ("AvatarSpec", "EmotionSnapshot", "TripReport", "SpeechRequest", "VoiceProfile")
    )
    assert speech["avatarId"] == avatar["avatarId"] == emotion["avatarId"]
    assert speech["emotionId"] == emotion["emotionId"]
    assert speech["emotion"] == emotion["emotion"]
    assert speech["tripId"] == report["tripId"] == emotion["tripId"]
    assert speech["voiceProfileId"] == avatar["voiceProfileId"] == voice["voiceProfileId"]
    assert speech["text"] == report["finalText"]
