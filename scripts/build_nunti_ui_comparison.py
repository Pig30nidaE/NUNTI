#!/usr/bin/env python3
"""Build labeled screenshot QA boards without editing Figma or source images.

Before images are actual Pleos captures. After/day/night images are Figma UI
proposals, not implemented app screenshots. Missing inputs fail before writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL import __version__ as PILLOW_VERSION

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs/redesign/pleos-ui-v1"
APP_BOX = (853, 90, 2535, 1300)
APP_SIZE = (1682, 1210)
DISPLAY_SIZE = (2560, 1440)
STATES = (
    ("pre-trip", "PRE_TRIP", "production-pre-trip.png", "AvatarStudioActivity"),
    (
        "reveal-parked",
        "REVEAL_PARKED",
        "production-reveal-settled.png",
        "AvatarStudioActivity",
    ),
    (
        "driving-restricted",
        "DRIVING_RESTRICTED",
        "production-driving-active.png",
        "JourneyActivity",
    ),
    ("post-trip", "POST_TRIP", "production-post-trip.png", "JourneyActivity"),
)
FONT_CHOICES = (
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        image.load()
        # Screenshots have opaque backgrounds. Reject transparent proposals
        # rather than invent a background that was not present in Figma.
        rgba = image.convert("RGBA")
        if rgba.getchannel("A").getextrema() != (255, 255):
            raise ValueError(f"Expected an opaque complete screen: {path}")
        return rgba.convert("RGB")


def frame_record(metadata: dict, filename: str) -> dict:
    """Optional metadata schema: {frames: {filename.png: {nodeId, url, ...}}}."""
    frames = metadata.get("frames", {})
    value = frames.get(filename) if isinstance(frames, dict) else None
    if isinstance(value, dict):
        return {
            "figmaFileKey": metadata.get("fileKey"),
            "figmaPageId": metadata.get("pageId"),
            **value,
        }
    return {"figmaNodeId": None, "verification": "NOT_SUPPLIED"}


def inputs(baseline: Path, exports: Path, metadata: dict) -> tuple[dict, list[dict]]:
    paths = [baseline / entry[2] for entry in STATES]
    paths.extend(
        exports / f"{slug}-{mode}.png"
        for slug, *_ in STATES
        for mode in ("day", "night")
    )
    missing = [label(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Waiting for source exports:\n" + "\n".join(missing))
    normalized = {}
    records = []
    for slug, state, filename, activity in STATES:
        path = baseline / filename
        image = load_image(path)
        if image.size != DISPLAY_SIZE:
            raise ValueError(
                f"Before screenshot must be {DISPLAY_SIZE}: {path}, got {image.size}"
            )
        key = f"{slug}-before"
        normalized[key] = image.crop(APP_BOX)
        records.append(
            {
                "id": key,
                "state": state,
                "role": "BEFORE",
                "sourceKind": "ACTUAL_ANDROID_EMULATOR",
                "path": label(path),
                "sha256": digest(path),
                "sourcePixels": list(image.size),
                "cropBoxXYXY": list(APP_BOX),
                "cropBoxXYWH": [853, 90, *APP_SIZE],
                "normalizedPixels": list(APP_SIZE),
                "normalization": "LOSSLESS_PIXEL_CROP",
                "frameSource": {
                    "package": "ai.nunti.avatar.demo",
                    "activity": activity,
                    "displayMode": "day",
                    "androidUser": 10,
                    "serial": "emulator-5554",
                    "visiblePlatformBlock": slug == "driving-restricted",
                },
            }
        )
        for mode in ("day", "night"):
            path = exports / f"{slug}-{mode}.png"
            image = load_image(path)
            scale_x = image.width / APP_SIZE[0]
            scale_y = image.height / APP_SIZE[1]
            if scale_x != scale_y or not scale_x.is_integer() or scale_x < 1:
                raise ValueError(
                    f"Figma frame must be {APP_SIZE} or an exact integer multiple: {path}, got {image.size}"
                )
            key = f"{slug}-{mode}"
            normalized[key] = (
                image
                if image.size == APP_SIZE
                else image.resize(APP_SIZE, Image.Resampling.LANCZOS)
            )
            records.append(
                {
                    "id": key,
                    "state": state,
                    "role": "AFTER",
                    "sourceKind": "FIGMA_UI_PROPOSAL",
                    "path": label(path),
                    "sha256": digest(path),
                    "sourcePixels": list(image.size),
                    "cropBoxXYXY": [0, 0, *image.size],
                    "cropBoxXYWH": [0, 0, *image.size],
                    "normalizedPixels": list(APP_SIZE),
                    "exportScale": int(scale_x),
                    "normalization": "UNCHANGED_PIXELS"
                    if scale_x == 1
                    else "LANCZOS_DOWNSAMPLE",
                    "frameSource": frame_record(metadata, path.name),
                    "displayMode": mode,
                    "implementedRedesign": False,
                    "drivingRuntimeVisibilityApproved": False,
                }
            )
    return normalized, records


def draw_board(images: dict, font_path: Path, *, comparison: bool) -> Image.Image:
    margin, gutter, card_width, image_height = 40, 32, 841, 605
    top, row_height, header_height = 146, 740, 78
    board = Image.new(
        "RGB",
        (margin * 2 + card_width * 2 + gutter, top + row_height * 4 + 24),
        "#EDEFE9",
    )
    draw = ImageDraw.Draw(board)

    def text(position, value, size=26, fill="#213E34"):
        draw.text(
            position, value, fill=fill, font=ImageFont.truetype(str(font_path), size)
        )

    title = (
        "NUNTI / actual app vs Figma proposal"
        if comparison
        else "NUNTI / Figma proposals in day and night"
    )
    subtitle = (
        "Same 1682 x 1210 app area. Actual platform chrome is excluded."
        if comparison
        else "Design review only. These are not Android runtime captures."
    )
    text((margin, 26), title, 40)
    text((margin, 83), subtitle, 25)
    for index, (slug, state, *_rest) in enumerate(STATES):
        y = top + index * row_height
        text((margin, y), f"0{index + 1}  {state}", 28)
        image_y = y + 45 + header_height
        for column in range(2):
            x = margin + column * (card_width + gutter)
            actual = comparison and column == 0
            driving = slug == "driving-restricted"
            if actual:
                key = f"{slug}-before"
                headline = (
                    "BEFORE / ACTUAL PLATFORM BLOCK"
                    if driving
                    else "BEFORE / ACTUAL ANDROID APP"
                )
                caption = (
                    "D / 30 km/h. Companion is covered by the system."
                    if driving
                    else "Existing production path in the installed debug APK"
                )
                color, ink = (
                    ("#803E36", "#FFFFFF") if driving else ("#2B4C40", "#FFFFFF")
                )
            else:
                mode = "day" if comparison or column == 0 else "night"
                key = f"{slug}-{mode}"
                headline = (
                    "AFTER" if comparison else mode.upper()
                ) + " / FIGMA UI PROPOSAL"
                caption = (
                    "Driving visibility is NOT runtime-approved."
                    if driving
                    else "Design proposal; not an implemented redesign"
                )
                color, ink = "#E5D1A9", "#47391F"
            draw.rectangle((x, y + 45, x + card_width - 1, image_y - 1), fill=color)
            text((x + 17, y + 54), headline, 28, ink)
            text((x + 17, y + 91), caption, 23, ink)
            board.paste(
                images[key].resize(
                    (card_width, image_height), Image.Resampling.LANCZOS
                ),
                (x, image_y),
            )
            draw.rectangle(
                (x, image_y, x + card_width - 1, image_y + image_height - 1),
                outline="#ADB9AD",
                width=1,
            )
    return board


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DESIGN / "baseline")
    parser.add_argument("--exports", type=Path, default=DESIGN / "exports")
    parser.add_argument("--output", type=Path, default=DESIGN / "comparison")
    parser.add_argument(
        "--frame-sources", type=Path, default=DESIGN / "exports/frame-sources.json"
    )
    parser.add_argument("--font", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    metadata = (
        json.loads(args.frame_sources.read_text())
        if args.frame_sources.is_file()
        else {}
    )
    try:
        images, records = inputs(args.baseline, args.exports, metadata)
    except (FileNotFoundError, ValueError) as error:
        print(str(error))
        return 2
    if args.check_only:
        print(
            json.dumps(
                {"status": "READY", "sources": len(records), "appPixels": APP_SIZE}
            )
        )
        return 0
    font = args.font or next((path for path in FONT_CHOICES if path.is_file()), None)
    if font is None or not font.is_file():
        raise FileNotFoundError("Provide an installed font with --font")
    args.output.mkdir(parents=True, exist_ok=True)
    normalized_dir = args.output / "normalized"
    normalized_dir.mkdir(exist_ok=True)
    outputs = []
    for key, image in images.items():
        path = normalized_dir / (key + ".png")
        image.save(path)
        outputs.append(
            {
                "path": label(path),
                "pixels": list(image.size),
                "sha256": digest(path),
                "sourceId": key,
            }
        )
    for filename, comparison in (
        ("before-after-day.png", True),
        ("day-night-proposals.png", False),
    ):
        image = draw_board(images, font, comparison=comparison)
        path = args.output / filename
        image.save(path)
        outputs.append(
            {"path": label(path), "pixels": list(image.size), "sha256": digest(path)}
        )
    manifest = {
        "schemaVersion": 1,
        "purpose": "SCREENSHOT_QA_NOT_IMPLEMENTATION_PARITY",
        "script": {"path": label(Path(__file__)), "sha256": digest(Path(__file__))},
        "pillowVersion": PILLOW_VERSION,
        "font": {"path": str(font), "sha256": digest(font)},
        "appPixels": list(APP_SIZE),
        "beforeCropBoxXYXY": list(APP_BOX),
        "boardScale": 0.5,
        "boardResampling": "LANCZOS",
        "sourceImagesModified": False,
        "frameSourceMetadata": {
            "path": label(args.frame_sources),
            "sha256": digest(args.frame_sources),
        }
        if metadata
        else None,
        "limits": [
            "After images are Figma proposals, not an implemented Android redesign.",
            "Driving Before is the visible platform block. The proposed companion is not approved for runtime exposure.",
            "Night proposals have no matching production night baseline in this capture set.",
            "Historical production artwork and trip data can differ from the approved A mascot and sample data in the Figma proposal.",
        ],
        "inputs": records,
        "outputs": outputs,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "status": "WRITTEN",
                "sources": len(records),
                "outputs": len(outputs),
                "manifest": label(args.output / "manifest.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
