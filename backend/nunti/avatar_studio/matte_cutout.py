"""Conservative flat-border RGB cutout and measured, non-semantic formation.

Original RGB channels and canvas size are preserved. Border-connected background
and at most one conservatively identified detached ground shadow are removed.
This is neither semantic segmentation nor verification of a face, route motif,
artwork quality, or destination likeness.
"""

from __future__ import annotations

import hashlib
import io
from collections import deque
from statistics import median

from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError

from .design_intent import resample_path, validate_route

VERSION = "flat-border-cutout-2"
_DIRECTIONS = ((-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1))


class MatteCutoutError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _neighbors(index, width, height, diagonal=False):
    x, y = index % width, index // width
    if x:
        yield index - 1
    if x + 1 < width:
        yield index + 1
    if y:
        yield index - width
    if y + 1 < height:
        yield index + width
    if diagonal:
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            if 0 <= x + dx < width and 0 <= y + dy < height:
                yield (y + dy) * width + x + dx


def _components(mask, width, height):
    visited = bytearray(len(mask))
    result = []
    for seed in range(len(mask)):
        if not mask[seed] or visited[seed]:
            continue
        pixels, queue = [], deque([seed])
        visited[seed] = 1
        left, top, right, bottom = width, height, 0, 0
        while queue:
            index = queue.popleft()
            pixels.append(index)
            x, y = index % width, index // width
            left, top, right, bottom = min(left, x), min(top, y), max(right, x), max(bottom, y)
            for neighbor in _neighbors(index, width, height, diagonal=True):
                if mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        result.append((pixels, (left, top, right + 1, bottom + 1)))
    return sorted(result, key=lambda component: len(component[0]), reverse=True)


def _detached_ground_shadow(component, primary, rgb, background, differences, width, height):
    """Recognize only a faint, soft oval immediately below the main body.

    Geometry alone cannot distinguish a shadow from a separate prop. Require
    near-neutral darkening and an actual soft falloff as well; ambiguous objects
    remain foreground and the multiple-object check still rejects them.
    """
    pixels, (left, top, right, bottom) = component
    body, (body_left, body_top, body_right, body_bottom) = primary
    body_width, body_height = body_right - body_left, body_bottom - body_top
    shadow_width, shadow_height = right - left, bottom - top
    area_ratio = len(pixels) / len(body)
    aspect = shadow_width / shadow_height
    fill = len(pixels) / (shadow_width * shadow_height)
    if not (
        body_bottom <= top <= body_bottom + height * 0.06
        and bottom <= body_bottom + height * 0.16
        and body_left <= left < right <= body_right
        and abs((left + right) - (body_left + body_right)) / 2 <= body_width * 0.25
        and 0.25 * body_width <= shadow_width <= 0.95 * body_width
        and shadow_height <= min(height * 0.06, body_height * 0.14)
        and 0.005 <= area_ratio <= 0.08
        and len(pixels) <= width * height * 0.02
        and aspect >= 4
        and 0.55 <= fill <= 0.90
    ):
        return None

    def percentile(values, fraction):
        ordered = sorted(values)
        return ordered[round((len(ordered) - 1) * fraction)]

    contrast = [differences[index] for index in pixels]
    darkening = [tuple(background[c] - rgb[index][c] for c in range(3)) for index in pixels]
    chroma = [max(delta) - min(delta) for delta in darkening]
    occupied = set(pixels)
    edge = [
        index
        for index in pixels
        if any(neighbor not in occupied for neighbor in _neighbors(index, width, height))
    ]
    edge_set = set(edge)
    interior = [index for index in pixels if index not in edge_set]
    if not edge or not interior:
        return None
    edge_median = median(differences[index] for index in edge)
    interior_median = median(differences[index] for index in interior)
    ellipse_fraction = sum(
        ((index % width + 0.5 - (left + right) / 2) / (shadow_width / 2)) ** 2
        + ((index // width + 0.5 - (top + bottom) / 2) / (shadow_height / 2)) ** 2
        <= 1.15
        for index in pixels
    ) / len(pixels)
    if not (
        max(contrast) <= 32
        and percentile(contrast, 0.95) <= 28
        and median(contrast) <= 24
        and min(min(delta) for delta in darkening) >= -2
        and percentile(chroma, 0.95) <= 10
        and max(chroma) <= 14
        and interior_median - edge_median >= 2
        and ellipse_fraction >= 0.98
    ):
        return None
    return {
        "reason": "DETACHED_SOFT_GROUND_SHADOW",
        "policy": "BELOW_BODY_WITHIN_WIDTH_SMALL_FLAT_OVAL_LOW_NEUTRAL_CONTRAST_SOFT_EDGE",
        "area": len(pixels),
        "bbox": [left, top, right, bottom],
        "areaRelativeToBody": round(area_ratio, 6),
        "aspectRatio": round(aspect, 6),
        "bboxFill": round(fill, 6),
        "ellipseFraction": round(ellipse_fraction, 6),
        "gapBelowBody": top - body_bottom,
        "maxBackgroundContrast": max(contrast),
        "p95BackgroundContrast": percentile(contrast, 0.95),
        "medianBackgroundContrast": median(contrast),
        "p95DarkeningChroma": percentile(chroma, 0.95),
        "edgeMedianContrast": edge_median,
        "interiorMedianContrast": interior_median,
        "semanticIdentityVerified": False,
    }


def _outer_boundary(pixels, width, height):
    """Moore-neighbour trace of the actual foreground pixel centres."""
    occupied = bytearray(width * height)
    for pixel in pixels:
        occupied[pixel] = 1
    first = min(pixels)
    start = first % width, first // width
    current, backtrack = start, (start[0] - 1, start[1])
    first_next, boundary = None, []
    for _ in range(width * height * 4):
        relative = backtrack[0] - current[0], backtrack[1] - current[1]
        offset = _DIRECTIONS.index(relative)
        next_point, previous = None, backtrack
        for step in range(8):
            dx, dy = _DIRECTIONS[(offset + step) % 8]
            candidate = current[0] + dx, current[1] + dy
            if (
                0 <= candidate[0] < width
                and 0 <= candidate[1] < height
                and occupied[candidate[1] * width + candidate[0]]
            ):
                next_point = candidate
                break
            previous = candidate
        if next_point is None:
            raise MatteCutoutError(
                "BOUNDARY_NOT_TRACEABLE", "외곽을 닫힌 선으로 추적할 수 없습니다."
            )
        if first_next is None:
            first_next = next_point
        elif current == start and next_point == first_next:
            break
        boundary.append((current[0] + 0.5, current[1] + 0.5))
        current, backtrack = next_point, previous
    else:
        raise MatteCutoutError("BOUNDARY_NOT_TRACEABLE", "외곽 추적이 제한 안에 끝나지 않았습니다.")
    if len(boundary) < 24:
        raise MatteCutoutError("BOUNDARY_TOO_SMALL", "측정할 캐릭터 외곽이 너무 작습니다.")
    sampled = resample_path(boundary + boundary[:1], 192)
    return [[round(x / width, 7), round(y / height, 7)] for x, y in sampled]


def _palette(rgb, foreground, background, tolerance):
    colors = [
        rgb[index]
        for index in foreground[::3]
        if max(abs(rgb[index][c] - background[c]) for c in range(3)) > tolerance + 3
    ]
    if not colors:
        colors = [rgb[index] for index in foreground[::3]]
    strip = Image.new("RGB", (len(colors), 1))
    strip.putdata(colors)
    quantized = strip.quantize(colors=5)
    values = quantized.getpalette()
    counts = sorted(quantized.getcolors(), reverse=True)
    return [
        "#" + "".join(f"{v:02x}" for v in values[index * 3 : index * 3 + 3]) for _, index in counts
    ]


def _project_route(route, bbox, width, height):
    left, top, right, bottom = bbox
    xs, ys = [p[0] for p in route], [p[1] for p in route]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    scale = min((right - left) * 0.72 / max(dx, 1e-9), (bottom - top) * 0.70 / max(dy, 1e-9))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [
        [
            round(((left + right) / 2 + (x - cx) * scale) / width, 7),
            round(((top + bottom) / 2 + (y - cy) * scale) / height, 7),
        ]
        for x, y in resample_path(route, 96)
    ]


def cutout_matte_rgb(png_bytes: bytes, route_points) -> tuple[bytes, dict, dict]:
    """Return RGBA PNG, measured formation, and an auditable cutout report.

    The caller must store original png_bytes separately. Rejections leave those
    bytes unchanged and must not fall back to cropping or procedural artwork.
    """
    route = validate_route(route_points)
    if not isinstance(png_bytes, bytes) or not 0 < len(png_bytes) <= 20 * 1024 * 1024:
        raise MatteCutoutError("INVALID_PNG", "PNG 바이트가 비었거나 크기 제한을 넘었습니다.")
    try:
        with Image.open(io.BytesIO(png_bytes)) as source:
            if source.format != "PNG" or source.mode != "RGB":
                raise MatteCutoutError("SOURCE_NOT_RGB_PNG", "원본은 RGB PNG여야 합니다.")
            width, height = source.size
            if min(width, height) < 64 or max(width, height) > 2048 or width * height > 4194304:
                raise MatteCutoutError(
                    "UNSUPPORTED_DIMENSIONS", "지원하는 원본 이미지 크기가 아닙니다."
                )
            image = source.copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise MatteCutoutError("INVALID_PNG", "PNG를 읽을 수 없습니다.") from exc
    raw = image.tobytes()
    rgb = [tuple(raw[n : n + 3]) for n in range(0, len(raw), 3)]
    border = list(range(width)) + list(range((height - 1) * width, height * width))
    border += [y * width for y in range(1, height - 1)]
    border += [y * width + width - 1 for y in range(1, height - 1)]
    background = tuple(
        round(median(rgb[index][channel] for index in border)) for channel in range(3)
    )
    differences = [max(abs(pixel[c] - background[c]) for c in range(3)) for pixel in rgb]
    border_distances = sorted(differences[index] for index in border)
    spread = border_distances[round((len(border_distances) - 1) * 0.98)]
    if spread > 8:
        raise MatteCutoutError("BACKGROUND_NOT_FLAT", "가장자리 배경이 단색에 가깝지 않습니다.")
    tolerance = max(10, spread + 6)
    removed, queue = bytearray(width * height), deque()
    for index in border:
        if differences[index] <= tolerance and not removed[index]:
            removed[index] = 1
            queue.append(index)
    while queue:
        index = queue.popleft()
        for neighbor in _neighbors(index, width, height):
            if not removed[neighbor] and differences[neighbor] <= tolerance:
                removed[neighbor] = 1
                queue.append(neighbor)
    foreground = bytearray(0 if value else 255 for value in removed)
    components = _components(foreground, width, height)
    if not components or len(components[0][0]) < width * height * 0.025:
        raise MatteCutoutError("SUBJECT_TOO_SMALL", "충분한 크기의 단일 캐릭터가 없습니다.")
    primary, bbox = components[0]
    if sum(removed) < width * height * 0.30:
        raise MatteCutoutError(
            "INSUFFICIENT_BACKGROUND", "안정적으로 제거할 외곽 배경이 부족합니다."
        )
    source_components = components
    candidates = [
        (index, evidence)
        for index, component in enumerate(components[1:], 1)
        if (
            evidence := _detached_ground_shadow(
                component, components[0], rgb, background, differences, width, height
            )
        )
    ]
    removed_shadows = []
    # Multiple possible shadows are ambiguous. Do not waive the object check.
    if len(candidates) == 1:
        shadow_index, evidence = candidates[0]
        for index in components[shadow_index][0]:
            foreground[index] = 0
        removed_shadows.append(evidence)
        components = [
            component for index, component in enumerate(components) if index != shadow_index
        ]
    threshold = max(width * height * 0.01, len(primary) * 0.04)
    if any(len(pixels) >= threshold for pixels, _ in components[1:]):
        raise MatteCutoutError(
            "MULTIPLE_LARGE_OBJECTS", "큰 분리 객체나 인셋이 있어 원본 검토가 필요합니다."
        )
    left, top, right, bottom = bbox
    if left == 0 or top == 0 or right == width or bottom == height:
        raise MatteCutoutError(
            "SUBJECT_TOUCHES_FRAME", "캐릭터가 화면 가장자리에 닿아 외곽을 확정할 수 없습니다."
        )
    if len(primary) / ((right - left) * (bottom - top)) > 0.96:
        raise MatteCutoutError("RECTANGULAR_PANEL", "캐릭터 대신 직사각형 패널이 감지되었습니다.")
    hard_alpha = Image.frombytes("L", (width, height), bytes(foreground))
    # Inward-only AA never restores pixels already removed as background.
    alpha = ImageChops.darker(hard_alpha, hard_alpha.filter(ImageFilter.GaussianBlur(0.45)))
    output = image.convert("RGBA")
    output.putalpha(alpha)
    measured = bytes(255 if value >= 128 else 0 for value in alpha.tobytes())
    measured_components = _components(measured, width, height)
    boundary = _outer_boundary(measured_components[0][0], width, height)
    palette = _palette(rgb, primary, background, tolerance)
    spine = _project_route(route, measured_components[0][1], width, height)
    formation = {
        "version": "route-volume-2",
        "source": "MEASURED_ALPHA_BOUNDARY",
        "mapping": "GEOMETRIC_PROJECTION_NOT_SEMANTIC",
        "contour": boundary,
        "spine": spine,
        "faceCenter": None,
        "faceCenterVerified": False,
        "faceCenterSource": "UNKNOWN",
        "palette": palette,
        "alphaThreshold": 128,
    }
    stream = io.BytesIO()
    output.save(stream, format="PNG")
    png = stream.getvalue()
    report = {
        "version": VERSION,
        "originalSha256": hashlib.sha256(png_bytes).hexdigest(),
        "rgbaSha256": hashlib.sha256(png).hexdigest(),
        "width": width,
        "height": height,
        "background": {
            "rgb": list(background),
            "tolerance": tolerance,
            "borderP98Difference": spread,
            "removedPixels": sum(removed),
        },
        "foregroundComponents": [{"area": len(p), "bbox": list(b)} for p, b in components[:12]],
        "sourceForegroundComponents": [
            {"area": len(p), "bbox": list(b)} for p, b in source_components[:12]
        ],
        "removedGroundShadows": removed_shadows,
        "rgbChannelsPreserved": output.convert("RGB").tobytes() == raw,
        "cropApplied": False,
        "method": "BORDER_COLOR_KEY_CONSERVATIVE_DETACHED_SHADOW_INWARD_AA",
        "edgeMatting": "RGB_PRESERVED_NOT_SEMANTIC_MATTING",
        "qualityScope": "FLAT_BACKGROUND_ONLY_FACE_AND_MOTIFS_UNVERIFIED",
        "alphaBoundarySource": "MEASURED_ALPHA_BOUNDARY",
        "faceVerified": False,
        "semanticRouteVerified": False,
        "projectionOutsideAlphaSamples": sum(
            alpha.getpixel((min(width - 1, round(x * width)), min(height - 1, round(y * height))))
            < 128
            for x, y in spine
        ),
    }
    return png, formation, report
