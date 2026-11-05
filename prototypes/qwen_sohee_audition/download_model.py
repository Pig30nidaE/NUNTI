"""Fetch exactly the pinned native-preset model, reusing an identical tokenizer read-only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT / ".local/qwen-sohee-audition"
MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
REVISION = "41d3337e8b7f2843a75841595fc14e4b9a7a4b96"


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main() -> None:
    old = json.loads((ROOT / "prototypes/journey_voice_v3/model-lock.json").read_text())
    old_files = {item["path"]: item for item in old["files"]}
    api = f"https://huggingface.co/api/models/{MODEL_ID}/tree/{REVISION}?recursive=true"
    with urllib.request.urlopen(api, timeout=30) as response:
        files = json.load(response)
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{MODEL_ID}/revision/{REVISION}", timeout=30) as response:
        metadata = json.load(response)
    assert metadata["sha"] == REVISION
    assert metadata["cardData"]["license"] == "apache-2.0"
    records = []
    for item in files:
        if item["type"] != "file":
            continue
        name = item["path"]
        target = CACHE / "model" / name
        reused = name == "speech_tokenizer/model.safetensors" and item["lfs"]["oid"] == old_files[name]["sha256"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            if reused:
                existing = Path(old["localPath"]) / name
                assert digest(existing) == item["lfs"]["oid"]
                target.symlink_to(existing)
                print("REUSED_READ_ONLY", name, flush=True)
            else:
                print("DOWNLOADING", name, item["size"], flush=True)
                temporary = target.with_suffix(target.suffix + ".part")
                with urllib.request.urlopen(f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}", timeout=120) as source, temporary.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                temporary.replace(target)
        assert target.stat().st_size == item["size"]
        sha = digest(target)
        if "lfs" in item:
            assert sha == item["lfs"]["oid"]
        else:
            body = target.read_bytes()
            assert hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest() == item["oid"]
        records.append({"path": name, "bytes": item["size"], "sha256": sha, "reusedReadOnly": reused})
    config = json.loads((CACHE / "model/config.json").read_text())
    assert config["tts_model_type"] == "custom_voice"
    assert config["talker_config"]["spk_id"]["sohee"] == 2864
    assert config["talker_config"]["codec_language_id"]["korean"] == 2064
    lock = {"modelId": MODEL_ID, "revision": REVISION,
            "sourceModelId": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            "sourceRevision": "0c0e3051f131929182e2c023b9537f8b1c68adfe",
            "license": "Apache-2.0", "conversion": "MLX-community conversion, not Qwen vendor runtime",
            "cacheRelativePath": ".local/qwen-sohee-audition/model", "files": records,
            "newDownloadBytes": sum(item["bytes"] for item in records if not item["reusedReadOnly"]),
            "speaker": "Sohee", "speakerId": 2864, "language": "Korean", "languageId": 2064}
    assert lock["newDownloadBytes"] < 3_000_000_000
    path = HERE / "model-lock.json"
    if path.exists():
        assert json.loads(path.read_text()) == lock
    else:
        path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
    (HERE / "licenses").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "prototypes/journey_voice_v3/Qwen3-TTS-LICENSE.txt", HERE / "licenses/Qwen-Apache-2.0.txt")
    shutil.copy2(ROOT / "prototypes/journey_voice_v3/MLX-Audio-LICENSE.txt", HERE / "licenses/MLX-Audio-MIT.txt")
    shutil.copy2(CACHE / "model/README.md", HERE / "model-card.md")
    refs = {"nativeSpeakerList": "https://github.com/QwenLM/Qwen3-TTS#custom-voice-generate",
            "config": f"https://huggingface.co/{MODEL_ID}/blob/{REVISION}/config.json",
            "modelCard": f"https://huggingface.co/{MODEL_ID}/blob/{REVISION}/README.md",
            "fileMetadataApi": api}
    (HERE / "source-refs.json").write_text(json.dumps(refs, indent=2) + "\n")
    print(json.dumps({"newDownloadBytes": lock["newDownloadBytes"], "speakerId": 2864,
                      "languageId": 2064}), flush=True)


if __name__ == "__main__":
    main()
