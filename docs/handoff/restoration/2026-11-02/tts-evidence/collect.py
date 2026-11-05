#!/usr/bin/env python3
"""Preserve fresh verification outputs and check every locked dependency hash."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[4]
    tools = Path("/Users/pig30nidae/NUNTI/.local/tts-tools")
    dependencies = json.loads((root / "android/feature/tts/scripts/toolchain-lock.json").read_text())
    for item in dependencies:
        artifact = tools / "artifacts" / item["name"]
        actual = sha256(artifact)
        if actual != item["sha256"]:
            raise ValueError("Dependency hash mismatch: " + item["name"])
        item.update(actualSha256=actual, size=artifact.stat().st_size)
    verification = root / "android/feature/tts/build/verification"
    required = {
        "tests.txt": "62 tests passed; 0 failed",
        "integration.txt": "8 actual-fixture integration checks passed",
        "android-compile.txt": "runtime NOT tested.",
    }
    for filename, marker in required.items():
        if marker not in (verification / filename).read_text():
            raise ValueError("Missing verification result: " + filename)
    products = []
    for path in sorted(verification.iterdir()):
        if path.is_file():
            products.append({"path": str(path.relative_to(root)), "sha256": sha256(path), "size": path.stat().st_size})
            if path.suffix in (".txt", ".properties"):
                shutil.copy2(path, evidence / path.name)
    jdk = tools / "OpenJDK21U-jdk_aarch64_mac_hotspot_21.0.8_9.tar.gz"
    expected = "59422c2292ae4e76b87e00d8808dbe49cffa39af731e08bb0292ddb0af4e0261"
    if sha256(jdk) != expected:
        raise ValueError("JDK archive hash mismatch")
    shutil.copy2(jdk.with_suffix(jdk.suffix + ".sha256.txt"), evidence / "jdk-official.sha256.txt")
    report = {
        "capturedAt": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True).strip(),
        "python": {"version": sys.version, "executable": sys.executable},
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "javaHome": os.environ.get("JAVA_HOME"),
        "jdk": {
            "version": "Temurin 21.0.8+9",
            "archive": str(jdk),
            "sha256": expected,
            "source": "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.8%2B9/" + jdk.name,
            "checksumSource": "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.8%2B9/" + jdk.name + ".sha256.txt",
            "acquisition": "Downloaded with curl. Initial sandbox DNS failure exit 6; escalated checksum and archive download exit 0. Exact acquisition timestamps were not captured. The checksum was rerun and captured by capture.py.",
        },
        "dependencies": dependencies,
        "products": products,
        "newVerification": {"jvmTests": 62, "fixtureChecks": 8, "mockScenarios": ["A", "B", "C", "D"], "androidBinaryCompilation": True, "runtimeTested": False},
    }
    (evidence / "environment-and-artifacts.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"dependenciesVerified": len(dependencies), "products": len(products), "newVerification": report["newVerification"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
