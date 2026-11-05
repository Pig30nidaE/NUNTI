"""Download only pinned official source and the six V3 inference files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / ".local/chatterbox-audition"
LOCK = json.loads((HERE / "model-lock.json").read_text())


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source() -> None:
    revision = LOCK["codeRevision"]
    target = CACHE / "source"
    archive = CACHE / f"chatterbox-{revision}.tar.gz"
    if not archive.exists():
        download(f"https://codeload.github.com/resemble-ai/chatterbox/tar.gz/{revision}", archive)
    if not target.exists():
        extract = CACHE / "source-extract"
        extract.mkdir(exist_ok=True)
        with tarfile.open(archive) as tar:
            tar.extractall(extract, filter="data")
        (extract / f"chatterbox-{revision}").replace(target)
        extract.rmdir()
    (HERE / "licenses").mkdir(exist_ok=True)
    shutil.copy2(target / "LICENSE", HERE / "licenses/chatterbox-MIT.txt")
    (CACHE / "source-provenance.json").write_text(json.dumps({
        "repository": LOCK["codeRepository"], "revision": revision,
        "archiveSha256": sha256(archive), "licenseSha256": sha256(target / "LICENSE")
    }, indent=2) + "\n")
    print("SOURCE_READY", flush=True)


def models() -> None:
    evidence = []
    for item in LOCK["files"]:
        path = CACHE / "model" / item["path"]
        if not path.exists():
            print("DOWNLOADING", item["path"], item["size"], flush=True)
            download(f"https://huggingface.co/{LOCK['modelId']}/resolve/{LOCK['modelRevision']}/{item['path']}", path)
        if path.stat().st_size != item["size"]:
            raise ValueError(f"File size mismatch: {path}")
        digest = sha256(path)
        if "sha256" in item and digest != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {path}")
        if "gitBlobSha1" in item:
            body = path.read_bytes()
            blob = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
            if blob != item["gitBlobSha1"]:
                raise ValueError(f"Git blob mismatch: {path}")
        evidence.append({**item, "actualSha256": digest})
        print("VERIFIED", item["path"], flush=True)
    (HERE / "download-verification.json").write_text(json.dumps({
        "modelId": LOCK["modelId"], "revision": LOCK["modelRevision"],
        "totalBytes": sum(x["size"] for x in evidence), "files": evidence
    }, ensure_ascii=False, indent=2) + "\n")
    print("MODELS_READY", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=["source", "models"])
    args = parser.parse_args()
    source() if args.part == "source" else models()
