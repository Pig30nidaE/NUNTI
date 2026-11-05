"""Purpose/place counterfactuals exercise the actual illustration contract."""

from __future__ import annotations

import io
import json
import unittest
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageChops

from nunti.avatar_studio.design_intent import build_design_intent
from nunti.avatar_studio.illustration import render_avatar
from nunti.avatar_studio.journey_art import destination_semantics, render_character
from nunti.avatar_studio.semantic_reference import character_prompt, character_reference

ROUTE = [[0.1, 0.8], [0.3, 0.6], [0.25, 0.4], [0.6, 0.5], [0.85, 0.2]]


class CharacterArtTest(unittest.TestCase):
    def test_model_structure_reference_preserves_actual_outfit_and_destination_pixels(self):
        for destination, purpose in (("서울역", "출장"), ("수원역", "데이트"), ("을왕리", "수영")):
            with self.subTest(destination=destination, purpose=purpose):
                design = build_design_intent(
                    ROUTE, destination, "", purpose, fine_detail_seed="model-reference"
                )
                art = render_character(design)
                expected = (
                    Image.alpha_composite(Image.new("RGBA", art.size, "#faf9f4"), art)
                    .convert("RGB")
                    .resize((512, 512), Image.Resampling.LANCZOS)
                )
                with Image.open(io.BytesIO(character_reference(design))) as reference:
                    self.assertEqual(reference.mode, "RGB")
                    self.assertEqual(reference.size, (512, 512))
                    # The image model sees the whole clothed character and keepsake,
                    # not an unrelated face or the former neutral silhouette proxy.
                    self.assertEqual(reference.tobytes(), expected.tobytes())

    def test_model_prompt_retains_explicit_costume_action_prop_and_place_for_each_reference(self):
        cases = (
            ("서울역", "출장", "SUIT", "clock-shaped station satchel"),
            ("수원역", "데이트", "RIBBON_COAT", "train-shaped travel satchel"),
            ("을왕리", "수영", "SWIMSUIT", "scalloped shell-shaped beach bag"),
            ("을왕리", "출장", "SUIT", "scalloped shell-shaped beach bag"),
        )
        for destination, purpose, outfit, keepsake in cases:
            with self.subTest(destination=destination, purpose=purpose):
                _, design = render_avatar(ROUTE, destination, "", purpose, "model-prompt")
                value = {"destination": {"name": destination, "traits": ""}, "purpose": purpose}
                plan = design["characterPlan"]
                prompt = character_prompt(value, design)
                declarations = json.loads(prompt.rsplit("\n", 1)[1])
                self.assertEqual(declarations["costume"]["id"], outfit)
                self.assertEqual(declarations["costume"], plan["outfit"])
                self.assertEqual(declarations["prop"], plan["prop"])
                self.assertEqual(declarations["action"], plan["action"])
                self.assertEqual(declarations["destination"], value["destination"])
                if plan["pose"] != "HUG":
                    self.assertIn(plan["promptBrief"], prompt)
                self.assertIn(plan["outfit"]["descriptionEn"], prompt)
                self.assertIn(plan["actionEn"], prompt)
                self.assertIn(plan["prop"]["descriptionEn"], prompt)
                self.assertIn(keepsake, prompt)
                self.assertIn("Reference image 1 is the ONE complete character", prompt)
                self.assertIn("Reference image 2 is a FACE TECHNIQUE study only", prompt)
                self.assertIn("full anatomy, costume and pose all come from image 1", prompt)
                self.assertIn("no floor, scenery, cast shadow", prompt)
                self.assertEqual(declarations["surfaceRouteMarking"], "NONE")

    def test_all_ten_matrix_landmarks_have_recognizable_english_bag_constraints(self):
        # These are visual requirements, independent of Korean names in the data block.
        cases = (
            ("서울역", "STATION_CLOCK", ("clock-shaped", "station", "ticket")),
            ("수원역", "RAIL_WINDOW", ("train-shaped", "windows")),
            ("을왕리", "SHELL", ("scalloped", "shell-shaped")),
            ("북한산", "MOUNTAIN", ("outer silhouette", "two pointed mountain peaks")),
            ("서울숲", "LEAF", ("whole bag", "pointed leaf outline", "short stem")),
            ("서울시청", "CITY_WINDOW", ("building-shaped", "two-by-two", "four cream windows")),
            ("국립현대미술관", "ART_FRAME", ("picture-frame-shaped", "contrasting inset picture")),
            ("경복궁", "GATE", ("Korean palace-gate-shaped", "curved tiled roof", "doorway")),
            ("남산서울타워", "MOON", ("crescent-moon-shaped", "attached star")),
            ("에버랜드", "STAR", ("five-point-star-shaped", "pointed outer outline")),
        )
        for destination, landmark, visual_requirements in cases:
            with self.subTest(landmark=landmark):
                _, design = render_avatar(ROUTE, destination, "", "출장", "landmark-contract")
                self.assertEqual(design["characterPlan"]["destination"]["landmark"], landmark)
                value = {"destination": {"name": destination, "traits": ""}, "purpose": "출장"}
                prompt = character_prompt(value, design)
                visible_bag = prompt.split("The destination is visible as ", 1)[1].split(
                    ", large enough to recognize", 1
                )[0]
                for requirement in visual_requirements:
                    self.assertIn(requirement, visible_bag)
                self.assertNotIn("matching reference image 1", visible_bag)
                self.assertIn("bag fully visible in front of the hip", prompt)
                self.assertIn("An outfit's backpack never replaces the destination bag", prompt)
                prop = design["characterPlan"]["prop"]["descriptionEn"]
                self.assertIn(
                    f"(2) the activity object, {prop}; (3) the destination-shaped bag", prompt
                )

    def test_hug_pose_keeps_the_selected_activity_prop_without_changing_saved_design(self):
        for purpose in ("출장", "독서", "생일 축하", "휴식"):
            with self.subTest(purpose=purpose):
                design = None
                for seed in range(40):
                    _, candidate = render_avatar(
                        ROUTE, "경복궁", "", purpose, f"hug-contract-{seed}"
                    )
                    if candidate["characterPlan"]["pose"] == "HUG":
                        design = candidate
                        break
                self.assertIsNotNone(design, "The fixture must exercise an actual HUG plan")
                before = deepcopy(design)
                plan = design["characterPlan"]
                value = {"destination": {"name": "경복궁", "traits": ""}, "purpose": purpose}
                prompt = character_prompt(value, design)
                prop = plan["prop"]["descriptionEn"]
                self.assertIn(f"Pose: both hands visibly holding {prop} near the chest.", prompt)
                self.assertNotIn(plan["poseEn"], prompt)
                self.assertIn(f"Selected activity prop: {prop}.", prompt)
                self.assertIn("(1) the specified clothes; (2) the activity object", prompt)
                self.assertIn("(3) the destination-shaped bag", prompt)
                self.assertEqual(json.loads(prompt.rsplit("\n", 1)[1])["prop"], plan["prop"])
                self.assertEqual(design, before)

    def test_night_destination_changes_the_keepsake_without_requesting_a_scenic_background(self):
        _, design = render_avatar(
            ROUTE, "남산서울타워", "", "밤하늘 별 관찰", "night-background"
        )
        self.assertEqual(design["characterPlan"]["destination"]["landmark"], "MOON")
        self.assertEqual(design["characterPlan"]["purpose"]["role"], "NIGHT")
        value = {
            "destination": {"name": "남산서울타워", "traits": ""},
            "purpose": "밤하늘 별 관찰",
        }
        prompt = character_prompt(value, design)
        self.assertIn(
            "ONE isolated mascot on a perfectly plain uniform warm ivory background", prompt
        )
        self.assertIn("background stays empty even for night", prompt)
        self.assertIn("destination ONLY through the character's visible keepsake bag", prompt)
        self.assertIn("crescent-moon-shaped purse", prompt)
        self.assertIn("no floor, scenery, cast shadow, frame, panel or second character", prompt)
        # This verifies the model request, not whether a generated image obeys it.

    def test_thirty_natural_language_and_negation_regressions(self):
        manifest = json.loads(
            (
                Path(__file__).resolve().parents[2] / "docs/design/avatar-v6/semantic-holdout.json"
            ).read_text()
        )
        self.assertEqual(len(manifest["cases"]), 30)
        for case in manifest["cases"]:
            with self.subTest(case=case["id"], purpose=case["purpose"]):
                actual = build_design_intent(
                    ROUTE, "서울역", "", case["purpose"], fine_detail_seed="holdout"
                )["characterPlan"]["purpose"]
                self.assertEqual(actual["role"], case["role"])
                self.assertEqual(actual["resolution"], case["resolution"])

    def test_unknown_activity_is_explicit_and_not_presented_as_inferred_exploration(self):
        plan = build_design_intent(
            ROUTE, "서울역", "", "친구에게 빌린 물건 전달", fine_detail_seed="unknown"
        )["characterPlan"]
        self.assertEqual(plan["purpose"]["resolution"], "UNKNOWN")
        self.assertEqual(plan["purpose"]["source"], "UNSPECIFIED")
        self.assertIn("Activity is UNKNOWN", plan["promptBrief"])

    def test_model_prompt_keeps_the_selected_laptop_instead_of_inventing_a_briefcase(self):
        selected = None
        for seed in range(30):
            candidate = build_design_intent(
                ROUTE, "서울역", "", "출장", fine_detail_seed=f"prompt-{seed}"
            )["characterPlan"]
            if candidate["prop"]["id"] == "LAPTOP":
                selected = candidate
                break
        self.assertIsNotNone(selected)
        self.assertIn("open miniature laptop", selected["promptBrief"])
        self.assertNotIn("briefcase", selected["promptBrief"])
        self.assertIn(selected["poseEn"], selected["promptBrief"])
        self.assertIn(selected["actionEn"], selected["promptBrief"])

    def test_swim_prompt_wardrobe_has_no_hard_coded_prop(self):
        character = build_design_intent(
            ROUTE, "을왕리", "", "수영", fine_detail_seed="prompt-swim"
        )["characterPlan"]
        self.assertNotIn("ring", character["outfit"]["descriptionEn"])
        self.assertIn(character["prop"]["descriptionEn"], character["promptBrief"])
        self.assertIn("scalloped seashell-shaped bag", character["promptBrief"])

    def test_summary_does_not_append_a_noun_particle_to_a_whole_purpose_sentence(self):
        character = build_design_intent(
            ROUTE, "서울역", "", "출장 회의에서 발표하기", fine_detail_seed="summary"
        )["characterPlan"]
        self.assertNotIn("발표하기을", character["summary"])
        self.assertIn("승차권을", character["summary"])

    def test_known_station_names_do_not_depend_on_traits_or_activity(self):
        for destination in ("서울역", "수원역"):
            for purpose in ("출장", "수영", "어린 아이와 놀이"):
                plan = build_design_intent(
                    ROUTE, destination, "", purpose, fine_detail_seed="held-fixed"
                )["characterPlan"]
                self.assertEqual(plan["destination"]["kind"], "STATION")
                self.assertEqual(plan["destination"]["source"], "KNOWN_PLACE_NAME")

    def test_explicit_purpose_drives_costume_even_at_a_contradictory_destination(self):
        for destination in ("서울역", "을왕리"):
            business = build_design_intent(
                ROUTE, destination, "", "출장 회의", fine_detail_seed="held-fixed"
            )["characterPlan"]
            swim = build_design_intent(
                ROUTE, destination, "", "수영 물놀이", fine_detail_seed="held-fixed"
            )["characterPlan"]
            self.assertEqual(business["outfit"]["id"], "SUIT")
            self.assertEqual(swim["outfit"]["id"], "SWIMSUIT")
            self.assertEqual(business["voiceRole"], "CONFIDENT_PROFESSIONAL")
            self.assertEqual(swim["voiceRole"], "PLAYFUL_YOUNG")
            self.assertEqual(business["destination"], swim["destination"])

    def test_concrete_place_names_precede_ambiguous_substrings(self):
        places = {
            "을왕리": "BEACH",
            "남산서울타워": "NIGHT",
            "춘천 레고랜드": "PLAYGROUND",
            "송도센트럴파크": "GARDEN",
            "전주한옥마을": "HERITAGE",
            "서울시청": "CITY",
        }
        for name, kind in places.items():
            self.assertEqual(destination_semantics(name, "도시 공원")["kind"], kind)
        self.assertEqual(destination_semantics("미확인 장소", "놀이공원")["kind"], "PLAYGROUND")
        self.assertEqual(destination_semantics("알수없는 목적지", "")["kind"], "UNKNOWN")

    def test_explicit_child_and_professional_requests_produce_different_wardrobes(self):
        for purpose, role, outfit in (
            ("어린 아이와 놀이", "PLAY", "DUNGAREES"),
            ("자신감 있는 직장인 출장", "BUSINESS", "SUIT"),
            ("공부와 독서", "STUDY", "KNIT_VEST"),
            ("미술 전시 관람", "ART", "ARTIST_APRON"),
        ):
            c = build_design_intent(ROUTE, "수원역", "", purpose, fine_detail_seed="fixed")[
                "characterPlan"
            ]
            self.assertEqual((c["purpose"]["role"], c["outfit"]["id"]), (role, outfit))
            self.assertIn(outfit, c["renderParts"])

    def test_actual_costume_changes_pixels_when_family_and_pose_are_held_fixed(self):
        business = build_design_intent(ROUTE, "서울역", "", "출장", fine_detail_seed="fixed")
        artist = build_design_intent(ROUTE, "서울역", "", "미술 관람", fine_detail_seed="fixed")
        # Isolate semantic clothing/prop rendering from random body composition.
        for field in ("bodyFamily", "composition", "expression", "pose", "routeInfluence"):
            artist["characterPlan"][field] = deepcopy(business["characterPlan"][field])
        a, b = render_character(business), render_character(artist)
        difference = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        self.assertIsNotNone(difference.crop((200, 430, 570, 665)).getbbox())

    def test_destination_keepsakes_change_real_alpha_with_all_other_parts_fixed(self):
        a = build_design_intent(ROUTE, "서울역", "", "출장", fine_detail_seed="fixed")
        b = deepcopy(a)
        b["characterPlan"]["destination"] = destination_semantics("을왕리", "")
        self.assertIsNotNone(
            ImageChops.difference(
                render_character(a).getchannel("A"), render_character(b).getchannel("A")
            ).getbbox()
        )

    def test_swim_action_variants_really_change_silhouette(self):
        plan = build_design_intent(ROUTE, "을왕리", "", "수영", fine_detail_seed="fixed")
        images = []
        for pose in ("SPLASH", "FLOAT_KICK", "BACK_FLOAT"):
            changed = deepcopy(plan)
            changed["characterPlan"]["pose"] = pose
            images.append(render_character(changed).getchannel("A").tobytes())
        self.assertEqual(len(set(images)), 3)

    def test_exported_character_plan_reconstructs_exact_png_pixels(self):
        png, metadata = render_avatar(ROUTE, "서울역", "", "출장", "reproducible")
        actual = Image.open(io.BytesIO(png))
        replay = render_character({"characterPlan": metadata["characterPlan"]})
        self.assertEqual(actual.tobytes(), replay.tobytes())

    def test_face_anchor_stays_on_opaque_face_for_rotated_swimmers(self):
        for seed in ("swim-0", "swim-1", "swim-2", "swim-3"):
            png, metadata = render_avatar(ROUTE, "을왕리", "", "수영", seed)
            image = Image.open(io.BytesIO(png))
            x, y = (round(v * 768) for v in metadata["formation"]["faceCenter"])
            self.assertEqual(image.getpixel((x, y))[3], 255)
