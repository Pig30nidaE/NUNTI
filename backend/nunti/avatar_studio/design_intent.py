"""Navigation geometry and explicit journey intent become a character art plan.

V3 varies complete, activity-compatible character compositions. Route geometry
still supplies ordered formation correspondence; clothing and actions come from
the explicit visit purpose. Geography and the user's feelings are not invented.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re

from .journey_art import build_character_plan, character_tilt

DESIGN_VERSION = "journey-character-3"
FORMATION_VERSION = "route-volume-2"
SIZE = 768
_THEMES = (
    (
        "coast",
        ("바다", "해변", "해안", "파도", "물결", "coast", "ocean", "sea"),
        ("#a5dace", "#76bdbd", "#fff0c8"),
        "부드러운 파도형 외곽",
    ),
    (
        "garden",
        ("숲", "정원", "나무", "수목", "식물", "나뭇잎", "잎", "공원", "forest", "garden"),
        ("#d1dfb1", "#86b8a1", "#ffedba"),
        "두 잎이 자란 씨앗형 외곽",
    ),
    (
        "prism",
        ("유리", "공예", "전시", "미술", "박물관", "프리즘", "건축", "glass", "museum"),
        ("#d6cce3", "#9cbdca", "#ffe4c1"),
        "모서리가 둥근 프리즘 몸체",
    ),
    (
        "moon",
        ("야경", "밤하늘", "별빛", "천문", "night"),
        ("#b8c7df", "#b6a6d0", "#fff0c9"),
        "모서리가 부드러운 달빛형 외곽",
    ),
)


def validate_route(points):
    if not isinstance(points, (list, tuple)) or not 2 <= len(points) <= 4096:
        raise ValueError("route requires 2..4096 normalized points")
    result = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("each route point requires x and y")
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not 0 <= v <= 1
            for v in point
        ):
            raise ValueError("route coordinates must be finite numbers in 0..1")
        clean = (float(point[0]), float(point[1]))
        if not result or clean != result[-1]:
            result.append(clean)
    if len(result) < 2:
        raise ValueError("route requires distinct points")
    return result


def resample_path(points, count):
    lengths = [0.0]
    for a, b in zip(points, points[1:], strict=False):
        lengths.append(lengths[-1] + math.dist(a, b))
    if lengths[-1] <= 0:
        return [points[0]] * count
    output, cursor = [], 1
    for n in range(count):
        distance = lengths[-1] * n / (count - 1)
        while cursor < len(lengths) - 1 and lengths[cursor] < distance:
            cursor += 1
        span = lengths[cursor] - lengths[cursor - 1]
        t = (distance - lengths[cursor - 1]) / span if span else 0
        a, b = points[cursor - 1], points[cursor]
        output.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return output


def _unit(x, y):
    length = math.hypot(x, y)
    return (x / length, y / length) if length else (1.0, 0.0)


def route_features(route):
    samples = resample_path(route, 96)
    cx = sum(p[0] for p in samples) / len(samples)
    cy = sum(p[1] for p in samples) / len(samples)
    xx = sum((p[0] - cx) ** 2 for p in samples)
    yy = sum((p[1] - cy) ** 2 for p in samples)
    xy = sum((p[0] - cx) * (p[1] - cy) for p in samples)
    theta = 0.5 * math.atan2(2 * xy, xx - yy)
    axis = (math.cos(theta), math.sin(theta))
    flow = _unit(route[-1][0] - route[0][0], route[-1][1] - route[0][1])
    if axis[0] * flow[0] + axis[1] * flow[1] < 0:
        axis = (-axis[0], -axis[1])
    total = sum(math.dist(a, b) for a, b in zip(route, route[1:], strict=False))
    direct = math.dist(route[0], route[-1])
    distances = [0.0]
    for a, b in zip(route, route[1:], strict=False):
        distances.append(distances[-1] + math.dist(a, b))
    turns = []
    for index in range(1, len(route) - 1):
        before, here, after = route[index - 1 : index + 2]
        a = _unit(here[0] - before[0], here[1] - before[1])
        b = _unit(after[0] - here[0], after[1] - here[1])
        angle = math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])
        if abs(angle) > 0.12:
            turns.append((abs(angle), index, angle, distances[index] / total))
    chosen = []
    for turn in sorted(turns, reverse=True):
        if all(abs(turn[3] - prior[3]) >= 0.11 for prior in chosen):
            chosen.append(turn)
        if len(chosen) == 3:
            break
    chosen.sort(key=lambda value: value[3])
    bounds_x = max(p[0] for p in route) - min(p[0] for p in route)
    bounds_y = max(p[1] for p in route) - min(p[1] for p in route)
    return {
        "axis": list(axis),
        "flow": list(flow),
        "aspectRatio": round(bounds_x / max(bounds_y, 0.000001), 5),
        "tortuosity": round(total / max(direct, total * 0.05), 5),
        "turning": round(sum(t[0] for t in turns), 5),
        "landmarks": [
            {
                "arcFraction": round(t[3], 6),
                "pointIndex": t[1],
                "sourcePoint": list(route[t[1]]),
                "signedTurn": round(t[2], 6),
                "selection": "MAJOR_TURN",
            }
            for t in chosen
        ],
    }


def _theme(traits, destination, purpose):
    for source, text in (
        ("입력된 목적지 특성", traits),
        ("입력된 목적지 이름", destination),
        ("입력된 방문 목적", purpose),
    ):
        for name, words, palette, label in _THEMES:
            match = next(
                (
                    word
                    for word in words
                    if (
                        re.search(r"(?<![a-z])" + word + r"(?![a-z])", text.lower())
                        if word.isascii()
                        else word in text
                    )
                ),
                "",
            )
            if match:
                return name, palette, label, source, match
    return "pearl", ("#e3d9c5", "#b6cbc0", "#fff0cf"), "둥근 진주빛 외곽", "기본 창작 재질", ""


def _mood(purpose):
    if any(word in purpose for word in ("휴식", "쉬", "산책", "relax", "rest")):
        return "REST", "낮고 편안한 자세", 1.08, 0.94
    if any(word in purpose for word in ("탐험", "관람", "탐방", "explor")):
        return "EXPLORE", "앞을 향해 살짝 기울인 자세", 0.99, 1.02
    if any(word in purpose for word in ("기념", "축하", "celebrat")):
        return "KEEPSAKE", "작은 발을 모은 기념 자세", 1.01, 1.01
    return "NEUTRAL", "기본 동반자 자세", 1.0, 1.0


def _fit(points, width, height, center):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    scale = min(width / max(dx, 0.000001), height / max(dy, 0.000001))
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return [(center[0] + (p[0] - cx) * scale, center[1] + (p[1] - cy) * scale) for p in points]


def _ellipse(cx, cy, rx, ry, angle=0.0):
    return {"center": (cx, cy), "radii": (rx, ry), "angle": angle}


def ellipse_contour(ellipse, count=96):
    cx, cy = ellipse["center"]
    rx, ry = ellipse["radii"]
    cosine, sine = math.cos(ellipse["angle"]), math.sin(ellipse["angle"])
    return [
        (
            cx + rx * math.cos(t) * cosine - ry * math.sin(t) * sine,
            cy + rx * math.cos(t) * sine + ry * math.sin(t) * cosine,
        )
        for t in (n * math.tau / (count - 1) for n in range(count))
    ]


def _ray_extent(origin, direction, ellipse):
    cosine, sine = math.cos(ellipse["angle"]), math.sin(ellipse["angle"])
    dx, dy = origin[0] - ellipse["center"][0], origin[1] - ellipse["center"][1]
    ox, oy = dx * cosine + dy * sine, -dx * sine + dy * cosine
    ux = direction[0] * cosine + direction[1] * sine
    uy = -direction[0] * sine + direction[1] * cosine
    rx, ry = ellipse["radii"]
    a = (ux / rx) ** 2 + (uy / ry) ** 2
    b = 2 * (ox * ux / rx**2 + oy * uy / ry**2)
    c = (ox / rx) ** 2 + (oy / ry) ** 2 - 1
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return 0.0
    return max(0.0, (-b + math.sqrt(discriminant)) / (2 * a))


def _outline(center, rx, ry, ellipses, theme, phase):
    # A single rounded mass dominates; route crests never become a long thin worm.
    count = 191
    radii = []
    for n in range(count):
        theta = n * math.tau / count
        direction = math.cos(theta), math.sin(theta)
        base = 1 / math.sqrt((direction[0] / rx) ** 2 + (direction[1] / ry) ** 2)
        if theme in ("prism", "moon"):
            local = (theta - phase + math.pi / 6) % (math.pi / 3) - math.pi / 6
            hexagon = min(rx, ry) * 0.92 / math.cos(local)
            base = base * 0.3 + hexagon * 0.7
        radii.append(max(base, *(_ray_extent(center, direction, e) for e in ellipses)))
    # Round intersection seams while retaining the large route/leaf silhouette.
    for _ in range(2):
        radii = [
            (radii[(i - 1) % count] + 2 * r + radii[(i + 1) % count]) / 4
            for i, r in enumerate(radii)
        ]
    contour = [
        (
            center[0] + radius * math.cos(n * math.tau / count),
            center[1] + radius * math.sin(n * math.tau / count),
        )
        for n, radius in enumerate(radii)
    ]
    return contour + contour[:1]


def _normalized(points):
    return [[round(x / SIZE, 7), round(y / SIZE, 7)] for x, y in points]


def build_design_intent(points, destination, traits, purpose, *, fine_detail_seed):
    """Resolve place, activity and character composition before drawing any pixels."""
    route = validate_route(points)
    if any(not isinstance(v, str) for v in (destination, traits, purpose, fine_detail_seed)):
        raise ValueError("design text and fine_detail_seed must be strings")
    if not destination.strip() or not fine_detail_seed.strip():
        raise ValueError("destination and fine_detail_seed must not be empty")
    if any(len(v) > 4000 for v in (destination, traits, purpose, fine_detail_seed)):
        raise ValueError("design text exceeds 4000 characters")
    features = route_features(route)
    character = build_character_plan(destination, traits, purpose, fine_detail_seed, features)
    theme, palette, structure, theme_source, matched = _theme(traits, destination, purpose)
    # Known place metadata fills the lexical gap (e.g. 을왕리 has no '해변' syllable).
    if theme == "pearl":
        place_theme = {
            "BEACH": "coast",
            "RIVER": "coast",
            "GARDEN": "garden",
            "MOUNTAIN": "garden",
            "MUSEUM": "prism",
            "NIGHT": "moon",
        }.get(character["destination"]["kind"])
        if place_theme:
            selected = next(row for row in _THEMES if row[0] == place_theme)
            theme, _, palette, structure = selected
            theme_source = "확인된 목적지 이름"
            matched = character["destination"]["label"]
    mood, posture, width_factor, height_factor = _mood(purpose.lower())
    flow_x, flow_y = features["flow"]
    axis_x, axis_y = features["axis"]
    body = (384 + flow_x * 9, 446 + flow_y * 3)
    face = (body[0] + flow_x * 17, body[1] - 38 + flow_y * 5)
    aspect = min(5, features["aspectRatio"])
    rx = (156 + 10 * (aspect / (1 + aspect) - 0.5)) * width_factor
    ry = (151 - 7 * (aspect / (1 + aspect) - 0.5)) * height_factor
    fitted = _fit(resample_path(route, 96), 308, 252, (384, 413))
    # Keep the start as a short projecting tail; a large round mass carries the face.
    # Indices retain source arc fractions even though this styling changes arc lengths.
    spine = []
    for n, (x, y) in enumerate(fitted):
        tail_gain = 1 + 0.17 * max(0, 1 - (n / 95) / 0.25)
        spine.append((body[0] + (x - body[0]) * tail_gain, body[1] + (y - body[1]) * tail_gain))
    ellipses, ears = [], []
    # Major bends define the route's thick mantle, with small start-tail and end-crest.
    for n in range(0, 96, 3):
        t = n / 95
        radius = 15 + 31 * math.sin(math.pi * t) ** 2 + 19 * t
        ellipses.append(_ellipse(*spine[n], radius, radius * 0.96))
    ellipses.append(_ellipse(*spine[-1], 39, 39))
    if theme == "garden":
        lean = flow_x * 0.19 + axis_x * axis_y * 0.12
        leaves = [
            _ellipse(body[0] - 66, body[1] - 113, 55, 105, -0.37 + lean),
            _ellipse(body[0] + 65, body[1] - 124, 55, 111, 0.35 + lean),
        ]
        for leaf in leaves:
            ellipses.append(leaf)
            contour = ellipse_contour(leaf)
            tip = min(contour, key=lambda p: p[1])
            ears.append({"anchor": _normalized([body])[0], "tip": _normalized([tip])[0]})
    elif theme == "coast":
        # Broad overlapping folds, aligned to the route rather than a decorative hat.
        crest = spine[76]
        folds = [
            _ellipse(body[0] - 62 + axis_x * 15, body[1] - 91, 91, 54, -0.26 + axis_y * 0.2),
            _ellipse(crest[0], crest[1] + 12, 69, 40, math.atan2(flow_y, flow_x)),
        ]
        ellipses.extend(folds)
        ears.append({"anchor": _normalized([spine[72]])[0], "tip": _normalized([spine[-1]])[0]})
    else:
        # The route's end is the folded crest for pearl/prism, never a random ear choice.
        end = spine[-1]
        crest = _ellipse(end[0], end[1], 41, 49, axis_x * axis_y * 0.4)
        ellipses.append(crest)
        ears.append({"anchor": _normalized([spine[78]])[0], "tip": _normalized([end])[0]})
    feet = [
        _ellipse(body[0] - 60, body[1] + ry * 0.89, 29, 18, -0.1),
        _ellipse(body[0] + 60, body[1] + ry * 0.89, 29, 18, 0.1),
    ]
    ellipses.extend(feet)
    contour = _outline(body, rx, ry, ellipses, theme, math.atan2(axis_y, axis_x))
    for mark in features["landmarks"]:
        fraction = mark["arcFraction"]
        mark["targetPoint"] = _normalized([spine[round(fraction * 95)]])[0]
        mark["part"] = "tail" if fraction < 0.35 else "mantle" if fraction < 0.78 else "crest"
    features["bodyInterpretation"] = "CREATIVE_ROUTE_VOLUME_NOT_GEOGRAPHY"
    thread = _fit(route, 156, 92, (body[0], body[1] + 63))
    evidence = [
        {
            "source": "확인된 내비게이션 경로",
            "detail": (
                "큰 굽이와 주축을 귀의 기울기·바깥 꼬리 곡선·탄생 궤적으로 옮긴 창작 해석입니다. "
                "피부에 경로를 그리지 않습니다."
            ),
            "target": "귀의 방향·꼬리·탄생 궤적",
        },
        {
            "source": theme_source,
            "detail": (
                f"{character['destination']['evidence']}. "
                f"{character['destination']['landmarkLabel']}를 옷에 달린 기념 장식으로 표현합니다."
            )
            + (
                f" 명시된 ‘{matched}’의 색조를 함께 씁니다."
                if matched
                else " 확인되지 않은 지형을 추정하지 않습니다."
            ),
            "target": character["destination"]["landmarkLabel"],
        },
        {
            "source": "입력된 방문 목적",
            "detail": (
                f"‘{purpose or '미입력'}’: {character['outfit']['label']}, "
                f"{character['prop']['label']}, {character['action']} 자세. "
                "사용자 감정을 추정한 결과가 아닙니다."
            ),
            "target": "의상·행동·소품·음성 역할",
        },
    ]
    formation = {
        "version": FORMATION_VERSION,
        "contour": _normalized(contour),
        "spine": _normalized(spine),
        "faceCenter": _normalized([face])[0],
        "palette": list(palette),
        "ears": ears,
        "motionTheme": character["motionTheme"],
        "characterSignature": character["structuralSignature"],
    }
    # The final renderer replaces contour with the measured opaque silhouette.
    # Face center must already identify the new character rather than the old blob.
    cx = 384 + character["routeInfluence"]["earLean"] * 0.5
    cy = 346 + (17 if character["pose"] == "SIT" else 0)
    theta = -math.radians(character_tilt(character))
    face_x = cx - (cy - 430) * math.sin(theta)
    face_y = 430 + (cy - 430) * math.cos(theta)
    if character["composition"]["facing"] == -1:
        face_x = SIZE - face_x
    formation["faceCenter"] = _normalized([(face_x, face_y)])[0]
    geometry = json.dumps(
        {"formation": formation, "character": character["structuralSignature"]},
        sort_keys=True,
        separators=(",", ":"),
    )
    rng = random.Random(int(hashlib.sha256(fine_detail_seed.encode()).hexdigest(), 16))
    return {
        "designVersion": DESIGN_VERSION,
        "visualIntent": {
            "destinationTheme": theme,
            "purposeMood": mood,
            "purposeRole": character["purpose"]["role"],
            "destinationKind": character["destination"]["kind"],
            "renderingStyle": "MATTE_ILLUSTRATED_2_5D",
            "surfaceRouteMarking": "NONE",
            "routeInterpretation": "SILHOUETTE_AND_PROPORTION_ONLY",
            "evidence": evidence,
            "routeFeatures": features,
            "variationRole": "SEMANTIC_CHARACTER_COMPOSITION",
        },
        "characterPlan": character,
        "formation": formation,
        "bodyCenter": _normalized([body])[0],
        "bodyRadii": [rx / SIZE, ry / SIZE],
        "feet": [_normalized(ellipse_contour(foot, 48)) for foot in feet],
        "routeThread": {
            "points": _normalized(thread),
            "coordinateSpace": "ASSET_NORMALIZED",
            "renderedOnSurface": False,
            "role": "TRANSIENT_FORMATION_REFERENCE",
        },
        "geometrySignature": hashlib.sha256(geometry.encode()).hexdigest(),
        "fineDetailSeed": fine_detail_seed,
        "fineDetails": {
            "eyeScale": rng.uniform(0.92, 1.08),
            "eyeGap": rng.uniform(0.94, 1.06),
            "blush": rng.randrange(68, 112),
            "warmth": rng.uniform(0, 0.11),
            "glint": rng.uniform(-3, 3),
            "frostSeed": rng.getrandbits(32),
            "smile": rng.choice(("SOFT_SMILE", "TINY_OPEN_SMILE")),
        },
    }
