#!/usr/bin/env python3
"""Run isolated backend/JavaScript/JVM checks; never connect to the emulator.

The tests mock network/model boundaries. Existing local SDK/cache paths are used
offline. Logs and source hashes distinguish this result from runtime UI proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc  # noqa: UP017 - the system Python used by this CLI is 3.9


def snapshot():
    files = sorted(
        set(ROOT.glob("prototypes/avatar_generator/*.js"))
        | set(ROOT.glob("prototypes/avatar_generator/*.html"))
        | set(ROOT.glob("prototypes/avatar_generator/*.css"))
        | set(ROOT.glob("backend/nunti/avatar_studio/*.py"))
        | set(ROOT.glob("scripts/test*.mjs"))
        | set(ROOT.glob("android/feature/score/src/**/*.kt"))
    )
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in files
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only", choices=["all", "backend", "js", "score"], default="all"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = (
        args.output or ROOT / "docs/redesign/integration-v1" / ("regression-" + stamp)
    ).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "report.json").exists():
        parser.error("Choose a new output directory to preserve the previous report")
    env = os.environ.copy()
    env.update(
        JAVA_HOME=str(ROOT / ".local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home"),
        ANDROID_HOME=str(ROOT / ".local/pm-tools/sdk"),
        ANDROID_USER_HOME=str(ROOT / ".worktrees/tts/.local/android-user"),
        GRADLE_USER_HOME=str(ROOT / ".worktrees/tts/.local/gradle-user"),
        PYTHONPATH=str(ROOT / "backend"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
    )
    # Test fixtures supply their own synthetic authentication. Never inherit paid
    # provider credentials into a regression subprocess.
    for key in list(env):
        if key.endswith("API_KEY") or key in {"OPENAI_ADMIN_KEY", "HF_TOKEN"}:
            env.pop(key)
    jobs = []
    if args.only in {"all", "backend"}:
        jobs.append(
            (
                "backend",
                [
                    str(ROOT / ".worktrees/server/backend/.venv/bin/python"),
                    "-m",
                    "pytest",
                    "backend/tests",
                    "-q",
                    "--junitxml=" + str(out / "backend-junit.xml"),
                ],
                ROOT,
            )
        )
    if args.only in {"all", "js"}:
        sources = sorted(ROOT.glob("scripts/test_*_ui_state.mjs"))
        sources += [
            ROOT / "scripts/test_nunti_transformation_state.mjs",
            ROOT / "prototypes/avatar_generator/formation.test.mjs",
        ]
        jobs.extend((source.stem, ["node", str(source)], ROOT) for source in sources)
    if args.only in {"all", "score"}:
        jobs.append(
            (
                "score",
                [
                    "./gradlew",
                    ":feature:score:testDebugUnitTest",
                    "--rerun",
                    "--offline",
                    "--no-daemon",
                ],
                ROOT / "android",
            )
        )
    before = snapshot()

    def run(job):
        name, command, cwd = job
        started = time.monotonic()
        with (out / (name + ".log")).open("w") as log:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        result = {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "exitCode": completed.returncode,
            "seconds": round(time.monotonic() - started, 3),
            "log": name + ".log",
        }
        print(name, "PASS" if completed.returncode == 0 else "FAIL", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, jobs))
    for source in ROOT.glob(
        "android/build/feature/score/test-results/testDebugUnitTest/TEST-*.xml"
    ):
        if args.only in {"all", "score"}:
            shutil.copyfile(source, out / source.name)
    after = snapshot()
    changed = [
        name
        for name in sorted(before.keys() | after.keys())
        if before.get(name) != after.get(name)
    ]
    report = {
        "capturedAt": datetime.now(UTC).isoformat(),
        "status": "PASS" if all(item["exitCode"] == 0 for item in results) else "FAIL",
        "boundary": "Isolated tests only; no emulator, server restart, paid API or runtime pixel claim",
        "sourceBefore": before,
        "sourceAfter": after,
        "changedDuringRun": changed,
        "results": results,
    }
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(str(out / "report.json"))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
