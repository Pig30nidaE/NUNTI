#!/usr/bin/env python3
"""Add three pinned public speaker vectors; preserve all v1 assets and lockfiles."""
import json
import os
from pathlib import Path
import subprocess
from download_models import DEFAULT_MODEL_DIR, HERE, verify_file


def main():
    lock = json.loads((HERE / "model-lock-v2.json").read_text())
    for entry in lock["files"]:
        target = DEFAULT_MODEL_DIR / entry["path"]
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".download")
            url = f"https://huggingface.co/{lock['repository']}/resolve/{lock['revision']}/{entry['path']}"
            subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", url, "--output", str(temporary)], check=True)
            verify_file(temporary, entry)
            os.replace(temporary, target)
        print(entry["path"], verify_file(target, entry))


if __name__ == "__main__":
    main()
