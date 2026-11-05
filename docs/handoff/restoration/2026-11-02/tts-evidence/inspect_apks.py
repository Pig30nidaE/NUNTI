#!/usr/bin/env python3
"""Inspect fresh APK manifests, DEX contents, lint issues, and artifact hashes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[4]
    tool = Path("/Users/pig30nidae/NUNTI/.local/pm-tools/sdk/build-tools/35.0.0/aapt2")
    products = {}
    for variant, filename in (("debug", "app-debug.apk"), ("release", "app-release-unsigned.apk")):
        apk = root / "android/build/app/outputs/apk" / variant / filename
        command = [str(tool), "dump", "xmltree", str(apk), "--file", "AndroidManifest.xml"]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (evidence / (variant + "-manifest.txt")).write_text(result.stdout)
        result.check_returncode()
        with zipfile.ZipFile(apk) as archive:
            dex = b"\n".join(archive.read(name) for name in archive.namelist() if name.endswith(".dex"))
        contains_probe = b"Lai/nunti/app/RuntimeProbeActivity;" in dex
        manifest_probe = "RuntimeProbeActivity" in result.stdout
        if contains_probe != (variant == "debug") or manifest_probe != (variant == "debug"):
            raise ValueError("RuntimeProbeActivity packaging mismatch: " + variant)
        required = {
            "voiceSession": b"Lai/nunti/voice/AndroidVoiceSession;",
            "pleosTts": b"Lai/pleos/playground/tts/TextToSpeech;",
        }
        packaged = {name: descriptor in dex for name, descriptor in required.items()}
        if not all(packaged.values()):
            raise ValueError("Voice/Pleos DEX class missing: " + variant)
        products[variant] = {
            "path": str(apk), "size": apk.stat().st_size,
            "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
            "manifestCommand": command,
            "manifestCommandExitCode": result.returncode,
            "runtimeProbeInManifest": manifest_probe,
            "runtimeProbeInDex": contains_probe,
            **packaged,
        }
    lint = root / "android/build/app/reports/lint-results-debug.xml"
    issues = ET.parse(lint).getroot().findall("issue")
    counts = {severity: sum(issue.attrib.get("severity") == severity for issue in issues) for severity in ("Fatal", "Error", "Warning", "Information")}
    if counts["Fatal"] or counts["Error"]:
        raise ValueError("Lint errors present")
    shutil.copy2(lint, evidence / "lint-results-debug.xml")
    report = {
        "products": products,
        "lint": {"counts": counts, "issues": [{key: issue.attrib[key] for key in ("id", "severity", "message")} for issue in issues]},
        "isolatedDebugKeystore": str(root / ".local/android-user/debug.keystore"),
    }
    if not Path(report["isolatedDebugKeystore"]).is_file():
        raise ValueError("Expected isolated debug signing key missing")
    (evidence / "apk-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
