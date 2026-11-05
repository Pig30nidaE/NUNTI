"""The real-AI batch resumes only matching, intact actual artifacts."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "avatar_v6_ai_matrix", ROOT / "scripts/verify_avatar_v6_ai_matrix.py"
)
assert SPEC and SPEC.loader
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


class AvatarV6AiMatrixTest(unittest.TestCase):
    def test_selection_preserves_failed_attempt_and_uses_latest_verified_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = []
            for index, passed in enumerate([True, False, True]):
                source = root / f"attempt-{index}"
                folder = source / "cases/one"
                folder.mkdir(parents=True)
                raw = f"actual-model-original-{index}".encode()
                rgba = f"actual-model-rgba-{index}".encode()
                (folder / "original-rgb.png").write_bytes(raw)
                (folder / "avatar.png").write_bytes(rgba)
                matrix.save_json(folder / "input.json", {"same": "journey"})
                matrix.save_json(folder / "design.json", {"same": "character"})
                job = {"id": "one", "folder": str(folder), "jobFingerprint": str(index)}
                record = {"id": "one", "status": "READY", "jobFingerprint": str(index),
                          "rawSha256": matrix.sha(raw), "rgbaSha256": matrix.sha(rgba)}
                matrix.save_json(folder / "result.json", record)
                matrix.save_json(source / "jobs.json", {"jobs": [job]})
                matrix.save_json(source / "visual-review.json", {"cases": [{
                    "id": "one", "rgbaSha256": record["rgbaSha256"], "overallPass": passed,
                }]})
                sources.append(source)
            output = root / "selected"
            matrix.assemble_selection(output, sources)
            self.assertEqual((output / "cases/one/avatar.png").read_bytes(), b"actual-model-rgba-2")
            preserved = (sources[1] / "cases/one/avatar.png").read_bytes()
            self.assertEqual(preserved, b"actual-model-rgba-1")
            selection = json.loads((output / "selection.json").read_text())
            self.assertEqual(selection["actualModelAttemptsInTheseMatrixRuns"], 3)
            self.assertFalse(selection["decisions"][0]["attempts"][1]["coreReviewPass"])
            with self.assertRaisesRegex(ValueError, "new or empty"):
                matrix.assemble_selection(output, sources)
            matrix.save_json(sources[-1] / "cases/one/design.json", {"different": "character"})
            with self.assertRaisesRegex(ValueError, "changed character"):
                matrix.assemble_selection(root / "wrong-character", sources)

    def test_resumed_worker_receives_a_new_isolated_home(self):
        from nunti.avatar_studio.local_model import offline_environment

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            summary = dict.fromkeys(("status", "actualModelRgbImages", "actualRgbaAvatars",
                                     "distinctRgbaPixelImages", "cases", "statusCounts",
                                     "visualReviewCount", "voiceBindings"), None)
            with (patch.object(matrix.sys, "argv", ["audit", "--run", "--output", str(output)]),
                  patch.object(matrix, "prepare", return_value={"jobs": []}),
                  patch.object(matrix, "summarize", return_value=summary),
                  patch.object(matrix.subprocess, "run") as run,
                  patch("nunti.avatar_studio.local_model.offline_environment",
                        wraps=offline_environment) as environment,
                  patch("builtins.print")):
                run.return_value.returncode = 0
                self.assertEqual(matrix.main(), 0)
                self.assertEqual(matrix.main(), 0)
            first, second = [call.args[0] for call in environment.call_args_list]
            self.assertNotEqual(first, second)
            self.assertTrue((first / "home").is_dir())
            self.assertTrue((second / "home").is_dir())

    def test_visual_review_cannot_follow_a_replaced_image(self):
        records = [{"id": "one", "status": "READY", "rgbaSha256": "new-pixels"}]
        review = {"cases": [{"id": "one", "rgbaSha256": "old-pixels", "overallPass": True}]}
        accepted, rejected = matrix.verified_reviews(review, records)
        self.assertEqual(accepted, {})
        self.assertEqual(rejected[0]["id"], "one")
        review["cases"][0]["rgbaSha256"] = "new-pixels"
        accepted, rejected = matrix.verified_reviews(review, records)
        self.assertEqual(list(accepted), ["one"])
        self.assertEqual(rejected, [])

    def test_duplicate_reviews_are_not_silently_selected(self):
        record = {"id": "one", "status": "READY", "rgbaSha256": "pixels"}
        case = {"id": "one", "rgbaSha256": "pixels", "overallPass": True}
        accepted, rejected = matrix.verified_reviews({"cases": [case, case]}, [record])
        self.assertEqual(accepted, {})
        self.assertEqual(len(rejected), 2)

    def test_selected_30_cover_every_place_and_each_tested_role_three_times(self):
        from collections import Counter

        source = json.loads((ROOT / "docs/design/avatar-v6/cases.json").read_text())["cases"]
        selected = matrix.select_cases(source, ROOT / "docs/design/avatar-v6/ai-cases-30.json")
        self.assertEqual(len(selected), 30)
        self.assertEqual(len({case["destination"]["name"] for case in selected}), 20)
        roles = Counter(case["expectedPurposeRole"] for case in selected)
        self.assertEqual(len(roles), 10)
        self.assertEqual(set(roles.values()), {3})
        ids = {case["id"] for case in selected}
        self.assertTrue({"01-business", "01-swim", "01-date", "02-business", "02-swim",
                         "02-date", "03-business", "03-swim", "03-rest"} <= ids)

    def test_subset_rejects_unknown_or_duplicate_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subset.json"
            matrix.save_json(path, ["known", "missing"])
            with self.assertRaisesRegex(ValueError, "Unknown subset"):
                matrix.select_cases([{"id": "known"}], path)
            matrix.save_json(path, ["known", "known"])
            with self.assertRaisesRegex(ValueError, "duplicate case ids"):
                matrix.select_cases([{"id": "known"}], path)

    def test_resume_rejects_changed_job_or_changed_image(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            raw, rgba = b"recorded-raw-png", b"recorded-rgba-png"
            (folder / "original-rgb.png").write_bytes(raw)
            (folder / "avatar.png").write_bytes(rgba)
            job = {"folder": directory, "jobFingerprint": "prepared-a"}
            result = {"status": "READY", "jobFingerprint": "prepared-a",
                      "rawSha256": matrix.sha(raw), "rgbaSha256": matrix.sha(rgba)}
            matrix.verify_saved_result(job, result)
            with self.assertRaisesRegex(ValueError, "identity differs"):
                matrix.verify_saved_result({**job, "jobFingerprint": "prepared-b"}, result)
            (folder / "avatar.png").write_bytes(b"changed image")
            with self.assertRaisesRegex(ValueError, "RGBA image changed"):
                matrix.verify_saved_result(job, result)

    def test_cutout_failure_still_preserves_actual_model_rgb_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            raw = b"actual-model-original"
            (folder / "original-rgb.png").write_bytes(raw)
            job = {"folder": directory, "jobFingerprint": "prepared"}
            result = {"status": "CUTOUT_FAILED", "jobFingerprint": "prepared",
                      "rawSha256": matrix.sha(raw)}
            matrix.verify_saved_result(job, result)
            (folder / "original-rgb.png").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "raw image changed"):
                matrix.verify_saved_result(job, result)

    def test_progress_json_replaces_atomically_without_leftover_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/result.json"
            matrix.save_json(path, {"status": "RUNNING"})
            matrix.save_json(path, {"status": "READY", "id": "01-business"})
            self.assertEqual(json.loads(path.read_text()), {"status": "READY", "id": "01-business"})
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
