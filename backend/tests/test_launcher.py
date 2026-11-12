"""Launcher checks also runnable with macOS Python 3.9 and only the standard library."""

import contextlib
import io
import os
import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_avatar_generator.py"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        tools = ModuleType("local_tools")
        for name in ("ADB", "SDK", "avd_name", "emulator_env", "gradle_env", "gradle_flags"):
            setattr(tools, name, Mock())
        self.modules = patch.dict("sys.modules", {"local_tools": tools})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.launcher = SimpleNamespace(**runpy.run_path(str(SCRIPT)))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.root_patch = patch.dict(self.launcher.runtime.__globals__, ROOT=self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def candidate(self, directory):
        path = self.root / directory / "bin/python"
        path.parent.mkdir(parents=True)
        path.touch()
        return path

    def test_help_runs_without_starting_services(self):
        output = io.StringIO()
        with (
            patch("sys.argv", [str(SCRIPT), "--help"]),
            patch("subprocess.Popen") as start,
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as exit_status,
        ):
            runpy.run_path(str(SCRIPT), run_name="__main__")
        self.assertEqual(exit_status.exception.code, 0)
        self.assertIn("--restart-server", output.getvalue())
        start.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_runtime_prefers_current_checkout(self):
        current = self.candidate("backend/.venv")
        self.candidate(".worktrees/server/backend/.venv")
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(self.launcher.runtime(), current)
        self.assertEqual(run.call_count, 1)

    def test_runtime_skips_an_incompatible_environment(self):
        self.candidate("backend/.venv")
        fallback = self.candidate(".worktrees/server/backend/.venv")
        outcomes = [subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]
        with patch("subprocess.run", side_effect=outcomes):
            self.assertEqual(self.launcher.runtime(), fallback)

    def test_missing_runtime_reports_backend_requirement(self):
        with self.assertRaisesRegex(RuntimeError, "Python 3.12-3.14"):
            self.launcher.runtime()

    def test_dotenv_precedence_and_quoted_values(self):
        local = self.root / ".env.local"
        fallback = self.root / ".env"
        local.write_text("# ignored\nexport TEST_VALUE='local value'\n", encoding="utf-8")
        fallback.write_text('TEST_VALUE="fallback"\n', encoding="utf-8")
        with (
            patch.dict(self.launcher.env_file_value.__globals__, ENV_FILES=(local, fallback)),
            patch.dict(os.environ, {}, clear=True),
        ):
            self.assertEqual(self.launcher.env_file_value("TEST_VALUE"), "local value")
            os.environ["TEST_VALUE"] = "environment"
            self.assertEqual(self.launcher.env_file_value("TEST_VALUE"), "environment")
            self.assertIsNone(self.launcher.env_file_value("MISSING_VALUE"))


if __name__ == "__main__":
    unittest.main()
