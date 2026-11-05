"""Boundary, state and crash tests. Fake synthesis is never production fallback."""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
import wave

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generator import REVISION, PROVIDER, canonical, digest, geometry, inside, make_plan, normalize
from worker import Conflict, NotFound, Worker, file_sha, inspect_wav, make_handler, strict_json
from http.server import ThreadingHTTPServer


class FakeSynth:
    """Test-only deterministic PCM generator; never imported by serve()."""
    fingerprint = "a" * 64
    identity = {"providerId": PROVIDER, "revision": REVISION}
    model_loaded = False
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
    def render(self, text, direction, seed, output):
        if self.fail:
            raise RuntimeError("injected model failure")
        self.calls.append((text, direction, seed))
        frequency = 150 + int(hashlib.sha256(text.encode()).hexdigest()[:4], 16) % 300
        frames = b"".join(struct.pack("<h", round(1000 * math.sin(2 * math.pi * frequency * i / 24000))) for i in range(2400))
        with wave.open(str(output), "wb") as wav:
            wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            wav.writeframes(frames)
        return {**inspect_wav(output), "termination": {"tokenLimitReached": False}}


def request(request_id="a96e5ac0-ec43-4cb4-9671-403a3718aa7b"):
    return {"requestId": request_id, "destination": {"name": "노을 바다", "traits": "따뜻한 노을과 바다"}, "purpose": "휴식", "route": {"points": [[.1, .8], [.3, .3], [.7, .5], [.9, .1]]}}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.synth = FakeSynth()
        self.worker = Worker(Path(self.tmp.name) / "state", self.synth, background=False)
    def tearDown(self):
        self.worker.close()
        self.tmp.cleanup()
    def ready(self):
        self.worker.submit(request())
        return self.worker.process_one(request()["requestId"])
    def test_pending_visual_then_three_exact_clips(self):
        pending = self.worker.submit(request())
        self.assertEqual("GENERATING", pending["state"])
        self.assertNotIn("voiceManifest", pending["artifact"])
        self.assertEqual("노을 바다", pending["artifact"]["destinationName"])
        ready = self.worker.process_one(request()["requestId"])
        self.assertEqual("READY", ready["state"])
        self.assertEqual(3, len(self.synth.calls))
        self.assertEqual(pending["artifact"], {k: v for k, v in ready["artifact"].items() if k != "voiceManifest"})
        for clip in ready["artifact"]["voiceManifest"]["clips"]:
            self.assertEqual(clip["audioSha256"], hashlib.sha256(self.worker.audio(request()["requestId"], clip["audioPath"])).hexdigest())
    def test_retry_before_and_after_generation_no_new_audio(self):
        a = self.worker.submit(request())
        self.assertEqual(a, self.worker.submit(request()))
        ready = self.worker.process_one(request()["requestId"])
        self.assertEqual(ready, self.worker.submit(request()))
        self.assertEqual(ready, self.worker.process_one(request()["requestId"]))
        self.assertEqual(3, len(self.synth.calls))
    def test_conflict_does_not_replace(self):
        before = self.worker.submit(request())
        changed = request()
        changed["route"]["points"][0][0] = .11
        with self.assertRaises(Conflict):
            self.worker.submit(changed)
        self.assertEqual(before, self.worker.get(request()["requestId"]))
    def test_strict_shape_and_utf16_limits(self):
        mutations = [lambda r: r.update(extra=0), lambda r: r["destination"].update(name=""), lambda r: r["destination"].update(name="가" * 61),
                     lambda r: r["destination"].update(traits="가" * 241), lambda r: r.update(purpose="가" * 121), lambda r: r["route"].update(points=[]),
                     lambda r: r["route"].update(points=[[0, 0], [0, 0]]), lambda r: r["route"].update(points=[[0, 0], [1, float("nan")]]),
                     lambda r: r["route"].update(points=[[False, 0], [1, 1]]), lambda r: r["route"].update(points=[[0, 0], [1, 1.01]]),
                     lambda r: r.update(requestId="../path"), lambda r: r["destination"].update(name="hello\nworld"), lambda r: r["destination"].update(name="\ud800")]
        for mutation in mutations:
            value = request()
            mutation(value)
            with self.assertRaises((ValueError, UnicodeError)):
                self.worker.submit(value)
        self.assertEqual([], list(self.worker.jobs.iterdir()))
        self.assertEqual([], self.synth.calls)
    def test_maximum_destination_not_truncated(self):
        value = request()
        value["destination"]["name"] = "가" * 60
        plan = make_plan(value, self.synth.fingerprint, self.synth.identity)
        self.assertIn(value["destination"]["name"], plan["texts"]["greeting"])
        self.assertIn(value["destination"]["name"], plan["texts"]["arrival"])
        self.assertTrue(all(len(t.encode("utf-16-le")) // 2 <= 100 for t in plan["texts"].values()))
    def test_restarts_reuse_every_committed_byte(self):
        ready = self.ready()
        hashes = {str(p.relative_to(self.worker.jobs)): file_sha(p) for p in self.worker.jobs.rglob("*") if p.is_file()}
        self.worker.close()
        self.worker = Worker(Path(self.tmp.name) / "state", self.synth, background=False)
        self.assertEqual(ready, self.worker.get(request()["requestId"]))
        self.worker.process_one(request()["requestId"])
        self.assertEqual(3, len(self.synth.calls))
        self.assertEqual(hashes, {str(p.relative_to(self.worker.jobs)): file_sha(p) for p in self.worker.jobs.rglob("*") if p.is_file()})
    def test_changed_audio_fails_closed_get_and_restart(self):
        ready = self.ready()
        path = self.worker.jobs / request()["requestId"] / "clips/greeting/audio.wav"
        data = bytearray(path.read_bytes())
        data[-2] ^= 1
        path.write_bytes(data)
        self.assertEqual("FAILED", self.worker.get(request()["requestId"])["state"])
        with self.assertRaises(NotFound):
            self.worker.audio(request()["requestId"], ready["artifact"]["voiceManifest"]["clips"][0]["audioPath"])
        self.worker.close()
        self.worker = Worker(Path(self.tmp.name) / "state", self.synth, background=False)
        self.assertEqual("FAILED", self.worker.get(request()["requestId"])["state"])
        self.assertEqual(3, len(self.synth.calls))
    def test_missing_audio_fails_closed(self):
        self.ready()
        (self.worker.jobs / request()["requestId"] / "clips/arrival/audio.wav").unlink()
        self.assertEqual("FAILED", self.worker.get(request()["requestId"])["state"])
    def test_failure_is_persistent_no_fallback(self):
        self.synth.fail = True
        self.worker.submit(request())
        failed = self.worker.process_one(request()["requestId"])
        self.assertEqual("FAILED", failed["state"])
        self.assertNotIn("voiceManifest", failed["artifact"])
        self.synth.fail = False
        self.assertEqual(failed, self.worker.submit(request()))
        self.worker.close()
        self.worker = Worker(Path(self.tmp.name) / "state", self.synth, background=False)
        self.assertEqual(failed, self.worker.get(request()["requestId"]))
        self.assertEqual([], self.synth.calls)
    def test_audio_path_is_only_exact_manifest_file(self):
        self.ready()
        for filename in ("../plan.json", "audio.wav", "greeting.wav", "anything.wav"):
            with self.assertRaises(NotFound):
                self.worker.audio(request()["requestId"], filename)
    def test_route_independently_changes_silhouette(self):
        nonce = request()["requestId"]
        a, _ = geometry([[.1, .5], [.9, .5]], nonce)
        b, _ = geometry([[.5, .1], [.5, .9]], nonce)
        c, _ = geometry([[.1, .8], [.3, .1], [.7, .8], [.9, .1]], nonce)
        self.assertEqual(3, len({digest(v["outline"]) for v in (a, b, c)}))
        for visual in (a, b, c):
            self.assertEqual(72, len(visual["outline"]))
            self.assertEqual(72, len(visual["route"]))
            scale = visual["face"]["scale"]
            self.assertTrue(all(inside([.5 + .22 * scale * math.cos(i * math.pi / 90), .43 + .145 * scale * math.sin(i * math.pi / 90)], visual["outline"]) for i in range(180)))
    def test_same_route_new_uuid_new_identity_and_geometry(self):
        a = make_plan(request(), self.synth.fingerprint, self.synth.identity)
        b = make_plan(request(str(uuid.uuid4())), self.synth.fingerprint, self.synth.identity)
        self.assertNotEqual(a["artifact"]["characterId"], b["artifact"]["characterId"])
        self.assertNotEqual(a["artifact"]["visual"]["outline"], b["artifact"]["visual"]["outline"])
        self.assertNotEqual(a["artifact"]["voice"]["bindingId"], b["artifact"]["voice"]["bindingId"])
    def test_multiple_worker_process_lane_refused(self):
        with self.assertRaisesRegex(ValueError, "WORKSPACE_ALREADY_OWNED"):
            Worker(Path(self.tmp.name) / "state", self.synth, background=False)
    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                strict_json(data)


class CrashTests(unittest.TestCase):
    def test_all_publication_windows_resume_or_reject_without_rebinding(self):
        points = ["before-plan-publication", "after-plan-publication", "before-result-publication", "after-result-publication"]
        points += [phase + kind for kind in ("greeting", "arrival", "common") for phase in ("before-clip-publication-", "after-clip-publication-")]
        script = "from test_worker import *; w=Worker(Path(sys.argv[1]),FakeSynth(),background=False); w.submit(request()); w.process_one(request()['requestId'])"
        outcomes = []
        with tempfile.TemporaryDirectory() as temporary:
            for index, point in enumerate(points):
                state = Path(temporary) / str(index)
                env = {**os.environ, "NUNTI_ROUTE_CRASH_AT": point, "PYTHONPATH": str(Path(__file__).resolve().parent)}
                child = subprocess.run([sys.executable, "-c", script, str(state)], env=env, capture_output=True, text=True)
                self.assertEqual(86, child.returncode, child.stderr)
                before = {str(p.relative_to(state)): file_sha(p) for p in state.rglob("*") if p.is_file() and "/.clip-" not in str(p) and "/.job-" not in str(p) and p.name != ".worker.lock"}
                synth = FakeSynth()
                worker = Worker(state, synth, background=False)
                worker.submit(request())
                result = worker.process_one(request()["requestId"])
                self.assertEqual("READY", result["state"], (point, result))
                for relative, sha in before.items():
                    self.assertEqual(sha, file_sha(state / relative), (point, relative))
                self.assertEqual(3, len(result["artifact"]["voiceManifest"]["clips"]))
                outcomes.append({"point": point, "childExit": child.returncode, "restartNewFakeRenders": len(synth.calls), "committedBytesPreserved": True})
                worker.close()
        print(canonical({"crashWindows": outcomes}))


if __name__ == "__main__":
    unittest.main()
