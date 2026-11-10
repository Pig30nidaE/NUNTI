"""Compare real Android Canvas captures with final PNGs and Figma video frames."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/redesign/birth-motion-v1"
BACKGROUND = (246, 244, 239, 255)


def rgba(path):
    with Image.open(path) as image:
        return image.convert("RGBA")


def flatten(image):
    return Image.alpha_composite(Image.new("RGBA", image.size, BACKGROUND), image)


def statistics(first, second):
    difference = ImageChops.difference(first, second).convert("RGB")
    return {
        "meanAbsoluteRgbError": ImageStat.Stat(difference).mean,
        "maximumRgbError": [pair[1] for pair in difference.getextrema()],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path, help="Folder containing native-0000.png through native-4000.png")
    args = parser.parse_args()
    folder = args.runtime.resolve()
    base = rgba(folder / "native-0000.png")
    final = rgba(folder / "native-4000.png")
    reference = rgba(folder / "native-4000-reference.png")
    source = ROOT / "docs/redesign/route-variants-v1/samples/coast-curious/character.png"
    state = json.loads((folder / "native-4000.json").read_text())
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert final.tobytes() == reference.tobytes(), "Final Canvas pixels must equal the same Android-decoded final asset"
    assert state["finalSourceHash"] == source_hash

    # Remove only the explicitly variable feature areas. The protected silhouette,
    # limbs, sprout, bag and body must remain byte-for-byte identical every frame.
    variable_regions = [(235, 160, 545, 397), (275, 380, 555, 476), (360, 488, 450, 536)]
    protected = Image.new("L", base.size, 255)
    draw = ImageDraw.Draw(protected)
    for rectangle in variable_regions:
        draw.rectangle(rectangle, fill=0)

    frames = []
    for time in (0, 1000, 2200, 3000, 4000):
        native = rgba(folder / f"native-{time:04}.png")
        metadata = json.loads((folder / f"native-{time:04}.json").read_text())
        assert native.size == (768, 768)
        assert metadata["elapsedMs"] == time and metadata["gateAllowed"]
        assert metadata["gateSource"] == "ACTUAL_CAR_SERVICE" and metadata["captureWritten"]
        difference = ImageChops.difference(native, base)
        protected_difference = Image.composite(difference, Image.new("RGBA", base.size), protected)
        max_delta = max(channel[1] for channel in protected_difference.getextrema())
        assert max_delta == 0, f"Protected character pixels changed at {time}ms"
        figma = rgba(DOCS / f"figma-a-frame-{time / 1000:.1f}.png")
        comparison = statistics(flatten(native), figma)
        # Figma MP4 frames contain H.264 chroma quantization. This is a visual
        # parity bound, not a claim that compressed video equals source PNG bytes.
        assert max(comparison["meanAbsoluteRgbError"]) < 2.0, (time, comparison)
        frames.append({
            "nativeTimeMs": time,
            "figmaVideoTimeMs": 2166.667 if time == 2200 else time,
            "protectedRgbaMaxDifference": max_delta,
            "figmaComparison": comparison,
        })

    resting = statistics(flatten(rgba(source)), rgba(DOCS / "figma-final-resting.png"))
    assert max(resting["maximumRgbError"]) <= 2
    endpoints = []
    for path in sorted(folder.glob("final-*-*.png")):
        if path.name.endswith("-reference.png") or path.name == "final-ready-to-review.png":
            continue
        name = path.stem.removeprefix("final-")
        endpoint_reference = path.with_name(path.stem + "-reference.png")
        metadata = json.loads(path.with_suffix(".json").read_text())
        original = ROOT / "docs/redesign/route-variants-v1/samples" / name / "character.png"
        assert metadata["elapsedMs"] == 4000 and metadata["gateAllowed"]
        assert rgba(path).tobytes() == rgba(endpoint_reference).tobytes(), name
        assert metadata["finalSourceHash"] == hashlib.sha256(original.read_bytes()).hexdigest(), name
        endpoints.append({"sample": name, "canvasEqualsDecodedFinal": True, "originalSourceHashMatches": True})
    assert len(endpoints) == 9, "All nine actual native endpoints must be captured"
    report = {
        "status": "PASS",
        "runtimeEvidence": folder.relative_to(ROOT).as_posix(),
        "finalSourceSha256": source_hash,
        "finalCanvasEqualsDecodedFinalPixels": True,
        "protectedBodyPixelsUnchanged": True,
        "variableRegions768": variable_regions,
        "frameChecks": frames,
        "nineNativeEndpointChecks": endpoints,
        "figmaRestingVsFinalPng": resting,
        "limitations": [
            "Figma 2.2s requested frame is sampled at 2.166667s; Native capture is exactly 2.2s.",
            "Video comparisons include H.264 color quantization; resting PNG comparison does not.",
            "Native and Figma UI backgrounds differ; transparent native art is composited over the Figma background for this check.",
            "These five frames test continuity of protected pixels; native timeline and Figma fixed-core readback cover the intervening states.",
        ],
    }
    (DOCS / "pixel-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "frames": len(frames), "finalPixelsExact": True, "protectedPixelsUnchanged": True}))


if __name__ == "__main__":
    main()
