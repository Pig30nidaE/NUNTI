"""Download exactly one pinned public Whisper-small MLX checkpoint."""
from pathlib import Path
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / ".local/voice-audition-asr"
os.environ["HF_HOME"] = str(TOOLS / "hf")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
from huggingface_hub import snapshot_download

MODEL_ID = "mlx-community/whisper-small-mlx"
REVISION = "45f3915923c7a79a5a5b5a7d909d39aeb0e5630e"
model_path = Path(snapshot_download(MODEL_ID, revision=REVISION, max_workers=2))
files = []
for path in sorted(model_path.rglob("*")):
    if path.is_file():
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        files.append({"path": str(path.relative_to(model_path)), "bytes": path.stat().st_size, "sha256": digest})
record = {"modelId": MODEL_ID, "revision": REVISION, "localPath": str(model_path), "bytes": sum(f["bytes"] for f in files), "files": files, "source": "OpenAI Whisper small, converted by MLX-community", "note": "Independent ASR evidence. The conversion model card does not declare a license field; original OpenAI Whisper code/model are MIT."}
(HERE / "model-lock.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: record[k] for k in ["modelId", "revision", "bytes"]}), flush=True)
