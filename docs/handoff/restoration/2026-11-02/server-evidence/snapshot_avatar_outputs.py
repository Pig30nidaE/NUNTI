"""Read AVATAR outputs and preserve the exact synthetic inputs checked by SERVER."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo


def main():
    source = Path("/Users/pig30nidae/NUNTI/.worktrees/avatar/.local/avatar-build/reports")
    evidence = Path(__file__).resolve().parent
    destination = evidence / "avatar-generated"
    destination.mkdir(exist_ok=True)
    model_names = {"RouteSnapshot", "AvatarSpec", "VoiceProfile", "EmotionSnapshot"}
    files = [path for path in sorted(source.glob("*.json")) if path.stem.split(".")[-1] in model_names]
    assert len(files) == 10, files
    manifest = []
    for path in files:
        shutil.copyfile(path, destination / path.name)
        manifest.append({"file": path.name, "bytes": path.stat().st_size, "sourceMtime": datetime.fromtimestamp(path.stat().st_mtime, ZoneInfo("Asia/Seoul")).isoformat(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {"source": str(source), "capturedAt": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), "count": len(manifest), "files": manifest}
    (evidence / "avatar-inputs.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
