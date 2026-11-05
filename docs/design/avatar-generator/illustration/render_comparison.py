"""Rebuild the local three-form comparison without models, fixtures or APIs."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

from nunti.avatar_studio.illustration import _make_design, _render, render_avatar

OUTPUT = Path(__file__).resolve().parent
ROUTE = [
    [0.12, 0.86],
    [0.25, 0.72],
    [0.23, 0.51],
    [0.43, 0.45],
    [0.54, 0.63],
    [0.72, 0.43],
    [0.70, 0.22],
    [0.89, 0.13],
]


def main():
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    board = Image.new("RGB", (1536, 790), "#f6f3e9")
    draw = ImageDraw.Draw(board)
    draw.text((45, 30), "NUNTI  /  ROUTE GLASS KEEPSAKES", font=font, fill="#38534d")
    draw.text(
        (45, 70),
        "Same navigation route, three contour structures. Local Pillow drawings; no image model.",
        font=small,
        fill="#687b70",
    )
    names = [
        ("petal", "A  PETAL DROP", "Small petal ears + generous rounded body"),
        ("pebble", "B  PEBBLE", "Low, broad capsule + round bubble ears"),
        ("sprout", "C  SEED", "Tall ears + tapered seed-shaped body"),
    ]
    metadata = []
    for index, (form, title, subtitle) in enumerate(names):
        spec = _make_design(
            ROUTE,
            "해안 기념관",
            "바다, 유리 공예",
            "주말 기념 여행",
            "comparison-20261103",
            form=form,
        )
        image = _render(ROUTE, spec)
        image.save(OUTPUT / f"concept-{form}.png")
        x = index * 512
        draw.rounded_rectangle(
            (x + 20, 125, x + 492, 745),
            radius=30,
            fill="#fffdf6",
            outline="#e4e9dd",
            width=2,
        )
        # A neutral backing makes transparent edges and the gold route inspectable.
        preview = image.resize((500, 500), Image.Resampling.LANCZOS)
        board.paste(preview, (x + 6, 142), preview)
        draw.text((x + 45, 661), title, font=font, fill="#355249")
        draw.text((x + 45, 704), subtitle, font=small, fill="#7a8272")
        metadata.append(
            {"form": form, "seed": spec.seed, "route": ROUTE, "origin": "LOCAL_RENDER"}
        )
    board.save(OUTPUT / "comparison-three-forms.png")
    (OUTPUT / "comparison-inputs.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    qa = Image.new("RGB", (1080, 850), "#f6f3e9")
    draw = ImageDraw.Draw(qa)
    draw.text(
        (30, 25),
        "ACTUAL PUBLIC RENDERER / RGBA + 128px + 64px",
        font=font,
        fill="#38534d",
    )
    cases = [
        ("coast", "해안 기념관", "바다, 유리 공예", "주말 기념 여행", ROUTE),
        ("garden", "정원", "나무, 숲", "산책", [[0.1, 0.3], [0.5, 0.3], [0.9, 0.3]]),
        ("night", "야간 전시관", "밤, 별", "전시 관람", [[0.5, 0.1], [0.5, 0.9]]),
    ]
    designs = []
    for n, (identifier, destination, traits, purpose, route) in enumerate(cases):
        png, design = render_avatar(
            route, destination, traits, purpose, f"qa-{identifier}"
        )
        (OUTPUT / f"sample-{identifier}.png").write_bytes(png)
        image = Image.open(io.BytesIO(png))
        y = 95 + n * 242
        dark = Image.new("RGB", (230, 230), "#31443f")
        preview = image.resize((230, 230), Image.Resampling.LANCZOS)
        dark.paste(preview, (0, 0), preview)
        qa.paste(dark, (30, y))
        qa.paste(preview, (280, y), preview)
        for size, x in ((128, 550), (64, 730)):
            small_image = image.resize((size, size), Image.Resampling.LANCZOS)
            qa.paste(small_image, (x, y + 34), small_image)
            draw.text((x, y + 180), f"{size}px", font=small, fill="#687b70")
        draw.text((830, y + 55), identifier.upper(), font=font, fill="#38534d")
        draw.text((830, y + 100), design["form"], font=small, fill="#687b70")
        designs.append(
            {
                "destination": destination,
                "traits": traits,
                "purpose": purpose,
                "route": route,
                "design": design,
            }
        )
    qa.save(OUTPUT / "qa-cutouts-thumbnails.png")
    (OUTPUT / "sample-designs.json").write_text(
        json.dumps(designs, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
