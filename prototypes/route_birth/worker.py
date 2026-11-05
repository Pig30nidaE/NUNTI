#!/usr/bin/env python3
"""Offline route-born companion worker. One local GPU lane; responsive loopback HTTP."""
from __future__ import annotations
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import sys
import tempfile
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from generator import VERSION, PROVIDER, REVISION, canonical, digest, make_plan, normalize, require

DEFAULT_WORKSPACE = ROOT / ".local/route-birth"
KINDS = ("greeting", "arrival", "common")
ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crash_at(point):
    """Subprocess test only. No live-user route is put in diagnostic logs."""
    if os.environ.get("NUNTI_ROUTE_CRASH_AT") == point:
        os._exit(86)


def fsync_dir(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path, value):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write((canonical(value) + "\n").encode())
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        fsync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sealed(value):
    return {"body": value, "sha256": digest(value)}


def read_sealed(path):
    require(path.is_file() and not path.is_symlink(), "COMMITTED_FILE_MISSING")
    outer = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(outer, dict) and set(outer) == {"body", "sha256"} and outer["sha256"] == digest(outer["body"]), "COMMITTED_RECORD_CHANGED")
    return outer["body"]


def inspect_wav(path):
    require(path.is_file() and not path.is_symlink(), "COMMITTED_AUDIO_MISSING")
    with wave.open(str(path), "rb") as wav:
        sample_rate, channels, width, frames = wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()
        require(wav.getcomptype() == "NONE", "INVALID_WAV_ENCODING")
        pcm = wav.readframes(frames)
    require((sample_rate, channels, width) == (24000, 1, 2) and 0 < frames <= 720000 and len(pcm) == frames * 2, "INVALID_WAV_FORMAT")
    require(any(pcm), "SILENT_WAV")
    return {"sampleRateHz": sample_rate, "channels": channels, "sampleWidthBytes": width, "frames": frames,
            "durationMs": round(frames * 1000 / sample_rate), "audioSha256": file_sha(path)}


def source_for(plan):
    voice = plan["artifact"]["voice"]
    return {"kind": "directed-sohee-v1", "sourceModelRevision": REVISION, "bindingId": voice["bindingId"],
            "engineFingerprint": plan["engineFingerprint"], "directionSha256": hashlib.sha256(voice["direction"].encode()).hexdigest(), "seed": plan["seed"]}


class Conflict(ValueError):
    pass


class NotFound(ValueError):
    pass


class Worker:
    def __init__(self, workspace, synthesizer, background=True):
        self.workspace = Path(workspace).resolve()
        require(self.workspace != ROOT and not any(self.workspace.is_relative_to(ROOT / ".local" / name) for name in ("journey-mvp", "journey-voice-dynamic", "journey-voice-v3", "qwen-sohee-audition")), "WORKSPACE_MUST_BE_ISOLATED")
        self.workspace.mkdir(parents=True, exist_ok=True)
        require(not self.workspace.is_symlink(), "INVALID_WORKSPACE")
        self._lock_file = (self.workspace / ".worker.lock").open("a+b")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock_file.close()
            raise ValueError("WORKSPACE_ALREADY_OWNED") from None
        self.jobs = self.workspace / "jobs"
        self.jobs.mkdir(exist_ok=True)
        self.synthesizer = synthesizer
        self.fingerprint, self.identity = synthesizer.fingerprint, synthesizer.identity
        require(self.identity["providerId"] == PROVIDER and self.identity["revision"] == REVISION, "UNSUPPORTED_ENGINE")
        self._guard = threading.RLock()
        self._queue = queue.Queue()
        self._queued = set()
        self._failures = {}
        self._stop = threading.Event()
        self._thread = None
        # Hidden staging directories were never published. Existing committed job
        # directories, plans, audio and results are never silently replaced.
        for item in self.jobs.iterdir():
            if item.name.startswith(".job-") and item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            elif item.is_dir() and ID_RE.fullmatch(item.name):
                try:
                    plan = self._plan(item.name)
                    self._check_existing(plan)
                    if not (item / "result.json").exists() and not (item / "failure.json").exists():
                        self._enqueue(item.name)
                except Exception:
                    self._failures[item.name] = "COMMITTED_DATA_CORRUPT"
            else:
                raise ValueError("UNMANAGED_JOB_ENTRY")
        if background:
            self._thread = threading.Thread(target=self._run, name="route-born-synthesis", daemon=True)
            self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        # A caller must not release the interprocess lane while a model thread
        # still renders; normal HTTP process termination releases the OS lock.
        if not self._thread or not self._thread.is_alive():
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()

    def _plan(self, request_id):
        path = self.jobs / request_id
        require(path.is_dir() and not path.is_symlink(), "JOB_DIRECTORY_CHANGED")
        plan = read_sealed(path / "plan.json")
        require(plan == make_plan(plan["request"], self.fingerprint, self.identity) and plan["request"]["requestId"] == request_id, "COMMITTED_PLAN_CHANGED")
        return plan

    def _enqueue(self, request_id):
        if request_id not in self._queued:
            self._queued.add(request_id)
            self._queue.put(request_id)

    def submit(self, value):
        value = normalize(value)
        request_id, input_sha = value["requestId"], digest(value)
        with self._guard:
            path = self.jobs / request_id
            if path.exists():
                try:
                    plan = self._plan(request_id)
                except Exception:
                    self._failures[request_id] = "COMMITTED_DATA_CORRUPT"
                    return self.get(request_id)
                if plan["inputSha256"] != input_sha:
                    raise Conflict("REQUEST_ID_ALREADY_BOUND_TO_DIFFERENT_INPUT")
                return self.get(request_id)
            plan = make_plan(value, self.fingerprint, self.identity)
            staging = Path(tempfile.mkdtemp(prefix=".job-", dir=self.jobs))
            try:
                (staging / "clips").mkdir()
                atomic_json(staging / "plan.json", sealed(plan))
                fsync_dir(staging / "clips")
                fsync_dir(staging)
                crash_at("before-plan-publication")
                staging.rename(path)
                fsync_dir(self.jobs)
                crash_at("after-plan-publication")
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            self._enqueue(request_id)
            return self.get(request_id)

    def _clip(self, plan, category):
        path = self.jobs / plan["request"]["requestId"] / "clips" / category
        require(path.is_dir() and not path.is_symlink(), "COMMITTED_CLIP_MISSING")
        require({p.name for p in path.iterdir()} == {"audio.wav", "metadata.json"}, "COMMITTED_CLIP_FILES_CHANGED")
        metadata = read_sealed(path / "metadata.json")
        actual = inspect_wav(path / "audio.wav")
        expected = {"category": category, "text": plan["texts"][category], "textSha256": hashlib.sha256(plan["texts"][category].encode()).hexdigest(),
                    "characterId": plan["artifact"]["characterId"], "profileId": plan["artifact"]["voice"]["profileId"], "source": source_for(plan), "direction": plan["artifact"]["voice"]["direction"]}
        require(all(metadata.get(k) == v for k, v in {**expected, **actual}.items()), "COMMITTED_CLIP_CHANGED")
        require(set(metadata) == set(expected) | set(actual) | {"render"}, "COMMITTED_CLIP_METADATA_CHANGED")
        require(all(metadata["render"].get(k) == v for k, v in actual.items()), "RENDER_METADATA_CHANGED")
        require(metadata["render"].get("termination", {}).get("tokenLimitReached") is False, "RENDER_TOKEN_LIMIT_REACHED")
        clip_id = plan["artifact"]["characterId"] + "-" + category
        return {"clipId": clip_id, "characterId": expected["characterId"], "profileId": expected["profileId"], "speakerId": "Sohee", "locale": "ko-KR",
                "text": expected["text"], "textSha256": expected["textSha256"], "audioPath": clip_id + ".wav", "source": expected["source"], **actual}

    def _manifest(self, plan):
        return {"schemaVersion": 2, "providerId": PROVIDER, "characters": [{"characterId": plan["artifact"]["characterId"], "displayName": plan["artifact"]["displayName"]}],
                "scope": "OFFLINE_PC_SOHEE; native procedural route-born renderer; no Android model inference", "clips": [self._clip(plan, category) for category in KINDS]}

    def _check_existing(self, plan):
        path = self.jobs / plan["request"]["requestId"]
        require({p.name for p in path.iterdir()} <= {"plan.json", "clips", "result.json", "failure.json"} | {p.name for p in path.glob(".pending-*")}, "UNMANAGED_JOB_FILE")
        clips = path / "clips"
        require(clips.is_dir() and not clips.is_symlink(), "COMMITTED_CLIP_DIRECTORY_CHANGED")
        for item in clips.iterdir():
            if item.name in KINDS:
                self._clip(plan, item.name)
            else:
                require(item.name.startswith(".clip-") and item.is_dir() and not item.is_symlink(), "UNMANAGED_CLIP_ENTRY")
        if (path / "failure.json").exists():
            failure = read_sealed(path / "failure.json")
            require(set(failure) == {"requestId", "error"} and failure["requestId"] == plan["request"]["requestId"] and isinstance(failure["error"], str) and len(failure["error"]) <= 160, "COMMITTED_FAILURE_CHANGED")
            return
        if (path / "result.json").exists():
            artifact = {**plan["artifact"], "voiceManifest": self._manifest(plan)}
            require(read_sealed(path / "result.json") == artifact, "COMMITTED_RESULT_CHANGED")

    def get(self, request_id):
        if not ID_RE.fullmatch(request_id) or not (self.jobs / request_id).exists():
            raise NotFound("JOURNEY_NOT_FOUND")
        with self._guard:
            if request_id in self._failures:
                return {"requestId": request_id, "state": "FAILED", "error": self._failures[request_id]}
            try:
                plan = self._plan(request_id)
                self._check_existing(plan)
                path = self.jobs / request_id
                if (path / "failure.json").exists():
                    return {"requestId": request_id, "state": "FAILED", "error": read_sealed(path / "failure.json")["error"], "artifact": deepcopy(plan["artifact"])}
                if (path / "result.json").exists():
                    return {"requestId": request_id, "state": "READY", "artifact": read_sealed(path / "result.json")}
                return {"requestId": request_id, "state": "GENERATING", "artifact": deepcopy(plan["artifact"])}
            except Exception:
                self._failures[request_id] = "COMMITTED_DATA_CORRUPT"
                return {"requestId": request_id, "state": "FAILED", "error": "COMMITTED_DATA_CORRUPT"}

    def audio(self, request_id, audio_path):
        with self._guard:
            result = self.get(request_id)
            if result["state"] != "READY":
                raise NotFound("AUDIO_NOT_READY")
            for category, clip in zip(KINDS, result["artifact"]["voiceManifest"]["clips"]):
                if clip["audioPath"] == audio_path:
                    path = self.jobs / request_id / "clips" / category / "audio.wav"
                    data = path.read_bytes()
                    require(hashlib.sha256(data).hexdigest() == clip["audioSha256"], "COMMITTED_AUDIO_CHANGED")
                    return data
            raise NotFound("AUDIO_NOT_FOUND")

    def process_one(self, request_id):
        with self._guard:
            result = self.get(request_id)
            if result["state"] != "GENERATING":
                return result
            plan = self._plan(request_id)
        path = self.jobs / request_id
        try:
            for category in KINDS:
                committed = path / "clips" / category
                with self._guard:
                    if committed.exists():
                        self._clip(plan, category)
                        continue
                    # Staging clips have no public identity and can be discarded.
                    for item in (path / "clips").glob(".clip-*"):
                        require(item.is_dir() and not item.is_symlink(), "INVALID_PENDING_CLIP")
                        shutil.rmtree(item)
                    staging = Path(tempfile.mkdtemp(prefix=".clip-", dir=path / "clips"))
                try:
                    render = self.synthesizer.render(plan["texts"][category], plan["artifact"]["voice"]["direction"], plan["seed"], staging / "audio.wav")
                    actual = inspect_wav(staging / "audio.wav")
                    require(all(render.get(k) == v for k, v in actual.items()), "MODEL_RENDER_METADATA_CHANGED")
                    metadata = {"category": category, "text": plan["texts"][category], "textSha256": hashlib.sha256(plan["texts"][category].encode()).hexdigest(),
                                "characterId": plan["artifact"]["characterId"], "profileId": plan["artifact"]["voice"]["profileId"], "source": source_for(plan),
                                "direction": plan["artifact"]["voice"]["direction"], **actual, "render": render}
                    atomic_json(staging / "metadata.json", sealed(metadata))
                    with (staging / "audio.wav").open("rb") as audio:
                        os.fsync(audio.fileno())
                    fsync_dir(staging)
                    crash_at("before-clip-publication-" + category)
                    with self._guard:
                        # Recheck immutable inputs before publishing this clip.
                        require(self._plan(request_id) == plan, "PLAN_CHANGED_DURING_GENERATION")
                        staging.rename(committed)
                        fsync_dir(committed.parent)
                        crash_at("after-clip-publication-" + category)
                        self._clip(plan, category)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            with self._guard:
                artifact = {**plan["artifact"], "voiceManifest": self._manifest(plan)}
                crash_at("before-result-publication")
                require(not (path / "result.json").exists(), "RESULT_ALREADY_COMMITTED")
                atomic_json(path / "result.json", sealed(artifact))
                crash_at("after-result-publication")
                self._check_existing(plan)
        except Exception as error:
            with self._guard:
                # Keep raw destination/route out of diagnostics and HTTP errors.
                code = str(error) if isinstance(error, ValueError) and re.fullmatch(r"[A-Z0-9_]{1,120}", str(error)) else "SYNTHESIS_FAILED_" + type(error).__name__.upper()
                if not (path / "failure.json").exists():
                    atomic_json(path / "failure.json", sealed({"requestId": request_id, "error": code[:160]}))
        return self.get(request_id)

    def _run(self):
        while not self._stop.is_set():
            try:
                request_id = self._queue.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                self.process_one(request_id)
            finally:
                with self._guard:
                    self._queued.discard(request_id)
                self._queue.task_done()


def strict_json(data):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON_NUMBER")))


def make_handler(worker):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NuntiRouteBorn/1"
        def log_message(self, *_):
            pass  # No destination/route values in public HTTP diagnostic logs.
        def response(self, status, value, audio=False):
            data = value if audio else (canonical(value) + "\n").encode()
            self.send_response(status)
            self.send_header("Content-Type", "audio/wav" if audio else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def do_GET(self):
            try:
                require(not urlsplit(self.path).query, "QUERY_NOT_SUPPORTED")
                if self.path == "/health":
                    return self.response(200, {"status": "ok", "version": VERSION})
                match = re.fullmatch(r"/v1/journeys/([0-9a-f-]{36})(?:/audio/([^/]+))?", self.path)
                if not match:
                    raise NotFound("ENDPOINT_NOT_FOUND")
                request_id, filename = match.groups()
                if filename is not None:
                    require(unquote(filename) == filename and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.wav", filename), "INVALID_AUDIO_PATH")
                    return self.response(200, worker.audio(request_id, filename), audio=True)
                return self.response(200, worker.get(request_id))
            except NotFound as e:
                self.response(404, {"error": str(e)})
            except (ValueError, TypeError, KeyError):
                self.response(400, {"error": "INVALID_REQUEST"})
            except Exception:
                self.response(500, {"error": "WORKER_READ_FAILED"})
        def do_POST(self):
            try:
                if self.path != "/v1/journeys":
                    raise NotFound("ENDPOINT_NOT_FOUND")
                require(self.headers.get_content_type() == "application/json" and self.headers.get("Transfer-Encoding") is None, "JSON_BODY_REQUIRED")
                content_length = self.headers.get("Content-Length")
                require(content_length is not None and re.fullmatch(r"[0-9]+", content_length) is not None and 0 < int(content_length) <= 65536, "INVALID_BODY_LENGTH")
                self.connection.settimeout(10)
                body = self.rfile.read(int(content_length))
                require(len(body) == int(content_length), "INCOMPLETE_BODY")
                result = worker.submit(strict_json(body))
                self.response(202 if result["state"] == "GENERATING" else 200, result)
            except Conflict as e:
                self.response(409, {"error": str(e)})
            except NotFound as e:
                self.response(404, {"error": str(e)})
            except (ValueError, TypeError, KeyError, UnicodeError):
                self.response(400, {"error": "INVALID_REQUEST"})
            except Exception:
                self.response(500, {"error": "WORKER_SUBMISSION_FAILED"})
    return Handler


def synthesizer():
    sys.path.insert(0, str(ROOT / "prototypes/journey_voice_dynamic"))
    from engine import SoheeSynthesizer
    return SoheeSynthesizer()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    serve.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    require(1024 <= args.port <= 65535, "INVALID_PORT")
    worker = Worker(args.workspace, synthesizer())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(worker))
    server.daemon_threads = True
    print(canonical({"status": "listening", "version": VERSION, "host": "127.0.0.1", "port": args.port, "workspace": str(worker.workspace)}), flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        worker.close()


if __name__ == "__main__":
    main()
