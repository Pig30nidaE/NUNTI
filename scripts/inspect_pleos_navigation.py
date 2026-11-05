#!/usr/bin/env python3
"""Inspect installed Pleos navigation metadata; optionally capture its visible UI.

No app is started, installed, stopped, or granted permissions. Raw package dumps
and logcat are never printed or saved. Metadata cannot prove route integration.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
ADB = ROOT / ".local/pm-tools/sdk/platform-tools/adb"
OUTPUT = ROOT / ".local/navigation-review"
NAV_APP = "ai.umos.maps.android.navigation.app"
PACKAGES = (NAV_APP, "ai.pleos.playground.service.navi")
PERMISSION = re.compile(r"\bpleos\.car\.permission\.NAVI_[A-Z0-9_]+\b")
COMPONENT = re.compile(r"\b([A-Za-z][\w.]*)/([A-Za-z.$][\w.$]*)\b")
ERROR_PATTERNS = {
    "unknownHost": re.compile(r"UnknownHostException"),
    "sslHandshake": re.compile(r"SSLHandshakeException"),
    "certificateValidation": re.compile(
        r"SSLPeerUnverifiedException|CertPathValidatorException"
    ),
    "connectionFailure": re.compile(r"ConnectException|ECONNREFUSED|ENETUNREACH"),
    "socketTimeout": re.compile(r"SocketTimeoutException"),
    "http401": re.compile(
        r"(?:HTTP(?:/[\d.]+)?\s+|(?:status(?:Code)?|responseCode|code)\s*[:=]\s*)401\b",
        re.IGNORECASE,
    ),
    "http403": re.compile(
        r"(?:HTTP(?:/[\d.]+)?\s+|(?:status(?:Code)?|responseCode|code)\s*[:=]\s*)403\b",
        re.IGNORECASE,
    ),
}


class InspectionError(RuntimeError):
    pass


def label_text(value):
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", value):
        raise argparse.ArgumentTypeError(
            "label은 영문 소문자로 시작하는 1~48자의 소문자·숫자·밑줄·하이픈이어야 합니다."
        )
    return value


def serial_text(value):
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        raise argparse.ArgumentTypeError("ADB serial 형식이 올바르지 않습니다.")
    return value


def adb_read(serial, arguments, *, allow_failure=False, timeout=20):
    try:
        result = subprocess.run(
            [str(ADB), "-s", serial, *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise InspectionError("ADB_TIMEOUT") from error
    if result.returncode and not allow_failure:
        raise InspectionError("ADB_COMMAND_FAILED")
    return result.returncode, result.stdout


def package_summary(package, raw):
    installed = bool(re.search(r"Package\s+\[" + re.escape(package) + r"\]", raw))
    version_code = re.search(r"\bversionCode=(\d+)", raw)
    version_name = re.search(r"\bversionName=([A-Za-z0-9._+()-]{1,120})(?:\s|$)", raw)
    declared = []
    current = None
    for line in raw.splitlines():
        permission = re.search(
            r"Permission\s+\[(pleos\.car\.permission\.NAVI_[A-Z0-9_]+)\]", line
        )
        if permission:
            current = {"name": permission[1], "protection": None}
            declared.append(current)
        elif re.search(r"Permission\s+\[", line):
            current = None
        if current is not None:
            protection = re.search(r"\bprot=([A-Za-z0-9_|]+)", line)
            if protection:
                current["protection"] = protection[1]
                current = None
    grants = []
    user = None
    for line in raw.splitlines():
        user_line = re.match(r"\s*User\s+(\d+):", line)
        if user_line:
            user = int(user_line[1])
        grant = re.search(
            r"(pleos\.car\.permission\.NAVI_[A-Z0-9_]+):\s+granted=(true|false)", line
        )
        if grant:
            grants.append(
                {"name": grant[1], "granted": grant[2] == "true", "userIdContext": user}
            )
    components = sorted({f"{p}/{c}" for p, c in COMPONENT.findall(raw) if p == package})
    return {
        "package": package,
        "installed": installed,
        "versionName": version_name[1] if version_name else None,
        "versionCode": int(version_code[1]) if version_code else None,
        "navigationPermissionNamesMentioned": sorted(set(PERMISSION.findall(raw))),
        "declaredNavigationPermissions": declared,
        "observedNavigationPermissionGrants": grants,
        "componentCandidatesFromPackageDump": components,
    }


def launch_activity(serial, user, package):
    status, raw = adb_read(
        serial,
        [
            "shell",
            "cmd",
            "package",
            "resolve-activity",
            "--brief",
            "--user",
            str(user),
            "-a",
            "android.intent.action.MAIN",
            "-c",
            "android.intent.category.LAUNCHER",
            "-p",
            package,
        ],
        allow_failure=True,
    )
    matches = [
        f"{p}/{c}"
        for p, c in COMPONENT.findall(raw.decode(errors="replace"))
        if p == package
    ]
    return matches[-1] if status == 0 and matches else None


def log_error_counts(serial, package):
    status, raw_pids = adb_read(serial, ["shell", "pidof", package], allow_failure=True)
    values = raw_pids.decode(errors="replace").strip().split()
    pids = sorted({int(p) for p in values if p.isdigit()}) if status == 0 else []
    counts = dict.fromkeys(ERROR_PATTERNS, 0)
    lines_scanned = 0
    for pid in pids:
        status, raw = adb_read(
            serial, ["logcat", "-d", "-t", "300", f"--pid={pid}"], allow_failure=True
        )
        if status:
            continue
        for line in raw.decode(errors="replace").splitlines()[-300:]:
            lines_scanned += 1
            for key, pattern in ERROR_PATTERNS.items():
                if pattern.search(line):
                    counts[key] += 1
    return {
        "runningProcessCount": len(pids),
        "linesScanned": lines_scanned,
        "matchingLineCounts": counts,
        "scope": "At most 300 buffered logcat lines per current PID. Counts may overlap; no raw line, URL, query or credential is retained.",
        "routeConnectivityVerified": False,
    }


def snapshot(serial, folder):
    _, raw = adb_read(serial, ["shell", "dumpsys", "window"])
    focus = re.search(
        r"mCurrentFocus=Window\{([^}\n]*)\}", raw.decode(errors="replace")
    )
    components = COMPONENT.findall(focus[1]) if focus else []
    focused_package = components[-1][0] if components else None
    if focused_package != NAV_APP:
        return {
            "status": "SKIPPED_NAVIGATION_NOT_FOCUSED",
            "focusedPackage": focused_package,
        }
    remote = "/data/local/tmp/nunti-navigation-review-" + uuid4().hex + ".xml"
    try:
        adb_read(
            serial, ["shell", "uiautomator", "dump", "--compressed", remote], timeout=30
        )
        adb_read(serial, ["pull", remote, str(folder / "ui.xml")])
    finally:
        adb_read(serial, ["shell", "rm", "-f", remote], allow_failure=True)
    _, png = adb_read(serial, ["exec-out", "screencap", "-p"])
    if not png.startswith(b"\x89PNG\r\n\x1a\n") or len(png) > 25 * 1024 * 1024:
        raise InspectionError("INVALID_SCREENSHOT_OUTPUT")
    (folder / "screen.png").write_bytes(png)
    return {
        "status": "UI_SNAPSHOT_CAPTURED",
        "focusedPackage": focused_package,
        "xml": "ui.xml",
        "png": "screen.png",
        "routePayloadObserved": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default="emulator-5554", type=serial_text)
    parser.add_argument("--label", default="metadata", type=label_text)
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="내비 앱이 현재 포커스일 때만 UI XML·정지 PNG를 보존합니다.",
    )
    parser.add_argument(
        "--log-counts",
        action="store_true",
        help="현재 내비 프로세스 로그의 네트워크 오류 횟수만 집계합니다. 원시 로그는 저장하지 않습니다.",
    )
    args = parser.parse_args()
    if not ADB.is_file():
        raise InspectionError("ADB_NOT_FOUND")
    output = OUTPUT.resolve()
    if not output.is_relative_to(ROOT):
        raise InspectionError("OUTPUT_OUTSIDE_WORKSPACE")
    now = datetime.now(timezone.utc)  # noqa: UP017 -- macOS system Python 3.9 support.
    folder = output / (
        args.label + "-" + now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    )
    folder.mkdir(parents=True, mode=0o700)
    report = {
        "status": "METADATA_INSPECTION_STARTED",
        "capturedAtUtc": now.isoformat(),
        "serial": args.serial,
        "label": args.label,
        "integrationVerified": False,
        "routePayloadObserved": False,
        "externalNetworkRequests": 0,
        "appStarted": False,
        "permissionsChanged": False,
        "rawLogRetained": False,
        "videoRecorded": False,
        "speakerRecorded": False,
    }
    try:
        _, user_bytes = adb_read(args.serial, ["shell", "am", "get-current-user"])
        user = user_bytes.decode(errors="replace").strip()
        if not user.isdigit():
            raise InspectionError("CURRENT_USER_NOT_OBSERVED")
        report["androidUser"] = int(user)
        _, fingerprint = adb_read(
            args.serial, ["shell", "getprop", "ro.build.fingerprint"]
        )
        report["fingerprint"] = fingerprint.decode(errors="replace").strip()[:512]
        report["packages"] = []
        for package in PACKAGES:
            _, raw = adb_read(args.serial, ["shell", "dumpsys", "package", package])
            item = package_summary(package, raw.decode(errors="replace"))
            item["resolvedLauncherActivity"] = launch_activity(
                args.serial, int(user), package
            )
            if args.log_counts:
                item["networkErrorObservation"] = log_error_counts(args.serial, package)
            report["packages"].append(item)
        if args.snapshot:
            report["snapshot"] = snapshot(args.serial, folder)
        report["status"] = "INSTALLED_METADATA_OBSERVED"
    except InspectionError as error:
        report["status"] = "INSPECTION_INCOMPLETE"
        report["errorCode"] = str(error)
        raise
    finally:
        path = folder / "inspection.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        path.chmod(0o600)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "report": str(path),
                    "integrationVerified": False,
                    "routePayloadObserved": False,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except (InspectionError, OSError) as error:
        code = str(error) if isinstance(error, InspectionError) else "LOCAL_IO_FAILED"
        print(json.dumps({"status": "FAILED", "errorCode": code}), file=sys.stderr)
        raise SystemExit(1) from None
