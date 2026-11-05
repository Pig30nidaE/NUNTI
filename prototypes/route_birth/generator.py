"""Route geometry and companion plan. Pure; no model imports or I/O."""
from __future__ import annotations
import colorsys
import hashlib
import json
import math
import unicodedata
import uuid

VERSION = "route-born-1"
REVISION = "41d3337e8b7f2843a75841595fc14e4b9a7a4b96"
PROVIDER = "qwen3-tts-sohee-local"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value, maximum, name, allow_empty=False):
    require(isinstance(value, str), "INVALID_" + name)
    require(not any(unicodedata.category(c).startswith("C") for c in value), "INVALID_" + name)
    require(len(value.encode("utf-16-le")) // 2 <= maximum, "INVALID_" + name)
    require(allow_empty or bool(value.strip()), "INVALID_" + name)
    return value


def normalize(value):
    require(isinstance(value, dict) and set(value) == {"requestId", "destination", "purpose", "route"}, "INVALID_REQUEST_FIELDS")
    request_id = value["requestId"]
    require(isinstance(request_id, str), "INVALID_REQUEST_ID")
    try:
        parsed = uuid.UUID(request_id)
    except (ValueError, AttributeError):
        raise ValueError("INVALID_REQUEST_ID") from None
    require(str(parsed) == request_id, "INVALID_REQUEST_ID")
    destination, route = value["destination"], value["route"]
    require(isinstance(destination, dict) and set(destination) == {"name", "traits"}, "INVALID_DESTINATION_FIELDS")
    require(isinstance(route, dict) and set(route) == {"points"}, "INVALID_ROUTE_FIELDS")
    points = route["points"]
    require(isinstance(points, list) and 2 <= len(points) <= 512, "ROUTE_REQUIRES_2_TO_512_POINTS")
    normalized = []
    for point in points:
        require(isinstance(point, list) and len(point) == 2, "INVALID_ROUTE_POINT")
        require(all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in point), "INVALID_ROUTE_POINT")
        normalized.append([float(point[0]) + 0.0, float(point[1]) + 0.0])
    require(sum(math.dist(a, b) for a, b in zip(normalized, normalized[1:])) > 1e-6, "ROUTE_MUST_HAVE_LENGTH")
    return {"requestId": request_id,
            "destination": {"name": text(destination["name"], 60, "DESTINATION_NAME"), "traits": text(destination["traits"], 240, "DESTINATION_TRAITS", True)},
            "purpose": text(value["purpose"], 120, "PURPOSE", True), "route": {"points": normalized}}


def resample(points, count=72):
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    index, result = 1, []
    for i in range(count):
        target = lengths[-1] * i / (count - 1)
        while index < len(lengths) - 1 and lengths[index] < target:
            index += 1
        span = lengths[index] - lengths[index - 1]
        f = (target - lengths[index - 1]) / span if span else 0
        result.append([round(points[index - 1][k] * (1 - f) + points[index][k] * f, 8) for k in (0, 1)])
    return result


def inside(point, polygon):
    x, y = point
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            result = not result
    return result


def geometry(points, nonce, traits="", purpose=""):
    """Continuous route Fourier signals plus journey noise, never silhouette lookup.

    Exposed fixed nonce permits proving that route changes, independently of UUID
    randomness, change outline/palette. Input polyline is already boundary parsed.
    """
    route = resample(points)
    raw = hashlib.sha256(nonce.encode()).digest()
    noise = [int.from_bytes(raw[i:i + 2], "big") / 65535 for i in range(0, 30, 2)]
    length = sum(math.dist(a, b) for a, b in zip(route, route[1:]))
    dx = max(p[0] for p in route) - min(p[0] for p in route)
    dy = max(p[1] for p in route) - min(p[1] for p in route)
    aspect = (dy - dx) / max(dx + dy, 1e-9)
    angles = [math.atan2(b[1] - a[1], b[0] - a[0]) for a, b in zip(route, route[1:]) if math.dist(a, b) > 1e-8]
    turns = sum(abs(math.atan2(math.sin(b - a), math.cos(b - a))) for a, b in zip(angles, angles[1:]))
    bend = math.tanh(turns / 6)
    # Sampled path harmonics are continuous in the route, not a body-family tag.
    harmonics = []
    for frequency in (1, 2, 3, 4):
        harmonics.append(sum((p[0] - .5) * math.cos(2 * math.pi * frequency * i / 72) + (p[1] - .5) * math.sin(2 * math.pi * frequency * i / 72) for i, p in enumerate(route)) / 72)
    length_signal = math.tanh(length / 2)
    rx = .31 - .04 * aspect + .008 * length_signal + .004 * (noise[0] - .5)
    ry = .325 + .033 * aspect + .004 * length_signal + .004 * (noise[1] - .5)
    heading = math.atan2(route[-1][1] - route[0][1], route[-1][0] - route[0][0])
    signed_turns = sum(math.atan2(math.sin(b - a), math.cos(b - a)) for a, b in zip(angles, angles[1:]))
    route_phase = math.pi * (sum(p[0] * (i + 1) for i, p in enumerate(route)) / 2628 + sum(p[1] * (72 - i) for i, p in enumerate(route)) / 2628)
    outline = []
    for i in range(72):
        theta = -math.pi / 2 + 2 * math.pi * i / 72
        # Visible smooth lobes come from path harmonics, heading and turning.
        # The radial floor preserves space around the same cute readable face.
        wave = .16 * math.tanh(5 * harmonics[0]) * math.cos(2 * theta + heading)
        wave += (.035 + .15 * bend) * math.cos(3 * theta + route_phase)
        wave += .12 * math.tanh(6 * harmonics[1]) * math.sin(4 * theta + route_phase * 1.7)
        wave += .08 * math.tanh(signed_turns / 3) * math.cos(5 * theta - heading)
        wave += .035 * math.sin(2 * theta + noise[6] * 2 * math.pi) + .025 * math.cos(4 * theta + noise[7] * 2 * math.pi)
        radial = 1.02 + .18 * math.tanh(wave / .18)
        outline.append([round(.5 + rx * radial * math.cos(theta), 8), round(.51 + ry * radial * math.sin(theta), 8)])
    # Wider spacing is still wholly inside the exact generated polygon.
    scale = .85 + .12 * noise[8]
    face = {"cx": .5, "cy": .43, "scale": round(scale, 6), "eyeSpacing": round(.9 + .2 * noise[9], 6)}
    require(all(.05 <= n <= .95 for p in outline for n in p), "GEOMETRY_OUT_OF_BOUNDS")
    require(all(inside([.5 + .22 * scale * math.cos(i * math.pi / 90), .43 + .145 * scale * math.sin(i * math.pi / 90)], outline) for i in range(180)), "FACE_OUTSIDE_BODY")
    language = traits + " " + purpose
    cold = sum(language.count(word) for word in ("바다", "호수", "물", "겨울", "차분"))
    warm = sum(language.count(word) for word in ("노을", "햇살", "따뜻", "산책", "봄"))
    forest = sum(language.count(word) for word in ("숲", "산", "초록", "캠핑"))
    route_signal = sum((p[0] * .71 + p[1] * .29) * (i + 1) / (72 * 73 / 2) for i, p in enumerate(route))
    hue = (.54 + .1 * aspect + .11 * route_signal + .11 * (noise[10] - .5) - .38 * math.tanh(warm) - .21 * math.tanh(forest) + .05 * math.tanh(cold)) % 1
    saturation = .27 + .10 * bend
    def color(h, s, v):
        return "#" + "".join(f"{round(x * 255):02X}" for x in colorsys.hsv_to_rgb(h % 1, s, v))
    palette = [color(hue, saturation, .96), color(hue + .06 + .06 * noise[11], .20, 1), color(hue - .05, .42, .64)]
    return {"version": VERSION, "outline": outline, "route": route, "palette": palette, "face": face}, {"aspect": aspect, "bend": bend, "hue": hue, "length": length}


def make_plan(request, engine_fingerprint, engine_identity):
    value = normalize(request)
    input_sha = digest(value)
    character_id = "route-" + digest({"requestId": value["requestId"], "inputSha256": input_sha})[:24]
    visual, signals = geometry(value["route"]["points"], value["requestId"], value["destination"]["traits"], value["purpose"])
    # Name is composed from sound units independently of previous fixture names.
    syllables = ("루", "모", "보", "나", "누", "미", "포", "소", "토", "라", "리", "몽")
    raw = bytes.fromhex(input_sha)
    display = "".join(syllables[b % len(syllables)] for b in raw[:3])
    tall = signals["aspect"] > 0
    warmth = math.cos(2 * math.pi * signals["hue"])
    tempo = .91 + .12 * signals["bend"] + .025 * (raw[4] / 255 - .5)
    texture = "airy and gently rounded" if not tall else "light, clear and softly curious"
    direction = ("Speak Korean as a tiny, adorable travel keepsake companion. Use a natural youthful adult female voice, "
                 "small and close, never a caricature or baby pronunciation. The generated body is "
                 + ("taller and buoyant" if tall else "rounder and softly settled") + "; its palette feels "
                 + ("warm and pearly" if warmth > 0 else "cool and translucent") + ". Keep the delivery " + texture
                 + f", with an expressive but unhurried relative cadence of {tempo:.3f}. "
                 "Use gentle breath, clear consonants, natural phrase endings, modest smiles and no announcer projection. "
                 + ("The journey purpose calls for quiet reassurance." if any(w in value["purpose"] + value["destination"]["traits"] for w in ("휴식", "차분", "퇴근", "병원")) else "The journey purpose calls for soft, curious anticipation.")
                 + " Read only the supplied Korean text. Do not sing, add sound effects or extra words.")
    binding = "dvb-" + digest({"characterId": character_id, "direction": direction, "engineFingerprint": engine_fingerprint})[:32]
    profile = "route-sohee-" + digest({"bindingId": binding})[:20]
    seed = int(digest({"bindingId": binding, "requestId": value["requestId"]})[:8], 16)
    description = ("길의 굴곡을 닮아 " + ("가볍고 호기심 있게" if tall else "동글고 포근하게") + ", "
                   + ("따뜻한 진주빛" if warmth > 0 else "맑은 반투명빛") + " 외형에 맞춰 작고 부드럽게 말해요. Sohee 한 화자의 연기 변주예요.")
    artifact = {"schemaVersion": 1, "characterId": character_id, "journeyId": value["requestId"], "inputSha256": input_sha, "inputCanonical": canonical(value),
                "displayName": display, "destinationName": value["destination"]["name"], "purpose": value["purpose"], "visual": visual,
                "voice": {"description": description, "direction": direction, "bindingId": binding, "profileId": profile, "speaker": "Sohee"}}
    name = value["destination"]["name"]
    texts = {"greeting": f"안녕, 나는 {display}. {name}, 함께 가자.",
             "arrival": f"{name}, 도착했어. 오늘의 길을 나랑 간직하자.",
             "common": f"나는 {display}. 서두르지 않아도 괜찮아. 천천히 함께 가자."}
    require(all(0 < len(t.encode("utf-16-le")) // 2 <= 100 for t in texts.values()), "GENERATED_TEXT_TOO_LONG")
    return {"schemaVersion": 1, "request": value, "inputSha256": input_sha, "artifact": artifact, "texts": texts,
            "seed": seed, "engineFingerprint": engine_fingerprint, "engineIdentity": engine_identity}
