"""Render an original route-shaped local RGBA companion; no inference or stock assets."""

from __future__ import annotations

import hashlib
import io
import json
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .design_intent import build_design_intent
from .journey_art import render_character, silhouette_contour

SIZE = 768
_SCALE = 2
_CANVAS = SIZE * _SCALE
_VERSION = "purpose-wardrobe-storybook-4"


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float):
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _xy(point):
    return tuple(round(value * _SCALE) for value in point)


def _box(box):
    return tuple(round(value * _SCALE) for value in box)


def _layer():
    return Image.new("RGBA", (_CANVAS, _CANVAS))


def _curve(start, *segments, steps=28):
    """Sample connected cubic Beziers in display-space pixels."""
    points = [start]
    p0 = start
    for p1, p2, p3 in segments:
        for n in range(1, steps + 1):
            t = n / steps
            u = 1 - t
            points.append(
                tuple(
                    u**3 * p0[axis]
                    + 3 * u * u * t * p1[axis]
                    + 3 * u * t * t * p2[axis]
                    + t**3 * p3[axis]
                    for axis in (0, 1)
                )
            )
        p0 = p3
    return points


def _stroke(draw, points, color, width):
    scaled = [_xy(point) for point in points]
    draw.line(scaled, fill=color, width=max(1, round(width * _SCALE)), joint="curve")
    radius = width * _SCALE / 2
    for x, y in (scaled[0], scaled[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)


def _shape_mask(points):
    mask = Image.new("L", (_CANVAS, _CANVAS))
    ImageDraw.Draw(mask).polygon([_xy(point) for point in points], fill=255)
    return mask


def _clip(layer, mask):
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def _soft_ellipse(box, color, blur):
    layer = Image.new("RGBA", (_CANVAS, _CANVAS), (*color[:3], 0))
    ImageDraw.Draw(layer).ellipse(_box(box), fill=color)
    layer.putalpha(layer.getchannel("A").filter(ImageFilter.GaussianBlur(blur * _SCALE)))
    return layer


def _matte(points, color, accent):
    """Opaque pastel planes with one shallow underside tone, never clear glass."""
    mask = _shape_mask(points)
    base = _mix(color, (255, 249, 233), 0.22)
    result = Image.new("RGBA", (_CANVAS, _CANVAS), (*base, 0))
    result.putalpha(mask)
    bounds = mask.getbbox()
    left, top, right, bottom = (v / _SCALE for v in bounds)
    width, height = right - left, bottom - top
    underside = _layer()
    draw = ImageDraw.Draw(underside)
    tone = _mix(base, accent, 0.23)
    draw.ellipse(
        _box(
            (left - width * 0.1, top + height * 0.68, right + width * 0.3, bottom + height * 0.42)
        ),
        fill=(*tone, 255),
    )
    result = Image.alpha_composite(result, _clip(underside, mask))
    # A quiet coloured contour supports the illustrated silhouette at 64px.
    edge = _layer()
    _stroke(ImageDraw.Draw(edge), points + points[:1], (*_mix(base, accent, 0.45), 125), 1.1)
    return Image.alpha_composite(result, _clip(edge, mask)), mask


def _ellipse_points(cx, cy, rx, ry, tilt=0.0):
    result = []
    for n in range(121):
        angle = n / 120 * math.tau
        x, y = rx * math.cos(angle), ry * math.sin(angle)
        result.append(
            (
                cx + x * math.cos(tilt) - y * math.sin(tilt),
                cy + x * math.sin(tilt) + y * math.cos(tilt),
            )
        )
    return result


def _pixels(points):
    return [(x * SIZE, y * SIZE) for x, y in points]


def _front_face(image, mask, plan):
    x, y = _pixels([plan["formation"]["faceCenter"]])[0]
    details = plan["fineDetails"]
    patch = Image.new("RGBA", (_CANVAS, _CANVAS), (255, 246, 225, 0))
    facial_plane = _curve(
        (x, y - 94),
        ((x + 75, y - 110), (x + 136, y - 60), (x + 134, y + 10)),
        ((x + 134, y + 82), (x + 70, y + 119), (x, y + 117)),
        ((x - 82, y + 121), (x - 138, y + 74), (x - 132, y + 5)),
        ((x - 133, y - 65), (x - 73, y - 108), (x, y - 94)),
    )
    ImageDraw.Draw(patch).polygon([_xy(point) for point in facial_plane], fill=(255, 246, 225, 238))
    patch.putalpha(patch.getchannel("A").filter(ImageFilter.GaussianBlur(2.2 * _SCALE)))
    image = Image.alpha_composite(image, _clip(patch, mask))
    cheeks = Image.new("RGBA", (_CANVAS, _CANVAS), (242, 153, 125, 0))
    draw = ImageDraw.Draw(cheeks)
    for side in (-1, 1):
        cx = x + side * 87
        draw.ellipse(
            _box((cx - 26, y + 21, cx + 26, y + 48)), fill=(242, 153, 125, details["blush"])
        )
    cheeks.putalpha(cheeks.getchannel("A").filter(ImageFilter.GaussianBlur(9 * _SCALE)))
    image = Image.alpha_composite(image, _clip(cheeks, mask))
    for side in (-1, 1):
        cx = x + side * 52 * details["eyeGap"]
        r = 14.5 * details["eyeScale"]
        eye = _layer()
        draw = ImageDraw.Draw(eye)
        draw.ellipse(_box((cx - r, y - r * 1.18, cx + r, y + r * 1.18)), fill=(85, 52, 37, 252))
        draw = ImageDraw.Draw(eye)
        glint = details["glint"]
        draw.ellipse(
            _box((cx - r * 0.43 + glint, y - r * 0.72, cx - r * 0.02 + glint, y - r * 0.29)),
            fill=(255, 255, 250, 255),
        )
        draw.ellipse(
            _box((cx + r * 0.23, y + r * 0.43, cx + r * 0.4, y + r * 0.6)),
            fill=(244, 214, 166, 170),
        )
        image = Image.alpha_composite(image, eye)
    mouth = _layer()
    draw = ImageDraw.Draw(mouth)
    if details["smile"] == "TINY_OPEN_SMILE":
        opening = _curve(
            (x - 14, y + 31),
            ((x - 5, y + 36), (x + 6, y + 36), (x + 15, y + 30)),
            ((x + 14, y + 54), (x - 11, y + 55), (x - 14, y + 31)),
            steps=16,
        )
        draw.polygon([_xy(point) for point in opening], fill=(124, 75, 43, 255))
        draw.ellipse(_box((x - 7, y + 42, x + 10, y + 49)), fill=(235, 156, 143, 255))
    else:
        line = _curve(
            (x - 13, y + 34),
            ((x - 8, y + 42), (x - 1, y + 40), (x + 2, y + 36)),
            ((x + 7, y + 32), (x + 11, y + 40), (x + 17, y + 32)),
            steps=16,
        )
        _stroke(draw, line, (124, 75, 43, 245), 4)
    return Image.alpha_composite(image, mouth)


def _render_plan(plan):
    return render_character(plan)


def render_avatar(points, destination, traits, purpose, journey_id) -> tuple[bytes, dict]:
    """Create a new local image; full route geometry and explicit traits drive its body."""
    if not isinstance(journey_id, str) or not journey_id.strip() or len(journey_id) > 4000:
        raise ValueError("journey_id must be a nonempty string up to 4000 characters")
    fine_seed = hashlib.sha256(journey_id.encode("utf-8")).hexdigest()
    plan = build_design_intent(points, destination, traits, purpose, fine_detail_seed=fine_seed)
    image = _render_plan(plan)
    plan["formation"]["contour"] = silhouette_contour(image)
    plan["geometrySignature"] = hashlib.sha256(
        json.dumps(plan["formation"], sort_keys=True).encode()
    ).hexdigest()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    intent = plan["visualIntent"]
    prefix = {"coast": "포말", "garden": "새잎", "prism": "진주", "moon": "달빛", "pearl": "몽글"}[
        intent["destinationTheme"]
    ]
    name = prefix + ("콩", "모리", "누리", "포롱", "방울")[int(fine_seed[:4], 16) % 5]
    metadata = {
        "displayName": name,
        "personality": plan["characterPlan"]["summary"],
        "palette": plan["formation"]["palette"],
        "motifs": [
            {
                "label": label,
                "source": evidence["source"],
                "target": evidence["target"],
                "detail": evidence["detail"],
            }
            for label, evidence in zip(
                ("경로에서 태어난 몸짓", "목적지의 기념 장식", "여행 목적의 의상과 행동"),
                intent["evidence"],
                strict=True,
            )
        ],
        "voice": {
            "description": "작고 맑은 동반자. 부드럽고 짧게, 문장 끝을 과장하지 않는 목소리.",
            "rate": 0.91 if intent["purposeMood"] == "REST" else 0.96,
            "pitch": round(1.1 + plan["fineDetails"]["warmth"] * 0.4, 3),
        },
        "renderVersion": _VERSION,
        "designVersion": plan["designVersion"],
        "form": intent["destinationTheme"],
        "seedFingerprint": fine_seed[:16],
        "mediaOrigin": "LOCAL_RENDER",
        "routeThread": plan["routeThread"],
        "visualIntent": intent,
        "characterPlan": plan["characterPlan"],
        "formation": plan["formation"],
        "geometrySignature": plan["geometrySignature"],
    }
    return buffer.getvalue(), metadata
