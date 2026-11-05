"""Record non-secret tool and lock provenance for the SERVER restoration."""

from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[5]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def main():
    lock = ROOT / "backend/uv.lock"
    tracked_lock = subprocess.check_output(["git", "-C", str(ROOT), "show", "HEAD:backend/uv.lock"])
    uv_binary = ROOT / ".local/uv-bootstrap/bin/uv"
    uv_metadata = ROOT / ".local/uv-bootstrap/lib/python3.12/site-packages/uv-0.9.7.dist-info"
    report = {
        "recordedAt": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "pythonExecutable": sys.executable,
        "pathPython": subprocess.check_output(["/usr/bin/python3", "--version"], text=True).strip(),
        "uvVersion": subprocess.check_output([str(uv_binary), "--version"], text=True).strip(),
        "uvBinarySha256": hashlib.sha256(uv_binary.read_bytes()).hexdigest(),
        "uvInstaller": (uv_metadata / "INSTALLER").read_text().strip(),
        "uvBootstrapState": "Pre-existing in the assigned SERVER worktree. Version and pip metadata inspected; no claim that this run downloaded it.",
        "lockSha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "lockMatchesHead": lock.read_bytes() == tracked_lock,
        "packages": {dist.metadata["Name"]: dist.version for dist in sorted(importlib.metadata.distributions(), key=lambda dist: dist.metadata["Name"].lower())},
        "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted((ROOT / ".local/dist").glob("nunti_backend-*")) if path.is_file()},
    }
    assert report["lockMatchesHead"]
    destination = Path(__file__).with_name("environment.json")
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
