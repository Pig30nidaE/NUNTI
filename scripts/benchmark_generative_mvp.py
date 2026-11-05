#!/usr/bin/env python3
"""Prepare, run and blindly rate the Nunti v2 character benchmark.

No model SDKs. Preparation and evaluation are offline. --run talks only to the
configured Nunti servers, never directly to image or speech providers.
"""
from __future__ import annotations

import argparse
import copy
import csv
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import hashlib
from html import escape
import fcntl
import json
import math
import os
from pathlib import Path
import random
import re
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "docs/design/generative-mvp/benchmark"
PROFILES = ("primary", "value")
DIMENSIONS = ("cuteness", "collectibility", "naturalness", "voiceFit")
CSV_FIELDS = ("blindId", "phase", "mode", "raterId", *DIMENSIONS, "notes")
TERMINAL = {"READY", "FAILED", "RESULT_UNKNOWN"}


class BenchmarkError(ValueError):
    """Codes are safe to print; provider bodies and tokens are never printed."""


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BenchmarkError("INVALID_OR_MISSING_LOCAL_JSON") from exc


def load_key(path: Path) -> dict:
    key = load(path)
    if key.get("schemaVersion") != 1 or not isinstance(key.get("entries"), list) or len(key["entries"]) != 26:
        raise BenchmarkError("INVALID_BENCHMARK_KEY")
    seen = set()
    compare_cases, validation_cases = set(), set()
    for entry in key["entries"]:
        if (not re.fullmatch(r"N-[0-9a-f]{10}", entry.get("blindId", "")) or entry["blindId"] in seen
                or not re.fullmatch(r"journey-(0[1-9]|1[0-9]|20)", entry.get("caseId", ""))
                or entry.get("phase") not in ("compare", "validation")
                or entry.get("profile") not in (*PROFILES, None)):
            raise BenchmarkError("INVALID_BENCHMARK_KEY")
        request_id = entry["input"]["requestId"]
        if str(UUID(request_id)) != request_id:
            raise BenchmarkError("INVALID_BENCHMARK_REQUEST_ID")
        if entry["phase"] == "compare" and entry["profile"] not in PROFILES:
            raise BenchmarkError("INVALID_COMPARE_PROFILE")
        if entry["phase"] == "compare":
            compare_cases.add((entry["caseId"], entry["profile"]))
        else:
            validation_cases.add(entry["caseId"])
        seen.add(entry["blindId"])
    if (compare_cases != {(f"journey-{index:02d}", profile) for index in range(1, 7) for profile in PROFILES}
            or validation_cases != {f"journey-{index:02d}" for index in range(7, 21)}):
        raise BenchmarkError("INVALID_BENCHMARK_CASE_COVERAGE")
    return key


@contextmanager
def workspace_lock(workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    with (workspace / ".benchmark.lock").open("a") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BenchmarkError("BENCHMARK_ALREADY_RUNNING") from None
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(encode(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def money(value, *, positive=False) -> Decimal:
    if isinstance(value, bool):
        raise BenchmarkError("INVALID_COST")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise BenchmarkError("INVALID_COST") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise BenchmarkError("INVALID_COST")
    return result


def make_inputs() -> list[dict]:
    # These are test destinations and normalized drawn routes, not a character registry or map result.
    contexts = [
        ("밤바다 산책길", "밤바다, 별빛, 파도, 조용한 해안", "쉬러 가기", "coast"),
        ("새벽 산 캠핑장", "산, 안개, 침엽수, 새벽", "캠핑", "hairpin"),
        ("도심 작은 미술관", "전시, 골목, 유리, 낮", "전시 관람", "grid"),
        ("오래된 숲 정원", "숲, 이끼, 나무, 그늘", "친구 만나기", "loop"),
        ("잔잔한 호수 상점", "호수, 물결, 햇빛", "장보기", "arc"),
        ("새로운 곳", "아직 정하지 않은 특성", "가볍게 이동", "line"),
        ("비 오는 해안 카페", "바다, 비, 따뜻한 빛", "휴식", "coast"),
        ("눈 내린 산책 숲", "숲, 눈, 고요함", "산책", "loop"),
        ("해 질 녘 강변 공원", "강, 노을, 풀밭", "피크닉", "arc"),
        ("동네 도서관", "책, 종이, 나무, 낮", "책 빌리기", "grid"),
        ("봄 언덕 정원", "꽃, 언덕, 산들바람", "가족 나들이", "hairpin"),
        ("별이 뜬 해변", "밤바다, 별빛, 파도, 조용한 해안", "쉬러 가기", "coast"),
        ("아침 출근길", "도심, 유리, 이른 햇빛", "출근", "line"),
        ("들판 옆 작은 집", "들판, 나무, 오후", "친구 방문", "arc"),
        ("구름 낀 항구", "배, 안개, 바다", "구경", "grid"),
        ("구불구불 산길 쉼터", "산, 바위, 구름", "휴식", "hairpin"),
        ("겨울 호수 정원", "호수, 얼음, 낮은 햇빛", "사진 찍기", "loop"),
        ("여름 골목 시장", "도심, 시장, 밝은 색", "장보기", "grid"),
        ("긴 해안 드라이브", "바다, 모래, 햇빛", "가족 나들이", "coast"),
        ("처음 가는 목적지", "", "", "line"),
    ]
    results = []
    for index, (name, traits, purpose, shape) in enumerate(contexts):
        points = []
        for step in range(24):
            t = step / 23
            if shape == "loop":
                x, y = .5 + .35 * math.cos(t * math.pi * 1.8), .5 + .35 * math.sin(t * math.pi * 1.8)
            elif shape == "hairpin":
                x, y = .5 + .34 * math.sin(t * math.pi * 5), .1 + .8 * t
            elif shape == "grid":
                x, y = .1 + .8 * t, .25 + .12 * min(4, int(t * 5))
            elif shape == "arc":
                x, y = .1 + .8 * t, .75 - .55 * math.sin(t * math.pi)
            elif shape == "coast":
                x, y = .1 + .8 * t, .5 + .26 * math.sin(t * math.pi * (2 + index * .025))
            else:
                x, y = .1 + .8 * t, .3 + .35 * t
            points.append([round(x, 6), round(y, 6)])
        results.append({"caseId": f"journey-{index + 1:02d}", "phase": "compare" if index < 6 else "validation",
                        "scenario": shape, "input": {"requestId": str(uuid4()),
                        "destination": {"name": name, "traits": traits}, "purpose": purpose,
                        "route": {"points": points}}})
    return results


def blank_rows(key: dict, records: list[dict]) -> list[dict]:
    by_id = {row["blindId"]: row for row in records}
    return [{"blindId": entry["blindId"], "phase": entry["phase"],
             "mode": by_id.get(entry["blindId"], {}).get("mode", "UNRUN"),
             **{field: "" for field in ("raterId", *DIMENSIONS, "notes")}}
            for entry in key["entries"]]


def write_csv(path: Path, rows: list[dict]) -> None:
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader(); writer.writerows(rows)
    os.replace(temporary, path)


def prepare(workspace: Path) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    owned = ("inputs.json", "blind-key.json", "ratings-template.csv", "runner-config.json", "adoption-rules.json")
    if any((workspace / name).exists() for name in owned):
        if all((workspace / name).is_file() for name in owned):
            return {"status": "ALREADY_PREPARED_PRESERVED", "distinctInputs": 20, "maximumGenerationOutputs": 26}
        raise BenchmarkError("PARTIAL_PREPARATION_REQUIRES_INSPECTION")
    cases = make_inputs()
    entries = []
    for case in cases:
        for profile in PROFILES if case["phase"] == "compare" else (None,):
            request = copy.deepcopy(case["input"])
            if profile == "value":
                request["requestId"] = str(uuid4())
            entries.append({"blindId": "N-" + uuid4().hex[:10], "caseId": case["caseId"],
                            "phase": case["phase"], "profile": profile, "input": request})
    random.SystemRandom().shuffle(entries)
    key = {"schemaVersion": 1, "notice": "Coordinator only. Hide this provider key from raters.", "entries": entries}
    config = {"schemaVersion": 1,
              "serverProfiles": {profile: {"baseUrl": f"http://127.0.0.1:{8090 + index}",
                 "mode": "OFFLINE_FIXTURE", "expectedPipeline": "OPENAI_ELEVEN" if profile == "primary" else "GOOGLE_COMPARE",
                 "tokenFile": str(ROOT / ".local/generative-mvp/connection-offline_fixture.json"), "tokenField": "token"}
                 for index, profile in enumerate(PROFILES)},
              "limits": {"perGenerationUsd": .30, "comparisonBudgetUsd": 3.60,
                         "validationBudgetUsd": 4.20, "maximumRequests": 26},
              "notice": "Only server configuration chooses models. API mode requires --allow-api. Unknown actual cost stops API batching."}
    rules = {"schemaVersion": 1, "minimumAverageEach": 4, "dimensions": list(DIMENSIONS),
             "comparisonInputsEachProfile": 6, "newValidationInputsSelectedProfile": 14,
             "tieWithinPoints": .2, "tieBreak": "lower measured cost per adopted character",
             "fixtureAdoptionAllowed": False, "unknownCostAsZeroAllowed": False,
             "notice": "Six inputs run on two profiles plus fourteen new selected-profile inputs: twenty distinct inputs, twenty-six outputs maximum."}
    atomic_json(workspace / "inputs.json", {"schemaVersion": 1, "cases": cases})
    atomic_json(workspace / "blind-key.json", key)
    atomic_json(workspace / "runner-config.json", config)
    atomic_json(workspace / "adoption-rules.json", rules)
    write_csv(workspace / "ratings-template.csv", blank_rows(key, []))
    return {"status": "PREPARED_WITHOUT_NETWORK", "distinctInputs": 20, "comparisonOutputs": 12,
            "newValidationOutputs": 14, "fixtureIsQualityEvidence": False}


def actual_cost(data: dict) -> tuple[float | None, str]:
    cost = data.get("cost")
    if not isinstance(cost, dict) or cost.get("complete") is not True or cost.get("actualMicros") is None:
        return None, "COST_UNKNOWN"
    value = money(cost["actualMicros"])
    if value != value.to_integral_value():
        raise BenchmarkError("INVALID_COST_MICROS")
    return float(value / Decimal(1_000_000)), "MEASURED"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, profile: dict, config_path: Path):
        base = profile.get("baseUrl", "")
        parsed = urlsplit(base)
        mode = profile.get("mode")
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise BenchmarkError("INVALID_SERVER_BASE")
        if mode not in ("OFFLINE_FIXTURE", "API"):
            raise BenchmarkError("INVALID_CONFIG_MODE")
        if mode == "OFFLINE_FIXTURE" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise BenchmarkError("FIXTURE_SERVER_MUST_BE_LOCAL")
        if mode == "API" and parsed.scheme != "https" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise BenchmarkError("REMOTE_API_SERVER_REQUIRES_HTTPS")
        token_path = Path(profile.get("tokenFile", ""))
        if not token_path.is_absolute():
            token_path = config_path.parent / token_path
        try:
            source = token_path.read_text(encoding="utf-8").strip()
            token = json.loads(source)[profile["tokenField"]] if profile.get("tokenField") else source
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise BenchmarkError("OWNER_TOKEN_FILE_UNAVAILABLE") from exc
        if not isinstance(token, str) or not 8 <= len(token) <= 8192 or any(char.isspace() for char in token):
            raise BenchmarkError("INVALID_OWNER_TOKEN_FILE")
        self.base, self.mode, self._token = base.rstrip("/"), mode, token
        self.opener = build_opener(NoRedirect())

    def request(self, path: str, body=None, *, binary=False, maximum=2_000_000):
        if not path.startswith("/v2/") or "?" in path or "#" in path or ".." in path:
            raise BenchmarkError("INVALID_SERVER_PATH")
        request = Request(self.base + path, data=encode(body).encode() if body is not None else None,
                          headers={"Authorization": "Bearer " + self._token, "Content-Type": "application/json"},
                          method="POST" if body is not None else "GET")
        try:
            with self.opener.open(request, timeout=35) as response:
                raw = response.read(maximum + 1)
        except HTTPError as exc:
            raise BenchmarkError(f"SERVER_HTTP_{exc.code}") from None
        except (URLError, OSError, TimeoutError):
            raise BenchmarkError("SERVER_TRANSPORT_RESULT_UNKNOWN") from None
        if len(raw) > maximum:
            raise BenchmarkError("SERVER_RESPONSE_TOO_LARGE")
        if binary:
            return raw
        try:
            envelope = json.loads(raw)
            if not isinstance(envelope.get("data"), dict):
                raise ValueError()
            return envelope["data"]
        except (ValueError, TypeError, AttributeError):
            raise BenchmarkError("INVALID_SERVER_ENVELOPE") from None


def save_blind_media(client: Client, artifact: dict, directory: Path) -> None:
    image = artifact["visual"]["asset"]
    media = [("image.png", image["sha256"], image.get("path"), 8_388_608)]
    clips = artifact["voiceManifest"]["clips"]
    for category in ("greeting", "common", "arrival"):
        matched = [clip for clip in clips if clip["clipId"].endswith("-" + category)]
        if len(matched) != 1:
            raise BenchmarkError("THREE_INITIAL_CLIPS_REQUIRED")
        digest = matched[0]["audioSha256"]
        media.append((category + ".wav", digest, "/v2/assets/" + digest, 2_000_000))
    directory.mkdir(parents=True, exist_ok=True)
    for name, digest, path, maximum in media:
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or path != "/v2/assets/" + digest:
            raise BenchmarkError("INVALID_MEDIA_IDENTITY")
        target = directory / name
        raw = target.read_bytes() if target.exists() else client.request(path, binary=True, maximum=maximum)
        if len(raw) > maximum or hashlib.sha256(raw).hexdigest() != digest:
            raise BenchmarkError("BENCHMARK_MEDIA_HASH_MISMATCH")
        if not target.exists():
            target.write_bytes(raw)


def refresh_ratings(workspace: Path, key: dict, records: list[dict]) -> None:
    path = workspace / "ratings.csv"
    if not path.exists():
        write_csv(path, blank_rows(key, records)); return
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    modes = {row["blindId"]: row["mode"] for row in records}
    for row in rows:
        if row["blindId"] in modes:
            if row["mode"] not in ("UNRUN", modes[row["blindId"]]):
                raise BenchmarkError("RATINGS_ORIGIN_CHANGED")
            row["mode"] = modes[row["blindId"]]
    write_csv(path, rows)


def write_review(workspace: Path, key: dict, records: list[dict]) -> None:
    observed = {row["blindId"]: row for row in records}
    cards = []
    for entry in key["entries"]:
        row = observed.get(entry["blindId"])
        if not row or not row.get("mediaVerified"):
            continue
        blind = entry["blindId"]
        destination = entry["input"]["destination"]
        folder = "blind-media/" + blind
        audio = "".join(f'<label>{label}<audio controls preload="none" src="{folder}/{category}.wav"></audio></label>'
                        for category, label in (("greeting", "인사"), ("common", "공통 대사"), ("arrival", "도착")))
        cards.append(f'<article><h2>{blind}</h2><p class="mode">{escape(row["mode"])}</p>'
                     f'<p>{escape(destination["name"])} · {escape(destination["traits"])} · '
                     f'{escape(entry["input"]["purpose"])}</p><div class="images">'
                     f'<img width="256" height="256" src="{folder}/image.png" alt="동반자 원본">'
                     f'<img width="128" height="128" src="{folder}/image.png" alt="128 픽셀 동반자">'
                     f'<img width="64" height="64" src="{folder}/image.png" alt="64 픽셀 동반자"></div>{audio}</article>')
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><title>Nunti 블라인드 평가</title>'
            '<style>body{max-width:950px;margin:32px auto;padding:0 20px;font:16px sans-serif;color:#243e3c;background:#f6f3ed}'
            'article{padding:24px;margin:24px 0;background:white;border:1px solid #c9d7d1;border-radius:12px}'
            '.images{display:flex;align-items:center;gap:20px;flex-wrap:wrap}.images img{object-fit:contain;background:#e4eeea}'
            'label{display:block;margin-top:14px}audio{display:block;width:min(100%,480px);margin-top:5px}.mode{font-weight:bold}</style>'
            '<h1>Nunti 블라인드 평가</h1><p>식별자는 ratings.csv의 blindId와 같습니다. 공급자 키는 평가가 끝난 뒤에 확인합니다.</p>'
            '<p>OFFLINE_FIXTURE는 기존 이미지와 음성의 연결 시험입니다. 새 생성 품질로 평가하거나 채택하지 않습니다.</p>'
            + ''.join(cards) + '</html>')
    (workspace / "review.html").write_text(page, encoding="utf-8")


def run(workspace: Path, config_path: Path, phase: str, profile_name: str | None,
        limit: int, allow_api=False, poll_seconds=900, client_factory=Client, base_override=None) -> dict:
    key, config = load_key(workspace / "blind-key.json"), load(config_path)
    if base_override:
        if profile_name not in PROFILES:
            raise BenchmarkError("BASE_OVERRIDE_REQUIRES_PROFILE")
        config["serverProfiles"][profile_name]["baseUrl"] = base_override
    if phase == "validation" and profile_name not in PROFILES:
        raise BenchmarkError("VALIDATION_PROFILE_REQUIRED")
    if not 1 <= limit <= 26:
        raise BenchmarkError("INVALID_REQUEST_LIMIT")
    limits = config["limits"]
    per_job = money(limits["perGenerationUsd"], positive=True)
    if per_job > Decimal("0.30") or not 1 <= limits["maximumRequests"] <= 26:
        raise BenchmarkError("BENCHMARK_LIMIT_EXCEEDED")
    ledger_path = workspace / "runner-ledger.json"
    ledger = load(ledger_path) if ledger_path.exists() else {"schemaVersion": 1, "records": []}
    records = ledger["records"]
    if phase == "validation":
        existing_profiles = {entry["profile"] for entry in key["entries"]
                             if entry["phase"] == phase and entry["profile"] is not None}
        if existing_profiles and existing_profiles != {profile_name}:
            raise BenchmarkError("VALIDATION_PROFILE_ALREADY_BOUND")
        for entry in key["entries"]:
            if entry["phase"] == phase:
                entry["profile"] = profile_name
        atomic_json(workspace / "blind-key.json", key)
    by_id = {row["blindId"]: row for row in records}
    planned = sorted((entry for entry in key["entries"] if entry["phase"] == phase
                      and (profile_name is None or entry["profile"] == profile_name)),
                     key=lambda row: (row["caseId"], row["profile"]))
    pending = []
    for entry in planned:
        observed = by_id.get(entry["blindId"], {})
        if (observed.get("state") != "READY" or observed.get("mediaVerified") is not True
                or (observed.get("mode") == "API" and observed.get("actualUsd") is None)):
            pending.append(entry)
    pending = pending[:limit]
    used_reservations = sum((money(row["reservedUsd"]) for row in records if row["phase"] == phase), Decimal(0))
    new_count = sum(entry["blindId"] not in by_id for entry in pending)
    phase_budget = money(limits["comparisonBudgetUsd" if phase == "compare" else "validationBudgetUsd"], positive=True)
    if used_reservations + per_job * new_count > phase_budget or len(records) + new_count > limits["maximumRequests"]:
        raise BenchmarkError("EXPERIMENT_BUDGET_REACHED")
    clients = {}
    # Preflight every scheduled server before the first mutation. Capabilities call no provider.
    for name in sorted({entry["profile"] for entry in pending}):
        server = config["serverProfiles"][name]
        if server["mode"] == "API" and not allow_api:
            raise BenchmarkError("API_RUN_REQUIRES_ALLOW_API")
        client = client_factory(server, config_path)
        capability = client.request("/v2/generation-capabilities")
        if capability.get("mode") != server["mode"] or capability.get("pipeline") != server["expectedPipeline"]:
            raise BenchmarkError("SERVER_MODE_OR_PIPELINE_MISMATCH")
        if money(capability.get("characterBudgetMicros"), positive=True) > per_job * 1_000_000:
            raise BenchmarkError("SERVER_CHARACTER_CAP_TOO_HIGH")
        clients[name] = client
    completed = 0
    for entry in pending:
        client = clients[entry["profile"]]
        row = by_id.get(entry["blindId"])
        if row is None:
            if any(previous["mode"] == "API" and (previous["state"] == "RESULT_UNKNOWN" or previous.get("actualUsd") is None)
                   for previous in records):
                raise BenchmarkError("UNRESOLVED_API_OUTCOME_OR_COST_NO_NEW_POST")
            row = {"blindId": entry["blindId"], "caseId": entry["caseId"], "phase": phase,
                   "profile": entry["profile"], "mode": client.mode,
                   "serverBase": client.base,
                   "requestId": entry["input"]["requestId"], "state": "SUBMITTING",
                   "reservedUsd": float(per_job), "actualUsd": None, "costStatus": "COST_UNKNOWN"}
            records.append(row); by_id[row["blindId"]] = row
            atomic_json(ledger_path, ledger)  # Crash before or during POST is never replayed as a new POST.
            try:
                data = client.request("/v2/character-generations", entry["input"])
            except BenchmarkError:
                row["state"] = "RESULT_UNKNOWN"; atomic_json(ledger_path, ledger)
                raise
        else:
            if row.get("serverBase") != client.base:
                raise BenchmarkError("SAVED_SERVER_BASE_CHANGED")
            # Only GET after any previous submission attempt, including ambiguous outcomes.
            data = client.request("/v2/jobs/" + row["requestId"])
        start = time.monotonic()
        while True:
            if data.get("requestId") != row["requestId"] or data.get("mode") != row["mode"]:
                raise BenchmarkError("SERVER_JOB_IDENTITY_CHANGED")
            state = data.get("state")
            if state not in {"QUEUED", "RUNNING", *TERMINAL}:
                raise BenchmarkError("INVALID_JOB_STATE")
            row["state"] = state
            row["actualUsd"], row["costStatus"] = actual_cost(data)
            atomic_json(ledger_path, ledger)
            if state in TERMINAL:
                break
            if time.monotonic() - start >= poll_seconds:
                raise BenchmarkError("POLL_TIMEOUT_NO_RESUBMISSION")
            time.sleep(.25)
            data = client.request("/v2/jobs/" + row["requestId"])
        atomic_json(workspace / "private-results" / (row["blindId"] + ".json"), data)
        if state != "READY":
            raise BenchmarkError("TERMINAL_GENERATION_FAILURE")
        artifact = data.get("artifact")
        expected_input = json.dumps(entry["input"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if (not isinstance(artifact, dict) or artifact.get("mode") != row["mode"]
                or artifact.get("journeyId") != row["requestId"]
                or artifact.get("inputSha256") != hashlib.sha256(expected_input.encode()).hexdigest()):
            raise BenchmarkError("INVALID_CHARACTER_ARTIFACT")
        row["characterId"] = artifact["characterId"]
        save_blind_media(client, artifact, workspace / "blind-media" / row["blindId"])
        row["mediaVerified"] = True
        atomic_json(ledger_path, ledger)
        refresh_ratings(workspace, key, records)
        write_review(workspace, key, records)
        completed += 1
        if row["mode"] == "API" and row["actualUsd"] is None:
            raise BenchmarkError("ACTUAL_COST_UNKNOWN_BATCH_STOPPED")
        if row["actualUsd"] is not None and money(row["actualUsd"]) > per_job:
            raise BenchmarkError("ACTUAL_CHARACTER_COST_EXCEEDED")
    return {"status": "RUN_COMPLETE", "completedThisRun": completed,
            "actualUsd": None if any(row.get("actualUsd") is None for row in records) else sum(row["actualUsd"] for row in records),
            "fixtureIsQualityEvidence": False}


def evaluate(workspace: Path, ratings_path: Path) -> dict:
    key = load_key(workspace / "blind-key.json")
    ledger_path = workspace / "runner-ledger.json"
    records = load(ledger_path)["records"] if ledger_path.exists() else []
    mapping = {entry["blindId"]: entry for entry in key["entries"]}
    evidence = {row["blindId"]: row for row in records}
    grouped = {}
    seen = set()
    try:
        with ratings_path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != CSV_FIELDS:
                raise BenchmarkError("INVALID_RATING_COLUMNS")
            for row in reader:
                if row["mode"] == "OFFLINE_FIXTURE":
                    raise BenchmarkError("FIXTURE_OR_UNRUN_IS_NOT_QUALITY_EVIDENCE")
                if not any(row[field].strip() for field in DIMENSIONS):
                    continue
                if row["blindId"] not in mapping or row["blindId"] not in evidence:
                    raise BenchmarkError("RATING_HAS_NO_RUN_EVIDENCE")
                entry, observed = mapping[row["blindId"]], evidence[row["blindId"]]
                if row["mode"] != "API" or observed["mode"] != "API":
                    raise BenchmarkError("FIXTURE_OR_UNRUN_IS_NOT_QUALITY_EVIDENCE")
                if (observed["state"] != "READY" or observed.get("mediaVerified") is not True
                        or observed.get("profile") != entry["profile"] or row["phase"] != entry["phase"]):
                    raise BenchmarkError("RATING_ORIGIN_MISMATCH")
                rater = row["raterId"].strip()
                if not rater or (row["blindId"], rater) in seen:
                    raise BenchmarkError("MISSING_OR_DUPLICATE_RATER")
                seen.add((row["blindId"], rater))
                values = {field: money(row[field], positive=True) for field in DIMENSIONS}
                if any(value < 1 or value > 5 for value in values.values()):
                    raise BenchmarkError("RATINGS_MUST_BE_1_TO_5")
                grouped.setdefault((entry["phase"], entry["profile"]), {}).setdefault(entry["caseId"], []).append(values)
    except OSError as exc:
        raise BenchmarkError("RATINGS_FILE_UNAVAILABLE") from exc

    summaries = {}
    for (phase, profile), cases in grouped.items():
        # Each journey has equal weight even when journeys have different rater counts.
        means = {field: sum(sum(values[field] for values in ratings) / len(ratings)
                           for ratings in cases.values()) / len(cases) for field in DIMENSIONS}
        members = [row for row in records if row["phase"] == phase and row["profile"] == profile]
        adopted = sum(row["state"] == "READY" and row.get("mediaVerified") is True for row in members)
        known = bool(members) and all(row.get("actualUsd") is not None and row.get("costStatus") == "MEASURED" for row in members)
        budget_ok = known and all(money(row["actualUsd"]) <= Decimal("0.30") for row in members)
        cost = sum(money(row["actualUsd"]) for row in members) / adopted if known and adopted else None
        expected = 6 if phase == "compare" else 14
        summaries[f"{phase}:{profile}"] = {"profile": profile, "phase": phase, "ratedDistinctInputs": len(cases),
            "dimensionMeans": {field: float(value) for field, value in means.items()},
            "qualityScore": float(sum(means.values()) / len(DIMENSIONS)),
            "qualityGate": len(cases) == expected and all(value >= 4 for value in means.values()),
            "costCapGate": budget_ok,
            "adoptedCharacterCostUsd": float(cost) if cost is not None else None,
            "costStatus": "MEASURED" if cost is not None else "COST_UNKNOWN"}
    eligible = [summary for key, summary in summaries.items() if key.startswith("compare:") and summary["qualityGate"]
                and (summary["costCapGate"] or summary["costStatus"] == "COST_UNKNOWN")]
    chosen = None
    reason = "QUALITY_GATE_NOT_MET_OR_INCOMPLETE"
    if eligible:
        eligible.sort(key=lambda row: row["qualityScore"], reverse=True)
        tied = [row for row in eligible if Decimal(str(eligible[0]["qualityScore"])) - Decimal(str(row["qualityScore"])) <= Decimal("0.2")]
        if any(row["adoptedCharacterCostUsd"] is None for row in tied):
            reason = "TIED_OR_SINGLE_CANDIDATE_COST_UNKNOWN"
        else:
            chosen = min(tied, key=lambda row: (row["adoptedCharacterCostUsd"], -row["qualityScore"], row["profile"]))["profile"]
            reason = "QUALITY_FIRST_MEASURED_COST_WITHIN_POINT_TWO"
    validation = summaries.get(f"validation:{chosen}") if chosen else None
    final = bool(validation and validation["qualityGate"] and validation["costCapGate"])
    if chosen and validation and not final:
        reason = "NEW_VALIDATION_GATE_NOT_MET"
    report = {"schemaVersion": 1,
              "status": "ADOPTED_PROFILE_SELECTED" if final else "PROVISIONAL_PROFILE_SELECTED" if chosen and not validation else "NOT_ADOPTED",
              "selectedProfile": chosen if final else None, "provisionalProfile": chosen,
              "reason": reason, "summaries": summaries, "humanQualityApproved": final,
              "fixtureIsQualityEvidence": False, "costUnknownAsZero": False}
    atomic_json(workspace / "evaluation.json", report)
    return report


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.workspace = Path(self.temp.name)
        prepare(self.workspace)

    def tearDown(self):
        self.temp.cleanup()

    def rate(self, primary=4.5, value=4.4, cost_primary=.2, cost_value=.1, *, mode="API", validation=False):
        key = load(self.workspace / "blind-key.json")
        rows, records = [], []
        for entry in key["entries"]:
            if entry["phase"] == "validation":
                if not validation:
                    continue
                entry["profile"] = "value"
            profile = entry["profile"]
            records.append({"blindId": entry["blindId"], "caseId": entry["caseId"], "phase": entry["phase"],
                            "profile": profile, "mode": mode, "state": "READY", "mediaVerified": True,
                            "actualUsd": cost_primary if profile == "primary" else cost_value, "costStatus": "MEASURED"})
            rows.append({"blindId": entry["blindId"], "phase": entry["phase"], "mode": mode, "raterId": "rater-1",
                         **{field: primary if profile == "primary" else value for field in DIMENSIONS}, "notes": "self-test only"})
        atomic_json(self.workspace / "blind-key.json", key)
        atomic_json(self.workspace / "runner-ledger.json", {"records": records})
        path = self.workspace / "ratings.csv"; write_csv(path, rows)
        return path

    def test_twenty_inputs_twenty_six_outputs_and_prepare_preserves(self):
        self.assertEqual(len(load(self.workspace / "inputs.json")["cases"]), 20)
        key = self.workspace / "blind-key.json"; before = key.read_bytes()
        self.assertEqual(len(load(key)["entries"]), 26)
        self.assertEqual(prepare(self.workspace)["status"], "ALREADY_PREPARED_PRESERVED")
        self.assertEqual(before, key.read_bytes())

    def test_quality_first_over_cheaper(self):
        report = evaluate(self.workspace, self.rate(primary=4.8, value=4.4))
        self.assertEqual(report["provisionalProfile"], "primary")
        self.assertFalse(report["humanQualityApproved"])

    def test_close_quality_uses_measured_cost(self):
        self.assertEqual(evaluate(self.workspace, self.rate())["provisionalProfile"], "value")

    def test_each_dimension_has_gate(self):
        path = self.rate()
        with path.open(newline="") as stream: rows = list(csv.DictReader(stream))
        for row in rows: row["voiceFit"] = "3.9"
        write_csv(path, rows)
        self.assertEqual(evaluate(self.workspace, path)["status"], "NOT_ADOPTED")

    def test_unknown_cost_never_zero(self):
        report = evaluate(self.workspace, self.rate(cost_value=None))
        self.assertIsNone(report["provisionalProfile"])
        self.assertIsNone(report["summaries"]["compare:value"]["adoptedCharacterCostUsd"])
        self.assertEqual(actual_cost({}), (None, "COST_UNKNOWN"))
        self.assertEqual(actual_cost({"cost": {"complete": False, "actualMicros": 0}}), (None, "COST_UNKNOWN"))

    def test_fixture_never_adopts(self):
        with self.assertRaisesRegex(BenchmarkError, "FIXTURE_OR_UNRUN"):
            evaluate(self.workspace, self.rate(mode="OFFLINE_FIXTURE"))

    def test_fourteen_new_validation_required(self):
        report = evaluate(self.workspace, self.rate(validation=True))
        self.assertEqual(report["status"], "ADOPTED_PROFILE_SELECTED")
        self.assertEqual(report["selectedProfile"], "value")

    def test_partial_ratings_and_duplicate_rejected(self):
        path = self.rate()
        with path.open(newline="") as stream: rows = list(csv.DictReader(stream))
        rows.append(rows[0]); write_csv(path, rows)
        with self.assertRaisesRegex(BenchmarkError, "DUPLICATE"):
            evaluate(self.workspace, path)

    def test_invalid_cost_and_score(self):
        for value in (None, True, "NaN", -1):
            with self.assertRaises(BenchmarkError): money(value)
        with self.assertRaises(BenchmarkError): actual_cost({"cost": {"complete": True, "actualMicros": 1.2}})
        path = self.rate(primary=5.1)
        with self.assertRaisesRegex(BenchmarkError, "1_TO_5"): evaluate(self.workspace, path)
        path = self.rate(primary=.5)
        with self.assertRaisesRegex(BenchmarkError, "1_TO_5"): evaluate(self.workspace, path)

    def test_cost_above_operating_cap_never_adopts(self):
        report = evaluate(self.workspace, self.rate(cost_primary=.31, cost_value=.32))
        self.assertEqual(report["status"], "NOT_ADOPTED")

    def test_api_flag_prevents_client_or_network(self):
        config = load(self.workspace / "runner-config.json")
        for profile in config["serverProfiles"].values(): profile["mode"] = "API"
        config_path = self.workspace / "runner-config.json"; atomic_json(config_path, config)
        def no_client(*args): raise AssertionError("Network client must not be created")
        with self.assertRaisesRegex(BenchmarkError, "ALLOW_API"):
            run(self.workspace, config_path, "compare", None, 1, client_factory=no_client)

    def test_experiment_cap_before_network(self):
        config = load(self.workspace / "runner-config.json"); config["limits"]["comparisonBudgetUsd"] = .29
        config_path = self.workspace / "runner-config.json"; atomic_json(config_path, config)
        def no_client(*args): raise AssertionError("Network client must not be created")
        with self.assertRaisesRegex(BenchmarkError, "BUDGET"):
            run(self.workspace, config_path, "compare", None, 1, client_factory=no_client)

    def test_explicit_zero_is_measured_but_missing_is_unknown(self):
        self.assertEqual(actual_cost({"cost": {"complete": True, "actualMicros": 0}}), (0.0, "MEASURED"))
        self.assertEqual(actual_cost({"cost": {"complete": True, "actualMicros": None}}), (None, "COST_UNKNOWN"))

    def fake_client(self, *, mode="OFFLINE_FIXTURE", fail_post=False, unknown_cost=False, mismatch=False):
        calls = []
        binaries = {"image": b"mock transport image bytes", "audio": b"mock transport audio bytes"}
        digests = {name: hashlib.sha256(value).hexdigest() for name, value in binaries.items()}
        entries = load_key(self.workspace / "blind-key.json")["entries"]
        bodies = {entry["input"]["requestId"]: entry["input"] for entry in entries}

        class FakeClient:
            def __init__(self, server, config_path):
                self.mode, self.base = mode, server["baseUrl"]
                self.pipeline = server["expectedPipeline"]

            def request(self, path, body=None, **kwargs):
                calls.append((path, body is not None))
                if path.endswith("generation-capabilities"):
                    return {"mode": "API" if mismatch else mode, "pipeline": self.pipeline, "characterBudgetMicros": 300000}
                if kwargs.get("binary"):
                    return binaries["image"] if path.endswith(digests["image"]) else binaries["audio"]
                if body is not None and fail_post:
                    raise BenchmarkError("SERVER_TRANSPORT_RESULT_UNKNOWN")
                request_id = body["requestId"] if body else path.rsplit("/", 1)[1]
                canonical = json.dumps(bodies[request_id], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                artifact = {"mode": mode, "characterId": "mock-" + request_id, "journeyId": request_id,
                    "inputSha256": hashlib.sha256(canonical.encode()).hexdigest(),
                    "visual": {"asset": {"sha256": digests["image"], "path": "/v2/assets/" + digests["image"]}},
                    "voiceManifest": {"clips": [{"clipId": "mock-" + category, "audioSha256": digests["audio"]}
                                                for category in ("greeting", "common", "arrival")]}}
                return {"requestId": request_id, "mode": mode, "state": "READY", "artifact": artifact,
                        "cost": {"complete": not unknown_cost, "actualMicros": None if unknown_cost else 0}}
        return FakeClient, calls

    def test_ambiguous_post_resumes_by_get_without_repost(self):
        config = self.workspace / "runner-config.json"
        failing, first_calls = self.fake_client(fail_post=True)
        with self.assertRaisesRegex(BenchmarkError, "RESULT_UNKNOWN"):
            run(self.workspace, config, "compare", "primary", 1, client_factory=failing)
        resumed, resumed_calls = self.fake_client()
        result = run(self.workspace, config, "compare", "primary", 1, client_factory=resumed)
        self.assertEqual(result["completedThisRun"], 1)
        self.assertEqual(sum(is_post for _, is_post in first_calls), 1)
        self.assertEqual(sum(is_post for _, is_post in resumed_calls), 0)
        self.assertTrue(any(path.startswith("/v2/jobs/") for path, _ in resumed_calls))

    def test_api_unknown_cost_stops_batch_after_one_post(self):
        config_path = self.workspace / "runner-config.json"
        config = load(config_path)
        config["serverProfiles"]["primary"]["mode"] = "API"
        atomic_json(config_path, config)
        fake, calls = self.fake_client(mode="API", unknown_cost=True)
        with self.assertRaisesRegex(BenchmarkError, "ACTUAL_COST_UNKNOWN"):
            run(self.workspace, config_path, "compare", "primary", 2, allow_api=True, client_factory=fake)
        self.assertEqual(sum(is_post for _, is_post in calls), 1)
        row = load(self.workspace / "runner-ledger.json")["records"][0]
        self.assertIsNone(row["actualUsd"])

    def test_changed_server_mode_rejects_before_submission(self):
        fake, calls = self.fake_client(mismatch=True)
        with self.assertRaisesRegex(BenchmarkError, "MODE_OR_PIPELINE"):
            run(self.workspace, self.workspace / "runner-config.json", "compare", "primary", 1, client_factory=fake)
        self.assertFalse(any(is_post for _, is_post in calls))

    def test_workspace_excludes_concurrent_writer(self):
        with workspace_lock(self.workspace):
            with self.assertRaisesRegex(BenchmarkError, "ALREADY_RUNNING"):
                with workspace_lock(self.workspace):
                    self.fail("Second writer acquired the lock")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--evaluate", type=Path, metavar="RATINGS_CSV")
    action.add_argument("--run", action="store_true")
    action.add_argument("--self-test", action="store_true")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--phase", choices=("compare", "validation"), default="compare")
    parser.add_argument("--profile", choices=PROFILES)
    parser.add_argument("--base", help="Override one selected profile's Nunti server base; requires --profile")
    parser.add_argument("--limit", type=int, default=1, help="Maximum additional or resumed jobs; default 1")
    parser.add_argument("--allow-api", action="store_true", help="Explicit opt-in for configured API servers")
    parser.add_argument("--poll-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BenchmarkTests))
        return 0 if result.wasSuccessful() else 1
    try:
        with workspace_lock(args.workspace):
            if args.prepare:
                result = prepare(args.workspace)
            elif args.evaluate:
                result = evaluate(args.workspace, args.evaluate)
            else:
                if not 1 <= args.poll_seconds <= 1800:
                    raise BenchmarkError("INVALID_POLL_TIMEOUT")
                result = run(args.workspace, args.config or args.workspace / "runner-config.json",
                             args.phase, args.profile, args.limit, args.allow_api, args.poll_seconds,
                             base_override=args.base)
        print(encode(result), end="")
        return 0
    except BenchmarkError as exc:
        print(encode({"status": "STOPPED", "error": str(exc), "newProviderFallback": False}), end="")
        return 2
    except (KeyError, TypeError, AttributeError, OSError, ValueError):
        print(encode({"status": "STOPPED", "error": "INVALID_CONFIG_OR_EVIDENCE", "newProviderFallback": False}), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
