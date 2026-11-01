from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from nunti.api import create_app
from nunti.config import Settings

from .conftest import TOKEN_A, TOKEN_B


def body(response):
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_health_capabilities_auth_and_scoping(client, trip):
    assert client.get("/health", headers={"Authorization": ""}).status_code == 200
    assert client.get("/v1/capabilities", headers={"Authorization": ""}).status_code == 401
    assert body(client.get("/v1/capabilities"))["contractStatus"] == "DRAFT"
    assert client.get(trip, headers={"Authorization": f"Bearer {TOKEN_B}"}).status_code == 404
    assert body(client.delete(trip, headers={"Authorization": f"Bearer {TOKEN_B}"}))["deleted"]
    assert client.get(trip).status_code == 200


def test_fail_closed_defaults_and_https(settings, sample):
    with pytest.raises(ValueError):
        Settings()
    with TestClient(create_app(replace(settings, sync_enabled=False))) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN_A}"
        assert client.post("/v1/trips", json=sample("TripCreate")).status_code == 403
        assert client.delete("/v1/trips/trip-mock").status_code == 200
    with TestClient(create_app(replace(settings, require_https=True))) as client:
        assert (
            client.get(
                "/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN_A}"}
            ).status_code
            == 403
        )
        assert (
            client.get(
                "https://testserver/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN_A}"}
            ).status_code
            == 200
        )


@pytest.mark.parametrize(
    "change",
    [
        {"routeRevision": "1"},
        {"routeRevision": True},
        {"collectedAt": "2026-02-30T00:00:00Z"},
        {"collectedAt": "2026-11-01T00:00:00"},
        {"schemaVersion": "2.0"},
        {"distanceMeters": -1},
        {"source": None},
        {"preciseGps": {"lat": 37.1, "lon": 127.1}},
    ],
)
def test_invalid_route_input(client, trip, sample, change):
    value = sample("RouteSnapshot") | change
    response = client.put(trip + "/route", json=value)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_missing_trip_malformed_input_and_redaction(client, sample):
    assert client.get("/v1/trips/no-such-trip").status_code == 404
    assert client.get("/v1/trips/invalid%20id").status_code == 422
    assert client.post("/v1/trips", json={}).status_code == 422
    secret = "private-home-address-123"
    response = client.post("/v1/trips", json=sample("TripCreate") | {secret: secret})
    assert secret not in response.text
    assert (
        client.post(
            "/v1/trips", content="{broken", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )
    assert client.post("/v1/trips", content="plain").status_code == 415
    assert client.post("/v1/trips", content=b"x" * 262145).status_code == 413
    assert "meta" in client.get("/not-a-route").json()


def test_trip_route_and_avatar_idempotency(client, avatar_trip, sample):
    path = avatar_trip
    assert body(client.post("/v1/trips", json=sample("TripCreate")))["status"] == "duplicate"
    route = sample("RouteSnapshot")
    assert body(client.put(path + "/route", json=route))["status"] == "duplicate"
    assert client.put(path + "/route", json=route | {"distanceMeters": 6}).status_code == 409
    newer = route | {"routeId": "route-new", "routeRevision": 3}
    body(client.put(path + "/route", json=newer))
    assert body(client.get(path))["avatar"] is None
    assert client.put(path + "/route", json=route | {"routeRevision": 2}).status_code == 409
    # Exact historical retry is acknowledged without rolling back the active route.
    assert body(client.put(path + "/route", json=route))["status"] == "duplicate"
    assert body(client.get(path))["route"]["value"]["routeRevision"] == 3
    avatar = sample("AvatarSpec") | {"routeId": "route-new", "routeRevision": 3}
    body(client.put(path + "/avatar", json=avatar))
    assert body(client.get(path))["avatar"]["value"] == avatar
    assert body(client.put(path + "/avatar", json=sample("AvatarSpec")))["status"] == "duplicate"
    assert client.put(path + "/avatar", json=avatar | {"themeId": "different"}).status_code == 409


def test_avatar_and_emotion_dependencies(client, trip, sample):
    assert client.put(trip + "/avatar", json=sample("AvatarSpec")).status_code == 409
    assert client.post(trip + "/emotions", json=sample("EmotionBatch")).status_code == 409
    body(client.put(trip + "/route", json=sample("RouteSnapshot")))
    avatar = sample("AvatarSpec") | {"routeRevision": 2}
    assert client.put(trip + "/avatar", json=avatar).status_code == 409


def test_duplicate_batch_atomicity_and_late_event_order(client, trip, sample):
    event = sample("DrivingEvent")
    late = event | {"eventId": "event-earlier", "occurredAt": "2026-11-01T12:01:00+09:00"}
    batch = {"schemaVersion": "1.0", "events": [event]}
    first = body(client.post(trip + "/events", json=batch))[0]
    retry = body(client.post(trip + "/events", json=batch))[0]
    assert retry == first | {"status": "duplicate"}
    conflict = {"schemaVersion": "1.0", "events": [late, event | {"severity": "LOW"}]}
    assert client.post(trip + "/events", json=conflict).status_code == 409
    assert body(client.get(trip))["eventCount"] == 1  # Whole batch rolled back.
    body(client.post(trip + "/events", json={"schemaVersion": "1.0", "events": [late]}))
    result = body(client.get(trip + "/events?limit=1"))
    assert result["items"][0]["value"]["eventId"] == "event-earlier"
    assert result["nextOffset"] == 1
    assert body(client.get(trip + "/events?offset=1"))["items"][0]["value"] == event


def test_concurrent_duplicate_delivery(client, trip, sample):
    def send(_):
        return client.post(trip + "/events", json=sample("EventBatch"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(send, range(16)))
    assert sum(body(result)[0]["status"] == "stored" for result in results) == 1
    assert body(client.get(trip))["eventCount"] == 1


def test_trip_mismatch_emotion_dedup_and_reference_arrival(client, avatar_trip, sample):
    path = avatar_trip
    event = sample("EventBatch")
    event["events"][0]["tripId"] = "wrong-trip"
    assert client.post(path + "/events", json=event).status_code == 409
    emotion = sample("EmotionBatch")
    body(client.post(path + "/emotions", json=emotion))  # Trigger event can arrive later.
    assert body(client.post(path + "/emotions", json=emotion))[0]["status"] == "duplicate"
    changed = deepcopy(emotion)
    changed["emotions"][0]["emotion"] = "HAPPY"
    assert client.post(path + "/emotions", json=changed).status_code == 409
    assert body(client.get(path))["emotionCount"] == 1
    report = sample("TripReport")
    assert client.get(path + "/report").status_code == 404
    body(client.put(path + "/report", json=report))
    stored = body(client.get(path + "/report"))
    assert stored["value"]["finalText"] == report["finalText"]
    assert stored["value"]["overallScore"] is None
    assert stored["unresolvedEvidenceEventIds"] == ["event-brake"]
    body(client.post(path + "/events", json=sample("EventBatch")))
    assert body(client.get(path + "/report"))["unresolvedEvidenceEventIds"] == []
    assert body(client.put(path + "/report", json=report))["status"] == "duplicate"
    assert client.put(path + "/report", json=report | {"finalText": "changed"}).status_code == 409
    assert client.put(path + "/report", json=report | {"tripId": "other"}).status_code == 409


def test_restart_retention_delete_and_cascade(settings, sample):
    headers = {"Authorization": f"Bearer {TOKEN_A}"}
    with TestClient(create_app(settings), headers=headers) as client:
        body(client.post("/v1/trips", json=sample("TripCreate")))
        body(client.post("/v1/trips/trip-mock/events", json=sample("EventBatch")))
    with TestClient(create_app(settings), headers=headers) as client:
        assert body(client.get("/v1/trips/trip-mock"))["eventCount"] == 1
        store = client.app.state.store
        with store.transaction() as db:
            db.execute("UPDATE trips SET expires_at='2000-01-01T00:00:00Z'")
        assert client.get("/v1/trips/trip-mock").status_code == 404
        assert store.purge_expired() == 1
        with store.connection() as db:
            assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 0
        body(client.post("/v1/trips", json=sample("TripCreate")))
        body(client.post("/v1/trips/trip-mock/events", json=sample("EventBatch")))
        body(client.delete("/v1/trips/trip-mock"))
        body(client.delete("/v1/trips/trip-mock"))
        assert client.get("/v1/trips/trip-mock").status_code == 404
        with store.connection() as db:
            assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 0


def test_mock_gating_and_openapi(settings, client):
    assert len(body(client.get("/v1/mock/scenarios"))["scenarios"]) == 10
    assert client.get("/v1/mock/scenarios/no-such-scenario").status_code == 404
    spec = client.get("/openapi.json").json()
    assert spec["paths"]["/v1/trips"]["post"]["security"] == [{"HTTPBearer": []}]
    assert "422" in spec["paths"]["/v1/trips"]["post"]["responses"]
    with TestClient(create_app(replace(settings, enable_mocks=False))) as disabled:
        assert disabled.get("/v1/mock/scenarios").status_code == 404
