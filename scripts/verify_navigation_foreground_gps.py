#!/usr/bin/env python3
"""Separate native-foreground GPS consumption from background location limits.

Run only while the official navigation guidance screen is already foreground.
The test uses one saved API-route midpoint and restores the full original GPS.
"""

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

import verify_navigation_integration as core


def return_to_nunti():
    subprocess.run(
        [
            str(core.SDK / "platform-tools/adb"),
            "-s",
            "emulator-5554",
            "shell",
            "am",
            "start",
            "-W",
            "--user",
            "10",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "-f",
            "0x10200000",
            "-n",
            "ai.nunti.avatar.demo/ai.nunti.app.MainActivity",
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    time.sleep(0.8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--hold-seconds", type=float, default=16)
    args = parser.parse_args()
    if not 4 <= args.hold_seconds <= 20:
        raise ValueError("FOREGROUND_GPS_HOLD_MUST_BE_4_TO_20_SECONDS")
    if not args.run:
        print("PREVIEW_ONLY: requires native navigation foreground and --run")
        return
    import grpc
    from google.protobuf.empty_pb2 import Empty
    from record_emulator_audio import find_discovery

    folder = core.WORK / ("foreground-" + str(time.time_ns()))
    folder.mkdir(parents=True, mode=0o700)
    plan = json.loads(args.plan.read_bytes())
    points = core.coordinates_from_plan(plan)
    core.verify_plan(plan, points)
    requested_point = points[len(points) // 2]
    _, properties, target = find_discovery("emulator-5554")
    metadata = (("authorization", "Bearer " + properties["grpc.token"]),)
    report = {
        "status": "STARTED",
        "nativeGuidanceForegroundInitiallyRequired": True,
        "foregroundGpsHoldSeconds": args.hold_seconds,
        "requestedLonLat": requested_point,
        "paidApiCalls": 0,
        "vehicleHardwarePropertiesChanged": False,
        "videoRecorded": False,
        "speakerRecorded": False,
    }
    with tempfile.TemporaryDirectory(dir=folder, prefix="proto-") as temporary:
        pb, _ = core.grpc_bindings(Path(temporary))
        channel = grpc.insecure_channel(target)
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
        fields = tuple(pb.GpsState.DESCRIPTOR.fields_by_name)
        (folder / "gps-before.json").write_text(
            core.canonical({k: getattr(baseline, k) for k in fields})
        )
        try:
            requested = pb.GpsState()
            requested.CopyFrom(baseline)
            requested.longitude, requested.latitude = requested_point
            requested.passiveUpdate, requested.speed = False, 0
            requested.satellites = max(1, baseline.satellites)
            set_gps(requested, timeout=5, metadata=metadata)
            time.sleep(args.hold_seconds)
            provider_state = subprocess.check_output(
                [
                    str(core.SDK / "platform-tools/adb"),
                    "-s",
                    "emulator-5554",
                    "shell",
                    "dumpsys",
                    "location",
                ],
                timeout=10,
            )
            (folder / "android-location-native-foreground.txt").write_bytes(
                provider_state
            )
            actual = get_gps(Empty(), timeout=5, metadata=metadata)
            report["gpsReadbackMatched"] = (
                abs(actual.longitude - requested.longitude) < 1e-6
                and abs(actual.latitude - requested.latitude) < 1e-6
            )
            return_to_nunti()
            observed = core.native_observation("emulator-5554", refresh=True)
            (folder / "sdk-after-native-foreground.json").write_text(
                core.canonical(observed)
            )
            point = core.location(observed["snapshot"])
            distance = core.point_distance_m(requested_point, point) if point else None
            report.update(
                sdkLonLat=point,
                sdkDistanceToRequestedMeters=distance,
                sdkLocationConsumptionVerified=distance is not None and distance <= 100,
            )
        finally:
            set_gps(baseline, timeout=5, metadata=metadata)
            time.sleep(1.1)
            restored = get_gps(Empty(), timeout=5, metadata=metadata)
            report["gpsStateRestored"] = all(
                getattr(restored, k) == getattr(baseline, k) for k in fields
            )
            (folder / "gps-after-restore.json").write_text(
                core.canonical({k: getattr(restored, k) for k in fields})
            )
            try:
                core.native_observation("emulator-5554", command="foreground")
                time.sleep(args.hold_seconds)
                return_to_nunti()
                observed = core.native_observation("emulator-5554", refresh=True)
                (folder / "sdk-after-restore.json").write_text(core.canonical(observed))
                point = core.location(observed["snapshot"])
                report["sdkRestoredGpsConsumptionObserved"] = (
                    point is not None
                    and core.point_distance_m(
                        [baseline.longitude, baseline.latitude], point
                    )
                    <= 100
                )
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                report["sdkRestoreObservationErrorType"] = type(error).__name__
            channel.close()
            report["status"] = (
                "PASS_NATIVE_FOREGROUND_GPS_CONSUMPTION"
                if report.get("sdkLocationConsumptionVerified")
                and report.get("gpsStateRestored")
                else "NATIVE_FOREGROUND_GPS_CONSUMPTION_UNVERIFIED"
            )
            (folder / "verification.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            )
            print(
                json.dumps(
                    {**report, "report": str(folder / "verification.json")},
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    main()
