"""Package approved A layers for the offline Android motion prototype.

No model/network call. The destination artwork is divided only along empty rows;
source pixels and final PNG bytes stay unchanged. All ten endpoints are verified
against the runtime compositor's already exported samples.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend/nunti/avatar_studio/assets/nunti-a-layers-v1"
SAMPLES = ROOT / "docs/redesign/route-variants-v1/samples"
OUT = ROOT / "android/app/src/debug/assets/nunti_motion_v1"
DOCS = ROOT / "docs/redesign/birth-motion-v1"
SIZE = (768, 768)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def copy(source, relative):
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def save(image, relative):
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "PNG", optimize=False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    original = json.loads((SOURCE / "manifest.json").read_text())
    for path, meta in original["files"].items():
        assert digest(SOURCE / path) == meta["sha256"], path

    core = Image.new("RGBA", SIZE)
    for name in original["coreOrder"]:
        with Image.open(SOURCE / "core" / (name + ".png")) as layer:
            core = Image.alpha_composite(core, layer)
    save(core, "core.png")
    copy(SOURCE / "base.png", "base.png")
    for name in ("base", "calm", "curious", "adventurous"):
        copy(SOURCE / "expressions" / (name + ".png"), "expression-" + name + ".png")
    for path in sorted((SOURCE / "roads").glob("*.png")):
        copy(path, "roads/" + path.name)

    for kind in ("coast", "mountain", "city"):
        with Image.open(SOURCE / "destinations" / (kind + ".png")) as destination:
            # All scarf ink ends at y=464; all pocket ink starts at y>=494.
            # Divide in empty space, with no resampling, tinting or repainting.
            assert not destination.getchannel("A").crop((0, 465, 768, 494)).getbbox()
            scarf = Image.new("RGBA", SIZE)
            pocket = Image.new("RGBA", SIZE)
            scarf.paste(destination.crop((0, 0, 768, 480)), (0, 0))
            pocket.paste(destination.crop((0, 480, 768, 768)), (0, 480))
            rejoined = Image.alpha_composite(scarf, pocket)
            assert rejoined.getchannel("A").tobytes() == destination.getchannel("A").tobytes()
            # Ignore RGB stored behind fully transparent pixels only.
            for background in ("black", "white"):
                surface = Image.new("RGBA", SIZE, background)
                assert Image.alpha_composite(surface, rejoined).tobytes() == Image.alpha_composite(surface, destination).tobytes()
            save(scarf, f"destinations/{kind}-scarf.png")
            save(pocket, f"destinations/{kind}-pocket.png")

    samples = {}
    endpoints = []
    for folder in sorted(SAMPLES.iterdir()):
        if not folder.is_dir():
            continue
        spec = json.loads((folder / "AvatarSpec.json").read_text())
        sample_id = folder.name
        copy(folder / "character.png", f"finals/{sample_id}.png")
        copy(folder / "AvatarSpec.json", f"AvatarSpecs/{sample_id}.json")
        paths = {layer["id"].split("-", 1)[0]: layer["path"] for layer in spec["layers"]}
        category = spec["destinationMotif"]
        entry = {
            "final": f"finals/{sample_id}.png",
            "spec": f"AvatarSpecs/{sample_id}.json",
            "expression": f"expression-{spec['expression']}.png",
            "scarf": None if category == "none" else f"destinations/{category}-scarf.png",
            "pocket": None if category == "none" else f"destinations/{category}-pocket.png",
            "road": paths.get("road"),
            "label": spec["accessibilityLabel"],
        }
        samples[sample_id] = entry
        image = core.copy()
        for relative in (entry["expression"], entry["scarf"], entry["pocket"], entry["road"]):
            if relative is not None:
                with Image.open(OUT / relative) as layer:
                    image = Image.alpha_composite(image, layer)
        with Image.open(folder / "character.png") as expected:
            assert not ImageChops.difference(image, expected).getbbox(alpha_only=False), sample_id
        assert digest(OUT / entry["final"]) == digest(folder / "character.png")
        endpoints.append({"sample": sample_id, "pixelsMatch": True, "finalSha256": digest(folder / "character.png")})

    files = {
        path.relative_to(OUT).as_posix(): {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "schemaVersion": 1,
        "assetVersion": "nunti-motion-v1",
        "sourceAssetVersion": original["assetVersion"],
        "canvas": list(SIZE),
        "fixedFaceAnchors": original["fixedFaceAnchors"],
        "owner": original["owner"],
        "licensingNote": original["licensingNote"],
        "approval": {"character": "A / Matte Form, user-approved", "motion": "Comparison prototype, not a production default"},
        "source": "backend/nunti/avatar_studio/assets/nunti-a-layers-v1/manifest.json",
        "builder": "scripts/build_nunti_motion_assets.py",
        "export": {"format": "PNG RGBA", "size": list(SIZE), "resampling": "none", "destinationSplitY": 480},
        "fallback": "base.png",
        "files": files,
        "samples": samples,
    }
    write_json(OUT / "manifest.json", manifest)
    write_json(DOCS / "asset-verification.json", {
        "sourceAssetsVerified": True, "networkCalls": 0, "imageGenerationCalls": 0,
        "destinationSplitLossless": True, "endpointChecks": endpoints,
        "bundle": OUT.relative_to(ROOT).as_posix(), "bundleBytes": sum(v["bytes"] for v in files.values()),
    })
    print(json.dumps({"samples": len(samples), "endpointsMatch": True, "files": len(files), "path": str(OUT)}))


if __name__ == "__main__":
    main()
