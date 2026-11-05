#!/usr/bin/env python3
"""Kill real child processes at journal/publication boundaries, then retry.

Only existing files or clearly marked test-double WAVs are used. No GPU/model
is imported or run. Production eight-character assets are never mutated.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from worker import DEFAULT_WORKSPACE, HERE, bootstrap, build_bundle, dynamic, file_sha, read, register_cases
from test_worker import TestEngine
from verify_bundle import verify

EVENTS = []
CHILD = '''import json,sys
from pathlib import Path
from worker import bootstrap,build_bundle,lane,register_cases,HERE,read
from test_worker import TestEngine
workspace=Path(sys.argv[1])
try:
    with lane(workspace):
        bootstrap(workspace)
        if sys.argv[2] == "bundle":
            register_cases(workspace,[HERE/"cases"/c["input"] for c in read(HERE/"cases/index.json")["cases"]])
            print(json.dumps(build_bundle(workspace,TestEngine())))
except (ValueError,KeyError,OSError,TypeError,RuntimeError) as exc:
    print(str(exc),file=sys.stderr)
    sys.exit(2)
'''


def child(workspace, action, point=None):
    env = os.environ.copy()
    env.pop("NUNTI_MVP_CRASH_AT", None)
    if point:
        env["NUNTI_MVP_CRASH_AT"] = point
    result = subprocess.run([sys.executable, "-c", CHILD, str(workspace), action], cwd=HERE, env=env, capture_output=True, text=True, timeout=30)
    EVENTS.append({"action": action, "crashPoint": point, "exitCode": result.returncode,
                   "rejection": result.stderr.strip() if result.returncode == 2 else None})
    return result


class CrashRecoveryTests(unittest.TestCase):
    def setUp(self):
        DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="test-crash-", dir=DEFAULT_WORKSPACE)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def prepare_bundle(self, workspace, append=False):
        state = bootstrap(workspace)
        register_cases(workspace, [HERE / "cases" / c["input"] for c in read(HERE / "cases/index.json")["cases"]])
        build_bundle(workspace, TestEngine())
        if append:
            dynamic.generate([HERE / "cases/05-forest-visit.json"], state, TestEngine())
        return state

    def test_bootstrap_exit_after_each_publication_step_recovers_exact_bytes(self):
        for point in ("bootstrap-after-journal", "bootstrap-after-state", "bootstrap-after-receipt"):
            with self.subTest(point=point):
                workspace = self.root / point
                self.assertEqual(child(workspace, "bootstrap", point).returncode, 86)
                self.assertTrue((workspace / "bootstrap-pending.json").exists())
                retried = child(workspace, "bootstrap")
                self.assertEqual(retried.returncode, 0, retried.stderr)
                self.assertFalse((workspace / "bootstrap-pending.json").exists())
                self.assertEqual(bootstrap(workspace), workspace / "state")

    def test_initial_bundle_exit_after_each_publication_step_recovers(self):
        for point in ("bundle-after-journal", "bundle-after-manifest", "bundle-after-receipt"):
            with self.subTest(point=point):
                workspace = self.root / point
                self.assertEqual(child(workspace, "bundle", point).returncode, 86)
                retried = child(workspace, "bundle")
                self.assertEqual(retried.returncode, 0, retried.stderr)
                self.assertFalse((workspace / "bundle-pending.json").exists())
                self.assertEqual(verify(workspace, 4, 4)["actualWavClips"], 12)

    def test_append_bundle_exit_after_each_publication_step_preserves_old_identity(self):
        for point in ("bundle-after-journal", "bundle-after-manifest", "bundle-after-receipt"):
            with self.subTest(point=point):
                workspace = self.root / point
                self.prepare_bundle(workspace, append=True)
                previous = read(workspace / "bundle/bundle.json")["characters"]
                hashes = {p.name: file_sha(p) for p in (workspace / "bundle/voice").glob("*.wav")}
                self.assertEqual(child(workspace, "bundle", point).returncode, 86)
                retried = child(workspace, "bundle")
                self.assertEqual(retried.returncode, 0, retried.stderr)
                self.assertEqual(verify(workspace, 5, 5)["actualWavClips"], 15)
                current = read(workspace / "bundle/bundle.json")["characters"]
                self.assertTrue(all(c in current for c in previous))
                self.assertTrue(all(file_sha(workspace / "bundle/voice" / name) == value for name, value in hashes.items()))

    def test_pending_bootstrap_changed_wav_is_not_repaired(self):
        workspace = self.root / "changed-state"
        self.assertEqual(child(workspace, "bootstrap", "bootstrap-after-state").returncode, 86)
        wav = next((workspace / "state/characters").rglob("*.wav"))
        changed = bytearray(wav.read_bytes())
        changed[-1] ^= 1
        wav.write_bytes(changed)
        retried = child(workspace, "bootstrap")
        self.assertEqual(retried.returncode, 2)
        self.assertIn("PENDING_STATE_CHANGED", retried.stderr)
        self.assertFalse((workspace / "bootstrap-receipt.json").exists())
        self.assertEqual(wav.read_bytes(), bytes(changed))

    def test_committed_state_missing_without_pending_is_not_copied_again(self):
        workspace = self.root / "missing-state"
        state = bootstrap(workspace)
        shutil.rmtree(state)
        retried = child(workspace, "bootstrap")
        self.assertEqual(retried.returncode, 2)
        self.assertIn("STATE_MISSING_NO_AUTOMATIC_REPLACEMENT", retried.stderr)
        self.assertFalse(state.exists())

    def test_committed_bootstrap_receipt_missing_without_pending_is_not_recreated(self):
        workspace = self.root / "missing-bootstrap-receipt"
        bootstrap(workspace)
        (workspace / "bootstrap-receipt.json").unlink()
        retried = child(workspace, "bootstrap")
        self.assertEqual(retried.returncode, 2)
        self.assertIn("STATE_WITHOUT_ORIGINAL_RECEIPT", retried.stderr)

    def test_pending_bundle_tamper_is_not_repaired(self):
        workspace = self.root / "changed-bundle"
        self.prepare_bundle(workspace, append=True)
        self.assertEqual(child(workspace, "bundle", "bundle-after-manifest").returncode, 86)
        path = workspace / "bundle/bundle.json"
        changed = path.read_bytes() + b" "
        path.write_bytes(changed)
        retried = child(workspace, "bundle")
        self.assertEqual(retried.returncode, 2)
        self.assertIn("PENDING_BUNDLE_FILES_MISSING_OR_CHANGED", retried.stderr)
        self.assertEqual(path.read_bytes(), changed)

    def test_pending_append_missing_old_file_is_not_treated_as_initial_publication(self):
        for missing in ("bundle/bundle.json", "bundle-receipt.json"):
            with self.subTest(missing=missing):
                workspace = self.root / missing.replace("/", "-")
                self.prepare_bundle(workspace, append=True)
                self.assertEqual(child(workspace, "bundle", "bundle-after-journal").returncode, 86)
                (workspace / missing).unlink()
                retried = child(workspace, "bundle")
                self.assertEqual(retried.returncode, 2)
                self.assertIn("PENDING_BUNDLE_FILES_MISSING_OR_CHANGED", retried.stderr)
                self.assertFalse((workspace / missing).exists())

    def test_committed_bundle_pair_missing_without_pending_is_not_recreated(self):
        for missing in ("bundle/bundle.json", "bundle-receipt.json"):
            with self.subTest(missing=missing):
                workspace = self.root / missing.replace("/", "-")
                self.prepare_bundle(workspace)
                (workspace / missing).unlink()
                retried = child(workspace, "bundle")
                self.assertEqual(retried.returncode, 2)
                self.assertFalse((workspace / missing).exists())


if __name__ == "__main__":
    program = unittest.main(verbosity=2, exit=False)
    evidence = {"status": "PASS" if program.result.wasSuccessful() else "FAIL", "tests": program.result.testsRun,
                "actualChildProcesses": len(EVENTS), "processExitInjectionCode": 86,
                "gpuOrModelInferenceUsed": False, "originalProductionAssetsMutated": False,
                "processEvents": EVENTS}
    (HERE / "crash-recovery-verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
