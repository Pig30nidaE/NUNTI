#!/usr/bin/env python3
"""Verify real production WebView captures, keeping UI layout QA separate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def rgba(path):
    with Image.open(path) as image:
        return image.convert("RGBA")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--continuation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folders = [args.runtime.resolve()]
    if args.continuation:
        folders.insert(0, args.continuation.resolve())
    artifacts = json.loads((args.runtime / "artifacts.json").read_text())
    endpoints = []
    for item in artifacts:
        slug = item["slug"]
        folder = next(
            path for path in folders if (path / (slug + "-final.png")).exists()
        )
        final = folder / (slug + "-final.png")
        reference = folder / (slug + "-browser-reference.png")
        assert rgba(final).size == (768, 768)
        assert rgba(final).tobytes() == rgba(reference).tobytes(), slug
        endpoints.append(
            {
                "sample": slug,
                "canvasEqualsBrowserDecodedServerPixels": True,
                "capture": str(final),
                "captureSha256": hashlib.sha256(final.read_bytes()).hexdigest(),
                "serverSourceSha256": item["artifact"]["visual"]["sha256"],
            }
        )
    assert len(endpoints) == 9
    base = rgba(args.runtime / "timeline-0000.png")
    protected = Image.new("L", (768, 768), 255)
    draw = ImageDraw.Draw(protected)
    variable = [(235, 160, 545, 397), (275, 380, 555, 476), (360, 488, 450, 536)]
    for rectangle in variable:
        draw.rectangle(rectangle, fill=0)
    frames = []
    for milliseconds in [0, 1000, 2200, 3000, 4000]:
        frame = rgba(args.runtime / f"timeline-{milliseconds:04}.png")
        state = json.loads(
            (args.runtime / f"timeline-{milliseconds}-state.json").read_text()
        )
        assert state["allowed"] and state["motion"]["elapsedMs"] == milliseconds
        difference = ImageChops.difference(frame, base)
        protected_diff = Image.composite(
            difference, Image.new("RGBA", frame.size), protected
        )
        maximum = max(channel[1] for channel in protected_diff.getextrema())
        assert maximum == 0, (milliseconds, maximum)
        frames.append(
            {
                "elapsedMs": milliseconds,
                "actualParkedGateAllowed": True,
                "protectedRgbaMaximumDifference": maximum,
            }
        )
    report = {
        "status": "PASS",
        "surface": "ACTUAL_PRODUCTION_WEBVIEW_CANVAS",
        "endpointChecks": endpoints,
        "frameChecks": frames,
        "excludedVariableRegions768": variable,
        "limitations": [
            "Five sampled instants prove protected-pixel continuity at those instants.",
            "Final comparison uses the same browser decoder; original server PNG encoding can differ.",
            "This is character-art evidence, not a claim that the entire emulator UI equals Figma pixels.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "PASS",
                "endpoints": len(endpoints),
                "protectedFrames": len(frames),
            }
        )
    )


if __name__ == "__main__":
    main()
