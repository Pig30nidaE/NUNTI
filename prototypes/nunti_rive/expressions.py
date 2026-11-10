"""Bake compact expression overlays from the approved, registered vinyl art."""

from dataclasses import dataclass
from math import pi, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


SOURCE = Path(__file__).resolve().parent.parent / "avatar_generator"
SKINS = ("sea", "city", "mountain")
LEFT = (260, 220, 366, 323)
RIGHT = (413, 220, 516, 323)
WIDE = (260, 214, 516, 326)
HAPPY_EYES = (260, 220, 516, 323)
MOUTH = (347, 300, 433, 366)
PATCHES = {
    "blink-left": LEFT,
    "blink-right": RIGHT,
    "blink-left-half": LEFT,
    "blink-right-half": RIGHT,
    "wide": WIDE,
    "happy-eyes": HAPPY_EYES,
    "happy-mouth": MOUTH,
}


@dataclass(frozen=True)
class Eye:
    side: str
    box: tuple[int, int, int, int]
    center: tuple[int, int]
    bounds: tuple[int, int, int, int]
    samples: tuple[tuple[int, int], ...]


EYES = (
    Eye("left", LEFT, (313, 273), (266, 227, 362, 318), (
        (265, 240), (262, 271), (263, 291), (286, 319), (313, 322),
        (342, 319), (364, 288), (364, 243), (315, 221),
    )),
    Eye("right", RIGHT, (465, 274), (419, 227, 510, 318), (
        (417, 240), (416, 268), (416, 288), (434, 319), (466, 322),
        (494, 317), (506, 300), (504, 250), (464, 221),
    )),
)


def _size(box):
    return box[2] - box[0], box[3] - box[1]


def _mask(box, bounds, radius, feather):
    mask = Image.new("L", _size(box))
    shifted = tuple(value - box[index % 2] for index, value in enumerate(bounds))
    ImageDraw.Draw(mask).rounded_rectangle(shifted, radius=radius, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(feather))


def _clean_eye(master, core, eye, original, mask):
    # Restore the approved blank face, matching its lighting to this skin
    # from unaffected points around the eye. Preserve the local cheek blush.
    left, top = eye.box[:2]
    samples = [
        (x - left, y - top, tuple(a - b for a, b in zip(master.getpixel((x, y))[:3], core.getpixel((x, y))[:3])))
        for x, y in eye.samples
    ]
    reference = core.crop(eye.box)
    pixels = reference.load()
    for y in range(reference.height):
        for x in range(reference.width):
            red, green, blue, alpha = pixels[x, y]
            offsets = [0.0, 0.0, 0.0]
            weight_sum = 0.0
            for sx, sy, delta in samples:
                weight = 1 / (180 + (x - sx) ** 2 + (y - sy) ** 2)
                weight_sum += weight
                for channel, difference in enumerate(delta):
                    offsets[channel] += difference * weight
            corrected = [
                max(0, min(255, round(value + offset / weight_sum)))
                for value, offset in zip((red, green, blue), offsets)
            ]
            pixels[x, y] = (*corrected, alpha)
    return Image.composite(reference, original, mask)


def _reshape(image, box, center, scale_x, scale_y, lift):
    cx = center[0] - box[0]
    cy = center[1] - box[1]
    transform = (1 / scale_x, 0, cx - cx / scale_x, 0, 1 / scale_y, cy - (cy + lift) / scale_y)
    return image.transform(image.size, Image.Transform.AFFINE, transform, Image.Resampling.BICUBIC)


def _crease(eye, points, width, shadow):
    left, top = eye.box[:2]
    antialias = 3
    out_width, out_height = _size(eye.box)
    pad = Image.new("RGBA", (out_width * antialias, out_height * antialias))
    draw = ImageDraw.Draw(pad)

    def sweep(color, thickness, vertical_offset=0):
        lower = []
        upper = []
        for sample in range(37):
            t = sample / 36
            v = 1 - t
            weights = (v ** 3, 3 * v * v * t, 3 * v * t * t, t ** 3)
            x = sum(weight * point[0] for weight, point in zip(weights, points)) - left
            y = sum(weight * point[1] for weight, point in zip(weights, points)) - top + vertical_offset
            half = thickness * (.22 + .78 * sin(pi * t) ** .58) * .5
            lower.append((x * antialias, (y + half) * antialias))
            upper.append((x * antialias, (y - half) * antialias))
        draw.polygon(lower + upper[::-1], fill=color)

    sweep((175, 90, 67, shadow), width + 5, 2.4)
    sweep((90, 49, 40, 244), width)
    sweep((165, 110, 88, 142), 1.5, -1.0)
    return pad.resize((out_width, out_height), Image.Resampling.LANCZOS)


def _closed(eye, clean, happy=False):
    center = eye.center[0]
    drop = 1 if eye.side == "right" else 0
    if happy:
        points = ((-34, 291), (-20, 266), (17, 261), (34, 288))
    else:
        points = ((-37, 288), (-20, 309), (12, 314), (37, 289))
    side = -1 if eye.side == "right" else 1
    shape = tuple((center + x * side, y + drop) for x, y in points)
    return Image.alpha_composite(clean, _crease(eye, shape, 4.55, 70))


def _half_closed(eye, clean, original, mask):
    # Occlude the upper iris as a real lid would. Leave the visible iris at
    # its original scale, including its original side and lower contours.
    center = eye.center[0]
    left, top = eye.box[:2]
    edge_y = 280 if eye.side == "left" else 281
    half = Image.new("L", original.size)
    pixels = half.load()
    mask_pixels = mask.load()
    radius = 40
    for x in range(half.width):
        along = (left + x - center) / radius
        cutoff = edge_y + 7 * (1 - along * along)
        for y in range(half.height):
            open_fraction = min(1, max(0, (top + y - cutoff + 1) / 2))
            pixels[x, y] = round(mask_pixels[x, y] * open_fraction)
    covered = Image.composite(original, clean, half)
    points = ((center - radius, edge_y), (center - 13, edge_y + 9.3),
              (center + 13, edge_y + 9.3), (center + radius, edge_y))
    return Image.alpha_composite(covered, _crease(eye, points, 2.7, 44))


def _patch(image, mask):
    image = image.copy()
    image.putalpha(mask)
    return image


def _expressions(master, core):
    result = {}
    happy_eyes = Image.new("RGBA", _size(HAPPY_EYES))
    wide = Image.new("RGBA", _size(WIDE))
    for eye in EYES:
        box, bounds = eye.box, eye.bounds
        mask = _mask(box, bounds, 30, 2.2)
        original = master.crop(box)
        clean = _clean_eye(master, core, eye, original, mask)
        result[f"blink-{eye.side}"] = _patch(_closed(eye, clean), mask)
        result[f"blink-{eye.side}-half"] = _patch(_half_closed(eye, clean, original, mask), mask)
        happy = _patch(_closed(eye, clean, happy=True), mask)
        happy_eyes.alpha_composite(happy, (box[0] - HAPPY_EYES[0], 0))

        wide_box = (box[0], WIDE[1], box[2], WIDE[3])
        larger_eye = _reshape(master.crop(wide_box), wide_box, eye.center, 1.055, 1.17, -1.2)
        wide_mask = _mask(wide_box, (bounds[0], bounds[1] - 6, bounds[2], bounds[3] + 4), 27, 3.5)
        wide.alpha_composite(_patch(larger_eye, wide_mask), (box[0] - WIDE[0], 0))

    result["happy-eyes"] = happy_eyes
    result["wide"] = wide
    mouth = _reshape(master.crop(MOUTH), MOUTH, (391, 331), 1.15, 1.05, -1)
    result["happy-mouth"] = _patch(mouth, _mask(MOUTH, (351, 304, 430, 360), 14, 3.7))
    return result


def bake_expressions(output: Path):
    """Export transparent head-local plates keyed by skin and expression."""
    output.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE / "nunti-motion" / "core.png") as image:
        core = image.convert("RGBA")
    sources = {
        "base": SOURCE / "nunti-motion" / "base.png",
        **{skin: SOURCE / "skin-v2" / "polish" / skin / "final.png" for skin in SKINS},
    }
    for skin, path in sources.items():
        with Image.open(path) as image:
            for name, plate in _expressions(image.convert("RGBA"), core).items():
                plate.save(output / f"{skin}-{name}.png", optimize=True)
