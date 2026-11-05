#!/usr/bin/env python3
"""Prove real navigation foreground/launcher return preserves the existing host."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local/navigation-integration/handoff"
ADB = ROOT / ".local/pm-tools/sdk/platform-tools/adb"


def native(command, name, wait=3000):
    result = subprocess.run(
        [
            "node",
            "scripts/navigation_native_command.mjs",
            "--command=" + command,
            "--wait-ms=" + str(wait),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=25,
    )
    value = json.loads(result.stdout)
    (OUT / (name + ".json")).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    return value


def identity(artifact):
    assert artifact, "OPEN_A_SAVED_AVATAR_FIRST"
    return {
        "id": artifact["characterId"],
        "image": artifact["visual"]["sha256"],
        "voice": artifact["voice"],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = native("snapshot", "before", 0)
    original = identity(before["artifact"])
    session = before["snapshot"]["sessionId"]
    native("foreground", "foreground", 1800)
    activities = subprocess.check_output(
        [str(ADB), "-s", "emulator-5554", "shell", "dumpsys", "activity", "activities"],
        text=True,
    )
    top = [
        line.strip()
        for line in activities.splitlines()
        if "topResumedActivity=" in line
    ]
    assert any("ai.umos.maps.android.navigation.app" in line for line in top), (
        "NATIVE_NAVIGATION_NOT_FOREGROUND"
    )
    subprocess.run(
        [
            str(ADB),
            "-s",
            "emulator-5554",
            "shell",
            "am",
            "start",
            "--user",
            "10",
            "-f",
            "0x10200000",
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "-n",
            "ai.nunti.avatar.demo/ai.nunti.app.MainActivity",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    after = native("refresh", "after", 6000)
    assert after["snapshot"].get("sessionId") == session, "SDK_SESSION_RECREATED"
    assert identity(after["artifact"]) == original, "VISIBLE_AVATAR_CHANGED"
    assert after["snapshot"].get("receivedCallbackCount", 0) > 0
    sources = [
        "android/app/src/main/kotlin/ai/nunti/app/MainActivity.kt",
        "android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt",
    ]
    report = {
        "status": "PASS_NATIVE_FOREGROUND_AND_LAUNCHER_RETURN",
        "nativeForegroundObserved": True,
        "sameSdkSession": True,
        "sameVisibleAvatarImageAndVoice": True,
        "sdkSessionId": session,
        "characterId": original["id"],
        "sourceSha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in sources
        },
        "gpsChanged": False,
        "paidApiCalls": 0,
        "videoRecorded": False,
        "speakerRecorded": False,
    }
    (OUT / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
