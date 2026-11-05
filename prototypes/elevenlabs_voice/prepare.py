"""Read two capability endpoints or export an offline request. Never synthesize."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

ANNA_VOICE_ID = "uyVNoMrnUku1dZyVEXwD"
BASE_URL = "https://api.elevenlabs.io"
READ_PATHS = ("/v1/models", "/v1/voices/" + ANNA_VOICE_ID)
MODEL_IDS = ("eleven_v4", "eleven_v3", "eleven_multilingual_v2")
OUTPUT_FORMATS = ("mp3_44100_128", "pcm_24000")
SOURCES = {
    "models": "https://elevenlabs.io/docs/api-reference/models/list",
    "voice": "https://elevenlabs.io/docs/api-reference/voices/get",
    "createSpeech": "https://elevenlabs.io/docs/api-reference/text-to-speech/convert",
    "v4ProductGuide": "https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech",
    "v4ConvertExample": "https://elevenlabs.io/docs/overview/intro",
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class AccessFailure(Exception):
    def __init__(self, code: str, http_status: int | None = None):
        self.code = code
        self.http_status = http_status


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Unknown arguments can contain a mistakenly pasted credential.
        self.exit(2, json.dumps({"status": "INVALID_ARGUMENTS", "networkRequests": 0,
                                 "help": "Use --help; credentials are accepted only through the environment."}) + "\n")


def get_json(path: str, key: str, opener) -> object:
    if path not in READ_PATHS:
        raise AccessFailure("READ_PATH_NOT_ALLOWED")
    request = urllib.request.Request(BASE_URL + path, method="GET",
                                     headers={"xi-api-key": key, "Accept": "application/json"})
    try:
        with opener.open(request, timeout=20) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise AccessFailure("RESPONSE_TOO_LARGE")
        return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as error:
        # Never emit response bodies, headers, URLs, or exception text.
        error.close()
        raise AccessFailure("HTTP_ERROR", error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AccessFailure("NETWORK_ERROR") from None
    except (UnicodeError, json.JSONDecodeError):
        raise AccessFailure("INVALID_JSON_RESPONSE") from None


def check_access() -> tuple[dict, int]:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key or not key.strip():
        return {"status": "MISSING_API_KEY", "environmentVariable": "ELEVENLABS_API_KEY",
                "networkRequests": 0, "synthesisRequests": 0,
                "nextAction": "Provide the key through the environment; do not paste it into chat."}, 2
    if not key.isascii() or any(character in key for character in "\r\n"):
        return {"status": "INVALID_API_KEY_FORMAT", "networkRequests": 0,
                "synthesisRequests": 0}, 2
    opener = urllib.request.build_opener(NoRedirect())
    results = {"status": "READ_ONLY_METADATA_RETRIEVED", "networkRequests": 0,
               "synthesisRequests": 0, "synthesisAccessVerified": False}
    for path in READ_PATHS:
        results["networkRequests"] += 1
        try:
            payload = get_json(path, key, opener)
            if path == READ_PATHS[0]:
                if not isinstance(payload, list):
                    raise AccessFailure("UNEXPECTED_MODELS_RESPONSE")
                models = {item["model_id"]: item for item in payload
                          if isinstance(item, dict) and isinstance(item.get("model_id"), str)}
                selected = []
                for model_id in MODEL_IDS:
                    item = models.get(model_id)
                    record = {"modelId": model_id, "listed": item is not None}
                    if item is not None:
                        for source, target in [("can_do_text_to_speech", "canDoTextToSpeech"),
                                               ("requires_alpha_access", "requiresAlphaAccess")]:
                            if isinstance(item.get(source), bool):
                                record[target] = item[source]
                    selected.append(record)
                results["models"] = selected
            else:
                if not isinstance(payload, dict) or payload.get("voice_id") != ANNA_VOICE_ID:
                    raise AccessFailure("VOICE_ID_MISMATCH")
                # Do not copy name, owner, sharing, email, recordings, or sample URLs.
                results["voice"] = {"requestedVoiceId": ANNA_VOICE_ID,
                                    "metadataRetrieved": True, "synthesisAccessVerified": False}
        except AccessFailure as failure:
            results["status"] = "ACCESS_CHECK_INCOMPLETE"
            results["failure"] = {"endpoint": path, "code": failure.code}
            if failure.http_status is not None:
                results["failure"]["httpStatus"] = failure.http_status
            return results, 3
    return results, 0


def write_request(path: Path, text_path: Path, model_id: str, voice_id: str,
                  operation: str, output_format: str) -> dict:
    if model_id not in MODEL_IDS or voice_id != ANNA_VOICE_ID or operation != "create-speech":
        raise ValueError("UNSUPPORTED_EXPLICIT_REQUEST_SELECTION")
    if output_format not in OUTPUT_FORMATS:
        raise ValueError("UNSUPPORTED_OUTPUT_FORMAT")
    # Decode bytes directly. Do not strip, normalize, append tags, or translate newlines.
    original_bytes = text_path.read_bytes()
    text = original_bytes.decode("utf-8")
    endpoint = "/v1/text-to-speech/" + voice_id
    payload = {
        "schemaVersion": 1, "status": "OFFLINE_REQUEST_ONLY",
        "synthesisImplemented": False, "networkRequests": 0,
        "accessVerified": False, "voiceModelCombinationVerified": False,
        "endpointCompatibility": "Official request shape; not tested with this account and voice",
        "request": {"method": "POST", "endpoint": endpoint,
                    "url": BASE_URL + endpoint + "?" + urllib.parse.urlencode({"output_format": output_format}),
                    "query": {"output_format": output_format},
                    "headers": {"Content-Type": "application/json"},
                    "body": {"text": text, "model_id": model_id}},
        "authentication": {"headerName": "xi-api-key", "environmentVariable": "ELEVENLABS_API_KEY",
                           "valueIncluded": False},
        "input": {"encoding": "UTF-8", "originalByteLength": len(original_bytes),
                  "originalSha256": hashlib.sha256(original_bytes).hexdigest(),
                  "bodyTextUtf8Sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                  "characters": len(text), "normalizationByThisTool": "none"},
        "sources": SOURCES,
        "notProven": ["account model entitlement", "Anna voice entitlement",
                      "credits or subscription", "exact public-UI model/settings reproduction",
                      "synthesis success or audio quality"],
    }
    if payload["input"]["originalSha256"] != payload["input"]["bodyTextUtf8Sha256"]:
        raise ValueError("TEXT_BYTES_CHANGED")
    with path.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(payload, target, ensure_ascii=False, indent=2)
        target.write("\n")
    return {"status": "OFFLINE_REQUEST_WRITTEN", "networkRequests": 0, "synthesisRequests": 0,
            "modelId": model_id, "voiceId": voice_id, "endpoint": endpoint,
            "outputFormat": output_format, "textSha256": payload["input"]["originalSha256"]}


def main() -> int:
    parser = SafeArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-access", action="store_true")
    modes.add_argument("--write-request", type=Path)
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--model-id", choices=MODEL_IDS)
    parser.add_argument("--voice-id")
    parser.add_argument("--operation", choices=["create-speech"])
    parser.add_argument("--output-format", choices=OUTPUT_FORMATS)
    args = parser.parse_args()
    if args.check_access:
        if any(value is not None for value in [args.text_file, args.model_id, args.voice_id,
                                               args.operation, args.output_format]):
            parser.error("--check-access accepts no synthesis request arguments")
        result, code = check_access()
    else:
        if any(value is None for value in [args.text_file, args.model_id, args.voice_id,
                                          args.operation, args.output_format]):
            parser.error("offline export requires --text-file, --model-id, --voice-id, --operation, --output-format")
        try:
            result = write_request(args.write_request, args.text_file, args.model_id, args.voice_id,
                                   args.operation, args.output_format)
            code = 0
        except FileExistsError:
            result, code = {"status": "REQUEST_ALREADY_EXISTS", "networkRequests": 0}, 4
        except (OSError, UnicodeError, ValueError):
            result, code = {"status": "INVALID_OFFLINE_REQUEST", "networkRequests": 0}, 4
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
