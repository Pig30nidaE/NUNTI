"""Exercise access boundaries with fake transports only; never contact a provider."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import prepare

CANARY = "TEST_ONLY_NEVER_REAL_CREDENTIAL_12345"


class FakeOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(json.dumps(value).encode())


class PrepareTests(unittest.TestCase):
    def access(self, responses):
        opener = FakeOpener(responses)
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": CANARY}), patch.object(prepare.urllib.request, "build_opener", return_value=opener):
            result, status = prepare.check_access()
        self.assertNotIn(CANARY, json.dumps(result))
        return result, status, opener

    def test_missing_key_never_constructs_network_transport(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(prepare.urllib.request, "build_opener", side_effect=AssertionError("network attempted")):
            result, status = prepare.check_access()
        self.assertEqual((result["status"], result["networkRequests"], status), ("MISSING_API_KEY", 0, 2))

    def test_whitespace_key_never_constructs_network_transport(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "   "}), patch.object(prepare.urllib.request, "build_opener", side_effect=AssertionError("network attempted")):
            result, status = prepare.check_access()
        self.assertEqual(result["status"], "MISSING_API_KEY")

    def test_newline_key_is_rejected_without_echo_or_network(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": CANARY + "\n"}), patch.object(prepare.urllib.request, "build_opener", side_effect=AssertionError("network attempted")):
            result, status = prepare.check_access()
        self.assertEqual(result["status"], "INVALID_API_KEY_FORMAT")
        self.assertNotIn(CANARY, json.dumps(result))

    def test_only_two_exact_gets_and_filtered_public_model_fields(self):
        result, status, opener = self.access([
            [{"model_id": "eleven_v4", "name": CANARY, "description": CANARY,
              "can_do_text_to_speech": True, "requires_alpha_access": False},
             {"model_id": "some-other-model", "description": CANARY}],
            {"voice_id": prepare.ANNA_VOICE_ID, "name": CANARY,
             "sharing": {"whitelisted_emails": [CANARY]}, "samples": [CANARY]},
        ])
        self.assertEqual(status, 0)
        self.assertEqual([request.method for request in opener.requests], ["GET", "GET"])
        self.assertEqual([request.full_url for request in opener.requests],
                         [prepare.BASE_URL + path for path in prepare.READ_PATHS])
        self.assertEqual(result["networkRequests"], 2)
        self.assertFalse(result["synthesisAccessVerified"])
        self.assertEqual(len(result["models"]), 3)
        self.assertNotIn("name", result["voice"])

    def test_auth_error_body_and_headers_are_not_emitted(self):
        error = urllib.error.HTTPError(prepare.BASE_URL, 401, CANARY,
                                       {"private": CANARY}, io.BytesIO(CANARY.encode()))
        result, status, opener = self.access([error])
        self.assertEqual(status, 3)
        self.assertEqual(result["failure"]["httpStatus"], 401)
        self.assertEqual(len(opener.requests), 1)

    def test_redirect_is_not_followed_by_handler(self):
        request = prepare.urllib.request.Request(prepare.BASE_URL + "/v1/models")
        self.assertIsNone(prepare.NoRedirect().redirect_request(request, None, 302, "", {}, "https://elsewhere.invalid/"))

    def test_unknown_read_path_is_rejected_before_transport(self):
        opener = FakeOpener([])
        with self.assertRaises(prepare.AccessFailure):
            prepare.get_json("/v1/voices", CANARY, opener)
        self.assertEqual(opener.requests, [])

    def test_wrong_voice_response_does_not_dump_payload(self):
        result, status, opener = self.access([[], {"voice_id": CANARY, "name": CANARY}])
        self.assertEqual(result["failure"]["code"], "VOICE_ID_MISMATCH")
        self.assertEqual(status, 3)

    def test_offline_text_bytes_are_exact_including_crlf_and_spaces(self):
        original = "  안녕하세요.\r\n다음 줄!  \n".encode()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, target = folder / "input.txt", folder / "request.json"
            source.write_bytes(original)
            with patch.object(prepare.urllib.request, "build_opener", side_effect=AssertionError("network attempted")):
                result = prepare.write_request(target, source, "eleven_v4", prepare.ANNA_VOICE_ID, "create-speech", "mp3_44100_128")
            data = json.loads(target.read_text())
            self.assertEqual(data["request"]["body"]["text"].encode(), original)
            self.assertEqual(data["input"]["originalSha256"], data["input"]["bodyTextUtf8Sha256"])
            self.assertEqual(result["networkRequests"], 0)
            self.assertFalse(data["synthesisImplemented"])
            self.assertFalse(data["accessVerified"])
            self.assertNotIn(CANARY, target.read_text())

    def test_existing_request_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, target = folder / "input.txt", folder / "request.json"
            source.write_text("원문")
            target.write_text("preserve me")
            with self.assertRaises(FileExistsError):
                prepare.write_request(target, source, "eleven_v3", prepare.ANNA_VOICE_ID, "create-speech", "pcm_24000")
            self.assertEqual(target.read_text(), "preserve me")

    def test_wrong_explicit_voice_is_not_prepared(self):
        with self.assertRaises(ValueError):
            prepare.write_request(Path("unused"), Path("unused"), "eleven_v4", "wrong", "create-speech", "mp3_44100_128")

    def test_mistaken_cli_credential_is_not_echoed(self):
        run = subprocess.run([sys.executable, str(Path(prepare.__file__)), "--api-key", CANARY],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 2)
        self.assertNotIn(CANARY, run.stdout + run.stderr)
        self.assertIn("INVALID_ARGUMENTS", run.stderr)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PrepareTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
