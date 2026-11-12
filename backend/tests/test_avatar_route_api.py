"""Exercise explicit routing, preserved geometry, replay, and generation over real HTTP/SQLite.

External OSRM HTTP is injected. These tests never contact the public demo server.
"""

import io
import json
import math
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from nunti.avatar_studio.api import Settings, create_app
from nunti.avatar_studio.models import Route, RoutePlanInput, canonical, digest
from nunti.avatar_studio.route_api import (
    LIVE_REQUEST_LIMIT,
    PlanStore,
    normalize_geometry,
    parse_response,
)
from nunti.avatar_studio.storage import StudioError

TOKEN = "route-api-test-token-01234567890123456789"


def request_value():
    return {
        "origin": {"latitude": 37.405, "longitude": 127.09, "name": "시험 출발지"},
        "destination": {"latitude": 37.525, "longitude": 126.928, "name": "더현대 서울"},
        "nativeSnapshot": {"source": "NaviHelper", "tripId": "trip-test"},
    }


def provider_bytes(origin, destination):
    return canonical(
        {
            "code": "Ok",
            "routes": [
                {
                    "distance": 25_000,
                    "duration": 1800,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [origin["longitude"], origin["latitude"]],
                            [127.04, 37.43],
                            [127.05, 37.48],
                            [126.98, 37.50],
                            [destination["longitude"], destination["latitude"]],
                        ],
                    },
                }
            ],
        }
    ).encode()


def fake_render(*args):
    image = Image.new("RGBA", (768, 768), (40, 120, 160, 100))
    image.putpixel((0, 0), (0, 0, 0, 0))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue(), {"input_tokens": 10, "output_tokens": 10}, 1000


def client_for(config, fetcher=provider_bytes, renderer=fake_render):
    return TestClient(
        create_app(config, route_fetcher=fetcher, wardrobe_renderer=renderer),
        base_url="http://127.0.0.1:8768",
        client=("127.0.0.1", 52100),
        headers={"Authorization": "Bearer " + config.token},
    )


def avatar_input(plan):
    route = deepcopy(plan["route"])
    route["confirmed"] = True
    return {
        "requestId": str(uuid4()),
        "destination": {"name": plan["destination"]["name"], "traits": "쇼핑"},
        "purpose": "휴식",
        "route": route,
    }


@pytest.fixture
def config(tmp_path):
    return Settings(
        TOKEN,
        tmp_path / "studio",
        route_api_enabled=True,
        paid_api_approved=True,
        wardrobe_enabled=True,
        image_key="unit-test-not-a-key",
    )


def test_normalization_uses_one_projection_scale_and_preserves_direction():
    coordinates = [[127.0, 37.0], [127.01, 37.02], [127.03, 37.02]]
    points, metadata = normalize_geometry(coordinates)
    assert len(points) == 3
    assert points[0][0] < points[-1][0] and points[0][1] > points[-1][1]
    dx = math.radians(0.01)
    dy = math.log(math.tan(math.pi / 4 + math.radians(37.02) / 2)) - math.log(
        math.tan(math.pi / 4 + math.radians(37) / 2)
    )
    assert (points[1][0] - points[0][0]) / dx == pytest.approx(
        (points[0][1] - points[1][1]) / dy, rel=1e-7
    )
    assert metadata["yAxisInverted"] is True
    assert metadata["sourceCoordinateOrder"] == "LONGITUDE_LATITUDE"
    assert metadata["normalizedSha256"] == digest(canonical(points).encode())
    assert max(max(p) for p in points) <= 0.95 + 1e-8
    assert min(min(p) for p in points) >= 0.05 - 1e-8


def test_simplification_bounds_preserve_original_endpoints():
    coordinates = [[127 + i / 100_000, 37 + (0.0005 if i % 2 else 0)] for i in range(1700)]
    points, metadata = normalize_geometry(coordinates)
    endpoints, _ = normalize_geometry([coordinates[0], coordinates[-1]])
    assert 2 <= len(points) <= 512
    assert points[0][0] == endpoints[0][0]
    assert points[-1][0] == endpoints[-1][0]
    assert points[0][1] > points[-1][1]
    assert metadata["sourcePointCount"] == 1700
    assert metadata["maxDeviationNormalized"] <= metadata["rdpToleranceNormalized"] + 1e-9


@pytest.mark.parametrize(
    "change",
    [
        lambda route: route.update(geometry={"type": "Point", "coordinates": [127, 37]}),
        lambda route: route["geometry"].update(coordinates=[[127.09, 37.405], [True, 37.525]]),
        lambda route: route["geometry"].update(coordinates=[[127.09, 37.405], [127, 90]]),
        lambda route: route["geometry"].update(coordinates=[[127.09, 37.405], [0, 0]]),
        lambda route: route.update(duration=-1),
        lambda route: route.update(distance=float("nan")),
    ],
)
def test_invalid_provider_geometry_is_rejected(change):
    value = request_value()
    response = json.loads(provider_bytes(value["origin"], value["destination"]))
    change(response["routes"][0])
    with pytest.raises(StudioError, match="ROUTE_PROVIDER_INVALID_RESPONSE"):
        parse_response(json.dumps(response).encode(), value["origin"], value["destination"])


def test_disabled_boundary_and_capability_explain_external_source(config):
    def unexpected(*args):
        raise AssertionError("network must not run")

    with client_for(
        replace(config, route_api_enabled=False, paid_api_approved=False), unexpected
    ) as client:
        capabilities = client.get("/v3/capabilities").json()["data"]
        assert capabilities["routeApiAvailable"] is False
        assert capabilities["routeApiInfo"]["geometryMatchesHyundaiRoute"] is False
        assert capabilities["routeApiInfo"]["apiKeyRequired"] is False
        assert capabilities["imageApiPaidApproved"] is False
        response = client.post("/v3/route-plans", json=request_value())
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ROUTE_API_NOT_ENABLED"


def test_real_http_saved_plan_raw_response_and_cached_replay(config):
    calls = []

    def fetcher(origin, destination):
        calls.append((origin, destination))
        return provider_bytes(origin, destination)

    with client_for(config, fetcher) as client:
        response = client.post("/v3/route-plans", json=request_value())
        assert response.status_code == 200
        plan = response.json()["data"]
        geometry = plan["geometry"]
        assert plan["route"]["inputOrigin"] == "API_ROUTE"
        assert plan["route"]["apiPlanId"] == plan["planId"]
        assert plan["route"]["confirmed"] is False
        assert plan["retrieval"] == {"geometryCacheHit": False, "externalRequestMade": True}
        assert geometry["rawSha256"] == digest(canonical(geometry["coordinates"]).encode())
        raw = client.get(geometry["responsePath"])
        assert raw.status_code == 200
        assert digest(raw.content) == geometry["responseSha256"]
        assert geometry["provider"] == "OSRM_FOSSGIS"
        assert plan["nativeSnapshot"] == request_value()["nativeSnapshot"]
        assert plan["nativeSnapshotVerified"] is False
        assert plan["geometryMatchesHyundaiRoute"] is False
        assert "fixthemap" in plan["fixMapUrl"]
        saved = client.get("/v3/route-plans/" + plan["planId"]).json()["data"]
        cached = client.post("/v3/route-plans", json=request_value()).json()["data"]
        assert cached == saved
        assert saved["planId"] == plan["planId"]
        assert saved["geometry"] == geometry
        assert saved["retrieval"] == {"geometryCacheHit": True, "externalRequestMade": False}
        renamed = request_value()
        renamed["origin"]["name"] = "새 출발지 이름"
        renamed["nativeSnapshot"]["tripId"] = "rerouted-trip"
        renamed_plan = client.post("/v3/route-plans", json=renamed).json()["data"]
        assert renamed_plan["planId"] != plan["planId"]
        assert renamed_plan["geometry"] == geometry
        assert len(calls) == 1


def test_generation_requires_confirmation_and_exact_saved_geometry(config):
    renders = []

    def renderer(*args):
        renders.append(args)
        return fake_render(*args)

    with client_for(config, renderer=renderer) as client:
        plan = client.post("/v3/route-plans", json=request_value()).json()["data"]
        value = avatar_input(plan)
        value["route"]["confirmed"] = False
        assert client.post("/v3/avatars", json=value).status_code == 422
        value = avatar_input(plan)
        value["route"]["points"][1][0] += 0.0001
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "API_ROUTE_POINTS_MISMATCH"
        value = avatar_input(plan)
        value["destination"]["name"] = "다른 목적지"
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "API_ROUTE_DESTINATION_MISMATCH"
        assert not renders
        value = avatar_input(plan)
        response = client.post("/v3/avatars", json=value)
        assert response.status_code == 200
        character = response.json()["data"]
        assert character["route"]["apiRoute"]["planId"] == plan["planId"]
        assert character["route"]["apiRoute"]["geometry"] == plan["geometry"]
        assert character["route"]["apiRoute"]["geometryMatchesHyundaiRoute"] is False
        assert client.post("/v3/avatars", json=value).json()["data"] == character
        reroute = request_value()
        reroute["nativeSnapshot"]["tripId"] = "rerouted"
        new_plan = client.post("/v3/route-plans", json=reroute).json()["data"]
        assert new_plan["planId"] != plan["planId"]
        assert client.get("/v3/avatars/" + character["characterId"]).json()["data"] == character
        assert len(renders) == 1


def test_saved_plan_is_owner_scoped_and_tamper_checked(config):
    with client_for(config) as client:
        plan = client.post("/v3/route-plans", json=request_value()).json()["data"]
    other = replace(config, token="other-route-api-owner-01234567890123456789")
    with client_for(other) as client:
        assert client.get("/v3/route-plans/" + plan["planId"]).status_code == 404
        assert client.post("/v3/avatars", json=avatar_input(plan)).status_code == 404
        assert client.get(plan["geometry"]["responsePath"]).status_code == 404
    with client_for(config) as client:
        repository = PlanStore(client.app.state.store)
        altered = repository.read(config.owner, plan["planId"])
        altered["routePoints"][0][0] += 0.001
        with repository.store.connect() as db:
            db.execute(
                "UPDATE route_api_plans SET payload=? WHERE owner=? AND id=?",
                (canonical(altered), config.owner, plan["planId"]),
            )
        response = client.get("/v3/route-plans/" + plan["planId"])
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SAVED_ROUTE_PLAN_CHANGED"


def test_rate_limit_is_shared_and_persistent(config):
    with client_for(config) as client:
        repository = PlanStore(client.app.state.store)
        repository.claim_http()
        with pytest.raises(StudioError, match="ROUTE_API_RATE_LIMIT"):
            repository.claim_http()
        with repository.store.connect() as db:
            db.execute("UPDATE route_api_attempts SET started_at=0")
            db.executemany(
                "INSERT INTO route_api_attempts VALUES(?)", [(0,)] * (LIVE_REQUEST_LIMIT - 1)
            )
    with client_for(config) as client:
        response = client.post("/v3/route-plans", json=request_value())
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ROUTE_API_DEMO_LIMIT_REACHED"


def test_route_source_and_snapshot_boundary(config):
    original = {
        "points": [[0.1, 0.1], [0.9, 0.9]],
        "inputOrigin": "ROUTE_FILE",
        "sourceLabel": "경로 시험",
        "confirmed": True,
    }
    assert Route.model_validate(original).apiPlanId is None
    with pytest.raises(ValueError, match="API_ROUTE_SOURCE_REQUIRED"):
        Route.model_validate({**original, "apiPlanId": "a" * 64})
    with pytest.raises(ValueError, match="API_ROUTE_SOURCE_REQUIRED"):
        Route.model_validate({**original, "inputOrigin": "API_ROUTE"})
    with client_for(config) as client:
        invalid = request_value()
        invalid["origin"]["latitude"] = True
        assert client.post("/v3/route-plans", json=invalid).status_code == 422
        invalid = request_value()
        invalid["nativeSnapshot"] = {"payload": "x" * 65_537}
        assert client.post("/v3/route-plans", json=invalid).status_code == 422
        invalid = request_value()
        invalid["origin"] = invalid["destination"]
        response = client.post("/v3/route-plans", json=invalid)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "ROUTE_ENDPOINTS_TOO_CLOSE"
    with pytest.raises(ValueError):
        RoutePlanInput.model_validate({**request_value(), "nativeSnapshot": {"n": float("nan")}})
