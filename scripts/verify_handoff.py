#!/usr/bin/env python3
"""Check handoff documents and preserved evidence without running the app."""

import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit, urlunsplit
import wave


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "docs/handoff"
EVIDENCE = ROOT / "docs/architecture/validation-evidence"
RUNTIME = EVIDENCE / "pleos-runtime"
FINAL_REQUEST = "probe-490bbbf0-93c5-40bd-b3bc-3fd3655ee1ad"
REQUIRED = [
    "README.md", "STATUS.md", "RELOCATION.md",
    "prompts/pm.md", "prompts/tts.md", "prompts/avatar.md", "prompts/server.md",
    "reports/tts.md", "reports/avatar.md", "reports/server.md",
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inside_repo(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Local target escapes the repository")
    return path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(results, name, operation):
    try:
        detail = operation()
        results.append({"check": name, "ok": True, "detail": detail})
    except Exception as exc:
        results.append({"check": name, "ok": False, "error": str(exc)})


def document(path):
    text = path.read_text(encoding="utf-8")
    require(bool(text.strip()), "Document is empty")
    return {"bytes": path.stat().st_size}


def markdown_targets(text):
    # Ignore examples in fenced blocks and inline code. Include reference targets.
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    text = re.sub(r"`[^`\n]*`", "", text)
    inline = re.findall(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)", text)
    references = re.findall(r"(?m)^\s*\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)", text)
    return [target.strip("<>") for target in inline + references]


def local_link(source, target):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("#"):
        return {"externalOrAnchor": True}
    path_text = unquote(parsed.path)
    if not path_text:
        return {"sameDocument": True}
    path = inside_repo(source.parent / path_text)
    require(path.exists(), "Local link target does not exist")
    return {"target": str(path.relative_to(ROOT))}


def hashes(results, manifest_path, field):
    def load():
        values = read_json(manifest_path)[field]
        require(isinstance(values, dict) and bool(values), "Hash mapping is empty or invalid")
        return values

    try:
        values = load()
    except Exception as exc:
        results.append({"check": str(manifest_path.relative_to(ROOT)), "ok": False, "error": str(exc)})
        return
    for name, expected in values.items():
        def compare(name=name, expected=expected):
            path = inside_repo(manifest_path.parent / name)
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(actual == expected, "SHA-256 mismatch")
            return {"sha256": actual}
        check(results, "sha256:" + str(manifest_path.parent.relative_to(ROOT) / name), compare)


def speech_events():
    events = [json.loads(line) for line in (RUNTIME / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    final = [event for event in events if event.get("kind") == "SPEECH" and event.get("requestId") == FINAL_REQUEST]
    require([event.get("status") for event in final] == ["QUEUED", "STARTED", "COMPLETED"], "Final request status sequence differs")
    require(final[1].get("startLatencyMs") == 41, "Final request startLatencyMs is not 41")
    require(all(event.get("mode") == "ON_DEVICE" for event in final), "Final request mode differs")
    require([event["at"] for event in final] == sorted(event["at"] for event in final), "Final request timestamps are out of order")
    return {"requestId": FINAL_REQUEST, "statuses": [event["status"] for event in final], "startLatencyMs": 41}


def lifecycle(results):
    try:
        cases = read_json(RUNTIME / "lifecycle-results.json")
        require(isinstance(cases, list), "Lifecycle evidence must be a list")
    except Exception as exc:
        results.append({"check": "lifecycle", "ok": False, "error": str(exc)})
        return
    expected = {
        "stop": ("CANCELLED", "USER_CANCELLED"),
        "repeat_after_stop": ("REJECTED", "REPEATED_TEXT"),
        "background": ("CANCELLED", "BACKGROUND"),
        "repeat_after_background": ("REJECTED", "REPEATED_TEXT"),
    }
    for name, outcome in expected.items():
        def compare(name=name, outcome=outcome):
            matches = [case for case in cases if case.get("case") == name]
            require(len(matches) == 1, "Lifecycle case missing or duplicated")
            value = matches[0]
            terminal = value["terminal"]
            require((terminal.get("status"), terminal.get("reason")) == outcome, "Lifecycle status or reason differs")
            if name in ("stop", "background"):
                started = value["started"]
                require(started.get("status") == "STARTED" and started.get("requestId") == terminal.get("requestId"), "Lifecycle STARTED event differs")
                require(started["at"] <= terminal["at"], "Lifecycle timestamps are out of order")
            return {"status": outcome[0], "reason": outcome[1]}
        check(results, "lifecycle:" + name, compare)


def wav_stats(json_path):
    expected = read_json(json_path)
    path = inside_repo(json_path.parent / expected["file"])
    with wave.open(str(path), "rb") as audio:
        rate, width, channels = audio.getframerate(), audio.getsampwidth(), audio.getnchannels()
        require((rate, width, channels, audio.getcomptype()) == (48000, 2, 2, "NONE"), "WAV format differs from 48kHz/16bit/stereo PCM")
        frames = audio.getnframes()
        samples = array.array("h", audio.readframes(frames))
    if sys.byteorder != "little":
        samples.byteswap()
    require(len(samples) == frames * channels and bool(samples), "WAV sample count is invalid")
    actual = {
        "durationSeconds": frames / rate,
        "samples": len(samples),
        "nonzeroSamples": sum(value != 0 for value in samples),
        "peak": max(abs(value) for value in samples),
        "rms": math.sqrt(sum(value * value for value in samples) / len(samples)),
    }
    for name, value in actual.items():
        match = math.isclose(value, expected[name], rel_tol=1e-9, abs_tol=1e-9) if name in ("durationSeconds", "rms") else value == expected[name]
        require(match, "WAV statistic differs: " + name)
    return {"rate": rate, "sampleWidthBytes": width, "channels": channels, **actual}


def git_value(*args):
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def origin_url():
    value = git_value("remote", "get-url", "origin")
    if value and "://" in value:
        parts = urlsplit(value)
        host = parts.netloc.rsplit("@", 1)[-1]
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Also write the JSON result to this path")
    args = parser.parse_args()
    results = []
    for name in REQUIRED:
        check(results, "document:" + name, lambda name=name: document(HANDOFF / name))
    for source in sorted(HANDOFF.rglob("*.md")):
        try:
            targets = markdown_targets(source.read_text(encoding="utf-8"))
        except Exception as exc:
            results.append({"check": "links:" + str(source.relative_to(ROOT)), "ok": False, "error": str(exc)})
            continue
        for target in targets:
            check(results, "link:" + str(source.relative_to(ROOT)) + ":" + target,
                  lambda source=source, target=target: local_link(source, target))
    hashes(results, RUNTIME / "manifest.json", "artifacts")
    hashes(results, EVIDENCE / "root-integration.json", "files")
    check(results, "final-speech-events", speech_events)
    lifecycle(results)
    for name in ("tts-first", "tts-final"):
        check(results, "wav:" + name, lambda name=name: wav_stats(RUNTIME / (name + ".json")))
    report = {
        "scope": "Checks handoff files and preserved evidence only. No new application tests, vehicle playback, human listening, or driving transition verification is performed.",
        "git": {"head": git_value("rev-parse", "HEAD"), "origin": origin_url()},
        "ok": all(result["ok"] for result in results),
        "passed": sum(result["ok"] for result in results),
        "failed": sum(not result["ok"] for result in results),
        "checks": results,
    }
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            report["ok"] = False
            report["failed"] += 1
            report["checks"].append({"check": "output", "ok": False, "error": str(exc)})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
