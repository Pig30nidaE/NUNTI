"""Audit validity: a different hash, seed or color is not a different design."""

from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "avatar_v6_matrix", ROOT / "scripts/verify_avatar_v6_matrix.py"
)
assert SPEC and SPEC.loader
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


class AvatarV6MatrixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "docs/design/avatar-v6/cases.json").read_text())

    def test_matrix_covers_20_places_and_10_controlled_purposes(self):
        cases = self.manifest["cases"]
        self.assertEqual(len(cases), 200)
        self.assertEqual(len({case["id"] for case in cases}), 200)
        self.assertEqual(len({case["requestId"] for case in cases}), 200)
        self.assertEqual(len({case["destination"]["name"] for case in cases}), 20)
        self.assertEqual(len({case["expectedPurposeRole"] for case in cases}), 10)
        self.assertEqual(len({case["renderSeed"] for case in cases}), 1)
        for place in {case["destination"]["name"] for case in cases}:
            group = [case for case in cases if case["destination"]["name"] == place]
            self.assertEqual(len(group), 10)
            self.assertEqual(len({case["routeId"] for case in group}), 1)
            self.assertEqual(len({case["expectedPurposeRole"] for case in group}), 10)

    def test_every_route_marks_synthetic_provenance_and_is_ready_offline(self):
        routes = self.manifest["routes"]
        self.assertEqual(len(routes), 20)
        self.assertEqual(len({matrix.digest(route["points"]) for route in routes.values()}), 20)
        for route in routes.values():
            self.assertEqual(route["inputOrigin"], "TEST_ROUTE")
            self.assertNotIn("apiPlanId", route)
            self.assertFalse(route["provenance"]["isRouteToNamedDestination"])
            self.assertEqual(route["provenance"]["kind"], "SYNTHETIC_QA_TRANSFORM")
            self.assertEqual(route["provenance"]["source"]["provider"], "OSRM_FOSSGIS")
            self.assertGreaterEqual(len(route["points"]), 2)
            self.assertTrue(all(0 <= v <= 1 for point in route["points"] for v in point))

    def test_semantic_diversity_excludes_palette_seed_hash_and_microvariation(self):
        plan = {"bodyFamily": "BUNNY", "outfit": {"id": "SUIT", "cut": "JACKET"},
                "pose": "CONFIDENT", "action": "PRESENT", "prop": {"id": "BRIEFCASE"},
                "expression": "SMILE", "composition": {"facing": "FRONT", "tilt": 0},
                "structuralSignature": "one", "seed": "one", "palette": ["#ffffff"]}
        altered = deepcopy(plan)
        altered.update({"structuralSignature": "two", "seed": "two", "palette": ["#eeeeee"]})
        altered["composition"]["tilt"] = 0.0004
        self.assertEqual(matrix.structural_fields(plan), matrix.structural_fields(altered))
        altered["outfit"]["id"] = "SWIMSUIT"
        self.assertNotEqual(matrix.structural_fields(plan), matrix.structural_fields(altered))

    def test_identical_pixels_are_flagged_but_distinct_silhouettes_are_not(self):
        image = Image.new("RGBA", (160, 160))
        ImageDraw.Draw(image).ellipse((40, 30, 120, 130), fill="#d9a3b2")
        first = matrix.pixel_features(image)
        same = matrix.similarity(first, matrix.pixel_features(image.copy()))
        self.assertEqual(same["pHashDistance"], 0)
        self.assertEqual(same["opaqueSilhouetteIoU"], 1)
        self.assertTrue(matrix.is_near_duplicate(same))
        other = Image.new("RGBA", (160, 160))
        ImageDraw.Draw(other).rectangle((10, 10, 150, 150), fill="#d9a3b2")
        metrics = matrix.similarity(first, matrix.pixel_features(other))
        self.assertFalse(matrix.is_near_duplicate(metrics))

    def test_small_color_change_is_still_near_duplicate(self):
        images = []
        for fill in ("#d9a3b2", "#daa4b3"):
            image = Image.new("RGBA", (160, 160))
            ImageDraw.Draw(image).ellipse((40, 30, 120, 130), fill=fill)
            images.append(matrix.pixel_features(image))
        self.assertTrue(matrix.is_near_duplicate(matrix.similarity(*images)))

    def test_destination_check_allows_ambiguous_landmarks_but_not_generic_park(self):
        cases = {case["destination"]["name"]: case for case in self.manifest["cases"]}
        self.assertEqual(matrix.accepted_destination_kinds(cases["춘천 레고랜드"]), ["PLAYGROUND"])
        self.assertNotIn("GARDEN", matrix.accepted_destination_kinds(cases["춘천 레고랜드"]))
        self.assertNotIn("MOUNTAIN", matrix.accepted_destination_kinds(cases["남산서울타워"]))
        self.assertIn("NIGHT", matrix.accepted_destination_kinds(cases["경주 첨성대"]))
        self.assertIn("CITY", matrix.accepted_destination_kinds(cases["동대문디자인플라자"]))
        self.assertIn("MUSEUM", matrix.accepted_destination_kinds(cases["동대문디자인플라자"]))


if __name__ == "__main__":
    unittest.main()
