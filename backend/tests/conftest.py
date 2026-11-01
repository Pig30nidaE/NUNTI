import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nunti.api import create_app
from nunti.config import Settings

ROOT = Path(__file__).resolve().parents[2]
TOKEN_A = "test-only-token-a-not-for-production-0001"
TOKEN_B = "test-only-token-b-not-for-production-0002"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        db_path=tmp_path / "server.sqlite3",
        tokens={TOKEN_A: "a", TOKEN_B: "b"},
        sync_enabled=True,
        enable_mocks=True,
        require_https=False,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN_A}"}) as client:
        yield client


@pytest.fixture
def sample():
    def read(name):
        return json.loads((ROOT / "contracts/v1/examples" / f"{name}.valid.json").read_text())

    return read


@pytest.fixture
def trip(client, sample):
    value = sample("TripCreate")
    assert client.post("/v1/trips", json=value).status_code == 200
    return "/v1/trips/" + value["tripId"]


@pytest.fixture
def avatar_trip(client, trip, sample):
    assert client.put(trip + "/route", json=sample("RouteSnapshot")).status_code == 200
    assert client.put(trip + "/avatar", json=sample("AvatarSpec")).status_code == 200
    return trip
