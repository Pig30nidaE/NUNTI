#!/usr/bin/env python3
"""Rerun the AVATAR restoration checks without changing product sources."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[4]
TOOLS = ROOT / ".local/avatar-tools"
BUILD = ROOT / ".local/avatar-build"
KOTLIN_SHA256 = "a623871f1cd9c938946948b70ef9170879f0758043885bbd30c32f024e511714"
JSON_SHA256 = "3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796"


def digest(path, algorithm="sha256"):
    return hashlib.new(algorithm, path.read_bytes()).hexdigest()


def timestamp():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()


def main():
    env = os.environ.copy()
    if "JAVA_HOME" not in env:
        raise SystemExit("Set JAVA_HOME to the restored JDK 21 first")
    env["PATH"] = env["JAVA_HOME"] + "/bin:" + env.get("PATH", "")
    env["KOTLINC"] = str(TOOLS / "kotlinc/bin/kotlinc")
    env["JSON_JAR"] = str(TOOLS / "json-20250517.jar")
    env["AVATAR_BUILD_DIR"] = str(BUILD)
    env["CONTRACT_ROOT"] = str(ROOT / "contracts/v1")
    commands = []

    def run(label, command):
        started = timestamp()
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (EVIDENCE / f"{label}.log").write_text(result.stdout)
        commands.append({"label": label, "command": command, "cwd": str(ROOT),
                         "startedAt": started, "endedAt": timestamp(),
                         "exitCode": result.returncode, "log": f"{label}.log"})
        (EVIDENCE / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        print(f"{label}: exit {result.returncode}", flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
        return result.stdout

    archive = TOOLS / "kotlin-compiler-2.2.21.zip"
    json_jar = TOOLS / "json-20250517.jar"
    assert digest(archive) == KOTLIN_SHA256, "Kotlin release SHA-256 mismatch"
    assert digest(json_jar) == JSON_SHA256, "Pinned org.json SHA-256 mismatch"
    assert digest(json_jar, "sha1") == (TOOLS / "json-20250517.jar.sha1").read_text().strip(), "Maven SHA-1 mismatch"
    if not (TOOLS / "kotlinc/bin/kotlinc").exists():
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.testzip() is None, "Kotlin ZIP CRC failure"
            zipped.extractall(TOOLS)
        for path in (TOOLS / "kotlinc/bin").iterdir():
            path.chmod(0o755)
    provenance = {
        "checkedAt": timestamp(),
        "kotlin": {"version": "2.2.21", "sha256": digest(archive),
                   "url": "https://github.com/JetBrains/kotlin/releases/download/v2.2.21/kotlin-compiler-2.2.21.zip",
                   "sha256Source": "https://api.github.com/repos/JetBrains/kotlin/releases/tags/v2.2.21"},
        "orgJson": {"version": "20250517", "sha256": digest(json_jar),
                    "sha1": digest(json_jar, "sha1"),
                    "url": "https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar",
                    "sha1Source": "https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar.sha1"},
        "environment": {key: env[key] for key in ["JAVA_HOME", "KOTLINC", "JSON_JAR", "AVATAR_BUILD_DIR", "CONTRACT_ROOT"]},
    }
    (EVIDENCE / "tool-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    run("git-head", ["git", "rev-parse", "HEAD"])
    run("git-branch", ["git", "branch", "--show-current"])
    run("java-version", [env["JAVA_HOME"] + "/bin/java", "-version"])
    run("kotlin-version", [env["KOTLINC"], "-version"])
    run("handoff-verification", [sys.executable, "scripts/verify_handoff.py", "--output", str(EVIDENCE / "handoff-verification.json")])
    run("avatar-tests", ["bash", "android/feature/avatar/scripts/test.sh"])
    report_dir = BUILD / "reports"
    metrics = json.loads((report_dir / "metrics.json").read_text())
    assert metrics["testsPassed"] == 58
    assert metrics["fixtureCount"] == metrics["deterministicMatches"] == metrics["groundedOutputs"] == metrics["missingEvidenceFallbackSuccesses"] == 1000
    assert metrics["constraintConflicts"] == 0
    shutil.copytree(report_dir, EVIDENCE / "reports", dirs_exist_ok=True)
    hashes = {str(path.relative_to(EVIDENCE)): digest(path) for path in sorted((EVIDENCE / "reports").rglob("*")) if path.is_file()}
    (EVIDENCE / "generated-sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == "__main__":
    main()
