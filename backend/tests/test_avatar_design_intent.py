"""Counterfactual geometry tests use one fixed fine-detail seed, not random image drift."""

from __future__ import annotations

import math
import unittest

from nunti.avatar_studio.design_intent import build_design_intent, resample_path

ROUTE = [[0.1, 0.8], [0.2, 0.5], [0.4, 0.6], [0.5, 0.3], [0.9, 0.2]]


def plan(route=ROUTE, traits="바다, 파도", purpose="휴식", seed="held-fixed"):
    return build_design_intent(route, "가상의 시험 목적지", traits, purpose, fine_detail_seed=seed)


class AvatarDesignIntentTest(unittest.TestCase):
    def test_journey_seed_varies_composition_within_the_explicit_activity(self):
        a, b = plan(seed="detail-a"), plan(seed="detail-b")
        self.assertNotEqual(
            a["characterPlan"]["structuralSignature"], b["characterPlan"]["structuralSignature"]
        )
        self.assertEqual(a["characterPlan"]["purpose"], b["characterPlan"]["purpose"])
        self.assertEqual(a["characterPlan"]["destination"], b["characterPlan"]["destination"])
        self.assertEqual(a["characterPlan"]["outfit"]["id"], b["characterPlan"]["outfit"]["id"])
        for key in ("purposeRole", "destinationKind", "routeFeatures", "surfaceRouteMarking"):
            self.assertEqual(a["visualIntent"][key], b["visualIntent"][key])
        self.assertNotEqual(a["fineDetails"], b["fineDetails"])

    def test_route_role_is_shape_and_transient_formation_not_a_skin_tattoo(self):
        result = plan()
        self.assertEqual(result["visualIntent"]["surfaceRouteMarking"], "NONE")
        self.assertEqual(
            result["visualIntent"]["routeInterpretation"], "SILHOUETTE_AND_PROPORTION_ONLY"
        )
        self.assertFalse(result["routeThread"]["renderedOnSurface"])
        self.assertEqual(result["routeThread"]["role"], "TRANSIENT_FORMATION_REFERENCE")
        self.assertTrue(result["formation"]["spine"])

    def test_fixed_seed_route_counterfactual_changes_volume_and_correspondence(self):
        a, b = plan(), plan(route=[[0.1, 0.5], [0.9, 0.5]])
        self.assertNotEqual(a["formation"]["contour"], b["formation"]["contour"])
        self.assertNotEqual(a["formation"]["spine"], b["formation"]["spine"])
        self.assertNotEqual(a["visualIntent"]["routeFeatures"], b["visualIntent"]["routeFeatures"])
        self.assertEqual(a["fineDetails"], b["fineDetails"])

    def test_fixed_seed_destination_counterfactual_changes_real_structure(self):
        results = [plan(traits=t) for t in ("바다, 파도", "정원, 숲", "전시, 공예")]
        self.assertEqual(len({r["geometrySignature"] for r in results}), 3)
        self.assertEqual(len({str(r["formation"]["contour"]) for r in results}), 3)
        self.assertEqual(results[0]["fineDetails"], results[1]["fineDetails"])
        self.assertTrue(all(r["visualIntent"]["evidence"][1]["target"] for r in results))

    def test_spine_order_is_source_arc_fraction_not_resampled_target_distance(self):
        a = plan()
        source = resample_path(ROUTE, 96)
        spine = a["formation"]["spine"]
        # Keep source progress; compact endpoint/tail styling is allowed.
        self.assertLess(source[0][0], source[-1][0])
        self.assertLess(spine[0][0], spine[-1][0])
        landmarks = a["visualIntent"]["routeFeatures"]["landmarks"]
        fractions = [m["arcFraction"] for m in landmarks]
        self.assertEqual(fractions, sorted(fractions))
        for landmark in landmarks:
            self.assertEqual(landmark["sourcePoint"], ROUTE[landmark["pointIndex"]])
            self.assertEqual(landmark["targetPoint"], spine[round(landmark["arcFraction"] * 95)])
            self.assertIn(landmark["part"], ("tail", "mantle", "crest"))
            self.assertEqual(landmark["selection"], "MAJOR_TURN")

    def test_contour_is_compact_closed_finite_and_keeps_a_large_face_mass(self):
        routes = [ROUTE, [[0.1, 0.5], [0.9, 0.5]], [[0.5, 0.1], [0.5, 0.9]], list(reversed(ROUTE))]
        for route in routes:
            for traits in ("바다, 파도", "숲, 정원", "유리, 공예"):
                result = plan(route=route, traits=traits)
                formation = result["formation"]
                contour = formation["contour"]
                self.assertEqual((len(contour), len(formation["spine"])), (192, 96))
                self.assertEqual(contour[0], contour[-1])
                self.assertTrue(
                    all(math.isfinite(v) and 0.04 < v < 0.96 for p in contour for v in p)
                )
                width = max(p[0] for p in contour) - min(p[0] for p in contour)
                height = max(p[1] for p in contour) - min(p[1] for p in contour)
                self.assertLess(max(width / height, height / width), 1.9)
                self.assertGreater(min(result["bodyRadii"]), 0.16)

    def test_explicit_traits_outrank_names_then_purpose_without_geographic_lookup(self):
        garden = plan(traits="숲, 정원", purpose="바다 전시 관람")
        self.assertEqual(garden["visualIntent"]["destinationTheme"], "garden")
        blank = build_design_intent(ROUTE, "알수없는 시험 지명", "", "", fine_detail_seed="fixed")
        self.assertEqual(blank["visualIntent"]["destinationTheme"], "pearl")
        self.assertIn("추정하지", blank["visualIntent"]["evidence"][1]["detail"])

    def test_destination_name_counterfactual_uses_only_explicit_place_words(self):
        a = build_design_intent(ROUTE, "달빛 해변", "", "휴식", fine_detail_seed="fixed")
        b = build_design_intent(ROUTE, "작은 수목원", "", "휴식", fine_detail_seed="fixed")
        self.assertEqual(a["visualIntent"]["destinationTheme"], "coast")
        self.assertEqual(b["visualIntent"]["destinationTheme"], "garden")
        self.assertEqual(a["visualIntent"]["evidence"][1]["source"], "입력된 목적지 이름")
        self.assertNotEqual(a["formation"]["contour"], b["formation"]["contour"])
        self.assertEqual(a["fineDetails"], b["fineDetails"])

    def test_route_reversal_changes_tail_and_crest_roles_without_new_randomness(self):
        a, b = plan(), plan(route=list(reversed(ROUTE)))
        self.assertEqual(a["fineDetails"], b["fineDetails"])
        self.assertNotEqual(a["formation"]["contour"], b["formation"]["contour"])
        self.assertNotEqual(a["formation"]["spine"][0], b["formation"]["spine"][0])
