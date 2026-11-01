"""Captured outputs of the separately owned Kotlin module, not server-generated avatars."""

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from nunti.models import CONTRACTS

from .conftest import ROOT

DIRECTORY = Path(__file__).parent / "fixtures/avatar-generated"
MANIFEST = json.loads((DIRECTORY / "provenance.json").read_text())


@pytest.mark.parametrize("name", MANIFEST["files"])
def test_actual_kotlin_outputs_match_shared_schema(name):
    path = DIRECTORY / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == MANIFEST["files"][name]
    model_name = path.stem.split(".")[-1]
    schema = json.loads((ROOT / "contracts/v1" / f"{model_name}.schema.json").read_text())
    value = json.loads(path.read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    next(model for model in CONTRACTS if model.__name__ == model_name).model_validate(value)


@pytest.mark.parametrize(
    "route_name",
    ["mock-seoul-city", "mock-long-journey", "mock-verified-coast", "mock-verified-mountain"],
)
def test_kotlin_avatar_can_be_stored(client, sample, route_name):
    path = "/v1/trips/trip-mock"
    assert client.post("/v1/trips", json=sample("TripCreate")).status_code == 200
    for kind, model in (("route", "RouteSnapshot"), ("avatar", "AvatarSpec")):
        value = json.loads((DIRECTORY / f"{route_name}.{model}.json").read_text())
        response = client.put(path + "/" + kind, json=value)
        assert response.status_code == 200, response.text
    actual = client.get(path).json()["data"]["avatar"]["value"]
    assert actual == value


def test_openapi_examples_and_responses(client):
    spec = client.get("/openapi.json").json()
    for operations in spec["paths"].values():
        for operation in operations.values():
            for response in operation["responses"].values():
                content = response.get("content", {}).get("application/json", {})
                if "example" in content:
                    schema = content["schema"] | {"components": spec["components"]}
                    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
                        content["example"]
                    )
