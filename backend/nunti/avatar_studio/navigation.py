"""Conservative colored-line extraction. Screen pixels are never geographic evidence."""

from __future__ import annotations

import colorsys
import heapq
import io
import math
import re
import warnings as image_warnings
from collections import Counter
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 8_388_608
SAMPLE_EDGE = 512
MAX_ROUTE_POINTS = 512
COLOR_HINTS = {
    "blue": "#2478ec",
    "cyan": "#16b9c2",
    "purple": "#8650dd",
    "green": "#2ca557",
    "red": "#dd3535",
    "orange": "#ed8745",
}


@dataclass
class _Candidate:
    path: list[tuple[int, int]]
    length: float
    pixels: int
    hue: int


def _image(value: bytes) -> tuple[Image.Image, list[str]]:
    if not isinstance(value, bytes) or not value or len(value) > MAX_IMAGE_BYTES:
        raise ValueError("INVALID_IMAGE_BYTES")
    notes = []
    try:
        with image_warnings.catch_warnings():
            image_warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(value)) as source:
                if source.format not in {"PNG", "JPEG"}:
                    raise ValueError("UNSUPPORTED_IMAGE_FORMAT")
                w, h = source.size
                if not (64 <= w <= 4096 and 64 <= h <= 4096 and w * h <= MAX_IMAGE_PIXELS):
                    raise ValueError("IMAGE_DIMENSIONS_EXCEEDED")
                if getattr(source, "n_frames", 1) != 1:
                    raise ValueError("ANIMATED_IMAGE_UNSUPPORTED")
                if source.getexif().get(274, 1) != 1:
                    notes.append("IMAGE_EXIF_ORIENTATION_APPLIED")
                source.load()
                oriented = ImageOps.exif_transpose(source).convert("RGBA")
                background = Image.new("RGBA", oriented.size, "white")
                background.alpha_composite(oriented)
                return background.convert("RGB"), notes
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("IMAGE_DIMENSIONS_EXCEEDED") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("INVALID_IMAGE") from exc


def _hint_hue(hint) -> int | None:
    if hint is None:
        return None
    if isinstance(hint, str) and hint in COLOR_HINTS:
        hint = COLOR_HINTS[hint]
    if isinstance(hint, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", hint):
        rgb = tuple(int(hint[i : i + 2], 16) for i in (1, 3, 5))
    elif (
        isinstance(hint, (list, tuple))
        and len(hint) == 3
        and all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 255 for n in hint)
    ):
        rgb = tuple(hint)
    else:
        raise ValueError("INVALID_COLOR_HINT")
    h, s, v = colorsys.rgb_to_hsv(*(n / 255 for n in rgb))
    if s < 0.35 or v < 0.25:
        raise ValueError("COLOR_HINT_NOT_CHROMATIC")
    return round(h * 255) % 256


def _hue_distance(a: int, b: int) -> int:
    d = abs(a - b)
    return min(d, 256 - d)


def _components(mask: set[int], width: int, height: int):
    remaining = mask.copy()
    while remaining:
        start = remaining.pop()
        component = {start}
        stack = [start]
        while stack:
            p = stack.pop()
            x, y = p % width, p // width
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    q = ny * width + nx
                    if q in remaining:
                        remaining.remove(q)
                        component.add(q)
                        stack.append(q)
        yield component


def _thin(component: set[int], width: int, height: int) -> set[int]:
    """Zhang-Suen thinning, bounded by the already bounded source sample."""
    live = component.copy()
    # Sampled road strokes are thin; the cap also bounds work on unexpected input.
    for _ in range(48):
        changed = False
        for phase in (0, 1):
            remove = []
            for p in live:
                x, y = p % width, p // width
                if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                    continue
                offsets = (-width, -width + 1, 1, width + 1, width, width - 1, -1, -width - 1)
                n = [int(p + offset in live) for offset in offsets]
                count = sum(n)
                transitions = sum(not n[i] and n[(i + 1) % 8] for i in range(8))
                if not (2 <= count <= 6 and transitions == 1):
                    continue
                if phase == 0:
                    keep = n[0] * n[2] * n[4] or n[2] * n[4] * n[6]
                else:
                    keep = n[0] * n[2] * n[6] or n[0] * n[4] * n[6]
                if not keep:
                    remove.append(p)
            if remove:
                live.difference_update(remove)
                changed = True
        if not changed:
            return live
    raise ValueError("ROUTE_STROKE_TOO_COMPLEX")


def _neighbors(p: int, live: set[int], width: int):
    x, y = p % width, p // width
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if (dx == 0 and dy == 0) or x + dx < 0 or x + dx >= width or y + dy < 0:
                continue
            q = (y + dy) * width + x + dx
            if q not in live:
                continue
            # Avoid artificial triangles at a staircase corner of a one-pixel line.
            if dx and dy and (y * width + x + dx in live or (y + dy) * width + x in live):
                continue
            yield q, math.sqrt(2) if dx and dy else 1.0


def _path(component: set[int], width: int, height: int) -> tuple[list[tuple[int, int]], float]:
    live = _thin(component, width, height)
    graph = {p: list(_neighbors(p, live, width)) for p in live}
    # A few pixels of text/antialiasing can create a small spur; do not discard a real branch.
    for _ in range(2):
        remove = set()
        for start in [p for p in live if len(graph[p]) == 1]:
            branch = [start]
            previous, current = start, graph[start][0][0]
            while len(branch) <= 8 and len(graph[current]) == 2:
                branch.append(current)
                following = [q for q, _ in graph[current] if q != previous][0]
                previous, current = current, following
            if len(branch) <= 8 and len(graph[current]) >= 3:
                remove.update(branch)
        if not remove:
            break
        live.difference_update(remove)
        graph = {p: list(_neighbors(p, live, width)) for p in live}
    endpoints = [p for p in live if len(graph[p]) == 1]
    if not endpoints:
        raise ValueError("ROUTE_CLOSED_LOOP_AMBIGUOUS")
    if len(endpoints) != 2 or any(len(graph[p]) > 2 for p in live):
        raise ValueError("ROUTE_BRANCHING_AMBIGUOUS")
    start, finish = sorted(endpoints, key=lambda p: (p % width, p // width))
    distances = {start: 0.0}
    previous = {}
    queue = [(0.0, start)]
    while queue:
        d, p = heapq.heappop(queue)
        if d != distances[p]:
            continue
        if p == finish:
            break
        for q, weight in graph[p]:
            new = d + weight
            if new < distances.get(q, math.inf):
                distances[q] = new
                previous[q] = p
                heapq.heappush(queue, (new, q))
    if finish not in distances:
        raise ValueError("ROUTE_DISCONNECTED")
    ordered = [finish]
    while ordered[-1] != start:
        ordered.append(previous[ordered[-1]])
    ordered.reverse()
    if len(ordered) < len(live) * 0.95:
        raise ValueError("ROUTE_ORDER_AMBIGUOUS")
    return [(p % width, p // width) for p in ordered], distances[finish]


def _simplify(points: list[tuple[int, int]], tolerance: float = 1.0):
    # Iterative Douglas-Peucker avoids a recursion limit on a long zigzag path.
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = points[a]
        bx, by = points[b]
        dx, dy = bx - ax, by - ay
        denominator = dx * dx + dy * dy
        maximum, pivot = tolerance * tolerance, None
        for i in range(a + 1, b):
            px, py = points[i]
            t = (
                0.0
                if denominator == 0
                else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / denominator))
            )
            error = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if error > maximum:
                maximum, pivot = error, i
        if pivot is not None:
            keep.add(pivot)
            stack.extend(((a, pivot), (pivot, b)))
    return [points[i] for i in sorted(keep)]


def extract_route(png_bytes: bytes, color_hint=None) -> dict:
    """Return an unconfirmed route in whole-image 0..1 screen coordinates.

    A color hint is one of COLOR_HINTS, '#RRGGBB', or an RGB triple. It narrows color selection, not
    route identity or travel direction. Ambiguous alternatives are never auto-selected.
    All ValueError messages are bounded codes suitable for the API boundary.
    """
    image, notes = _image(png_bytes)
    hint = _hint_hue(color_hint)
    w, h = image.size
    image.thumbnail((SAMPLE_EDGE, SAMPLE_EDGE), Image.Resampling.LANCZOS)
    sw, sh = image.size
    hsv = image.convert("HSV").tobytes()
    chromatic = {
        i // 3: hsv[i] for i in range(0, len(hsv), 3) if hsv[i + 1] >= 100 and hsv[i + 2] >= 70
    }
    if not chromatic:
        raise ValueError("NO_COLORED_ROUTE")
    if hint is not None:
        hues = [hint]
    else:
        histogram = Counter((hue // 8) * 8 + 4 for hue in chromatic.values())
        hues = []
        for hue, _ in histogram.most_common():
            if all(_hue_distance(hue, other) > 22 for other in hues):
                hues.append(hue)
                if len(hues) == 6:
                    break
    candidates = []
    failures = []
    background = False
    for hue in hues:
        mask = {i for i, value in chromatic.items() if _hue_distance(value, hue) <= 15}
        # Close sample-pixel antialias holes; a broad branch or loop remains visible.
        plane = bytearray(sw * sh)
        for index in mask:
            plane[index] = 255
        closed = Image.frombytes("L", (sw, sh), bytes(plane)).filter(ImageFilter.MaxFilter(3))
        closed = closed.filter(ImageFilter.MinFilter(3)).tobytes()
        mask = {i for i, value in enumerate(closed) if value}
        for component in _components(mask, sw, sh):
            if len(component) < 30:
                continue
            xs = [p % sw for p in component]
            ys = [p // sw for p in component]
            bw, bh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            if max(bw, bh) < max(sw, sh) * 0.18:
                continue
            if len(component) > sw * sh * 0.18 or len(component) / (bw * bh) > 0.70:
                # An ordinary thin horizontal/vertical route naturally fills its narrow bbox.
                if min(bw, bh) > 16 or len(component) > sw * sh * 0.18:
                    background = True
                    continue
            try:
                ordered, length = _path(component, sw, sh)
            except ValueError as exc:
                failures.append(str(exc))
                continue
            if length < max(sw, sh) * 0.23:
                continue
            mean_width = len(component) / max(length, 1)
            if mean_width > 22:
                background = True
                continue
            candidates.append(_Candidate(ordered, length, len(component), hue))
    if not candidates:
        if failures:
            raise ValueError(failures[0])
        if background:
            raise ValueError("ROUTE_COLOR_BACKGROUND_AMBIGUOUS")
        raise ValueError("NO_ROUTE_FOUND")
    candidates.sort(key=lambda item: item.length, reverse=True)
    chosen = candidates[0]
    if len(candidates) > 1 and candidates[1].length >= chosen.length * 0.45:
        raise ValueError("MULTIPLE_ROUTES_AMBIGUOUS")
    if failures:
        # Another prominent component formed an unresolved network; do not ignore that alternative.
        raise ValueError("OTHER_ROUTE_GEOMETRY_AMBIGUOUS")
    simplified = _simplify(chosen.path)
    if len(simplified) > MAX_ROUTE_POINTS:
        raise ValueError("ROUTE_TOO_COMPLEX")
    confidence = 0.86 if hint is not None else 0.76
    if background:
        notes.append("OTHER_COLORED_BACKGROUND_IGNORED")
        confidence -= 0.10
    if len(candidates) > 1:
        notes.append("SMALLER_COLORED_COMPONENTS_PRESENT")
        confidence -= 0.08
    notes.extend(
        ("USER_CONFIRMATION_REQUIRED", "SCREEN_COORDINATES_ONLY", "ROUTE_DIRECTION_UNVERIFIED")
    )
    return {
        "points": [[round((x + 0.5) / sw, 7), round((y + 0.5) / sh, 7)] for x, y in simplified],
        "confidence": round(max(0.0, confidence), 2),
        "warnings": notes,
        "imageWidth": w,
        "imageHeight": h,
        "inputOrigin": "NAVIGATION_SCREENSHOT",
    }
