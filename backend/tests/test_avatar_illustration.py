"""Real PNG contracts, including the user's opaque matte material correction."""

from __future__ import annotations

import io
import json
import unittest
from copy import deepcopy

from PIL import Image, ImageChops, ImageStat

from nunti.avatar_studio.design_intent import build_design_intent
from nunti.avatar_studio.illustration import _front_face, _render_plan, render_avatar

ROUTE = [[0.1, 0.8], [0.3, 0.6], [0.25, 0.4], [0.6, 0.5], [0.85, 0.2]]
INPUT = (ROUTE, "해안 기념관", "바다, 해변, 파도", "휴식")


class AvatarIllustrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.png, cls.design = render_avatar(*INPUT, "same-journey")
        cls.image = Image.open(io.BytesIO(cls.png))

    def test_png_has_transparent_background_and_opaque_matte_body(self):
        self.assertEqual(
            (self.image.format, self.image.mode, self.image.size), ("PNG", "RGBA", (768, 768))
        )
        alpha = self.image.getchannel("A")
        hist = alpha.histogram()
        self.assertGreater(hist[0], 768 * 768 * 0.4)
        self.assertGreater(hist[255], 768 * 768 * 0.12)
        x, y = self.design["formation"]["faceCenter"]
        self.assertEqual(alpha.getpixel((round(x * 768), round(y * 768))), 255)
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertEqual(self.design["visualIntent"]["renderingStyle"], "MATTE_ILLUSTRATED_2_5D")

    def test_retry_preserves_exact_png_and_design(self):
        self.assertEqual((self.png, self.design), render_avatar(*INPUT, "same-journey"))

    def test_new_journey_changes_real_composition_and_preserves_activity(self):
        for jid in ("new-detail-a", "new-detail-b", "new-detail-c"):
            png, design = render_avatar(*INPUT, jid)
            self.assertNotEqual(self.png, png)
            difference = ImageChops.difference(self.image, Image.open(io.BytesIO(png))).convert(
                "RGB"
            )
            self.assertGreater(sum(ImageStat.Stat(difference).mean), 0.1)
            self.assertNotEqual(self.design["formation"]["contour"], design["formation"]["contour"])
            self.assertNotEqual(
                self.design["characterPlan"]["structuralSignature"],
                design["characterPlan"]["structuralSignature"],
            )
            self.assertEqual(
                self.design["characterPlan"]["purpose"], design["characterPlan"]["purpose"]
            )
            for key in ("purposeRole", "destinationKind", "routeFeatures", "surfaceRouteMarking"):
                self.assertEqual(self.design["visualIntent"][key], design["visualIntent"][key])

    def test_same_fine_seed_route_change_alters_actual_shape_alpha(self):
        png, design = render_avatar([[0.1, 0.5], [0.9, 0.5]], *INPUT[1:], "same-journey")
        changed = Image.open(io.BytesIO(png))
        self.assertIsNotNone(
            ImageChops.difference(self.image.getchannel("A"), changed.getchannel("A")).getbbox()
        )
        self.assertNotEqual(self.design["geometrySignature"], design["geometrySignature"])
        self.assertEqual(self.design["seedFingerprint"], design["seedFingerprint"])

    def test_same_fine_seed_destination_traits_change_large_shape(self):
        png, design = render_avatar(ROUTE, INPUT[1], "정원, 나무, 숲", INPUT[3], "same-journey")
        changed = Image.open(io.BytesIO(png))
        self.assertIsNotNone(
            ImageChops.difference(self.image.getchannel("A"), changed.getchannel("A")).getbbox()
        )
        self.assertNotEqual(self.design["formation"]["contour"], design["formation"]["contour"])
        self.assertEqual(self.design["seedFingerprint"], design["seedFingerprint"])
        self.assertEqual(design["visualIntent"]["destinationTheme"], "garden")

    def test_formation_matches_drawn_silhouette_and_keeps_source_point_order(self):
        formation = self.design["formation"]
        self.assertEqual(formation["version"], "route-volume-2")
        self.assertEqual(len(formation["contour"]), 192)
        self.assertEqual(formation["contour"][0], formation["contour"][-1])
        self.assertEqual(len(formation["spine"]), 96)
        alpha = self.image.getchannel("A")
        for x, y in formation["contour"][::8]:
            px, py = round(x * 768), round(y * 768)
            nearby = [
                alpha.getpixel((px + dx, py + dy)) for dx in range(-2, 3) for dy in range(-2, 3)
            ]
            self.assertGreater(max(nearby), 100)
        self.assertEqual(len(self.design["routeThread"]["points"]), len(ROUTE))
        self.assertEqual(self.design["routeThread"]["coordinateSpace"], "ASSET_NORMALIZED")

    def test_metadata_distinguishes_creative_geometry_and_local_render(self):
        json.dumps(self.design, ensure_ascii=False, allow_nan=False)
        self.assertEqual(self.design["mediaOrigin"], "LOCAL_RENDER")
        self.assertEqual(self.design["designVersion"], "journey-character-3")
        self.assertEqual(
            self.design["visualIntent"]["variationRole"], "SEMANTIC_CHARACTER_COMPOSITION"
        )
        self.assertEqual(self.design["visualIntent"]["surfaceRouteMarking"], "NONE")
        self.assertEqual(
            self.design["visualIntent"]["routeInterpretation"], "SILHOUETTE_AND_PROPORTION_ONLY"
        )
        self.assertFalse(self.design["routeThread"]["renderedOnSurface"])
        self.assertEqual(self.design["routeThread"]["role"], "TRANSIENT_FORMATION_REFERENCE")
        self.assertIn("창작", self.design["motifs"][0]["detail"])
        self.assertIn("바다", self.design["motifs"][1]["detail"])
        for motif in self.design["motifs"]:
            self.assertTrue(
                all(
                    isinstance(motif[k], str) and motif[k]
                    for k in ("label", "source", "target", "detail")
                )
            )

    def test_construction_guides_cannot_reappear_as_skin_marks(self):
        # Keep the actual planned body fixed, then move only construction paths.
        # The silhouette counterfactual tests above separately require geometry
        # to change with the real route. This regression protects finished skin.
        for traits in ("바다, 파도", "정원, 숲", "전시, 공예"):
            with self.subTest(traits=traits):
                plan = build_design_intent(
                    ROUTE, INPUT[1], traits, INPUT[3], fine_detail_seed="clean-surface"
                )
                changed = deepcopy(plan)
                changed["routeThread"]["points"] = [[0.1, 0.1], [0.9, 0.9]]
                changed["formation"]["spine"] = [[0.1, 0.9], [0.9, 0.1]]
                changed["panels"] = [{"kind": "GUIDE", "points": [[0, 0], [1, 0], [1, 1]]}]
                self.assertEqual(_render_plan(plan).tobytes(), _render_plan(changed).tobytes())

    def test_feathered_face_has_no_black_alpha_blur_fringe(self):
        plan = build_design_intent(*INPUT, fine_detail_seed="clean-surface")
        base = (185, 220, 200, 255)
        image = _front_face(
            Image.new("RGBA", (1536, 1536), base),
            Image.new("L", (1536, 1536), 255),
            plan,
        )
        cx, cy = (round(v * 1536) for v in plan["formation"]["faceCenter"])
        # Above eyes and cheeks, the cream plane can only brighten the body.
        # Blurring transparent black RGB with alpha used to draw a dark ring.
        for x in range(cx - 360, cx + 361):
            pixel = image.getpixel((x, cy - 120))
            self.assertTrue(all(pixel[c] >= base[c] for c in range(3)))

    def test_purpose_changes_planned_posture_without_claiming_emotion(self):
        _, design = render_avatar(ROUTE, INPUT[1], INPUT[2], "관람", "same-journey")
        self.assertNotEqual(self.design["formation"]["contour"], design["formation"]["contour"])
        self.assertIn("감정을 추정한 결과가 아닙니다", design["motifs"][2]["detail"])

    def test_rejects_invalid_route_and_identity(self):
        invalid = (
            [],
            [[0.1, 0.2]],
            [[0.3, 0.3], [0.3, 0.3]],
            [[0, 0], [float("nan"), 1]],
            [[0, 0], [2, 1]],
            [[0, 0], [True, 1]],
            [[0, 0], [".5", 1]],
        )
        for route in invalid:
            with self.subTest(route=route), self.assertRaises(ValueError):
                render_avatar(route, *INPUT[1:], "invalid")
        with self.assertRaises(ValueError):
            render_avatar(*INPUT, "")
