#!/usr/bin/env python3
"""Reproduce the three illustration directions and six destination keepsakes."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from nunti.avatar_studio.design_intent import build_design_intent
from nunti.avatar_studio.illustration import render_avatar
from nunti.avatar_studio.journey_art import render_character
from PIL import Image, ImageDraw

ROUTE = [[0.1, 0.8], [0.3, 0.6], [0.25, 0.4], [0.6, 0.5], [0.85, 0.2]]
DIRECTIONS = ("STORYBOOK", "FOLK_CHIBI", "SOFT_TOY")
SCENARIOS = (
    ("서울역", "출장 회의"),
    ("수원역", "출장 회의"),
    ("을왕리 해수욕장", "수영과 물놀이"),
    ("북한산", "등산"),
    ("국립중앙박물관", "미술 관람"),
    ("경복궁", "휴식"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".local/avatar-quality-v6/art-studies"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    comparison = Image.new("RGB", (1800, 1800), (250, 247, 240))
    draw = ImageDraw.Draw(comparison)
    for row, (destination, purpose) in enumerate(
        (SCENARIOS[0], SCENARIOS[2], SCENARIOS[3])
    ):
        plan = build_design_intent(
            ROUTE, destination, "", purpose, fine_detail_seed="art-study-fixed"
        )
        for col, direction in enumerate(DIRECTIONS):
            image = render_character(plan, direction)
            image.save(args.output / f"study-{row}-{direction}.png")
            image.thumbnail((600, 600))
            comparison.paste(image, (col * 600, row * 600), image)
            draw.text((col * 600 + 18, row * 600 + 18), direction, fill=(70, 60, 60))
    comparison.save(args.output / "comparison.png")

    keepsakes = Image.new("RGB", (1800, 1200), (250, 247, 240))
    draw = ImageDraw.Draw(keepsakes)
    manifest = []
    for i, (destination, purpose) in enumerate(SCENARIOS):
        png, design = render_avatar(
            ROUTE, destination, "", purpose, f"preview-{i % 3}-{i // 3}"
        )
        (args.output / f"final-{i}.png").write_bytes(png)
        (args.output / f"final-{i}.json").write_text(
            json.dumps(design, ensure_ascii=False, indent=2) + "\n"
        )
        image = Image.open(io.BytesIO(png))
        image.thumbnail((600, 600))
        keepsakes.paste(image, ((i % 3) * 600, (i // 3) * 600), image)
        character = design["characterPlan"]
        draw.text(
            ((i % 3) * 600 + 15, (i // 3) * 600 + 15),
            f"{character['destination']['landmark']} / {character['purpose']['role']}",
            fill=(70, 60, 60),
        )
        manifest.append(
            {"destination": destination, "purpose": purpose, "character": character}
        )
    keepsakes.save(args.output / "destination-keepsakes.png")
    (args.output / "manifest.json").write_text(
        json.dumps(
            {"syntheticRoute": True, "scenarios": manifest},
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(args.output.resolve())


if __name__ == "__main__":
    main()
