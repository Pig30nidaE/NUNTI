#!/usr/bin/env python3
"""Storage/bundle tests. Fake WAV generation is not evidence of speech synthesis."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave
from worker import DEFAULT_WORKSPACE, HERE, SOURCE, bootstrap, bounded_case_text, build_bundle, digest, dynamic, file_sha, preflight, read, register_cases, tree_hashes, visual_from_recipe
from verify_bundle import verify

BOUNDARY_RESULTS = []


class TestEngine:
    def __init__(self):
        voice = read(next((SOURCE / "characters").glob("*/plan.json")))["voice"]
        self.identity, self.fingerprint = voice["engineIdentity"], voice["engineFingerprint"]
        self.model_loaded = False
        self.calls = 0

    def render(self, text, direction, seed, output):
        self.calls += 1
        with wave.open(str(output), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(24000)
            target.writeframes(b"\x02\x00" * 2400)
        return dynamic.inspect_wav(output)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="test-worker-", dir=DEFAULT_WORKSPACE)
        self.workspace = Path(self.temporary.name)
        self.state = bootstrap(self.workspace)
        register_cases(self.workspace, [HERE / "cases" / c["input"] for c in read(HERE / "cases/index.json")["cases"]])
        self.engine = TestEngine()

    def tearDown(self):
        self.temporary.cleanup()

    def test_original_copy_is_identical_and_rerun_preserves_bytes(self):
        receipt = read(self.workspace / "bootstrap-receipt.json")
        for relative, expected in receipt["sourceFileSha256"].items():
            self.assertEqual(file_sha(self.state / relative), expected)
        self.assertEqual(bootstrap(self.workspace), self.state)

    def test_visual_fields_and_registry_priority_match_source(self):
        recipe = read(SOURCE / "recipes.json")["journeys"]["synthetic-coast-001"]["recipe"]
        visual = visual_from_recipe(recipe)
        self.assertEqual(set(visual), {"characterId", "seed", "bodyFamily", "shapeId", "palette", "widthMultiplier", "heightMultiplier", "motif", "routePattern", "purpose"})
        self.assertEqual((visual["motif"], visual["routePattern"], visual["purpose"]), ("coastal_city", "coastal", "rest"))

    def test_initial_bundle_joins_actual_source_voice_and_visual(self):
        self.assertEqual(build_bundle(self.workspace, self.engine)["characters"], 4)
        self.assertEqual(verify(self.workspace, 4, 4)["actualWavClips"], 12)

    def test_new_case_append_preserves_old_entries_and_wav_bytes(self):
        build_bundle(self.workspace, self.engine)
        original = read(self.workspace / "bundle/bundle.json")["characters"]
        wav = {p.name: file_sha(p) for p in (self.workspace / "bundle/voice").glob("*.wav")}
        dynamic.generate([HERE / "cases/05-forest-visit.json"], self.state, self.engine)
        self.assertEqual(build_bundle(self.workspace, self.engine)["characters"], 5)
        current = read(self.workspace / "bundle/bundle.json")["characters"]
        self.assertTrue(all(entry in current for entry in original))
        self.assertTrue(all(file_sha(self.workspace / "bundle/voice" / name) == value for name, value in wav.items()))

    def test_visual_manifest_tamper_is_rejected(self):
        build_bundle(self.workspace, self.engine)
        path = self.workspace / "bundle/bundle.json"
        value = read(path)
        value["characters"][0]["visual"]["purpose"] = "errand"
        value["characters"][0]["visualSha256"] = digest(value["characters"][0]["visual"])
        dynamic.atomic_json(path, value)
        with self.assertRaisesRegex(ValueError, "BUNDLE_MANIFEST_CHANGED"):
            build_bundle(self.workspace, self.engine)

    def test_exported_wav_corruption_is_not_replaced(self):
        build_bundle(self.workspace, self.engine)
        wav = next((self.workspace / "bundle/voice").glob("*.wav"))
        wav.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "EXPORTED_ASSET_CHANGED"):
            build_bundle(self.workspace, self.engine)
        self.assertEqual(wav.read_bytes(), b"corrupted")

    def test_source_identity_corruption_is_not_overwritten(self):
        path = next((self.state / "characters").glob("*/character.json"))
        value = read(path)
        value["displayName"] = "changed"
        dynamic.atomic_json(path, value)
        with self.assertRaisesRegex(ValueError, "COPIED_ORIGINAL_CHANGED"):
            bootstrap(self.workspace)

    def test_new_committed_audio_corruption_refuses_resynthesis(self):
        request = HERE / "cases/05-forest-visit.json"
        result = dynamic.generate([request], self.state, self.engine)
        character = result["characters"][0]["characterId"]
        artifact = read(self.state / "characters" / character / "character.json")
        wav = self.state / "characters" / character / artifact["clips"]["common"]["audioPath"]
        changed = bytearray(wav.read_bytes())
        changed[-1] ^= 1
        wav.write_bytes(changed)
        calls = self.engine.calls
        with self.assertRaisesRegex(ValueError, "CACHED_AUDIO_CHANGED"):
            dynamic.generate([request], self.state, self.engine)
        self.assertEqual(self.engine.calls, calls)
        self.assertEqual(wav.read_bytes(), bytes(changed))

    def test_all_eight_bodies_come_from_original_history_plus_four_cpu_recipes(self):
        registry = read(dynamic.recipes.REGISTRY_PATH)
        ledger = read(self.state / "recipes.json")
        for name in ("05-forest-visit", "06-lake-errand", "07-city-commute", "08-unplanned"):
            request = dynamic.recipes.normalize_request(read(HERE / "cases" / (name + ".json")), registry)
            _, changed = dynamic.recipes.generate(request, ledger, registry)
            self.assertTrue(changed)
        families = {r["recipe"]["design"]["bodyFamily"] for r in ledger["journeys"].values()}
        self.assertEqual(families, {b["family"] for b in registry["bodies"]})

    def request_file(self, name):
        request = read(HERE / "cases/05-forest-visit.json")
        request["journeyId"] = "boundary-journey-" + name
        request["requestId"] = "boundary-request-" + name
        path = self.workspace / (name + ".json")
        dynamic.atomic_json(path, request)
        return path

    def fill_to_31_cpu_recipes(self):
        ledger = read(self.state / "recipes.json")
        registry = read(dynamic.recipes.REGISTRY_PATH)
        for i in range(27):
            request = read(self.request_file("existing-" + str(i)))
            normalized = dynamic.recipes.normalize_request(request, registry)
            dynamic.recipes.generate(normalized, ledger, registry)
        self.assertEqual(len(ledger["journeys"]), 31)
        dynamic.recipes.save_atomic(self.state / "recipes.json", ledger)

    def run_rejected_cli(self, arguments, error):
        # The system Python intentionally has no pinned inference environment.
        # An expected boundary error demonstrates rejection before engine setup.
        state_before = tree_hashes(self.state)
        index_before = (self.workspace / "cases.json").read_bytes()
        result = subprocess.run([sys.executable, str(HERE / "worker.py"), "--workspace", str(self.workspace), "generate", *arguments], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(error, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(tree_hashes(self.state), state_before)
        self.assertEqual((self.workspace / "cases.json").read_bytes(), index_before)
        BOUNDARY_RESULTS.append({"expectedError": error, "exitCode": result.returncode,
                                 "rejectedBeforeEngineSetup": True, "stateFilesByteUnchanged": len(state_before),
                                 "caseIndexByteUnchanged": True})

    def test_case_text_exact_android_utf16_limits_are_accepted(self):
        for name, value in (("caseId", "a" * 120), ("label", "가" * 60), ("label", "😀" * 30), ("summary", "가" * 240), ("summary", "😀" * 120)):
            self.assertEqual(bounded_case_text(value, name), value)
        request = self.request_file("accepted-text")
        preflight(self.workspace, [request], "😀" * 30, "가" * 240)
        register_cases(self.workspace, [request], "😀" * 30, "가" * 240)
        stored = read(self.workspace / "cases.json")["cases"][read(request)["journeyId"]]
        self.assertEqual(stored["label"], "😀" * 30)
        self.assertEqual(stored["summary"], "가" * 240)

    def test_case_text_overflow_and_blank_are_rejected(self):
        for name, value in (("caseId", "a" * 121), ("label", "가" * 61), ("label", "😀" * 31), ("summary", "가" * 241), ("summary", "😀" * 121), ("label", " \t\n"), ("summary", "")):
            with self.subTest(name=name, length=len(value)), self.assertRaisesRegex(ValueError, "INVALID_CASE_TEXT"):
                bounded_case_text(value, name)

    def test_long_cli_text_is_rejected_before_model_or_identity_writes(self):
        request = self.request_file("long-text")
        for option, value in (("--label", "가" * 61), ("--label", "😀" * 31), ("--summary", "가" * 241), ("--label", "   ")):
            with self.subTest(option=option, length=len(value)):
                self.run_rejected_cli(["--input", str(request), option, value], "INVALID_CASE_TEXT")

    def test_32nd_unique_character_is_accepted_and_33rd_batch_is_rejected(self):
        self.fill_to_31_cpu_recipes()
        first, second = self.request_file("new-32"), self.request_file("new-33")
        preflight(self.workspace, [first])
        self.run_rejected_cli(["--input", str(first), str(second)], "INVALID_CASE_COUNT")
        ledger = read(self.state / "recipes.json")
        registry = read(dynamic.recipes.REGISTRY_PATH)
        dynamic.recipes.generate(dynamic.recipes.normalize_request(read(first), registry), ledger, registry)
        dynamic.recipes.save_atomic(self.state / "recipes.json", ledger)
        self.assertEqual(len(ledger["journeys"]), 32)
        self.run_rejected_cli(["--input", str(second)], "INVALID_CASE_COUNT")

    def test_same_journey_retry_or_reroute_counts_once_at_character_limit(self):
        self.fill_to_31_cpu_recipes()
        first = self.request_file("new-32")
        reroute = read(first)
        reroute["requestId"] += "-reroute"
        reroute["purpose"] = "commute"
        path = self.workspace / "reroute.json"
        dynamic.atomic_json(path, reroute)
        preflight(self.workspace, [first, path])

    def test_preexisting_long_case_id_is_rejected_before_model_setup(self):
        request = self.request_file("case-id")
        index = read(self.workspace / "cases.json")
        next(iter(index["cases"].values()))["caseId"] = "x" * 121
        dynamic.atomic_json(self.workspace / "cases.json", index)
        self.run_rejected_cli(["--input", str(request)], "INVALID_CASE_TEXT:caseId")


if __name__ == "__main__":
    program = unittest.main(verbosity=2, exit=False)
    result = {"status": "PASS" if program.result.wasSuccessful() else "FAIL", "tests": program.result.testsRun,
              "utf16TextLimits": {"caseId": 120, "label": 60, "summary": 240}, "maxUniqueCharacters": 32,
              "actualBoundaryRejectionProcesses": len(BOUNDARY_RESULTS), "gpuOrModelInferenceUsed": False,
              "rejectionEvidence": BOUNDARY_RESULTS}
    (HERE / "input-boundary-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
