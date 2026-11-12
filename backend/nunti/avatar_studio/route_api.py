"""Explicit, cached development routing API and immutable geometry provenance.

OSRM geometry is independent of Hyundai's selected route. No screenshot or
waypoint-summary reconstruction is accepted as the planned road geometry.
"""

import json
import math
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

from .models import NoRedirect, canonical, digest
from .storage import StudioError

PROVIDER = "OSRM_FOSSGIS"
API_BASE = "https://routing.openstreetmap.de/routed-car/route/v1/driving/"
NORMALIZATION_VERSION = "web-mercator-isotropic-rdp-1"
MAX_RESPONSE_BYTES = 2_097_152
MAX_RAW_POINTS = 20_000
LIVE_REQUEST_LIMIT = 12
ATTRIBUTION = "© OpenStreetMap contributors · routing: OSRM / FOSSGIS"
ATTRIBUTION_URL = "https://www.openstreetmap.org/copyright"
FIX_MAP_URL = "https://www.openstreetmap.org/fixthemap"
_provider_lock = threading.Lock()


def geographic_distance(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, math.radians(b[0] - a[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(min(1.0, math.sqrt(h)))


def segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length)) if length else 0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def simplify_indices(points, tolerance):
    keep = {0, len(points) - 1}
    pending = [(0, len(points) - 1)]
    while pending:
        first, last = pending.pop()
        farthest, index = tolerance, None
        for i in range(first + 1, last):
            error = segment_distance(points[i], points[first], points[last])
            if error > farthest:
                farthest, index = error, i
        if index is not None:
            keep.add(index)
            pending.extend(((first, index), (index, last)))
    return sorted(keep)


def normalize_geometry(coordinates):
    projected = [
        [math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))]
        for lon, lat in coordinates
    ]
    xs, ys = [p[0] for p in projected], [p[1] for p in projected]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    extent = max(dx, dy)
    if extent <= 1e-10:
        raise StudioError("ROUTE_GEOMETRY_EMPTY", 502)
    scale = 0.90 / extent
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    points = [[0.5 + (x - cx) * scale, 0.5 - (y - cy) * scale] for x, y in projected]
    tolerance = 0.00025
    indices = simplify_indices(points, tolerance)
    while len(indices) > 512:
        tolerance *= 2
        indices = simplify_indices(points, tolerance)
    deviation = max(
        (
            segment_distance(points[i], points[a], points[b])
            for a, b in zip(indices, indices[1:], strict=False)
            for i in range(a + 1, b)
        ),
        default=0.0,
    )
    normalized = [[round(v, 9) for v in points[i]] for i in indices]
    return normalized, {
        "version": NORMALIZATION_VERSION,
        "sourceCoordinateSystem": "WGS84",
        "sourceCoordinateOrder": "LONGITUDE_LATITUDE",
        "projection": "WEB_MERCATOR",
        "singleScale": scale,
        "yAxisInverted": True,
        "direction": "ORIGIN_TO_DESTINATION_PRESERVED",
        "sourcePointCount": len(coordinates),
        "normalizedPointCount": len(normalized),
        "rdpToleranceNormalized": tolerance,
        "maxDeviationNormalized": deviation,
        "normalizedSha256": digest(canonical(normalized).encode()),
    }


def parse_response(raw, origin, destination):
    try:
        value = json.loads(raw)
        if value.get("code") != "Ok":
            raise ValueError("provider did not find a route")
        route = value["routes"][0]
        geometry = route["geometry"]
        coordinates = geometry["coordinates"]
        if geometry["type"] != "LineString" or not 2 <= len(coordinates) <= MAX_RAW_POINTS:
            raise ValueError("invalid geometry")
        for point in coordinates:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(
                    isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n)
                    for n in point
                )
            ):
                raise ValueError("invalid coordinate")
            if not -180 <= point[0] <= 180 or not -85 <= point[1] <= 85:
                raise ValueError("unsupported coordinate")
        distance, duration = route["distance"], route["duration"]
        if any(
            isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or n < 0
            for n in (distance, duration)
        ):
            raise ValueError("invalid distance/time")
        start_snap = geographic_distance([origin["longitude"], origin["latitude"]], coordinates[0])
        end_snap = geographic_distance(
            [destination["longitude"], destination["latitude"]], coordinates[-1]
        )
        if max(start_snap, end_snap) > 2000:
            raise ValueError("route endpoints do not match request")
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise StudioError("ROUTE_PROVIDER_INVALID_RESPONSE", 502) from exc
    points, normalization = normalize_geometry(coordinates)
    return {
        "provider": PROVIDER,
        "coordinates": coordinates,
        "rawCoordinateOrder": "LONGITUDE_LATITUDE",
        "rawCoordinateSystem": "WGS84",
        "rawSha256": digest(canonical(coordinates).encode()),
        "responseSha256": digest(raw),
        "dataVersion": value.get("data_version"),
        "distanceMeters": distance,
        "durationSeconds": duration,
        "originSnapMeters": round(start_snap, 2),
        "destinationSnapMeters": round(end_snap, 2),
        "points": points,
        "normalization": normalization,
    }


def fetch_route(origin, destination):
    coordinates = ";".join(
        f"{p['longitude']:.7f},{p['latitude']:.7f}" for p in (origin, destination)
    )
    request = urllib.request.Request(
        API_BASE + coordinates + "?alternatives=false&steps=false&overview=full&geometries=geojson",
        headers={
            "User-Agent": "Nunti/0.1 local-prototype (https://github.com/Pig30nidaE/NUNTI)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if response.status != 200 or len(raw) > MAX_RESPONSE_BYTES:
                raise StudioError("ROUTE_PROVIDER_INVALID_RESPONSE", 502)
            return raw
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise StudioError("ROUTE_PROVIDER_UNAVAILABLE", 502) from exc


class PlanStore:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS route_geometry_cache (
                    owner TEXT NOT NULL, cache_key TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(owner, cache_key));
                CREATE TABLE IF NOT EXISTS route_api_attempts (started_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS route_api_plans (
                    owner TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(owner,id));
            """)

    def geometry(self, owner, key):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload FROM route_geometry_cache WHERE owner=? AND cache_key=?",
                (owner, key),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def read(self, owner, plan_id):
        if not re.fullmatch(r"[a-f0-9]{64}", plan_id):
            raise StudioError("ROUTE_PLAN_NOT_FOUND", 404)
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload FROM route_api_plans WHERE owner=? AND id=?", (owner, plan_id)
            ).fetchone()
        if row is None:
            raise StudioError("ROUTE_PLAN_NOT_FOUND", 404)
        plan = json.loads(row[0])
        unsigned = {key: value for key, value in plan.items() if key != "planId"}
        if digest(canonical(unsigned).encode()) != plan_id:
            raise StudioError("SAVED_ROUTE_PLAN_CHANGED", 409)
        return plan

    def put(self, owner, plan):
        with self.store.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO route_api_plans VALUES(?,?,?)",
                (owner, plan["planId"], canonical(plan)),
            )

    def claim_http(self):
        now = time.time()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count, last = db.execute(
                "SELECT COUNT(*), MAX(started_at) FROM route_api_attempts"
            ).fetchone()
            if count >= LIVE_REQUEST_LIMIT:
                raise StudioError("ROUTE_API_DEMO_LIMIT_REACHED", 409)
            if last is not None and now - last < 1.1:
                raise StudioError("ROUTE_API_RATE_LIMIT", 429)
            db.execute("INSERT INTO route_api_attempts VALUES(?)", (now,))


def create_plan(store, owner, value, fetcher=None):
    data = value.model_dump(exclude_none=True)
    origin, destination = data["origin"], data["destination"]
    if (
        geographic_distance(
            [origin["longitude"], origin["latitude"]],
            [destination["longitude"], destination["latitude"]],
        )
        < 10
    ):
        raise StudioError("ROUTE_ENDPOINTS_TOO_CLOSE")
    repository = PlanStore(store)
    coordinates = [
        {"latitude": point["latitude"], "longitude": point["longitude"]}
        for point in (origin, destination)
    ]
    cache_key = digest(canonical({"provider": PROVIDER, "coordinates": coordinates}).encode())
    with _provider_lock:
        geometry = repository.geometry(owner, cache_key)
        cached = geometry is not None
        if geometry is None:
            repository.claim_http()
            raw = (fetcher or fetch_route)(origin, destination)
            if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RESPONSE_BYTES:
                raise StudioError("ROUTE_PROVIDER_INVALID_RESPONSE", 502)
            geometry = parse_response(raw, origin, destination)
            response_sha = store.put_asset(owner, raw, "application/json")
            geometry["responsePath"] = "/v3/assets/" + response_sha
            geometry["acquiredAt"] = datetime.now(UTC).isoformat()
            with store.connect() as db:
                db.execute(
                    "INSERT INTO route_geometry_cache VALUES(?,?,?)",
                    (owner, cache_key, canonical(geometry)),
                )
    normalized = geometry["points"]
    plan = {
        "schemaVersion": "api-route-plan-1",
        "origin": origin,
        "destination": destination,
        "geometry": {key: item for key, item in geometry.items() if key != "points"},
        "routePoints": normalized,
        "nativeSnapshot": data.get("nativeSnapshot"),
        "nativeSnapshotVerified": False,
        "geometryMatchesHyundaiRoute": False,
        "requiresConfirmation": True,
        "attribution": ATTRIBUTION,
        "attributionUrl": ATTRIBUTION_URL,
        "fixMapUrl": FIX_MAP_URL,
        "warnings": [
            "HYUNDAI_SELECTED_ROUTE_NOT_VERIFIED",
            "EXTERNAL_OSRM_ROUTE",
            "USER_CONFIRMATION_REQUIRED",
        ],
    }
    plan["planId"] = digest(canonical(plan).encode())
    repository.put(owner, plan)
    return present_plan(plan, cached)


def present_plan(plan, cached=True):
    return {
        **plan,
        "route": {
            "points": plan["routePoints"],
            "inputOrigin": "API_ROUTE",
            "sourceLabel": "OSRM / OpenStreetMap API 자동차 경로 · 현대 선택 경로와 일치 미검증",
            "apiPlanId": plan["planId"],
            "confirmed": False,
        },
        "retrieval": {"geometryCacheHit": cached, "externalRequestMade": not cached},
    }


def validate_route_plan(store, owner, value):
    plan = PlanStore(store).read(owner, value.route.apiPlanId)
    if value.route.points != plan["routePoints"]:
        raise StudioError("API_ROUTE_POINTS_MISMATCH", 409)
    if value.destination.name != plan["destination"]["name"]:
        raise StudioError("API_ROUTE_DESTINATION_MISMATCH", 409)
    return plan
