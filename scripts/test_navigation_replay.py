#!/usr/bin/env python3
"""Offline checks for API provenance and GPX coordinate-order regressions."""

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import verify_navigation_integration as replay


def signed_plan():
    # A deliberately asymmetric fixture makes longitude/latitude and direction
    # changes visible. It is a synthetic parser fixture, not a road API response.
    raw = [[127.03, 37.49], [127.035, 37.493], [127.032, 37.499]]
    projected = [
        [math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))]
        for lon, lat in raw
    ]
    xs, ys = [p[0] for p in projected], [p[1] for p in projected]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    scale = 0.90 / max(max(xs) - min(xs), max(ys) - min(ys))
    normalized = [
        [round(0.5 + (x - cx) * scale, 9), round(0.5 - (y - cy) * scale, 9)]
        for x, y in projected
    ]
    plan = {
        "schemaVersion": "api-route-plan-1",
        "geometry": {
            "provider": "OSRM_FOSSGIS",
            "coordinates": raw,
            "rawSha256": replay.digest(replay.canonical(raw).encode()),
            "normalization": {
                "version": "web-mercator-isotropic-rdp-1",
                "normalizedSha256": replay.digest(
                    replay.canonical(normalized).encode()
                ),
                "sourcePointCount": len(raw),
                "normalizedPointCount": len(normalized),
                "direction": "ORIGIN_TO_DESTINATION_PRESERVED",
                "sourceCoordinateOrder": "LONGITUDE_LATITUDE",
            },
        },
        "routePoints": normalized,
        "geometryMatchesHyundaiRoute": False,
    }
    resign(plan)
    return plan


def resign(plan):
    unsigned = {
        k: v for k, v in plan.items() if k not in ("planId", "route", "retrieval")
    }
    plan["planId"] = replay.digest(replay.canonical(unsigned).encode())
    plan["route"] = {
        "points": plan["routePoints"],
        "inputOrigin": "API_ROUTE",
        "apiPlanId": plan["planId"],
        "confirmed": False,
    }


class NavigationReplayTests(unittest.TestCase):
    def test_real_prepare_path_preserves_route_direction_and_closed_loop(self):
        with tempfile.TemporaryDirectory(prefix="nunti-nav-test-") as temporary:
            folder = Path(temporary)
            plan = signed_plan()
            path = folder / "input-plan.json"
            path.write_text(json.dumps(plan))
            _, points, report = replay.prepare(path, folder)
            self.assertEqual(
                replay.read_gpx((folder / "route.gpx").read_bytes()), points
            )
            reversed_points = replay.read_gpx(
                (folder / "reverse-diagnostic.gpx").read_bytes()
            )
            self.assertEqual(reversed_points[0], points[-1])
            loop = replay.read_gpx((folder / "loop-diagnostic.gpx").read_bytes())
            self.assertEqual(loop[0], loop[-1])
            self.assertTrue(report["normalizedPointsDerivedFromSameRawSourceInOrder"])
            self.assertFalse(report["deviceReplayExecuted"])
            self.assertFalse(report["diagnosticReverseLoopAreNewRoutableApiResponses"])

    def test_modified_raw_coordinates_rejected_before_export(self):
        plan = signed_plan()
        plan["geometry"]["coordinates"][1][0] += 0.001
        with self.assertRaisesRegex(ValueError, "SOURCE_COORDINATES_SHA_MISMATCH"):
            replay.coordinates_from_plan(plan)

    def test_changed_normalized_geometry_rejected_even_if_resigned(self):
        plan = signed_plan()
        plan["routePoints"][1][0] += 0.01
        meta = plan["geometry"]["normalization"]
        meta["normalizedSha256"] = replay.digest(
            replay.canonical(plan["routePoints"]).encode()
        )
        resign(plan)
        with self.assertRaisesRegex(ValueError, "NORMALIZED_POINT_NOT_IN_SOURCE_ORDER"):
            replay.verify_plan(plan, replay.coordinates_from_plan(plan))

    def test_reversed_normalized_path_is_not_original_route(self):
        plan = signed_plan()
        plan["routePoints"].reverse()
        meta = plan["geometry"]["normalization"]
        meta["normalizedSha256"] = replay.digest(
            replay.canonical(plan["routePoints"]).encode()
        )
        resign(plan)
        with self.assertRaisesRegex(
            ValueError, "NORMALIZED_ENDPOINT_DIRECTION_CHANGED"
        ):
            replay.verify_plan(plan, replay.coordinates_from_plan(plan))

    def test_lat_lon_swap_does_not_pass_wgs84_range_validation(self):
        plan = signed_plan()
        plan["geometry"]["coordinates"] = [
            point[::-1] for point in plan["geometry"]["coordinates"]
        ]
        with self.assertRaisesRegex(ValueError, "WGS84_COORDINATE_OUT_OF_RANGE"):
            replay.coordinates_from_plan(plan)

    def test_spoofed_hyundai_geometry_claim_rejected(self):
        plan = signed_plan()
        plan["geometryMatchesHyundaiRoute"] = True
        resign(plan)
        with self.assertRaisesRegex(
            ValueError, "EXTERNAL_GEOMETRY_MUST_NOT_CLAIM_HYUNDAI_MATCH"
        ):
            replay.verify_plan(plan, replay.coordinates_from_plan(plan))

    def test_missing_or_changed_identity_is_not_preservation(self):
        self.assertIsNone(replay.artifact_identity(None))
        artifact = {
            "characterId": "one",
            "visual": {"sha256": "image"},
            "voice": {"profileId": "small"},
        }
        changed = copy.deepcopy(artifact)
        changed["visual"]["sha256"] = "different"
        self.assertNotEqual(
            replay.artifact_identity(artifact), replay.artifact_identity(changed)
        )

    def test_dispatch_receipt_without_sdk_callback_is_not_location_proof(self):
        receipt = {
            "ack": {"accepted": True},
            "callbackObserved": False,
            "snapshot": {"revision": 20},
        }
        result = SimpleNamespace(stdout=json.dumps(receipt))
        with (
            patch.object(replay.subprocess, "run", return_value=result),
            self.assertRaisesRegex(
                ValueError, "OFFICIAL_CURRENT_LOCATION_CALLBACK_NOT_OBSERVED"
            ),
        ):
            replay.native_observation("emulator-5554", refresh=True)

    def test_original_response_bytes_join_plan_and_gpx(self):
        with tempfile.TemporaryDirectory(prefix="nunti-nav-test-") as temporary:
            folder = Path(temporary)
            plan = signed_plan()
            raw = json.dumps(
                {
                    "code": "Ok",
                    "routes": [
                        {
                            "geometry": {
                                "type": "LineString",
                                "coordinates": plan["geometry"]["coordinates"],
                            }
                        }
                    ],
                }
            ).encode()
            plan["geometry"]["responseSha256"] = replay.digest(raw)
            resign(plan)
            plan_path, response_path = folder / "plan.json", folder / "response.json"
            plan_path.write_text(json.dumps(plan))
            response_path.write_bytes(raw)
            _, _, report = replay.prepare(plan_path, folder, response_path)
            self.assertTrue(report["providerResponseBytesVerified"])
            response_path.write_bytes(raw + b" ")
            with self.assertRaisesRegex(
                ValueError, "PROVIDER_RESPONSE_BYTES_SHA_MISMATCH"
            ):
                replay.prepare(plan_path, folder, response_path)

    def test_guiding_with_route_id_does_not_depend_on_isrouting_flag(self):
        snapshot = {
            "routeState": {"naviMode": "ROUTE_GUIDING", "isRouting": False},
            "currentLocation": {"routeId": "actual-route"},
            "destination": {"remainDistance": 27000},
            "routeLifecycle": "ENDED",
        }
        evidence = replay.route_eligibility(snapshot)
        self.assertTrue(evidence["eligible"])
        self.assertTrue(evidence["legacyLifecycleConflictsWithGuidingState"])
        snapshot["currentLocation"]["routeId"] = ""
        self.assertFalse(replay.route_eligibility(snapshot)["eligible"])


if __name__ == "__main__":
    unittest.main()
