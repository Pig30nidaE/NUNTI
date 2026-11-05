#!/usr/bin/env python3
"""Download only pinned public ONNX/JSON assets. Never execute remote Python."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL_DIR = HERE.parents[1] / ".local/journey-voice/models"


def verify_file(path, entry):
    data = path.read_bytes()
    if len(data) != entry["size"]:
        raise ValueError(f"Wrong size: {entry['path']}")
    if entry["sha256"]:
        digest = hashlib.sha256(data).hexdigest()
        expected = entry["sha256"]
    else:
        digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        expected = entry["gitBlobSha1"]
    if digest != expected:
        raise ValueError(f"Wrong digest: {entry['path']}")
    return hashlib.sha256(data).hexdigest()


def download(model_dir):
    lock = json.loads((HERE / "model-lock.json").read_text())

    def one(entry):
        target = model_dir / entry["path"]
        if target.exists():
            return entry["path"], verify_file(target, entry)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".download")
        url = f"https://huggingface.co/{lock['repository']}/resolve/{lock['revision']}/{entry['path']}"
        subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2", url, "--output", str(temporary)], check=True)
        digest = verify_file(temporary, entry)
        os.replace(temporary, target)
        return entry["path"], digest

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        hashes = dict(pool.map(one, lock["files"]))
    print(json.dumps({"modelRevision": lock["revision"], "sha256": hashes}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    download(parser.parse_args().model_dir)
