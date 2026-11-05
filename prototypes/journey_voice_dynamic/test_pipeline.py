"""Exercise persistence and recovery without loading a model or requiring MLX."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from contextlib import redirect_stdout, redirect_stderr
import io

import voice_cli as pipeline

EXAMPLES = pipeline.ROOT / "prototypes/journey_characters/examples"


class FakeEngine:
    identity = {"providerId": "test-local", "speaker": "Sohee", "generation": {"maxTokens": 375}}
    fingerprint = "f" * 64

    def __init__(self, fail_at=None):
        self.calls = 0
        self.fail_at = fail_at
        self.model_loaded = False

    def render(self, text, direction, seed, output):
        self.calls += 1
        self.model_loaded = True
        if self.calls == self.fail_at:
            raise RuntimeError("INTERRUPTED_INFERENCE")
        with wave.open(str(output), "wb") as audio:
            audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            audio.writeframes(struct.pack("<h", 100 + seed % 1000) * 2400)
        return pipeline.inspect_wav(output)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"

    def tearDown(self):
        self.temporary.cleanup()

    def run_generation(self, engine=None, paths=None, plan_only=False):
        return pipeline.generate(paths or [EXAMPLES / "coastal_rest.json"], self.state, engine or FakeEngine(), plan_only)

    def request(self, filename, **changes):
        data = json.loads((EXAMPLES / "coastal_rest.json").read_text())
        data.update(changes)
        path = self.root / filename
        path.write_text(json.dumps(data))
        return path

    def test_retry_and_reroute_preserve_committed_voice_and_audio(self):
        first = self.run_generation()["characters"][0]
        path = Path(first["planPath"])
        original_plan = path.read_bytes()
        changed = self.request("reroute.json", requestId="reroute-1", purpose="camping",
                               destination={"semanticTags": ["mountain"]})
        restarted = FakeEngine()
        retried = self.run_generation(restarted, [changed])["characters"][0]
        self.assertEqual((restarted.calls, retried["cacheHits"]), (0, 3))
        self.assertEqual(first["clips"], retried["clips"])
        self.assertEqual(original_plan, path.read_bytes())

    def test_new_journey_same_route_gets_new_character_and_direction(self):
        results = self.run_generation(paths=[EXAMPLES / "coastal_rest.json", EXAMPLES / "coastal_rest_next.json"])["characters"]
        plans = [pipeline.read_json(Path(result["planPath"])) for result in results]
        self.assertNotEqual(plans[0]["characterId"], plans[1]["characterId"])
        self.assertNotEqual(plans[0]["voice"]["seed"], plans[1]["voice"]["seed"])
        self.assertNotEqual(plans[0]["voice"]["direction"], plans[1]["voice"]["direction"])

    def test_request_id_collision_preserves_all_existing_state(self):
        self.run_generation()
        original = (self.state / "recipes.json").read_bytes()
        conflict = self.request("collision.json", journeyId="another-journey")
        with self.assertRaisesRegex(ValueError, "requestId already"):
            self.run_generation(paths=[conflict])
        self.assertEqual(original, (self.state / "recipes.json").read_bytes())

    def test_new_text_keeps_binding_and_reuses_its_cache(self):
        result = self.run_generation()["characters"][0]
        plan_bytes = Path(result["planPath"]).read_bytes()
        first = pipeline.speak(result["characterId"], "다음 여행도 함께 가자.", self.state, FakeEngine())
        second_engine = FakeEngine()
        second = pipeline.speak(result["characterId"], "다음 여행도 함께 가자.", self.state, second_engine)
        self.assertEqual(first["metadata"]["bindingId"], result["bindingId"])
        self.assertEqual(second_engine.calls, 0)
        self.assertTrue(second["cacheHit"])
        self.assertEqual(plan_bytes, Path(result["planPath"]).read_bytes())

    def test_partial_generation_resumes_completed_clips(self):
        with self.assertRaisesRegex(RuntimeError, "INTERRUPTED"):
            self.run_generation(FakeEngine(fail_at=2))
        restarted = FakeEngine()
        result = self.run_generation(restarted)["characters"][0]
        self.assertEqual((restarted.calls, result["cacheHits"]), (2, 1))
        self.assertTrue(Path(result["artifactPath"]).is_file())

    def test_engine_change_refuses_before_new_inference(self):
        self.run_generation()
        changed = FakeEngine()
        changed.fingerprint = "e" * 64
        with self.assertRaisesRegex(ValueError, "BOUND_ENGINE_UNAVAILABLE"):
            self.run_generation(changed)
        self.assertEqual(changed.calls, 0)

    def test_changed_clip_metadata_is_not_silently_regenerated(self):
        result = self.run_generation()["characters"][0]
        directory = Path(result["planPath"]).parent
        clip = next(iter(result["clips"].values()))
        metadata = directory / "clips" / clip["cacheKey"] / "metadata.json"
        record = pipeline.read_json(metadata)
        record["direction"] = "different direction"
        metadata.write_text(json.dumps(record))
        engine = FakeEngine()
        with self.assertRaisesRegex(ValueError, "CACHED_PROVENANCE_CHANGED"):
            self.run_generation(engine)
        self.assertEqual(engine.calls, 0)

    def test_missing_plan_after_empty_directory_creation_can_resume(self):
        self.run_generation(plan_only=True)
        plan = next((self.state / "characters").glob("*/plan.json"))
        plan.unlink()
        result = self.run_generation(plan_only=True)
        self.assertTrue(Path(result["characters"][0]["planPath"]).is_file())

    def test_committed_manifest_missing_is_rebuilt_without_inference(self):
        result = self.run_generation()["characters"][0]
        artifact = Path(result["artifactPath"])
        original = artifact.read_bytes()
        artifact.unlink()
        engine = FakeEngine()
        self.run_generation(engine)
        self.assertEqual(engine.calls, 0)
        self.assertEqual(original, artifact.read_bytes())

    def test_committed_clip_directory_missing_is_not_regenerated(self):
        import shutil
        result = self.run_generation()["characters"][0]
        directory = Path(result["planPath"]).parent
        clip = next(iter(result["clips"].values()))
        shutil.rmtree(directory / "clips" / clip["cacheKey"])
        engine = FakeEngine()
        with self.assertRaisesRegex(ValueError, "COMMITTED_AUDIO_MISSING"):
            self.run_generation(engine)
        self.assertEqual(engine.calls, 0)

    def test_new_text_missing_after_commit_is_not_regenerated(self):
        import shutil
        result = self.run_generation()["characters"][0]
        clip = pipeline.speak(result["characterId"], "다음 여행도 함께 가자.", self.state, FakeEngine())
        shutil.rmtree(Path(clip["audioPath"]).parent)
        engine = FakeEngine()
        with self.assertRaisesRegex(ValueError, "COMMITTED_AUDIO_MISSING"):
            pipeline.speak(result["characterId"], "다음 여행도 함께 가자.", self.state, engine)
        self.assertEqual(engine.calls, 0)

    def test_plan_from_another_character_cannot_be_used(self):
        results = self.run_generation(paths=[EXAMPLES / "coastal_rest.json", EXAMPLES / "mountain_camping.json"])["characters"]
        Path(results[0]["planPath"]).write_bytes(Path(results[1]["planPath"]).read_bytes())
        engine = FakeEngine()
        with self.assertRaisesRegex(ValueError, "CHARACTER_PLAN_WRONG_DIRECTORY"):
            pipeline.speak(results[0]["characterId"], "새 대사야.", self.state, engine)
        self.assertEqual(engine.calls, 0)

    def child(self, path, mode="normal"):
        code = '''import json, os, sys
from pathlib import Path
from test_pipeline import FakeEngine
import voice_cli
class ChildEngine(FakeEngine):
    def render(self, *args):
        if sys.argv[3] == "crash" and self.calls == 1:
            os._exit(86)
        return super().render(*args)
engine = ChildEngine()
result = voice_cli.generate([Path(sys.argv[1])], Path(sys.argv[2]), engine)
print(json.dumps({"calls": engine.calls, "result": result}))
'''
        return subprocess.Popen([sys.executable, "-c", code, str(path), str(self.state), mode],
                                cwd=Path(__file__).parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def child_result(self, process):
        stdout, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, stderr.decode())
        return json.loads(stdout)

    def test_process_exit_releases_lock_and_preserves_published_clip(self):
        first = self.child(EXAMPLES / "coastal_rest.json", "crash")
        first.communicate(timeout=15)
        self.assertEqual(first.returncode, 86)
        published = next((self.state / "characters").glob("*/clips/*/metadata.json"))
        before = published.read_bytes()
        second = self.child_result(self.child(EXAMPLES / "coastal_rest.json"))
        self.assertEqual(second["calls"], 2)
        self.assertEqual(before, published.read_bytes())

    def test_two_processes_same_journey_commit_one_voice(self):
        processes = [self.child(EXAMPLES / "coastal_rest.json") for _ in range(2)]
        results = [self.child_result(process) for process in processes]
        self.assertEqual(sum(result["calls"] for result in results), 3)
        self.assertEqual(results[0]["result"]["characters"][0]["bindingId"], results[1]["result"]["characters"][0]["bindingId"])

    def test_two_processes_different_journeys_preserve_both_histories(self):
        processes = [self.child(EXAMPLES / name) for name in ("coastal_rest.json", "mountain_camping.json")]
        results = [self.child_result(process) for process in processes]
        self.assertEqual(sum(result["calls"] for result in results), 6)
        ledger = pipeline.read_json(self.state / "recipes.json")
        self.assertEqual(len(ledger["journeys"]), 2)
        families = {entry["recipe"]["design"]["bodyFamily"] for entry in ledger["journeys"].values()}
        self.assertEqual(len(families), 2)

    def test_model_diagnostics_do_not_pollute_stdout(self):
        class NoisyEngine(FakeEngine):
            def render(self, *args):
                print("model diagnostic")
                return super().render(*args)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.run_generation(NoisyEngine())
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("model diagnostic", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
