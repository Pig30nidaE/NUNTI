#!/usr/bin/env python3
"""Verify versioned casting and DSP settings without overwriting v1 identity."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from voice_cli import ROOT, VoiceError, bind_recipe, read_json
from voice_v2 import bind_v2, synthesize_v2


class CandidateV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name)
        self.recipes = read_json(ROOT / "prototypes/journey_characters/sample-output.json")["recipes"]

    def tearDown(self):
        self.temp.cleanup()

    def test_three_new_source_speakers_and_versioned_profiles(self):
        values = [bind_v2(r, self.state) for r in self.recipes[:3]]
        self.assertEqual([v["speakerId"] for v in values], ["F3", "F4", "F5"])
        self.assertTrue(all(v["profileId"].endswith("-v2") for v in values))
        self.assertTrue(all(v["candidateVersion"] == 2 for v in values))

    def test_mild_pitch_settings_are_persisted_inside_binding_digest(self):
        binding = bind_v2(self.recipes[0], self.state)
        self.assertEqual(binding["postprocess"]["semitones"], 3.0)
        self.assertEqual(binding["postprocess"]["type"], "duration_preserving_pitch_shift")
        persisted = read_json(self.state / "bindings.json")["bindings"][self.recipes[0]["characterId"]]
        self.assertEqual(binding, persisted)

    def test_reroute_keeps_both_speaker_and_postprocess(self):
        recipe = copy.deepcopy(self.recipes[0])
        first = bind_v2(recipe, self.state)
        recipe["voiceIntent"]["requested"]["affect"] = "quiet_delight"
        self.assertEqual(first, bind_v2(recipe, self.state))

    def test_existing_v1_binding_is_not_replaced(self):
        old = bind_recipe(self.recipes[0], self.state)
        before = (self.state / "bindings.json").read_bytes()
        with self.assertRaisesRegex(VoiceError, "another experiment version"):
            bind_v2(self.recipes[0], self.state)
        self.assertEqual(before, (self.state / "bindings.json").read_bytes())
        self.assertEqual(bind_recipe(self.recipes[0], self.state), old)

    def test_default_v1_state_directory_is_refused_even_when_empty(self):
        with self.assertRaisesRegex(VoiceError, "separate state"):
            bind_v2(self.recipes[0], ROOT / ".local/journey-voice/state")

    def test_unknown_intent_is_not_replaced_by_small_voice(self):
        recipe = copy.deepcopy(self.recipes[0])
        recipe["voiceIntent"]["requested"]["affect"] = "UNSPECIFIED"
        with self.assertRaisesRegex(VoiceError, "UNBOUND_INTENT"):
            bind_v2(recipe, self.state)

    def test_invalid_text_is_rejected_before_creating_binding(self):
        with self.assertRaises(VoiceError):
            synthesize_v2(self.recipes[0], "안녕🚗", self.state)
        self.assertFalse((self.state / "bindings.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
