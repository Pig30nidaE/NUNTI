#!/usr/bin/env python3
"""Run Gradle with caches, Android preferences, signing home, and temp isolated."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent.parents[4]
    local = root / ".local"
    for name in ("gradle-user", "android-user", "home", "tmp"):
        (local / name).mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    settings = {
        "JAVA_HOME": "/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home",
        "ANDROID_HOME": "/Users/pig30nidae/NUNTI/.local/pm-tools/sdk",
        "ANDROID_USER_HOME": str(local / "android-user"),
        "GRADLE_USER_HOME": str(local / "gradle-user"),
        "JAVA_TOOL_OPTIONS": "-Duser.home=" + str(local / "home") + " -Djava.io.tmpdir=" + str(local / "tmp"),
    }
    environment.update(settings)
    command = ["./gradlew", "--no-daemon", "--max-workers=4", "-Pkotlin.compiler.execution.strategy=in-process", *sys.argv[1:]]
    print(json.dumps({"cwd": str(root / "android"), "environment": settings, "command": command}), flush=True)
    return subprocess.run(command, cwd=root / "android", env=environment).returncode


if __name__ == "__main__":
    sys.exit(main())
