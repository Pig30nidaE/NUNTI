#!/usr/bin/env python3
"""Exercise the real CLI and persisted files, including interrupted subprocesses."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
CLI = HERE / "recipe_cli.py"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class RecipeCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nunti-recipe-verify-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.ledger = self.directory / "ledger.json"
        self.counter = 0
        self.coast = read_json(HERE / "examples" / "coastal_rest.json")

    def run_cli(self, request=None, crash=None, ledger=None, expected=0):
        self.counter += 1
        input_path = self.directory / ("request-%d.json" % self.counter)
        input_path.write_text(json.dumps(request or self.coast), encoding="utf-8")
        command = [sys.executable, str(CLI), "generate", "--input", str(input_path),
                   "--ledger", str(ledger or self.ledger)]
        if crash:
            command += ["--simulate-crash", crash]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def generate(self, request=None, ledger=None):
        return json.loads(self.run_cli(request, ledger=ledger).stdout)

    def test_duplicate_request_and_process_restart_return_identical_bytes(self):
        first = self.run_cli()
        committed = self.ledger.read_bytes()
        second = self.run_cli()
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(committed, self.ledger.read_bytes())
        self.assertEqual(len(read_json(self.ledger)["journeys"]), 1)
        # Emulate a recipe persisted before the user's C art-direction choice.
        # Current generation must not repaint that existing character.
        legacy = read_json(self.ledger)
        recipe = legacy["journeys"][self.coast["journeyId"]]["recipe"]
        recipe["world"]["id"] = "soft_sculpt_25d"
        recipe["registryVersion"] = "soft-sculpt-0.1"
        recipe["design"]["materialIntent"] = "frosted sea-glass clay"
        del recipe["design"]["interiorIntent"]
        self.ledger.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
        legacy_bytes = self.ledger.read_bytes()
        self.assertEqual(self.generate(), recipe)
        self.assertEqual(self.ledger.read_bytes(), legacy_bytes)

    def test_reroute_and_changed_duplicate_preserve_frozen_recipe(self):
        first = self.run_cli()
        reroute = copy.deepcopy(self.coast)
        reroute["requestId"] = "request-coast-reroute"
        reroute["route"]["distanceKm"] = 220
        reroute["route"]["semanticTags"] = ["highway"]
        reroute["destination"]["semanticTags"] = ["city"]
        self.assertEqual(first.stdout, self.run_cli(reroute).stdout)
        # The same request ID with altered hints still obeys first-committed-journey wins.
        reroute["requestId"] = self.coast["requestId"]
        self.assertEqual(first.stdout, self.run_cli(reroute).stdout)
        self.assertEqual(len(read_json(self.ledger)["requests"]), 2)

    def test_same_route_new_journey_changes_identity_and_body_family(self):
        first = self.generate()
        next_request = read_json(HERE / "examples" / "coastal_rest_next.json")
        second = self.generate(next_request)
        self.assertNotEqual(first["characterId"], second["characterId"])
        self.assertNotEqual(first["seed"], second["seed"])
        self.assertNotEqual(first["design"]["bodyFamily"], second["design"]["bodyFamily"])
        self.assertNotEqual(first["design"]["silhouette"], second["design"]["silhouette"])
        self.assertEqual(first["design"]["palette"], second["design"]["palette"])
        self.assertEqual(second["novelty"]["priorCharacterCount"], 1)

    def test_history_exhausts_body_families_before_repeating(self):
        families = []
        for index in range(8):
            request = copy.deepcopy(self.coast)
            request["requestId"] = "repeat-request-%d" % index
            request["journeyId"] = "repeat-journey-%d" % index
            families.append(self.generate(request)["design"]["bodyFamily"])
        self.assertEqual(len(set(families)), 8)
        request["requestId"], request["journeyId"] = "repeat-request-8", "repeat-journey-8"
        repeated = self.generate(request)
        self.assertEqual(repeated["novelty"]["priorBodyFamilyUses"], 1)
        self.assertEqual(repeated["novelty"]["priorShapeUses"], 0)
        self.assertTrue(repeated["novelty"]["repetitionAfterRegistryExhaustion"])

    def isolated(self, request, label):
        return self.generate(request, self.directory / (label + ".json"))

    def test_destination_route_and_purpose_control_separate_design_axes(self):
        base = self.isolated(self.coast, "base")
        changed = copy.deepcopy(self.coast)
        changed["destination"]["semanticTags"] = ["mountain"]
        destination = self.isolated(changed, "destination")
        self.assertNotEqual(base["design"]["palette"], destination["design"]["palette"])
        self.assertNotEqual(base["design"]["materialIntent"], destination["design"]["materialIntent"])
        self.assertNotEqual(base["design"]["interiorIntent"]["destinationMotif"], destination["design"]["interiorIntent"]["destinationMotif"])
        self.assertEqual(base["design"]["interiorIntent"]["routePattern"], destination["design"]["interiorIntent"]["routePattern"])
        self.assertEqual(base["design"]["interiorIntent"]["light"], destination["design"]["interiorIntent"]["light"])
        self.assertEqual(base["design"]["bodyFamily"], destination["design"]["bodyFamily"])
        changed = copy.deepcopy(self.coast)
        changed["route"]["distanceKm"] = 16
        route_distance = self.isolated(changed, "distance")
        self.assertNotEqual(base["design"]["routeProportions"], route_distance["design"]["routeProportions"])
        self.assertEqual(base["voiceIntent"], route_distance["voiceIntent"])
        changed = copy.deepcopy(self.coast)
        changed["route"]["semanticTags"] = ["urban", "straight"]
        route_tags = self.isolated(changed, "route-tags")
        self.assertNotEqual(base["design"]["bodyFamily"], route_tags["design"]["bodyFamily"])
        self.assertNotEqual(base["design"]["interiorIntent"]["routePattern"], route_tags["design"]["interiorIntent"]["routePattern"])
        self.assertEqual(base["design"]["interiorIntent"]["destinationMotif"], route_tags["design"]["interiorIntent"]["destinationMotif"])
        changed = copy.deepcopy(self.coast)
        changed["purpose"] = "exhibition"
        purpose = self.isolated(changed, "purpose")
        self.assertNotEqual(base["design"]["personalityIntent"], purpose["design"]["personalityIntent"])
        self.assertNotEqual(base["voiceIntent"]["requested"], purpose["voiceIntent"]["requested"])
        self.assertNotEqual(base["design"]["interiorIntent"]["light"], purpose["design"]["interiorIntent"]["light"])
        self.assertEqual(base["design"]["interiorIntent"]["routePattern"], purpose["design"]["interiorIntent"]["routePattern"])
        self.assertEqual(base["design"]["shapeId"], purpose["design"]["shapeId"])
        self.assertEqual(base["design"]["palette"], purpose["design"]["palette"])

    def test_missing_purpose_remains_unspecified(self):
        request = copy.deepcopy(self.coast)
        del request["purpose"]
        recipe = self.generate(request)
        self.assertIsNone(recipe["creativeInspiration"]["purpose"])
        self.assertEqual(recipe["creativeInspiration"]["purposeStatus"], "UNSPECIFIED")
        self.assertEqual(recipe["voiceIntent"]["requested"]["timbre"], "neutral_and_clear")
        self.assertEqual(recipe["design"]["interiorIntent"]["light"]["diffusion"], "neutral soft glow")

    def test_semantic_tags_never_create_verified_road_facts(self):
        request = copy.deepcopy(self.coast)
        request["route"]["semanticTags"] = ["highway", "mountain", "curving"]
        recipe = self.generate(request)
        self.assertEqual(recipe["verifiedRoadFacts"], {"status": "UNKNOWN", "roadTypes": [], "source": None})
        self.assertEqual(recipe["status"], "RECIPE_ONLY")
        self.assertTrue(all(value == "UNCONNECTED" for value in recipe["providers"].values()))
        self.assertFalse(any(recipe["qualityStatus"].values()))
        self.assertEqual(recipe["design"]["interiorIntent"]["renderingStatus"], "NOT_RENDERED")

    def test_explicit_road_fact_is_copied_without_changing_creative_recipe(self):
        base = self.isolated(self.coast, "unknown-facts")
        request = copy.deepcopy(self.coast)
        request["route"]["verifiedRoadFacts"] = {
            "status": "VERIFIED", "roadTypes": ["HIGHWAY"],
            "source": "synthetic-fixture://fact-copy-test-only",
        }
        recipe = self.isolated(request, "provided-facts")
        self.assertEqual(recipe["verifiedRoadFacts"], request["route"]["verifiedRoadFacts"])
        self.assertEqual(recipe["design"], base["design"])

    def test_before_replace_crash_preserves_previous_ledger_and_retry_converges(self):
        self.generate()
        original = self.ledger.read_bytes()
        request = read_json(HERE / "examples" / "mountain_camping.json")
        reference = self.directory / "reference.json"
        reference.write_bytes(original)
        expected = self.run_cli(request, ledger=reference).stdout
        self.run_cli(request, crash="before-replace", expected=86)
        self.assertEqual(original, self.ledger.read_bytes())
        self.assertEqual(len(list(self.directory.glob(".ledger.json.tmp-*"))), 1)
        self.assertEqual(expected, self.run_cli(request).stdout)
        self.assertEqual(self.ledger.read_bytes(), reference.read_bytes())
        self.assertEqual(list(self.directory.glob(".ledger.json.tmp-*")), [])

    def test_after_replace_crash_commits_then_retry_returns_exact_recipe(self):
        reference = self.directory / "reference.json"
        expected = self.run_cli(ledger=reference).stdout
        self.run_cli(crash="after-replace", expected=86)
        committed = self.ledger.read_bytes()
        self.assertEqual(expected, self.run_cli().stdout)
        self.assertEqual(committed, self.ledger.read_bytes())
        self.assertEqual(committed, reference.read_bytes())

    def test_first_save_crash_before_replace_replays_without_new_identity(self):
        reference = self.directory / "reference.json"
        expected = self.run_cli(ledger=reference).stdout
        self.run_cli(crash="before-replace", expected=86)
        self.assertFalse(self.ledger.exists())
        self.assertEqual(expected, self.run_cli().stdout)
        self.assertEqual(self.ledger.read_bytes(), reference.read_bytes())

    def test_request_id_collision_rejected_without_mutation(self):
        self.generate()
        original = self.ledger.read_bytes()
        request = copy.deepcopy(self.coast)
        request["journeyId"] = "another-journey"
        result = self.run_cli(request, expected=2)
        self.assertIn("already belongs", result.stderr)
        self.assertEqual(original, self.ledger.read_bytes())

    def test_corrupt_ledger_is_not_reset(self):
        self.ledger.write_text("{incomplete", encoding="utf-8")
        original = self.ledger.read_bytes()
        self.run_cli(expected=2)
        self.assertEqual(original, self.ledger.read_bytes())

    def test_raw_location_and_unproven_facts_are_rejected(self):
        request = copy.deepcopy(self.coast)
        request["destination"]["latitude"] = 37.0
        self.run_cli(request, expected=2)
        self.assertFalse(self.ledger.exists())
        request = copy.deepcopy(self.coast)
        request["route"]["verifiedRoadFacts"]["roadTypes"] = ["HIGHWAY"]
        self.run_cli(request, expected=2)
        self.assertFalse(self.ledger.exists())

    def test_representative_samples_are_distinct_recipes_with_different_voice_intents(self):
        outputs = [self.generate(read_json(HERE / "examples" / filename)) for filename in (
            "coastal_rest.json", "mountain_camping.json", "city_exhibition.json", "coastal_rest_next.json")]
        self.assertEqual(len({x["characterId"] for x in outputs}), 4)
        self.assertEqual(len({x["design"]["bodyFamily"] for x in outputs}), 4)
        self.assertEqual(len({json.dumps(x["voiceIntent"]["requested"], sort_keys=True) for x in outputs}), 3)
        self.assertEqual([x["world"]["id"] for x in outputs], ["translucent_keepsake_25d"] * 4)
        self.assertEqual([x["registryVersion"] for x in outputs], ["translucent-keepsake-0.2"] * 4)
        # Identity remains the same as the earlier soft-sculpt prototype for each journey.
        expected = [
            ("nunti-9a3f63d68e67292a3a33fc5e", "2072cb0857b58924"),
            ("nunti-8da06e4267f4a71820a06e65", "a4f7f5abf625515f"),
            ("nunti-a455dd81d2c487095fc66e7d", "df1c06736d8d2694"),
            ("nunti-2d6aecb00617ef2899eff678", "75ec04d209594753"),
        ]
        self.assertEqual([(x["characterId"], x["seed"]) for x in outputs], expected)
        self.assertEqual([x["voiceIntent"]["identityKey"] for x in outputs], ["voice-" + item[0] for item in expected])
        for recipe in outputs:
            voice = recipe["voiceIntent"]
            self.assertEqual(voice["status"], "UNBOUND_INTENT")
            self.assertIsNone(voice["provider"])
            self.assertEqual(voice["fallback"]["strategy"], "same_character_asset_else_pending_or_silent")
            self.assertEqual(voice["fallback"]["assetMatchRequirement"], "same_character_voice_binding_and_same_utterance")
            self.assertEqual(voice["fallback"]["assetAvailability"], "UNVERIFIED")
            self.assertEqual(voice["fallback"]["implementationStatus"], "PROPOSAL_ONLY")
            self.assertFalse(voice["fallback"]["characterVoiceIdentityGuaranteed"])
        self.assertTrue(all("translucent" in x["design"]["materialIntent"] for x in outputs))

    def run_prompt_builder(self, document, index=0):
        input_path, output_path = self.directory / "prompt-input.json", self.directory / "prompt.txt"
        input_path.write_text(json.dumps(document), encoding="utf-8")
        subprocess.run([sys.executable, str(HERE / "build_illustration_prompt.py"), "--input", str(input_path),
                        "--recipe-index", str(index), "--output", str(output_path)],
                       check=True, capture_output=True, text=True, timeout=10)
        return output_path.read_text(encoding="utf-8")

    def test_illustration_prompt_uses_selected_recipe_visual_materials_and_geometry(self):
        coast = self.generate()
        city = self.generate(read_json(HERE / "examples" / "city_exhibition.json"))
        coast_prompt = self.run_prompt_builder(coast)
        city_prompt = self.run_prompt_builder({"recipes": [coast, city]}, index=1)
        for recipe, prompt in ((coast, coast_prompt), (city, city_prompt)):
            design = recipe["design"]
            for value in (design["materialIntent"], design["shapeId"], design["silhouette"],
                          design["interiorIntent"]["destinationMotif"], design["interiorIntent"]["routePattern"],
                          design["interiorIntent"]["light"]["color"], *design["palette"]):
                self.assertIn(value, prompt)
            self.assertIn("real transparent alpha background", prompt)
            self.assertIn("opaque warm cream facial patch", prompt)
            self.assertIn("full body visible", prompt)
        self.assertNotIn(city["design"]["materialIntent"], coast_prompt)
        self.assertNotIn(coast["design"]["materialIntent"], city_prompt)
        self.assertNotEqual(coast_prompt, city_prompt)

    def test_illustration_prompt_excludes_location_facts_personality_voice_and_seed(self):
        recipe = self.generate()
        recipe["destination"] = {"rawAddress": "PRIVATE_LOCATION_37.5665_126.9780"}
        recipe["creativeInspiration"]["rawCoordinates"] = "PRIVATE_COORDINATES_35.1796_129.0756"
        recipe["verifiedRoadFacts"] = {"status": "VERIFIED", "source": "PRIVATE_ROAD_EVIDENCE", "roadTypes": ["HIGHWAY"]}
        recipe["design"]["personalityIntent"] = ["PRIVATE_PERSONALITY"]
        recipe["voiceIntent"]["requested"]["timbre"] = "PRIVATE_VOICE"
        prompt = self.run_prompt_builder(recipe)
        for forbidden in ("PRIVATE_LOCATION", "PRIVATE_COORDINATES", "PRIVATE_ROAD_EVIDENCE", "PRIVATE_PERSONALITY",
                          "PRIVATE_VOICE", "verifiedRoadFacts", "HIGHWAY", recipe["seed"]):
            self.assertNotIn(forbidden, prompt)
        self.assertIn(recipe["characterId"], prompt)
        self.assertIn("recipe_sha256:", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
