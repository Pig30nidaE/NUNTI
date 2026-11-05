"""Exercise additive export against copies of the real generated demo artifacts."""
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from export_android import export, output_lock_path

HERE = Path(__file__).resolve().parent


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.output = self.root / "output"
        self.characters = sorted((HERE / "demo/characters").glob("*/character.json"))

    def tearDown(self):
        self.temporary.cleanup()

    def add(self, index):
        source = self.characters[index].parent
        shutil.copytree(source, self.state / "characters" / source.name)

    def test_new_characters_append_and_existing_audio_stays_identical(self):
        self.add(0)
        export(self.state, self.output)
        first = {p.name: p.read_bytes() for p in self.output.glob("*.wav")}
        self.add(1)
        result = export(self.state, self.output)
        self.assertEqual((result["characters"], result["clips"]), (2, 6))
        self.assertTrue(all((self.output / name).read_bytes() == data for name, data in first.items()))
        before = (self.output / "manifest.json").read_bytes()
        export(self.state, self.output)
        self.assertEqual(before, (self.output / "manifest.json").read_bytes())

    def test_missing_previous_character_is_rejected(self):
        self.add(0)
        self.add(1)
        export(self.state, self.output)
        before = (self.output / "manifest.json").read_bytes()
        shutil.rmtree(self.state / "characters" / self.characters[1].parent.name)
        with self.assertRaisesRegex(ValueError, "EXISTING_CHARACTER_EXPORT_CHANGED"):
            export(self.state, self.output)
        self.assertEqual(before, (self.output / "manifest.json").read_bytes())

    def test_existing_wav_corruption_is_rejected(self):
        self.add(0)
        export(self.state, self.output)
        target = next(self.output.glob("*.wav"))
        target.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "EXPORTED_ASSET_CHANGED"):
            export(self.state, self.output)
        self.assertEqual(target.read_bytes(), b"corrupt")

    def test_output_lock_blocks_another_process_before_publication(self):
        self.add(0)
        path = output_lock_path(self.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        ready = self.root / "ready"
        code = 'from pathlib import Path; from export_android import export; import sys; Path(sys.argv[3]).write_text("ready"); export(Path(sys.argv[1]), Path(sys.argv[2]))'
        with path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen([sys.executable, "-c", code, str(self.state), str(self.output), str(ready)], cwd=HERE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.exists())
                self.assertIsNone(process.poll())
                self.assertFalse(self.output.exists())
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                _, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr.decode())
        self.assertTrue((self.output / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
