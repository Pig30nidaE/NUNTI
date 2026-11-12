"""Find the JDK, Android SDK and emulator on this machine for the launcher scripts.

Project-local tools under .local/ (one teammate's setup) come first so that setup keeps working;
otherwise the usual machine-wide locations are used. Override with NUNTI_JAVA_HOME / NUNTI_ANDROID_HOME / NUNTI_AVD.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SDK = ROOT / ".local/pm-tools/sdk"
LOCAL_JDK = ROOT / ".local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home"
LOCAL_AVD_HOME = ROOT / ".local/pm-tools/avd"
LOCAL_GRADLE = ROOT / ".worktrees/tts/.local"


def _first(paths, check):
    for p in paths:
        if p and check(Path(p)):
            return Path(p)
    return None


def java_home() -> Path:
    def ok(p):
        return (p / "bin/java").is_file()

    candidates = [
        os.environ.get("NUNTI_JAVA_HOME"),
        LOCAL_JDK,
        os.environ.get("JAVA_HOME"),
        "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
        "/usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
    ]
    found = _first(candidates, ok)
    if found is None:
        out = subprocess.run(
            ["/usr/libexec/java_home", "-v", "21"],
            capture_output=True,
            text=True,
            check=False,
        )
        found = (
            Path(out.stdout.strip())
            if out.returncode == 0 and ok(Path(out.stdout.strip()))
            else None
        )
    if found is None:
        raise RuntimeError(
            "JDK 21을 찾지 못했습니다. brew install openjdk@21 또는 NUNTI_JAVA_HOME 을 설정해 주세요."
        )
    return found


def android_sdk() -> Path:
    def ok(p):
        return (p / "platform-tools/adb").is_file()

    found = _first(
        [
            os.environ.get("NUNTI_ANDROID_HOME"),
            LOCAL_SDK,
            os.environ.get("ANDROID_HOME"),
            os.environ.get("ANDROID_SDK_ROOT"),
            Path.home() / "Library/Android/sdk",
        ],
        ok,
    )
    if found is None:
        raise RuntimeError(
            "Android SDK를 찾지 못했습니다. NUNTI_ANDROID_HOME 을 설정해 주세요."
        )
    return found


SDK = android_sdk()
ADB = SDK / "platform-tools/adb"


def gradle_env() -> dict:
    """Environment for ./gradlew. The teammate's offline Gradle cache is used only if it is there."""
    env = dict(os.environ, JAVA_HOME=str(java_home()), ANDROID_HOME=str(SDK))
    if LOCAL_GRADLE.is_dir():
        env.update(
            ANDROID_USER_HOME=str(LOCAL_GRADLE / "android-user"),
            GRADLE_USER_HOME=str(LOCAL_GRADLE / "gradle-user"),
        )
    return env


def gradle_flags() -> list:
    # --offline only works with a filled cache; a machine without the teammate's cache must download.
    return ["--offline", "--no-daemon"] if LOCAL_GRADLE.is_dir() else ["--no-daemon"]


def emulator_env() -> dict:
    env = dict(os.environ, ANDROID_HOME=str(SDK))
    if LOCAL_AVD_HOME.is_dir():
        env.update(
            ANDROID_USER_HOME=str(ROOT / ".local/pm-tools/android-user"),
            ANDROID_AVD_HOME=str(LOCAL_AVD_HOME),
        )
    return env


def avd_name(preferred: str) -> str:
    """The AVD to start: NUNTI_AVD, else `preferred` if it exists here, else a Pleos AVD, else the first one."""
    if os.environ.get("NUNTI_AVD"):
        return os.environ["NUNTI_AVD"]
    out = subprocess.run(
        [str(SDK / "emulator/emulator"), "-list-avds"],
        env=emulator_env(),
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    if preferred in out or not out:
        return preferred
    return next((a for a in out if "pleos" in a.lower()), out[0])
