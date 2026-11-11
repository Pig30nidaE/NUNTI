"""Compile the approved A artwork into an aligned, reusable local layer kit.

The only generated edit is a blank skin underlay, used inside fixed face masks.
Every outer character pixel comes from the selected A reference. All layer masks,
face anchors and decorative paths are versioned here; no model runs at runtime.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/redesign/identity-refine-v1/nunti-a-front-transparent-v1.png"
SKIN = ROOT / "docs/redesign/route-variants-v1/sources/face-underlay-generated.png"
OUT = ROOT / "backend/nunti/avatar_studio/assets/nunti-a-layers-v1"
SIZE = (768, 768)
CROP = (232, 20, 968, 1272)
SCALE = 688 / (CROP[3] - CROP[1])
OFFSET = ((768 - round((CROP[2] - CROP[0]) * SCALE)) // 2, 40)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point(x, y):
    return (
        round((x - CROP[0]) * SCALE + OFFSET[0]),
        round((y - CROP[1]) * SCALE + OFFSET[1]),
    )


def frame(image):
    out = Image.new("RGBA", SIZE)
    cut = image.crop(CROP)
    cut = cut.resize((round(cut.width * SCALE), 688), Image.Resampling.LANCZOS)
    out.alpha_composite(cut, OFFSET)
    return out


def save(name, image):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=False)


def polygon_mask(points):
    mask = Image.new("L", SIZE)
    ImageDraw.Draw(mask).polygon([point(x, y) for x, y in points], fill=255)
    return mask


def masked(image, mask):
    result = image.copy()
    result.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    return result


def curve(draw, points, color, width):
    a, b, c, d = points
    samples = []
    for n in range(41):
        t = n / 40
        samples.append(
            tuple(
                (1 - t) ** 3 * a[i]
                + 3 * (1 - t) ** 2 * t * b[i]
                + 3 * (1 - t) * t * t * c[i]
                + t**3 * d[i]
                for i in (0, 1)
            )
        )
    draw.line(samples, fill=color, width=width, joint="curve")
    radius = width / 2
    for x, y in (a, d):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def expression_layer(source, kind):
    # Work at reference resolution, then use the common transform for every layer.
    layer = Image.new("RGBA", source.size)
    brown = (83, 49, 34, 255)
    mouth = (142, 59, 35, 255)
    if kind in ("curious", "adventurous"):
        mask = Image.new("L", source.size)
        draw = ImageDraw.Draw(mask)
        for box in ((385, 365, 575, 531), (650, 363, 834, 531)):
            draw.ellipse(box, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(5))
        layer = masked(source, mask)
    strokes = Image.new("RGBA", (source.width * 3, source.height * 3))
    draw = ImageDraw.Draw(strokes)

    def stroke(points, color, width):
        curve(draw, [(x * 3, y * 3) for x, y in points], color, width * 3)

    if kind == "calm":
        for x in (475, 744):
            stroke(
                [(x - 59, 443), (x - 27, 486), (x + 32, 486), (x + 60, 442)], brown, 11
            )
        stroke([(417, 344), (444, 324), (477, 325), (505, 343)], brown, 8)
        stroke([(704, 344), (732, 326), (771, 326), (798, 344)], brown, 8)
        stroke([(579, 560), (594, 580), (630, 580), (647, 557)], mouth, 7)
    elif kind == "curious":
        stroke([(416, 331), (445, 300), (480, 304), (510, 323)], brown, 9)
        stroke([(706, 346), (737, 352), (772, 350), (799, 339)], brown, 9)
        stroke([(580, 563), (602, 581), (633, 576), (649, 553)], mouth, 7)
    else:
        # Slightly inward-set brows, friendly rather than angry, same eye sockets.
        stroke([(415, 329), (449, 324), (481, 338), (508, 347)], brown, 10)
        stroke([(706, 347), (736, 334), (768, 324), (801, 329)], brown, 10)
        mouth_mask = Image.new("L", source.size)
        ImageDraw.Draw(mouth_mask).rounded_rectangle(
            (540, 499, 689, 620), radius=25, fill=255
        )
        mouth_mask = mouth_mask.filter(ImageFilter.GaussianBlur(5))
        layer = Image.alpha_composite(layer, masked(source, mouth_mask))
    layer = Image.alpha_composite(
        layer, strokes.resize(source.size, Image.Resampling.LANCZOS)
    )
    return frame(layer)


def destination_layer(kind, scarf_mask, source):
    colors = {
        "coast": (85, 149, 176),
        "mountain": (112, 146, 96),
        "city": (151, 128, 177),
    }
    color = colors[kind]
    # One destination ornament plus a secondary accent palette, never a new body.
    tint = Image.new("RGBA", SIZE, (*color, 110))
    mint = Image.new("L", SIZE)
    mint.putdata(
        [
            255 if g - r > 5 and b > r - 2 and g > 100 else 0
            for r, g, b, a in source.getdata()
        ]
    )
    color_mask = ImageChops.multiply(scarf_mask, mint)
    tint.putalpha(ImageChops.multiply(color_mask, Image.new("L", SIZE, 105)))
    tint.putalpha(ImageChops.multiply(tint.getchannel("A"), source.getchannel("A")))
    hi = Image.new("RGBA", (1536, 1536))
    d = ImageDraw.Draw(hi)
    ink = (*color, 255)
    # Pocket emblem centered below the protected original brand badge.
    if kind == "coast":
        for y in (1020, 1042):
            curve(d, [(743, y), (765, y - 23), (782, y + 23), (806, y)], ink, 6)
            curve(d, [(806, y), (826, y - 23), (844, y + 23), (865, y)], ink, 6)
    elif kind == "mountain":
        d.line(
            [(745, 1048), (785, 1000), (820, 1048)], fill=ink, width=7, joint="curve"
        )
        d.line(
            [(806, 1029), (828, 1005), (862, 1048)], fill=ink, width=7, joint="curve"
        )
        d.line(
            [(774, 1014), (785, 1022), (796, 1014)], fill=(236, 246, 226, 255), width=5
        )
    else:
        for x, y, h in ((750, 1012, 37), (786, 994, 55), (824, 1020, 29)):
            d.rounded_rectangle((x, y, x + 24, y + h), radius=5, fill=ink)
            for wy in range(y + 8, y + h - 5, 12):
                d.rectangle((x + 9, wy, x + 14, wy + 4), fill=(242, 233, 250, 255))
    return Image.alpha_composite(tint, hi.resize(SIZE, Image.Resampling.LANCZOS))


def road_layer(kind, variant):
    hi = Image.new("RGBA", (1536, 1536))
    d = ImageDraw.Draw(hi)
    x0, y0 = 665, 815
    ivory = (255, 250, 229, 245)
    outline = (65, 101, 88, 175)
    offset = variant * 3
    if kind == "highway":
        paths = [
            [
                (x0, y0 + offset),
                (x0 + 27, y0 - 3 + offset),
                (x0 + 60, y0 + 2),
                (x0 + 91, y0 + 1),
            ]
        ]
    elif kind == "rural":
        paths = [
            [
                (x0, y0 + 9),
                (x0 + 25, y0 - 12 - offset),
                (x0 + 57, y0 + 26),
                (x0 + 91, y0 + 2),
            ]
        ]
    elif kind == "urban":
        d.line(
            [
                (x0, y0 + 12),
                (x0 + 24 + offset, y0 + 12),
                (x0 + 24 + offset, y0 - 2),
                (x0 + 62, y0 - 2),
                (x0 + 62, y0 + 9),
                (x0 + 91, y0 + 9),
            ],
            fill=outline,
            width=8,
            joint="curve",
        )
        d.line(
            [
                (x0, y0 + 12),
                (x0 + 24 + offset, y0 + 12),
                (x0 + 24 + offset, y0 - 2),
                (x0 + 62, y0 - 2),
                (x0 + 62, y0 + 9),
                (x0 + 91, y0 + 9),
            ],
            fill=ivory,
            width=4,
            joint="curve",
        )
        paths = []
    else:
        paths = [
            [
                (x0, y0 + 8),
                (x0 + 22, y0 + 8),
                (x0 + 32, y0 - 13 - offset),
                (x0 + 51, y0 + 2),
            ],
            [
                (x0 + 51, y0 + 2),
                (x0 + 64, y0 + 14),
                (x0 + 76, y0 + 10),
                (x0 + 91, y0 + 8),
            ],
        ]
    for p in paths:
        curve(d, p, outline, 8)
        curve(d, p, ivory, 4)
    return hi.resize(SIZE, Image.Resampling.LANCZOS)


def main():
    source = Image.open(SOURCE).convert("RGBA")
    # The generated source has alpha=253 inside and stray alpha=1 pixels outside.
    # Normalize coverage for the local compositor without changing any RGB geometry.
    source.putalpha(
        source.getchannel("A").point(
            lambda a: 0 if a < 96 else min(255, round((a - 96) * 255 / 157))
        )
    )
    blank = Image.open(SKIN).convert("RGBA")
    # Align only the face surface using observed skin-outline landmarks.
    blank = blank.transform(
        source.size,
        Image.Transform.AFFINE,
        (603 / 562, 0, 242 - 318 * 603 / 562, 0, 455 / 448, 280 - 230 * 455 / 448),
        Image.Resampling.BICUBIC,
    )
    feature = Image.new("L", source.size)
    draw = ImageDraw.Draw(feature)
    for box in ((368, 283, 584, 551), (637, 291, 854, 551), (527, 480, 704, 640)):
        draw.rounded_rectangle(box, radius=25, fill=255)
    feature = feature.filter(ImageFilter.GaussianBlur(9))
    protect = Image.new("L", source.size)
    ImageDraw.Draw(protect).polygon(
        [
            (548, 197),
            (612, 199),
            (681, 234),
            (747, 250),
            (748, 277),
            (714, 312),
            (660, 320),
            (602, 302),
            (568, 283),
            (550, 250),
        ],
        fill=255,
    )
    feature = ImageChops.subtract(feature, protect)
    skin = Image.composite(blank, source, feature)
    skin.putalpha(source.getchannel("A"))
    foundation = frame(skin)
    original = frame(source)
    # Semantic cut masks are disjoint in the output frame. Their union is the
    # complete foundation; no resampling occurs after the final partition.
    selections = {
        "badge": [(642, 746), (730, 746), (745, 836), (664, 855), (637, 813)],
        "bag": [
            (356, 859),
            (468, 859),
            (494, 977),
            (458, 1024),
            (355, 1023),
            (337, 932),
        ],
        "scarf": [
            (420, 658),
            (709, 658),
            (896, 668),
            (920, 713),
            (880, 792),
            (796, 797),
            (715, 750),
            (478, 753),
            (420, 719),
        ],
        "sprout": [(400, 10), (805, 10), (805, 151), (400, 151)],
        "head": [(200, 145), (970, 145), (970, 673), (200, 673)],
    }
    remaining = Image.new("L", SIZE, 255)
    masks = {}
    for name, points in selections.items():
        masks[name] = ImageChops.multiply(polygon_mask(points), remaining)
        remaining = ImageChops.subtract(remaining, masks[name])
    masks["body"] = remaining
    for name, mask in masks.items():
        save(f"core/{name}.png", masked(foundation, mask))
    # Restore all original feature pixels for base. Hard ownership boundaries
    # are hidden in unchanged skin pixels; mood layers share the same anchors.
    restore = feature.point(lambda v: 255 if v else 0)
    restore = (
        frame(Image.merge("RGBA", (restore, restore, restore, restore)))
        .getchannel("A")
        .point(lambda v: 255 if v else 0)
    )
    base_expression = masked(original, restore)
    save("expressions/base.png", base_expression)
    assembled = Image.alpha_composite(foundation, base_expression)
    save("base.png", assembled)
    for kind in ("calm", "curious", "adventurous"):
        save(f"expressions/{kind}.png", expression_layer(source, kind))
    for kind in ("coast", "mountain", "city"):
        save(
            f"destinations/{kind}.png",
            destination_layer(kind, masks["scarf"], original),
        )
    for kind in ("urban", "highway", "rural", "mixed"):
        for variant in range(3):
            save(f"roads/{kind}-{variant}.png", road_layer(kind, variant))
    save("fallback/base.png", assembled)
    entries = {}
    for path in sorted(OUT.rglob("*.png")):
        im = Image.open(path)
        entries[str(path.relative_to(OUT))] = {
            "sha256": sha(path),
            "size": list(im.size),
            "mode": im.mode,
            "alphaRange": list(im.getchannel("A").getextrema()),
            "bytes": path.stat().st_size,
        }
    manifest = {
        "assetVersion": "nunti-a-layers-v1",
        "characterId": "nunti-a-v1",
        "canvas": [768, 768],
        "approval": {
            "direction": "A / Matte Form",
            "basis": "Explicit user selection in this chat, 2026-11-09",
            "productionMotionApproval": False,
        },
        "source": {
            "path": str(SOURCE.relative_to(ROOT)),
            "sha256": sha(SOURCE),
            "selectedSheet": "docs/redesign/identity-refine-v1/nunti-a-sheet-v3.png",
        },
        "faceUnderlay": {
            "path": str(SKIN.relative_to(ROOT)),
            "sha256": sha(SKIN),
            "usage": "Fixed masked inner-face skin only; no outer geometry used",
            "prompt": "docs/redesign/route-variants-v1/source-prompts.json",
        },
        "builder": "scripts/build_nunti_layer_assets.py",
        "coreOrder": ["body", "head", "sprout", "scarf", "bag", "badge"],
        "fixedFaceAnchors": {
            "leftEye": list(point(475, 446)),
            "rightEye": list(point(744, 446)),
            "mouth": list(point(613, 561)),
        },
        "owner": "NUNTI project / user",
        "licensingNote": "Project-supplied canonical reference; original rights record not independently verified. No third-party mascot references. Procedural ornaments authored in project.",
        "fallback": "fallback/base.png",
        "files": entries,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    fallback_manifest = {
        "assetVersion": manifest["assetVersion"],
        "canvas": manifest["canvas"],
        "fixedFaceAnchors": manifest["fixedFaceAnchors"],
        "files": {"base.png": entries["fallback/base.png"]},
    }
    (OUT / "fallback/manifest.json").write_text(
        json.dumps(fallback_manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Compiled {len(entries)} shared PNG assets to {OUT}")


if __name__ == "__main__":
    main()
