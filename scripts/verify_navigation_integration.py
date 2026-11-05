#!/usr/bin/env python3
"""Prepare API-route GPX and optionally replay GPS with authenticated emulator RPC.

Default execution only reads a saved API plan and writes replay artifacts. Device
GPS changes require --run-replay, are bounded, and restore the original full state.
No photograph, image extraction, paid provider, audio or video API is used.
"""

import argparse
import hashlib
import importlib
import json
import math
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/navigation-integration/replay"
SDK = ROOT / ".local/pm-tools/sdk"
NS = "http://www.topografix.com/GPX/1/1"
ET.register_namespace("", NS)


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(content):
    return hashlib.sha256(content).hexdigest()


def coordinates_from_plan(plan):
    geometry = plan.get("geometry", {})
    points = geometry.get("coordinates")
    if not isinstance(points, list) or not 2 <= len(points) <= 200000:
        raise ValueError("API_PLAN_RAW_COORDINATES_REQUIRED")
    for point in points:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("LON_LAT_PAIR_REQUIRED")
        lon, lat = point
        if any(
            isinstance(n, bool)
            or not isinstance(n, (int, float))
            or not math.isfinite(n)
            for n in point
        ):
            raise ValueError("FINITE_COORDINATE_REQUIRED")
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError("WGS84_COORDINATE_OUT_OF_RANGE")
    if all(point == points[0] for point in points):
        raise ValueError("EMPTY_ROUTE_GEOMETRY")
    if geometry.get("provider") != "OSRM_FOSSGIS":
        raise ValueError("UNEXPECTED_API_ROUTE_PROVIDER")
    if digest(canonical(points).encode()) != geometry.get("rawSha256"):
        raise ValueError("SOURCE_COORDINATES_SHA_MISMATCH")
    return points


def verify_plan(plan, points):
    """Verify saved provenance and that normalized points come from this raw path."""
    unsigned = {
        key: value
        for key, value in plan.items()
        if key not in ("planId", "route", "retrieval")
    }
    if digest(canonical(unsigned).encode()) != plan.get("planId"):
        raise ValueError("SAVED_ROUTE_PLAN_SHA_MISMATCH")
    route = plan.get("route", {})
    normalized = plan.get("routePoints")
    if (
        route.get("inputOrigin") != "API_ROUTE"
        or route.get("apiPlanId") != plan["planId"]
        or route.get("points") != normalized
        or not isinstance(normalized, list)
        or not 2 <= len(normalized) <= 512
    ):
        raise ValueError("API_ROUTE_PLAN_CONTRACT_MISMATCH")
    meta = plan["geometry"].get("normalization", {})
    if (
        meta.get("version") != "web-mercator-isotropic-rdp-1"
        or meta.get("normalizedSha256") != digest(canonical(normalized).encode())
        or meta.get("sourcePointCount") != len(points)
        or meta.get("normalizedPointCount") != len(normalized)
        or meta.get("direction") != "ORIGIN_TO_DESTINATION_PRESERVED"
        or meta.get("sourceCoordinateOrder") != "LONGITUDE_LATITUDE"
    ):
        raise ValueError("NORMALIZATION_PROVENANCE_MISMATCH")
    projected = [
        [math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))]
        for lon, lat in points
    ]
    xs, ys = [p[0] for p in projected], [p[1] for p in projected]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    scale = 0.90 / max(max(xs) - min(xs), max(ys) - min(ys))
    source = [
        [round(0.5 + (x - cx) * scale, 9), round(0.5 - (y - cy) * scale, 9)]
        for x, y in projected
    ]
    if normalized[0] != source[0] or normalized[-1] != source[-1]:
        raise ValueError("NORMALIZED_ENDPOINT_DIRECTION_CHANGED")
    cursor = 0
    for point in normalized:
        while cursor < len(source) and source[cursor] != point:
            cursor += 1
        if cursor == len(source):
            raise ValueError("NORMALIZED_POINT_NOT_IN_SOURCE_ORDER")
        cursor += 1
    if plan.get("geometryMatchesHyundaiRoute") is not False:
        raise ValueError("EXTERNAL_GEOMETRY_MUST_NOT_CLAIM_HYUNDAI_MATCH")


def gpx_bytes(points, name):
    gpx = ET.Element(
        f"{{{NS}}}gpx", {"version": "1.1", "creator": "Nunti API route replay"}
    )
    track = ET.SubElement(gpx, f"{{{NS}}}trk")
    ET.SubElement(track, f"{{{NS}}}name").text = name
    segment = ET.SubElement(track, f"{{{NS}}}trkseg")
    for lon, lat in points:
        ET.SubElement(segment, f"{{{NS}}}trkpt", {"lat": str(lat), "lon": str(lon)})
    return ET.tostring(gpx, encoding="utf-8", xml_declaration=True)


def read_gpx(raw):
    return [
        [float(p.attrib["lon"]), float(p.attrib["lat"])]
        for p in ET.fromstring(raw).iter(f"{{{NS}}}trkpt")
    ]


def prepare(plan_path, folder, provider_response_path=None):
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    points = coordinates_from_plan(plan)
    verify_plan(plan, points)
    if provider_response_path is not None:
        response_raw = provider_response_path.read_bytes()
        if digest(response_raw) != plan["geometry"].get("responseSha256"):
            raise ValueError("PROVIDER_RESPONSE_BYTES_SHA_MISMATCH")
        response = json.loads(response_raw)
        if (
            response.get("code") != "Ok"
            or response["routes"][0]["geometry"].get("type") != "LineString"
            or response["routes"][0]["geometry"].get("coordinates") != points
        ):
            raise ValueError("PROVIDER_RESPONSE_GEOMETRY_MISMATCH")
        (folder / "provider-response.json").write_bytes(response_raw)
    geometry_sha = digest(canonical(points).encode())
    name = "Nunti API route " + str(plan.get("planId", "unidentified"))[:16]
    gpx = gpx_bytes(points, name)
    assert read_gpx(gpx) == points, "GPX_LON_LAT_ROUNDTRIP_FAILED"
    reverse = list(reversed(points))
    diagnostic_loop = points + points[-2::-1]
    assert read_gpx(gpx_bytes(reverse, "Reverse diagnostic")) == reverse
    assert (
        read_gpx(gpx_bytes(diagnostic_loop, "Out-and-back diagnostic"))
        == diagnostic_loop
    )
    assert diagnostic_loop[0] == diagnostic_loop[-1]
    (folder / "source-plan.json").write_bytes(raw)
    (folder / "route.gpx").write_bytes(gpx)
    (folder / "reverse-diagnostic.gpx").write_bytes(
        gpx_bytes(reverse, "Reverse diagnostic")
    )
    (folder / "loop-diagnostic.gpx").write_bytes(
        gpx_bytes(diagnostic_loop, "Out-and-back diagnostic")
    )
    report = {
        "status": "PASS_ROUTE_REPLAY_ARTIFACTS_ONLY",
        "planId": plan.get("planId"),
        "sourcePlanSha256": digest(raw),
        "provider": "OSRM_FOSSGIS",
        "rawCoordinatesSha256": geometry_sha,
        "providerDeclaredRawSha256": plan["geometry"].get("rawSha256"),
        "rawCoordinatesSha256Verified": True,
        "savedPlanSha256Verified": True,
        "providerResponseBytesVerified": provider_response_path is not None,
        "normalizedPointsDerivedFromSameRawSourceInOrder": True,
        "normalizedPointsSha256": plan["geometry"]["normalization"]["normalizedSha256"],
        "pointCount": len(points),
        "gpxSha256": digest(gpx),
        "coordinateOrder": "SOURCE_LONGITUDE_LATITUDE_GPX_ATTRIBUTES_LAT_LON",
        "gpxRoundtripVerified": True,
        "reverseRoundtripVerified": True,
        "loopRoundtripVerified": True,
        "diagnosticReverseLoopAreNewRoutableApiResponses": False,
        "geometryMatchesHyundaiRoute": False,
        "deviceReplayExecuted": False,
        "sdkLocationConsumptionVerified": False,
        "paidApiCalls": 0,
        "videoRecorded": False,
        "speakerRecorded": False,
    }
    return plan, points, report


def native_observation(serial, refresh=False, command=None):
    command_name = command or ("refresh" if refresh else "snapshot")
    arguments = [
        "node",
        str(ROOT / "scripts/navigation_native_command.mjs"),
        "--serial=" + serial,
        "--command=" + command_name,
        "--wait-ms=" + ("15000" if command_name == "reroute" else "5000"),
    ]
    if command_name != "foreground":
        arguments.append("--return-to-nunti")
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=50,
    )
    value = json.loads(result.stdout)
    if refresh and (
        value.get("ack", {}).get("accepted") is not True
        or value.get("callbackObserved") is not True
    ):
        raise ValueError("OFFICIAL_CURRENT_LOCATION_CALLBACK_NOT_OBSERVED")
    return value


def artifact_identity(artifact):
    if not isinstance(artifact, dict) or not artifact.get("characterId"):
        return None
    voice = artifact.get("voice", {})
    return {
        "characterId": artifact["characterId"],
        "imageSha256": artifact.get("visual", {}).get("sha256"),
        "voiceProfileId": voice.get("profileId"),
        "voiceBindingId": voice.get("bindingId"),
        "voiceConfigurationSha256": digest(canonical(voice).encode()),
    }


def route_eligibility(snapshot):
    state = snapshot.get("routeState") or {}
    current = snapshot.get("currentLocation") or {}
    destination = snapshot.get("destination") or {}
    route_id = current.get("routeId")
    remaining = destination.get("remainDistance")
    evidence = {
        "naviMode": state.get("naviMode"),
        "isRouting": state.get("isRouting"),
        "routeIdPresent": isinstance(route_id, str) and bool(route_id.strip()),
        "remainingDistancePositive": isinstance(remaining, (int, float))
        and remaining > 0,
        "routeLifecycle": snapshot.get("routeLifecycle"),
    }
    evidence["eligible"] = bool(
        evidence["routeIdPresent"]
        and evidence["remainingDistancePositive"]
        and evidence["naviMode"] == "ROUTE_GUIDING"
    )
    evidence["legacyLifecycleConflictsWithGuidingState"] = bool(
        evidence["eligible"] and evidence["routeLifecycle"] == "ENDED"
    )
    return evidence


def location(snapshot):
    point = snapshot.get("currentLocation")
    if (
        isinstance(point, dict)
        and isinstance(point.get("latitude"), (int, float))
        and isinstance(point.get("longitude"), (int, float))
        and not isinstance(point["latitude"], bool)
        and not isinstance(point["longitude"], bool)
        and math.isfinite(point["latitude"])
        and math.isfinite(point["longitude"])
    ):
        return [point["longitude"], point["latitude"]]
    return None


def point_distance_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    value = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 12742000 * math.asin(min(1, math.sqrt(value)))


def observe_requested_location(serial, requested, timeout=10):
    """Allow the real navigation service to consume its asynchronous GPS feed."""
    deadline = time.monotonic() + timeout
    attempts = 0
    while True:
        observed = native_observation(serial, True)
        attempts += 1
        point = location(observed["snapshot"])
        distance = point_distance_m(requested, point) if point else None
        if (distance is not None and distance <= 100) or time.monotonic() >= deadline:
            return observed, point, distance, attempts
        time.sleep(0.4)


def grpc_bindings(temp):
    import grpc_tools
    from grpc_tools import protoc

    proto_dir = SDK / "emulator/lib"
    proto = proto_dir / "emulator_controller.proto"
    builtin = Path(grpc_tools.__file__).parent / "_proto"
    if protoc.main(
        [
            "protoc",
            "-I" + str(proto_dir),
            "-I" + str(builtin),
            "--python_out=" + str(temp),
            str(proto),
        ]
    ):
        raise ValueError("EMULATOR_PROTO_COMPILE_FAILED")
    sys.path.insert(0, str(temp))
    return importlib.import_module("emulator_controller_pb2"), digest(
        proto.read_bytes()
    )


def replay(serial, points, folder, report, samples, interval, run_reroute=False):
    import grpc
    from google.protobuf.empty_pb2 import Empty
    from google.protobuf.json_format import MessageToDict
    from record_emulator_audio import find_discovery

    if not serial.startswith("emulator-") or not serial[9:].isdigit():
        raise ValueError("EMULATOR_SERIAL_REQUIRED")
    _, props, target = find_discovery(serial)
    if props.get("grpc.server_cert") or props.get("grpc.tls"):
        raise ValueError("TLS_CONFIG_UNSUPPORTED_NO_PLAINTEXT_FALLBACK")
    metadata = (("authorization", "Bearer " + props["grpc.token"]),)
    observations = []
    baseline_native = native_observation(serial, True)
    baseline_sdk = baseline_native["snapshot"]
    if (
        baseline_sdk.get("source") != "PLEOS_NAVI_HELPER_API"
        or baseline_sdk.get("connected") is not True
    ):
        raise ValueError("OFFICIAL_NATIVE_SDK_SNAPSHOT_REQUIRED")
    report["nativeRouteEligibilityEvidence"] = route_eligibility(baseline_sdk)
    if run_reroute and not report["nativeRouteEligibilityEvidence"]["eligible"]:
        raise ValueError("ACTIVE_NATIVE_ROUTE_REQUIRED_FOR_REROUTE_TEST")
    (folder / "sdk-before.json").write_text(canonical(baseline_sdk))
    baseline_identity = artifact_identity(baseline_native.get("artifact"))
    report["artifactIdentityBefore"] = baseline_identity
    with tempfile.TemporaryDirectory(prefix="nunti-gps-proto-", dir=folder) as temp:
        pb, proto_sha = grpc_bindings(Path(temp))
        channel = grpc.insecure_channel(target)
        baseline = None
        try:
            grpc.channel_ready_future(channel).result(timeout=5)
            get_gps = channel.unary_unary(
                "/android.emulation.control.EmulatorController/getGps",
                request_serializer=Empty.SerializeToString,
                response_deserializer=pb.GpsState.FromString,
            )
            set_gps = channel.unary_unary(
                "/android.emulation.control.EmulatorController/setGps",
                request_serializer=pb.GpsState.SerializeToString,
                response_deserializer=Empty.FromString,
            )
            baseline = get_gps(Empty(), timeout=5, metadata=metadata)
            (folder / "gps-before.json").write_text(
                canonical(MessageToDict(baseline, preserving_proto_field_name=True))
            )
            report.update(
                locationSource="AUTHENTICATED_EMULATOR_GETGPS_SETGPS",
                protoSha256=proto_sha,
                temporaryLocationUiPassiveUpdateDisabled=True,
                gpsSpeedMetersPerSecond=0,
                vehicleHardwarePropertiesChanged=False,
                realVehicleTest=False,
            )
            indices = sorted(
                {round(i * (len(points) - 1) / (samples - 1)) for i in range(samples)}
            )
            for index in indices:
                lon, lat = points[index]
                requested = pb.GpsState(
                    latitude=lat,
                    longitude=lon,
                    speed=0,
                    bearing=0,
                    altitude=baseline.altitude,
                    satellites=max(1, baseline.satellites),
                    passiveUpdate=False,
                )
                set_gps(requested, timeout=5, metadata=metadata)
                report["deviceReplayExecuted"] = True
                time.sleep(interval)
                actual = get_gps(Empty(), timeout=5, metadata=metadata)
                accepted = (
                    abs(actual.latitude - lat) < 1e-6
                    and abs(actual.longitude - lon) < 1e-6
                )
                sdk_error = None
                try:
                    observed_native, sdk_point, sdk_distance, refresh_attempts = (
                        observe_requested_location(serial, [lon, lat])
                    )
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    observed_native, sdk_point, sdk_distance, refresh_attempts = (
                        {},
                        None,
                        None,
                        None,
                    )
                    sdk_error = type(error).__name__
                sdk = observed_native.get("snapshot")
                observation = {
                    "sourcePointIndex": index,
                    "requestedLonLat": [lon, lat],
                    "gpsReadbackMatched": accepted,
                    "sdkLonLat": sdk_point,
                    "sdkDistanceToRequestedMeters": sdk_distance,
                    "sdkRefreshAttempts": refresh_attempts,
                    "sdkSnapshot": sdk,
                    "sdkObservationErrorType": sdk_error,
                    "artifactIdentity": artifact_identity(
                        observed_native.get("artifact")
                    ),
                }
                observations.append(observation)
                (folder / f"sample-{len(observations):02d}.json").write_text(
                    canonical(observation)
                )
                # Request while on the path, before the destination sample can
                # end guidance. With two points, use the origin instead.
                if run_reroute and index == indices[(len(indices) - 1) // 2]:
                    try:
                        reroute = native_observation(serial, command="reroute")
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        reroute = {"errorType": type(error).__name__}
                    (folder / "sdk-reroute.json").write_text(canonical(reroute))
                    report.update(
                        rerouteSourcePointIndex=index,
                        rerouteCommandRequested=True,
                        rerouteCommandAccepted=reroute.get("ack", {}).get("accepted")
                        is True,
                        rerouteSdkCompletionVerified=reroute.get("callbackObserved")
                        is True
                        and "onReRouteEnded"
                        in reroute.get("observedCallbackTypes", []),
                        rerouteArtifactIdentityPreserved=bool(baseline_identity)
                        and artifact_identity(reroute.get("artifact"))
                        == baseline_identity,
                    )
            matches = [
                v
                for v in observations
                if v["sdkDistanceToRequestedMeters"] is not None
                and v["sdkDistanceToRequestedMeters"] <= 100
            ]
            report.update(
                gpsSamples=len(observations),
                gpsReadbackVerified=all(v["gpsReadbackMatched"] for v in observations),
                sdkLocationConsumptionVerified=len(matches) == len(observations),
                sdkMatchingSamples=len(matches),
                sdkToleranceMeters=100,
                status="PASS_GPS_REPLAY_AND_SDK_OBSERVATION"
                if len(matches) == len(observations)
                and all(v["gpsReadbackMatched"] for v in observations)
                else "GPS_REPLAY_SDK_CONSUMPTION_UNVERIFIED",
            )
        except grpc.RpcError as error:
            report.update(status="GPS_RPC_FAILED", errorCode=error.code().name)
            raise ValueError("GPS_RPC_FAILED_" + error.code().name) from None
        finally:
            if baseline is not None:
                try:
                    set_gps(baseline, timeout=5, metadata=metadata)
                    time.sleep(1.1)
                    restored = get_gps(Empty(), timeout=5, metadata=metadata)
                    report["gpsStateRestored"] = (
                        all(
                            abs(getattr(restored, k) - getattr(baseline, k)) < 1e-6
                            for k in (
                                "latitude",
                                "longitude",
                                "speed",
                                "bearing",
                                "altitude",
                            )
                        )
                        and restored.passiveUpdate == baseline.passiveUpdate
                        and restored.satellites == baseline.satellites
                    )
                    (folder / "gps-after-restore.json").write_text(
                        canonical(
                            MessageToDict(restored, preserving_proto_field_name=True)
                        )
                    )
                except (grpc.RpcError, OSError, ValueError) as error:
                    report["gpsStateRestored"] = False
                    report["restoreErrorType"] = type(error).__name__
                try:
                    after_native = native_observation(serial, True)
                    after_sdk = after_native["snapshot"]
                    (folder / "sdk-after-restore.json").write_text(canonical(after_sdk))
                    before_point, after_point = (
                        location(baseline_sdk),
                        location(after_sdk),
                    )
                    report["sdkRestoreObserved"] = bool(
                        before_point
                        and after_point
                        and point_distance_m(before_point, after_point) <= 100
                    )
                    after_identity = artifact_identity(after_native.get("artifact"))
                    report["artifactIdentityAfter"] = after_identity
                    report["artifactIdentityPreservedAcrossReplay"] = bool(
                        baseline_identity
                        and baseline_identity == after_identity
                        and all(
                            v["artifactIdentity"] == baseline_identity
                            for v in observations
                        )
                    )
                    report["artifactIdentityVerification"] = (
                        "UNAVAILABLE_NO_AVATAR"
                        if not baseline_identity
                        else "PRESERVED"
                        if report["artifactIdentityPreservedAcrossReplay"]
                        else "CHANGED"
                    )
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    report["sdkRestoreObserved"] = False
                    report["sdkRestoreErrorType"] = type(error).__name__
            channel.close()
            if baseline is not None and not report.get("gpsStateRestored"):
                report["status"] = "GPS_RESTORE_FAILED"
    if not report.get("gpsStateRestored"):
        raise ValueError("GPS_ORIGINAL_STATE_RESTORE_NOT_VERIFIED")
    if not report.get("gpsReadbackVerified") or not report.get(
        "sdkLocationConsumptionVerified"
    ):
        raise ValueError("GPS_REPLAY_SDK_CONSUMPTION_NOT_VERIFIED")
    if run_reroute and not report.get("rerouteSdkCompletionVerified"):
        report["status"] = "GPS_REPLAY_PASSED_REROUTE_COMPLETION_UNVERIFIED"
        raise ValueError("SDK_REROUTE_COMPLETION_NOT_VERIFIED")
    if baseline_identity and (
        not report.get("artifactIdentityPreservedAcrossReplay")
        or run_reroute
        and not report.get("rerouteArtifactIdentityPreserved")
    ):
        report["status"] = "ARTIFACT_IDENTITY_CHANGED_DURING_NAVIGATION"
        raise ValueError("ARTIFACT_IDENTITY_PRESERVATION_FAILED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--provider-response", type=Path)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--run-replay", action="store_true")
    parser.add_argument("--run-reroute", action="store_true")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=1.2)
    args = parser.parse_args()
    if not 2 <= args.samples <= 12 or not 1 <= args.interval <= 5:
        raise ValueError("REPLAY_BOUNDS_INVALID")
    if args.run_reroute and not args.run_replay:
        raise ValueError("REROUTE_TEST_REQUIRES_GPS_REPLAY")
    now = datetime.now(timezone.utc)  # noqa: UP017 - macOS system Python 3.9 remains supported.
    folder = WORK / (now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    folder.mkdir(parents=True, mode=0o700)
    report = {
        "status": "STARTED",
        "paidApiCalls": 0,
        "videoRecorded": False,
        "speakerRecorded": False,
    }
    try:
        _, points, report = prepare(args.plan.resolve(), folder, args.provider_response)
        if args.run_replay:
            replay(
                args.serial,
                points,
                folder,
                report,
                args.samples,
                args.interval,
                args.run_reroute,
            )
    except Exception as error:
        report.update(errorType=type(error).__name__)
        if report["status"].startswith("PASS") or report["status"] == "STARTED":
            report["status"] = "FAILED"
        raise
    finally:
        (folder / "verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "report": str(folder / "verification.json"),
                    "deviceReplayExecuted": report.get("deviceReplayExecuted", False),
                    "sdkLocationConsumptionVerified": report.get(
                        "sdkLocationConsumptionVerified", False
                    ),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("검증 중단: " + str(error), file=sys.stderr)
        raise SystemExit(1) from None
