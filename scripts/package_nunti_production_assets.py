"""Copy approved motion layers into the existing Studio/APK static assets.

No generation, recoloring or resampling. The server's AvatarSpec remains the
mapping authority; production intentionally has no table of nine sample IDs.
"""
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "android/app/src/debug/assets/nunti_motion_v1"
OUT = ROOT / "prototypes/avatar_generator/nunti-motion"


def main():
    original = json.loads((SOURCE / "manifest.json").read_text())
    source_layers = json.loads((ROOT / original["source"]).read_text())
    files = {}
    for name, meta in original["files"].items():
        if name.startswith(("finals/", "AvatarSpecs/")):
            continue
        raw = (SOURCE / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == meta["sha256"], name
        target = OUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, target)
        with Image.open(target) as image:
            assert image.size == (768, 768) and image.mode == "RGBA"
            files[name] = dict(meta, bounds=image.getchannel("A").getbbox())
    manifest = {
        **{key: original[key] for key in ("assetVersion", "sourceAssetVersion", "canvas", "owner", "licensingNote", "source", "export", "fallback")},
        "approval": {"character": "User approved A / Matte Form", "motion": "User approved integration of A / Light trail, once while parked"},
        "builder": "scripts/package_nunti_production_assets.py",
        "files": files,
        "sourceHashes": {name: value["sha256"] for name, value in source_layers["files"].items()},
    }
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    (OUT / "manifest.json").write_text(text + "\n")
    (OUT / "manifest.js").write_text("'use strict';\nwindow.NuntiMotionManifest = " + text + ";\n")
    print(json.dumps({"files": len(files), "bytes": sum(v["bytes"] for v in files.values()), "networkCalls": 0}))


if __name__ == "__main__":
    main()
