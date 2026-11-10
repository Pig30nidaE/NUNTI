"""App-computed samples and score snapshots: stored as sent, idempotent, owner-scoped."""

import copy

import pytest

from .conftest import TOKEN_B


@pytest.fixture
def samples(sample):
    return sample("SampleBatch")


@pytest.fixture
def scores(sample):
    return sample("ScoreBatch")


def test_samples_are_stored_in_time_order_and_counted(client, trip, samples):
    response = client.post(trip + "/samples", json=samples)
    assert response.status_code == 200
    assert [r["status"] for r in response.json()["data"]] == ["stored"] * 3
    stored = client.get(trip + "/samples").json()["data"]
    assert [item["value"]["sampleId"] for item in stored["items"]] == [
        "s-000000",
        "s-000001",
        "s-000002",
    ]
    assert stored["nextOffset"] is None
    # Not received stays null; it is never turned into zero.
    assert stored["items"][2]["value"]["speedKmh"] is None
    assert stored["items"][2]["value"]["brakePressed"] is None
    assert client.get(trip).json()["data"]["sampleCount"] == 3


def test_scores_round_trip_without_changing_values(client, trip, scores):
    assert client.post(trip + "/scores", json=scores).status_code == 200
    stored = client.get(trip + "/scores").json()["data"]["items"][0]["value"]
    expected = scores["scores"][0]
    for key in ("scoreId", "total", "coverage", "final", "engineVersion", "windowOverall"):
        assert stored[key] == expected[key]
    assert stored["areas"][3] == {"area": "EFFICIENCY", "score": None, "points": None}
    assert stored["newEvents"] == [{"tMs": 2000, "kind": "HARD_BRAKE"}]
    assert client.get(trip).json()["data"]["scoreCount"] == 1


def test_source_is_kept_so_demo_data_stays_distinguishable(client, trip, samples, scores):
    samples["source"] = {"kind": "MOCK", "provider": "nunti-demo", "version": "1"}
    client.post(trip + "/samples", json=samples)
    client.post(trip + "/scores", json=scores)
    sample = client.get(trip + "/samples").json()["data"]["items"][0]["value"]
    score = client.get(trip + "/scores").json()["data"]["items"][0]["value"]
    assert sample["source"]["kind"] == "MOCK"
    assert score["source"] == scores["source"]
    # An item's own source wins over the batch's.
    own = copy.deepcopy(samples)
    own["samples"][0]["sampleId"] = "own-source"
    own["samples"][0]["source"] = {"kind": "ANDROID_ADAPTER", "provider": "x", "version": "1"}
    client.post(trip + "/samples", json=own)
    stored = {
        i["value"]["sampleId"]: i["value"]
        for i in client.get(trip + "/samples").json()["data"]["items"]
    }
    assert stored["own-source"]["source"]["kind"] == "ANDROID_ADAPTER"


@pytest.mark.parametrize("path,fixture", [("/samples", "samples"), ("/scores", "scores")])
def test_resending_the_same_batch_is_a_duplicate(client, trip, request, path, fixture):
    batch = request.getfixturevalue(fixture)
    first = client.post(trip + path, json=batch).json()["data"]
    again = client.post(trip + path, json=batch).json()["data"]
    assert {r["status"] for r in again} == {"duplicate"}
    assert [r["receivedAt"] for r in again] == [r["receivedAt"] for r in first]


def test_same_id_with_different_content_conflicts(client, trip, scores):
    client.post(trip + "/scores", json=scores)
    changed = copy.deepcopy(scores)
    changed["scores"][0]["total"] = 12.0
    response = client.post(trip + "/scores", json=changed)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "id_conflict"


@pytest.mark.parametrize("path,fixture", [("/samples", "samples"), ("/scores", "scores")])
def test_trip_id_must_match_the_url(client, trip, request, path, fixture):
    batch = copy.deepcopy(request.getfixturevalue(fixture))
    batch["tripId"] = "another-trip"
    response = client.post(trip + path, json=batch)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "trip_id_mismatch"


@pytest.mark.parametrize("path", ["/samples", "/scores"])
def test_unknown_trip_is_not_found(client, samples, scores, path):
    batch = samples if path == "/samples" else scores
    batch = {**batch, "tripId": "no-such-trip"}
    assert client.post(f"/v1/trips/no-such-trip{path}", json=batch).status_code == 404


def test_other_owner_cannot_read_or_write(client, trip, samples):
    client.post(trip + "/samples", json=samples)
    other = {"Authorization": f"Bearer {TOKEN_B}"}
    assert client.get(trip + "/samples", headers=other).status_code == 404
    assert client.post(trip + "/samples", json=samples, headers=other).status_code == 404


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["samples"][0].update(speedKmh=-1),
        lambda b: b["samples"][0].update(speedKmh=float("nan")),
        lambda b: b["samples"][0].update(gear="X"),
        lambda b: b["samples"][0].update(speedKmh="55"),  # no string-to-number coercion
        lambda b: b["samples"][0].update(unexpected=1),
        lambda b: b.update(samples=[]),
        lambda b: b["samples"].extend([b["samples"][0]] * 100),  # more than 100
    ],
)
def test_invalid_samples_are_rejected(client, trip, samples, mutate):
    batch = copy.deepcopy(samples)
    try:
        mutate(batch)
    except ValueError:
        pass
    # NaN is not valid JSON, so send those as a raw body.
    body = __import__("json").dumps(batch, allow_nan=True).encode()
    response = client.post(
        trip + "/samples", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["scores"][0].update(total=100.5),
        lambda b: b["scores"][0].update(coverage=1.5),
        lambda b: b["scores"][0]["windowOverall"].append(-1),
        lambda b: b["scores"][0].update(final="yes"),
        lambda b: b["scores"][0]["items"][0].update(basis="x" * 65),
    ],
)
def test_invalid_scores_are_rejected(client, trip, scores, mutate):
    batch = copy.deepcopy(scores)
    mutate(batch)
    assert client.post(trip + "/scores", json=batch).status_code == 422


def test_pagination_covers_every_sample_once(client, trip, samples):
    batch = copy.deepcopy(samples)
    base = batch["samples"][0]
    batch["samples"] = [
        {
            **base,
            "sampleId": f"p-{i:03d}",
            "tMs": i * 1000,
            "occurredAt": f"2026-11-01T04:00:{i % 60:02d}Z",
        }
        for i in range(60)
    ]
    assert client.post(trip + "/samples", json=batch).status_code == 200
    first = client.get(trip + "/samples", params={"limit": 25}).json()["data"]
    assert len(first["items"]) == 25 and first["nextOffset"] == 25
    ids = []
    offset = 0
    while offset is not None:
        page = client.get(trip + "/samples", params={"limit": 25, "offset": offset}).json()["data"]
        ids += [item["value"]["sampleId"] for item in page["items"]]
        offset = page["nextOffset"]
    assert len(ids) == 60 and len(set(ids)) == 60


def test_deleting_the_trip_deletes_telemetry(client, trip, samples, scores):
    client.post(trip + "/samples", json=samples)
    client.post(trip + "/scores", json=scores)
    assert client.delete(trip).status_code == 200
    assert client.get(trip + "/samples").status_code == 404
    assert client.get(trip + "/scores").status_code == 404
