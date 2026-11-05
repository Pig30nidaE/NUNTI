"""Pin one Base model; reuse the byte-identical existing speech tokenizer read-only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = ROOT / ".local/journey-voice-v3-identity"
MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
REVISION = "e7dd0585652209fa0d7783659aad4e8a324de11c"
UPSTREAM_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
UPSTREAM_REVISION = "fd4b254389122332181a7c3db7f27e918eec64e3"


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as source, temporary.open("wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)
    temporary.replace(destination)


def main() -> None:
    previous = json.loads((HERE.parent / "model-lock.json").read_text())
    existing_files = {f["path"]: f for f in previous["files"]}
    api = f"https://huggingface.co/api/models/{MODEL_ID}/tree/{REVISION}?recursive=true"
    with urllib.request.urlopen(api, timeout=30) as response:
        tree = json.load(response)
    model_info_url = f"https://huggingface.co/api/models/{MODEL_ID}/revision/{REVISION}"
    with urllib.request.urlopen(model_info_url, timeout=30) as response:
        info = json.load(response)
    assert info["sha"] == REVISION
    assert info["cardData"]["license"] == "apache-2.0"
    files = []
    downloaded = 0
    reused = 0
    for item in tree:
        if item["type"] != "file":
            continue
        name = item["path"]
        destination = CACHE / "model" / name
        source_file = Path(previous["localPath"]) / name
        same_tokenizer = (
            name == "speech_tokenizer/model.safetensors"
            and item["lfs"]["oid"] == existing_files[name]["sha256"]
        )
        if not destination.exists():
            if same_tokenizer:
                assert sha256(source_file) == item["lfs"]["oid"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(source_file)
                print("REUSED_READ_ONLY", name, flush=True)
            else:
                print("DOWNLOADING", name, item["size"], flush=True)
                download(f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}", destination)
        assert destination.stat().st_size == item["size"]
        digest = sha256(destination)
        if "lfs" in item:
            assert digest == item["lfs"]["oid"], name
        else:
            body = destination.read_bytes()
            assert hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest() == item["oid"], name
        if same_tokenizer:
            reused += item["size"]
        else:
            downloaded += item["size"]
        files.append({"path": name, "bytes": item["size"], "sha256": digest,
                      "reusedReadOnly": same_tokenizer})
    assert downloaded < 3_000_000_000
    record = {"schemaVersion": 1, "modelId": MODEL_ID, "revision": REVISION,
              "conversion": "MLX-community conversion, not the Qwen vendor runtime",
              "cacheRelativePath": ".local/journey-voice-v3-identity/model",
              "upstreamModelId": UPSTREAM_ID, "upstreamRevision": UPSTREAM_REVISION,
              "license": "Apache-2.0", "files": files,
              "newDownloadBytes": downloaded, "reusedReadOnlyBytes": reused}
    lock_path = HERE / "model-lock.json"
    if lock_path.exists():
        assert json.loads(lock_path.read_text()) == record, "Model lock is immutable"
    else:
        lock_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    (HERE / "licenses").mkdir(exist_ok=True)
    shutil.copy2(HERE.parent / "Qwen3-TTS-LICENSE.txt", HERE / "licenses/Qwen3-TTS-Apache-2.0.txt")
    shutil.copy2(HERE.parent / "MLX-Audio-LICENSE.txt", HERE / "licenses/MLX-Audio-MIT.txt")
    shutil.copy2(CACHE / "model/README.md", HERE / "model-card.md")
    refs = {"modelCard": f"https://huggingface.co/{MODEL_ID}/blob/{REVISION}/README.md",
            "modelTreeApi": api, "modelMetadataApi": model_info_url,
            "upstream": f"https://huggingface.co/{UPSTREAM_ID}/tree/{UPSTREAM_REVISION}",
            "vendorVoiceDesignThenClone": "https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone"}
    (HERE / "source-refs.json").write_text(json.dumps(refs, indent=2) + "\n")
    print(json.dumps({"newDownloadBytes": downloaded, "reusedReadOnlyBytes": reused,
                      "totalModelBytes": downloaded + reused}), flush=True)


if __name__ == "__main__":
    main()
