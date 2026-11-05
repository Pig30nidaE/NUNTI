"""Download exactly one pinned, public MLX VoiceDesign model into an isolated cache."""
from pathlib import Path
import hashlib
import json
import os
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".local/journey-voice-v3"
os.environ["HF_HOME"] = str(TOOLS / "hf")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
from huggingface_hub import snapshot_download

MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
REVISION = "f90d617701d9f7f4ca499291e0b57f2b3c2fd2ee"
model_path = snapshot_download(MODEL_ID, revision=REVISION, max_workers=2)
files = []
for path in sorted(Path(model_path).rglob("*")):
    if path.is_file():
        digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        files.append({"path": str(path.relative_to(model_path)), "bytes": path.stat().st_size, "sha256": digest})
record = {"modelId": MODEL_ID, "revision": REVISION, "localPath": model_path,
          "conversion": "MLX-community conversion, not the Qwen vendor runtime", "files": files,
          "sourceModel": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
          "sourceModelRevision": "5ecdb67327fd37bb2e042aab12ff7391903235d3",
          "license": "Apache-2.0"}
(ROOT / "prototypes/journey_voice_v3/model-lock.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"downloaded": model_path, "files": len(files), "bytes": sum(x["bytes"] for x in files)}, indent=2), flush=True)
