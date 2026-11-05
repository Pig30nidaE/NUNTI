#!/usr/bin/env python3
"""Binding/cache boundary tests. Real model/audio checks live in verify_samples.py."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave
from voice_cli import HERE, ROOT, VoiceError, bind_recipe, canonical, load_recipe, read_json, sha, synthesize, validate_text


class TestEngine:
    fingerprint = "test-engine-only"
    runtime = {"engine": "TEST_DOUBLE_NOT_SYNTHESIS_EVIDENCE"}
    asset_hashes = {"test": "test"}
    calls = 0

    def render(self, text, binding, output):
        self.calls += 1
        with wave.open(str(output), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            handle.writeframes(b"\x01\x00" * 2400)
        return {"sampleRateHz": 24000, "channels": 1, "durationMs": 100, "audibleQualityAssessed": False}


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name)
        self.recipes = read_json(ROOT / "prototypes/journey_characters/sample-output.json")["recipes"]
        self.recipe = copy.deepcopy(self.recipes[0])
        self.engine = TestEngine()

    def tearDown(self):
        self.temp.cleanup()

    def synth(self, text="안녕하세요.", recipe=None, engine=None):
        return synthesize(recipe or self.recipe, text, self.state, engine=engine or self.engine)

    def test_three_traits_select_three_actual_catalog_speakers(self):
        bindings = [bind_recipe(recipe, self.state) for recipe in self.recipes[:3]]
        self.assertEqual([b["speakerId"] for b in bindings], ["F1", "M3", "F2"])
        self.assertEqual(len({b["profileId"] for b in bindings}), 3)

    def test_new_character_has_new_binding_even_with_same_trait(self):
        self.assertNotEqual(bind_recipe(self.recipes[0], self.state)["bindingId"], bind_recipe(self.recipes[3], self.state)["bindingId"])

    def test_same_character_reroute_does_not_recast(self):
        first = bind_recipe(self.recipe, self.state)
        self.recipe["voiceIntent"]["requested"]["affect"] = "quiet_delight"
        self.recipe["creativeInspiration"]["destinationTags"] = ["city"]
        self.assertEqual(first, bind_recipe(self.recipe, self.state))

    def test_restart_subprocess_preserves_binding(self):
        first = bind_recipe(self.recipe, self.state)
        result = subprocess.run([sys.executable, str(HERE / "voice_cli.py"), "--recipe", str(ROOT / "prototypes/journey_characters/sample-output.json"), "--state-dir", str(self.state), "--bind-only"], capture_output=True, text=True, check=True)
        self.assertEqual(first, json.loads(result.stdout))

    def test_unknown_intent_is_explicitly_unbound(self):
        self.recipe["voiceIntent"]["requested"]["affect"] = "UNSPECIFIED"
        with self.assertRaisesRegex(VoiceError, "UNBOUND_INTENT"):
            bind_recipe(self.recipe, self.state)
        self.assertFalse((self.state / "bindings.json").exists())

    def test_absent_intent_never_uses_default_speaker(self):
        self.recipe.pop("voiceIntent")
        with self.assertRaisesRegex(VoiceError, "UNBOUND_INTENT"):
            bind_recipe(self.recipe, self.state)

    def test_existing_binding_survives_later_unknown_intent(self):
        first = bind_recipe(self.recipe, self.state)
        self.recipe.pop("voiceIntent")
        self.assertEqual(first, bind_recipe(self.recipe, self.state))

    def test_cross_journey_character_reuse_rejected(self):
        bind_recipe(self.recipe, self.state)
        self.recipe["journeyId"] = "different-journey"
        with self.assertRaisesRegex(VoiceError, "another journey"):
            bind_recipe(self.recipe, self.state)

    def test_corrupt_ledger_refuses_to_reselect(self):
        (self.state / "bindings.json").write_text("{partial")
        with self.assertRaisesRegex(VoiceError, "Unreadable JSON"):
            bind_recipe(self.recipe, self.state)

    def test_tampered_binding_rejected(self):
        bind_recipe(self.recipe, self.state)
        path = self.state / "bindings.json"
        ledger = read_json(path)
        ledger["bindings"][self.recipe["characterId"]]["speakerId"] = "F2"
        path.write_text(json.dumps(ledger))
        with self.assertRaisesRegex(VoiceError, "digest mismatch"):
            bind_recipe(self.recipe, self.state)

    def test_exact_utf8_spaces_newlines_remain_in_metadata_and_cache_key(self):
        text = " 안녕.\n  오늘도 함께해. "
        _, result, _ = self.synth(text)
        self.assertEqual(result["text"].encode("utf-8"), text.encode("utf-8"))
        self.assertEqual(result["textSha256"], sha(text.encode("utf-8")))
        _, other, _ = self.synth(text.strip())
        self.assertNotEqual(result["cacheKey"], other["cacheKey"])

    def test_same_text_binding_hits_cache_and_preserves_actual_wav_bytes(self):
        path, first, hit = self.synth()
        data = path.read_bytes()
        self.assertFalse(hit)
        second_path, second, hit = self.synth()
        self.assertTrue(hit)
        self.assertEqual(self.engine.calls, 1)
        self.assertEqual(data, second_path.read_bytes())
        self.assertEqual(first, second)

    def test_different_text_requires_different_asset(self):
        _, first, _ = self.synth("안녕.")
        _, second, _ = self.synth("안녕!")
        self.assertNotEqual(first["cacheKey"], second["cacheKey"])
        self.assertEqual(self.engine.calls, 2)

    def test_model_runtime_change_has_separate_cache(self):
        _, first, _ = self.synth()
        second_engine = TestEngine()
        second_engine.fingerprint = "different-runtime"
        _, second, hit = self.synth(engine=second_engine)
        self.assertFalse(hit)
        self.assertNotEqual(first["cacheKey"], second["cacheKey"])

    def test_cached_audio_tamper_does_not_silently_regenerate(self):
        path, _, _ = self.synth()
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(VoiceError, "hash mismatch"):
            self.synth()
        self.assertEqual(self.engine.calls, 1)

    def test_cached_metadata_text_tamper_rejected(self):
        path, _, _ = self.synth()
        metadata = read_json(path.with_suffix(".json"))
        metadata["text"] = "다른 말."
        path.with_suffix(".json").write_text(json.dumps(metadata))
        with self.assertRaisesRegex(VoiceError, "metadata"):
            self.synth()

    def test_orphan_audio_after_interrupted_write_does_not_overwrite(self):
        path, _, _ = self.synth()
        path.with_suffix(".json").unlink()
        with self.assertRaisesRegex(VoiceError, "Orphan"):
            self.synth()
        self.assertTrue(path.exists())

    def test_malformed_or_empty_or_long_text_rejected_before_binding(self):
        for text in ("", " \n ", "가" * 101, "안녕🚗", "안녕@여행"):
            with self.subTest(text=text), self.assertRaises(VoiceError):
                self.synth(text)
        self.assertFalse((self.state / "bindings.json").exists())

    def test_path_like_character_id_rejected(self):
        with self.assertRaises(VoiceError):
            bind_recipe({"characterId": "../escape", "journeyId": "ok"}, self.state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
