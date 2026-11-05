"""Purpose-led character art: readable costumes, gestures and destination keepsakes.

This is a compositional grammar, not a catalog of complete characters. Independent
body, clothing, gesture and prop choices are constrained by the requested activity.
The place is separate from the activity: a business trip to a beach still wears a
suit. Route geometry shapes the silhouette and the temporary formation path, never
a mark drawn across the face or skin.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re

from PIL import Image, ImageDraw, ImageFilter

from .journey_language import (
    ACTIONS_EN,
    KEEPSAKES_EN,
    POSES_EN,
    PROPS_EN,
    WARDROBES_EN,
    resolve_purpose,
)

VERSION = "journey-character-3"
SIZE = 768
SCALE = 2

# Known names and lexical place types are evidence, not a geocoder. A station
# name never implies that its visitor is a commuter or business traveller.
KNOWN_PLACES = (
    (
        ("서울역", "seoul station"),
        "STATION",
        "서울역",
        "STATION_CLOCK",
        "역사 시계와 승차권",
        "#b86f64",
    ),
    (
        ("수원역", "suwon station"),
        "STATION",
        "수원역",
        "RAIL_WINDOW",
        "철도 창문과 승차권",
        "#637da0",
    ),
    (
        ("부산역", "busan station"),
        "STATION",
        "부산역",
        "RAIL_WINDOW",
        "철도 창문과 승차권",
        "#6c9faa",
    ),
    (("을왕리", "eulwangri"), "BEACH", "을왕리 해수욕장", "SHELL", "조개와 물결", "#58aeb2"),
    (("해운대", "haeundae"), "BEACH", "해운대 해수욕장", "SHELL", "조개와 물결", "#609ec5"),
    (("광안리", "gwangalli"), "BEACH", "광안리 해수욕장", "SHELL", "조개와 물결", "#8c9dcc"),
    (("경포",), "BEACH", "경포 해변", "SHELL", "조개와 물결", "#6bbbbb"),
    (
        ("남산서울타워", "남산 서울타워", "n서울타워", "n seoul tower", "첨성대"),
        "NIGHT",
        "전망·천문 공간",
        "MOON",
        "별빛 전망 배지",
        "#8a8fb9",
    ),
    (("서울시청", "서울 시청"), "CITY", "서울시청", "CITY_WINDOW", "도시 창문 배지", "#7c88af"),
    (("한옥마을",), "HERITAGE", "한옥마을", "GATE", "기와지붕 책갈피", "#9c7d75"),
    (
        ("레고랜드", "롯데월드", "에버랜드"),
        "PLAYGROUND",
        "놀이공원",
        "STAR",
        "놀이 별 배지",
        "#d0a264",
    ),
    (("센트럴파크", "central park"), "GARDEN", "공원", "LEAF", "잎사귀 책갈피", "#8dac79"),
    (
        ("북한산", "설악산", "한라산", "남산", "지리산"),
        "MOUNTAIN",
        "산",
        "MOUNTAIN",
        "산등성이 배지",
        "#7e9f7c",
    ),
    (
        ("경복궁", "창덕궁", "수원화성", "수원 화성"),
        "HERITAGE",
        "문화유산",
        "GATE",
        "기와지붕 책갈피",
        "#9c7d75",
    ),
    (
        ("코엑스", "동대문디자인플라자", "ddp", "판교테크노밸리"),
        "CITY",
        "도시 공간",
        "CITY_WINDOW",
        "도시 창문 배지",
        "#7c88af",
    ),
)

PLACE_TYPES = (
    (
        "BEACH",
        ("해수욕장", "해변", "바다", "해안", "beach", "coast"),
        "SHELL",
        "조개와 물결",
        "#63b6b3",
    ),
    ("STATION", ("기차역", "철도", "station"), "RAIL_WINDOW", "철도 창문과 승차권", "#8b9dbb"),
    ("PLAYGROUND", ("놀이공원", "놀이터", "키즈", "playground"), "STAR", "놀이 별 배지", "#d0a264"),
    ("HERITAGE", ("한옥", "유적", "전통", "heritage"), "GATE", "기와지붕 책갈피", "#9c7d75"),
    ("CITY", ("도심", "광장", "도시", "city"), "CITY_WINDOW", "도시 창문 배지", "#7c88af"),
    (
        "GARDEN",
        ("공원", "숲", "수목원", "정원", "식물원", "garden", "park", "forest"),
        "LEAF",
        "잎사귀 책갈피",
        "#8dac79",
    ),
    (
        "MUSEUM",
        ("미술관", "박물관", "전시", "갤러리", "museum", "gallery"),
        "ART_FRAME",
        "작은 전시 액자",
        "#ab91be",
    ),
    ("MOUNTAIN", ("등산", "산악", "mountain"), "MOUNTAIN", "산등성이 배지", "#7e9f7c"),
    ("CAFE", ("카페", "커피", "cafe", "coffee"), "COFFEE_BEAN", "커피콩 배지", "#b58f70"),
    ("NIGHT", ("천문", "별빛", "야경", "전망대", "night"), "MOON", "달빛 배지", "#8a8fb9"),
    ("RIVER", ("강변", "한강", "호수", "하천", "river", "lake"), "WAVE", "물결 책갈피", "#739faf"),
    ("LIBRARY", ("도서관", "서점", "library", "bookshop"), "BOOK", "책갈피", "#a99479"),
    (
        "PLAYGROUND",
        ("놀이공원", "놀이터", "키즈", "롯데월드", "에버랜드", "playground"),
        "STAR",
        "놀이 별 배지",
        "#d0a264",
    ),
)

# Ordered purpose matching: concrete activity precedes vague leisure words.
PURPOSES = (
    (
        "BUSINESS",
        ("출장", "업무", "회의", "미팅", "출근", "직장", "business", "meeting", "work"),
        "출장 동반자",
        "정장 재킷과 셔츠·넥타이",
        "SUIT",
        "자신 있게 인사하며 업무 가방을 든",
        "CONFIDENT_PROFESSIONAL",
        "TICKET_CONSTELLATION",
    ),
    (
        "SWIM",
        ("수영", "해수욕", "물놀이", "서핑", "swim", "surf"),
        "물놀이 동반자",
        "수영복과 수경",
        "SWIMSUIT",
        "튜브와 함께 발을 차며 물놀이하는",
        "PLAYFUL_YOUNG",
        "TIDAL_BLOOM",
    ),
    (
        "HIKING",
        ("등산", "트레킹", "산행", "하이킹", "hiking", "trek"),
        "등산 동반자",
        "아웃도어 조끼와 등산화",
        "TRAIL_VEST",
        "배낭을 메고 다음 봉우리를 향해 걷는",
        "BRIGHT_COMPANION",
        "LEAF_UPDRAFT",
    ),
    (
        "PLAY",
        ("아이", "어린", "꼬마", "놀이터", "놀이", "키즈", "소풍", "child", "play"),
        "꼬마 놀이 동반자",
        "멜빵바지와 작은 운동화",
        "DUNGAREES",
        "작은 장난감을 들고 신나게 뛰는",
        "PLAYFUL_YOUNG",
        "PLAYFUL_SPARKS",
    ),
    (
        "STUDY",
        ("공부", "시험", "독서", "도서", "학습", "study", "reading"),
        "독서 동반자",
        "니트 조끼와 둥근 안경",
        "KNIT_VEST",
        "펼친 책을 품고 집중하는",
        "WARM_STORYTELLER",
        "PAPER_FOLD",
    ),
    (
        "DATE",
        ("데이트", "연인", "커플", "date", "romantic"),
        "설레는 동반자",
        "리본 칼라와 단정한 코트",
        "RIBBON_COAT",
        "꽃 한 송이를 소중하게 내미는",
        "BRIGHT_COMPANION",
        "PETAL_WALTZ",
    ),
    (
        "ART",
        ("미술", "박물관", "전시", "관람", "갤러리", "공예", "art", "museum", "exhibition"),
        "예술 산책 동반자",
        "작업 앞치마와 베레모",
        "ARTIST_APRON",
        "붓과 스케치북으로 여정을 그리는",
        "WARM_STORYTELLER",
        "PAINT_PETALS",
    ),
    (
        "CAFE",
        ("카페", "커피", "디저트", "cafe", "coffee"),
        "카페 동반자",
        "포근한 카디건과 작은 스카프",
        "CARDIGAN",
        "따뜻한 찻잔을 두 손으로 감싸는",
        "WARM_STORYTELLER",
        "AROMA_RIBBON",
    ),
    (
        "NIGHT",
        ("야경", "별", "천문", "밤", "night", "stargaz"),
        "별빛 동반자",
        "별 단추가 달린 망토",
        "STAR_CAPE",
        "작은 별등으로 밤하늘을 밝히는",
        "WARM_STORYTELLER",
        "STARFALL",
    ),
    (
        "CELEBRATE",
        ("축하", "생일", "기념", "파티", "celebrat", "birthday"),
        "축하 동반자",
        "파티 조끼와 리본",
        "PARTY_VEST",
        "선물 상자를 내밀며 축하하는",
        "BRIGHT_COMPANION",
        "CONFETTI_BOUQUET",
    ),
    (
        "FOOD",
        ("맛집", "식사", "점심", "저녁", "먹", "요리", "food", "dinner", "lunch"),
        "맛있는 여행 동반자",
        "식도락 앞치마와 목수건",
        "FOOD_APRON",
        "작은 도시락을 자랑하는",
        "BRIGHT_COMPANION",
        "PICNIC_POP",
    ),
    (
        "REST",
        ("휴식", "힐링", "쉬", "산책", "여유", "rest", "relax", "walk"),
        "쉼표 동반자",
        "느슨한 니트와 부드러운 스카프",
        "SOFT_KNIT",
        "편안히 앉아 여행의 쉼표를 함께하는",
        "WARM_STORYTELLER",
        "SOFT_BREEZE",
    ),
)

PROPS = {
    "BUSINESS": (
        ("BRIEFCASE", "서류 가방"),
        ("DOCUMENT", "발표 자료"),
        ("LAPTOP", "작은 노트북"),
        ("TROLLEY", "출장 캐리어"),
    ),
    "SWIM": (
        ("FLOAT_RING", "둥근 튜브"),
        ("DUCK_FLOAT", "오리 튜브"),
        ("SURFBOARD", "미니 서핑보드"),
        ("BEACH_BALL", "비치볼과 튜브"),
    ),
    "HIKING": (
        ("TREKKING_POLE", "등산 스틱"),
        ("COMPASS", "나침반"),
        ("CANTEEN", "산행 물병"),
        ("TRAIL_MAP", "산행 지도"),
    ),
    "PLAY": (
        ("PINWHEEL", "바람개비"),
        ("KITE", "작은 연"),
        ("TOY_STAR", "별 장난감"),
        ("BUBBLES", "비눗방울 도구"),
    ),
    "STUDY": (
        ("OPEN_BOOK", "펼친 책"),
        ("NOTEBOOK", "공부 노트"),
        ("PENCIL", "커다란 연필"),
        ("BOOK_STACK", "책 두 권"),
    ),
    "DATE": (
        ("FLOWER", "한 송이 꽃"),
        ("BOUQUET", "작은 꽃다발"),
        ("HEART_LETTER", "마음이 담긴 편지"),
        ("PICNIC_BASKET", "피크닉 바구니"),
    ),
    "ART": (
        ("PALETTE", "팔레트와 붓"),
        ("SKETCHBOOK", "작은 스케치북"),
        ("PAINTBRUSH", "붓"),
        ("ART_FRAME", "그림 액자"),
    ),
    "CAFE": (
        ("TEACUP", "따뜻한 찻잔"),
        ("COFFEE", "테이크아웃 커피"),
        ("CROISSANT", "작은 크루아상"),
        ("DESSERT", "디저트 접시"),
    ),
    "NIGHT": (
        ("STAR_LANTERN", "별등"),
        ("TELESCOPE", "작은 망원경"),
        ("MOON_LANTERN", "달등"),
        ("STAR_MAP", "별자리 지도"),
    ),
    "CELEBRATE": (
        ("GIFT", "선물 상자"),
        ("CAKE", "생일 케이크"),
        ("BALLOON", "축하 풍선"),
        ("GARLAND", "작은 축하 깃발"),
    ),
    "FOOD": (
        ("BENTO", "도시락"),
        ("SANDWICH", "샌드위치"),
        ("PICNIC_BASKET", "도시락 바구니"),
        ("CHEF_SPOON", "작은 요리 스푼"),
    ),
    "REST": (
        ("CUSHION", "달 쿠션"),
        ("TEACUP", "따뜻한 차"),
        ("LEAF_FAN", "잎사귀 부채"),
        ("TRAVEL_PILLOW", "목 쿠션"),
    ),
    "EXPLORE": (
        ("CAMERA", "작은 카메라"),
        ("TRAIL_MAP", "여행 지도"),
        ("BINOCULARS", "쌍안경"),
        ("POSTCARD", "여행 엽서"),
    ),
}

FAMILIES = (
    "BUNNY",
    "BEAR",
    "CAT",
    "OTTER",
    "FOX",
    "PUP",
    "BIRD",
    "SEAL",
    "PANDA",
    "DEER",
    "MOUSE",
    "PENGUIN",
)
FAMILY_KO = dict(
    zip(
        FAMILIES,
        (
            "토끼",
            "곰",
            "고양이",
            "수달",
            "여우",
            "강아지",
            "새",
            "물범",
            "판다",
            "사슴",
            "생쥐",
            "펭귄",
        ),
        strict=True,
    )
)
POSES = ("HELLO", "STEP", "HUG", "TIPTOE", "SIT", "PRESENT")
CUTS = ("CLASSIC", "ROUND", "CROPPED", "LONG", "ASYMMETRIC")
EXPRESSIONS = ("SMILE", "DELIGHT", "WINK", "CURIOUS", "CONTENT")


def _matches(text, words):
    for word in words:
        if (
            re.search(r"(?<![a-z])" + re.escape(word) + r"[a-z]*(?![a-z])", text)
            if word.isascii()
            else word in text
        ):
            return word
    return ""


def destination_semantics(destination, traits):
    clean = destination.lower().strip()
    for aliases, kind, label, landmark, landmark_label, accent in KNOWN_PLACES:
        match = _matches(clean, aliases)
        if match:
            return {
                "kind": kind,
                "label": destination,
                "knownLabel": label,
                "landmark": landmark,
                "landmarkLabel": landmark_label,
                "accent": accent,
                "evidence": f"입력한 목적지 ‘{destination}’에서 확인한 장소명 ‘{match}’",
                "source": "KNOWN_PLACE_NAME",
            }
    # Explicit place traits have priority over lexical hints in an unknown name.
    for source, text in (("EXPLICIT_TRAITS", traits.lower()), ("PLACE_WORD", clean)):
        for kind, words, landmark, label, accent in PLACE_TYPES:
            match = _matches(text, words)
            if match:
                return {
                    "kind": kind,
                    "label": destination,
                    "landmark": landmark,
                    "landmarkLabel": label,
                    "accent": accent,
                    "evidence": (
                        f"입력된 {'목적지 특성' if source == 'EXPLICIT_TRAITS' else '목적지 이름'}"
                        f"의 ‘{match}’"
                    ),
                    "source": source,
                }
    if clean.endswith("역"):
        return {
            "kind": "STATION",
            "label": destination,
            "landmark": "RAIL_WINDOW",
            "landmarkLabel": "철도 창문과 승차권",
            "accent": "#8193aa",
            "evidence": f"목적지 ‘{destination}’의 명시된 ‘역’ 표기",
            "source": "PLACE_WORD",
        }
    return {
        "kind": "UNKNOWN",
        "label": destination,
        "landmark": "JOURNEY_STAR",
        "landmarkLabel": "여정 기념 별",
        "accent": "#ad9cbb",
        "evidence": "장소 유형이 확인되지 않아 지형이나 시설을 추정하지 않음",
        "source": "UNSPECIFIED",
    }


def build_character_plan(destination, traits, purpose, seed, features):
    place = destination_semantics(destination, traits)
    fallback = (
        "EXPLORE",
        (),
        "여행 동반자",
        "여행 조끼와 크로스백",
        "TRAVEL_VEST",
        "목적지를 둘러보며 여행을 기록하는",
        "BRIGHT_COMPANION",
        "JOURNEY_BLOOM",
    )
    resolved, matched, resolution = resolve_purpose(purpose, (*PURPOSES, fallback))
    if resolved is None:
        resolved = fallback
    role, _, label, outfit_label, outfit, action, voice, motion = resolved
    identity = hashlib.sha256(
        json.dumps(
            [destination, traits, purpose, seed, features], ensure_ascii=False, sort_keys=True
        ).encode()
    ).hexdigest()
    rng = random.Random(int(identity, 16))
    family = rng.choice(FAMILIES)
    prop, prop_label = rng.choice(PROPS[role])
    pose = rng.choice(POSES)
    if role == "SWIM":
        pose = rng.choice(("PADDLE", "SPLASH", "FLOAT_KICK", "BACK_FLOAT", "WAVE", "DIVE"))
    if role == "REST":
        pose = rng.choice(("SIT", "HUG", "PRESENT"))
    cut = rng.choice(CUTS)
    expression = rng.choice(EXPRESSIONS)
    composition = {
        "facing": rng.choice((-1, 1)),
        "tilt": rng.choice((-5, -3, 0, 3, 5)),
        "bodyProportion": rng.choice(("PETITE", "ROUND", "TALL", "WIDE")),
        "earGesture": rng.choice(("OPEN", "LEAN", "PERK", "FOLD")),
        "propSide": rng.choice((-1, 1)),
    }
    structure = {
        "bodyFamily": family,
        "outfit": outfit,
        "cut": cut,
        "pose": pose,
        "prop": prop,
        "expression": expression,
        "composition": composition,
        "destinationLandmark": place["landmark"],
    }
    route_lean = round(features["flow"][0] * 8 + features["axis"][1] * 4, 3)
    route_curl = round(min(1.6, features["turning"] / math.tau), 4)
    plan = {
        "version": VERSION,
        "destination": place,
        "purpose": {
            "role": role,
            "label": label,
            "input": purpose,
            "evidence": f"명시한 방문 목적 ‘{purpose}’의 ‘{matched}’를 우선 반영"
            if matched
            else (
                "방문 활동을 확인하지 못했습니다. "
                "UNKNOWN 상태로 남기고 기본 여행 의상만 사용합니다."
            ),
            "source": "EXPLICIT_PURPOSE" if matched else "UNSPECIFIED",
            **resolution,
        },
        "bodyFamily": family,
        "bodyLabel": FAMILY_KO[family],
        "outfit": {"id": outfit, "label": outfit_label, "cut": cut},
        "action": action,
        "pose": pose,
        "prop": {"id": prop, "label": prop_label},
        "expression": expression,
        "motionTheme": motion,
        "voiceRole": voice,
        "composition": composition,
        "routeInfluence": {
            "earLean": route_lean,
            "tailCurl": route_curl,
            "source": "ROUTE_FLOW_AND_TURNING",
            "surfaceMarking": "NONE",
        },
        "structuralSignature": hashlib.sha256(
            json.dumps(structure, sort_keys=True).encode()
        ).hexdigest(),
        "renderParts": [
            family,
            outfit,
            cut,
            pose,
            prop,
            expression,
            place["landmark"],
            composition["bodyProportion"],
            composition["earGesture"],
        ],
        "summary": (
            f"{destination} 여정을 함께할 {FAMILY_KO[family]} 눈티. "
            f"{outfit_label}에 {place['landmarkLabel']}"
            f"{'을' if (ord(place['landmarkLabel'][-1]) - 0xAC00) % 28 else '를'} 더했어요."
        ),
    }
    plan["outfit"]["descriptionEn"] = WARDROBES_EN[role]
    plan["prop"]["descriptionEn"] = PROPS_EN[prop]
    plan["actionEn"] = ACTIONS_EN[role]
    plan["poseEn"] = POSES_EN[pose]
    plan["keepsakeEn"] = KEEPSAKES_EN[place["landmark"]]
    plan["promptBrief"] = (
        f"An original collectible {family.lower()} Nunti companion wearing {WARDROBES_EN[role]}. "
        f"Destination: {destination}; explicit purpose: {purpose}. "
        f"Selected activity prop: {PROPS_EN[prop]}. Do not replace it with another activity prop. "
        f"Action: {ACTIONS_EN[role]}. Pose: {POSES_EN[pose]}. "
        f"Include {KEEPSAKES_EN[place['landmark']]} attached to the costume, "
        f"separate from clean skin. {expression.lower()} expression, "
        f"{cut.lower()} costume cut. Big appealing face, clear tiny hands and feet, "
        "matte opaque pastel illustration, two-dimensional linework with minimal 2.5D shading. "
        "Costume and action must read at thumbnail size. No route scars, no skin stripes, "
        "no glass or translucent body."
    )
    if resolution["resolution"] == "UNKNOWN":
        plan["promptBrief"] += (
            " Activity is UNKNOWN. Use the neutral travel wardrobe; "
            "do not invent a profession, hobby or emotional state."
        )
    return plan


def character_tilt(character):
    tilt = character["composition"]["tilt"]
    if character["purpose"]["role"] == "SWIM":
        tilt += {
            "PADDLE": 10,
            "SPLASH": -9,
            "FLOAT_KICK": 28,
            "BACK_FLOAT": 65,
            "WAVE": 0,
            "DIVE": -44,
        }[character["pose"]]
    return tilt


def _rgb(hexcolor):
    return tuple(int(hexcolor[i : i + 2], 16) for i in (1, 3, 5))


def _mix(a, b, t):
    return tuple(round(x * (1 - t) + y * t) for x, y in zip(a, b, strict=True))


class Painter:
    """Small antialiased vector brush; all model coordinates are in asset pixels."""

    def __init__(self, direction="STORYBOOK"):
        self.image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE))
        self.draw = ImageDraw.Draw(self.image)
        self.ink = (100, 80, 79)
        self.width = 3.6 if direction == "STORYBOOK" else 2.2 if direction == "SOFT_TOY" else 5.0

    @staticmethod
    def pts(points):
        return [(round(x * SCALE), round(y * SCALE)) for x, y in points]

    def line(self, points, color=None, width=None):
        width = self.width if width is None else width
        color = color or self.ink
        self.draw.line(
            self.pts(points), fill=color, width=max(1, round(width * SCALE)), joint="curve"
        )
        for x, y in (points[0], points[-1]):
            self.ellipse(
                (x - width / 2, y - width / 2, x + width / 2, y + width / 2), color, outline=False
            )

    def polygon(self, points, fill, outline=True, width=None):
        self.draw.polygon(self.pts(points), fill=fill)
        if outline:
            self.line(list(points) + [points[0]], self.ink if outline is True else outline, width)

    def ellipse(self, box, fill, outline=True, width=None):
        self.draw.ellipse(
            tuple(round(v * SCALE) for v in box),
            fill=fill,
            outline=self.ink if outline is True else outline or None,
            width=max(1, round((width or self.width) * SCALE)),
        )

    def roundrect(self, box, radius, fill, outline=True, width=None):
        self.draw.rounded_rectangle(
            tuple(round(v * SCALE) for v in box),
            radius=round(radius * SCALE),
            fill=fill,
            outline=self.ink if outline is True else outline or None,
            width=max(1, round((width or self.width) * SCALE)),
        )

    def path(self, start, segments, fill=None, outline=True, width=None):
        points, p = [start], start
        for c1, c2, end in segments:
            for n in range(1, 25):
                t = n / 24
                u = 1 - t
                points.append(
                    (
                        u**3 * p[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t**3 * end[0],
                        u**3 * p[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t**3 * end[1],
                    )
                )
            p = end
        if fill is not None:
            self.polygon(points, fill, outline, width)
        elif outline:
            self.line(points, self.ink if outline is True else outline, width)
        return points

    def star(self, cx, cy, radius, fill, points=5, inner=0.47, angle=-math.pi / 2, outline=True):
        polygon = [
            (
                cx + math.cos(angle + i * math.pi / points) * radius * (1 if i % 2 == 0 else inner),
                cy + math.sin(angle + i * math.pi / points) * radius * (1 if i % 2 == 0 else inner),
            )
            for i in range(points * 2)
        ]
        self.polygon(polygon, fill, outline)


def _head(p, character, cx, cy, fur, cream, accent, rx, ry):
    family = character["bodyFamily"]
    lean = character["routeInfluence"]["earLean"]
    ear = character["composition"]["earGesture"]
    inward = {"OPEN": -8, "LEAN": 14, "PERK": 0, "FOLD": 22}[ear]
    ear_color = _mix(fur, (206, 151, 148), 0.30)
    # Ears precede the head so their roots disappear naturally into the fur.
    if family == "BUNNY":
        for side in (-1, 1):
            x = cx + side * rx * 0.52
            tip = x + side * (16 - inward) + lean
            top = cy - ry - (94 if side == -1 or ear != "FOLD" else 49)
            p.path(
                (x - 30, cy - ry + 25),
                [
                    ((x - 50, top + 22), (tip - 23, top - 12), (tip, top)),
                    ((tip + 30, top + 5), (x + 31, cy - ry - 12), (x + 27, cy - ry + 32)),
                ],
                fur,
            )
            p.path(
                (x - 12, cy - ry + 1),
                [
                    ((x - 22, top + 39), (tip - 12, top + 11), (tip + 2, top + 17)),
                    ((tip + 13, top + 25), (x + 13, cy - ry - 20), (x + 12, cy - ry + 5)),
                ],
                ear_color,
                False,
            )
    elif family in ("CAT", "FOX"):
        for side in (-1, 1):
            x = cx + side * rx * 0.65
            tip = x + side * (18 - inward * 0.5) + lean * 0.7
            top = cy - ry - (45 if family == "CAT" else 65)
            p.path(
                (x - 38, cy - ry + 32),
                [
                    ((x - 40, top + 32), (tip - 9, top - 5), (tip, top)),
                    ((tip + 18, top + 10), (x + 44, cy - ry + 12), (x + 40, cy - ry + 42)),
                ],
                fur,
            )
            p.polygon(
                [(x - 21, cy - ry + 9), (tip, top + 19), (x + 24, cy - ry + 12)], ear_color, False
            )
    elif family == "PUP":
        for side in (-1, 1):
            x = cx + side * rx * 0.88
            p.path(
                (x - 23, cy - ry + 22),
                [
                    ((x - 51, cy - ry + 30), (x - 58 + lean, cy + 55), (x - 20, cy + 70)),
                    ((x + 33, cy + 79), (x + 49, cy - ry + 3), (x + 9, cy - ry + 12)),
                ],
                _mix(fur, (177, 135, 111), 0.32),
            )
    elif family == "DEER":
        for side in (-1, 1):
            x = cx + side * rx * 0.55
            p.line(
                [(x, cy - ry + 12), (x + side * 6, cy - ry - 46), (x + side * 29, cy - ry - 68)],
                (157, 119, 91),
                10,
            )
            p.line([(x + side * 6, cy - ry - 39), (x - side * 14, cy - ry - 58)], (157, 119, 91), 8)
            p.ellipse((x + side * 38 - 30, cy - ry - 18, x + side * 38 + 30, cy - ry + 22), fur)
    elif family in ("BEAR", "OTTER", "PANDA", "MOUSE"):
        for side in (-1, 1):
            x = cx + side * rx * 0.76 + lean * 0.35
            radius = 45 if family == "MOUSE" else 35 if family in ("BEAR", "PANDA") else 25
            y = cy - ry * 0.83 - (12 if ear == "PERK" else 0)
            efur = (105, 98, 103) if family == "PANDA" else fur
            p.ellipse((x - radius, y - radius, x + radius, y + radius), efur)
            p.ellipse(
                (x - radius * 0.55, y - radius * 0.55, x + radius * 0.55, y + radius * 0.55),
                ear_color,
                False,
            )
    else:
        # A soft tuft offers a clear silhouette to earless swimmers and birds.
        p.path(
            (cx - 34, cy - ry + 13),
            [
                ((cx - 35, cy - ry - 26), (cx - 3 + lean, cy - ry - 32), (cx + 7, cy - ry + 3)),
                ((cx + 18, cy - ry - 25), (cx + 44 + lean, cy - ry - 17), (cx + 31, cy - ry + 16)),
            ],
            fur,
        )
    # Full cheeks and a slightly flattened forehead are more expressive than a circle.
    cheek = 1.09 if family in ("OTTER", "SEAL", "FOX") else 1
    p.path(
        (cx - rx, cy - ry * 0.12),
        [
            ((cx - rx, cy - ry * 0.90), (cx - rx * 0.50, cy - ry * 1.05), (cx, cy - ry)),
            (
                (cx + rx * 0.55, cy - ry * 1.02),
                (cx + rx, cy - ry * 0.73),
                (cx + rx, cy - ry * 0.10),
            ),
            ((cx + rx * cheek, cy + ry * 0.62), (cx + rx * 0.50, cy + ry), (cx, cy + ry)),
            (
                (cx - rx * 0.61, cy + ry),
                (cx - rx * cheek, cy + ry * 0.53),
                (cx - rx, cy - ry * 0.12),
            ),
        ],
        fur,
    )
    # One shallow lower-plane shape, never glass highlights or route markings.
    p.path(
        (cx - rx * 0.82, cy + ry * 0.50),
        [
            (
                (cx - rx * 0.52, cy + ry * 0.88),
                (cx + rx * 0.48, cy + ry * 0.94),
                (cx + rx * 0.87, cy + ry * 0.41),
            ),
            (
                (cx + rx * 0.65, cy + ry * 0.99),
                (cx - rx * 0.64, cy + ry * 1.02),
                (cx - rx * 0.82, cy + ry * 0.50),
            ),
        ],
        _mix(fur, (170, 143, 131), 0.10),
        False,
    )
    if family in ("FOX", "OTTER", "PENGUIN", "PUP"):
        p.path(
            (cx - rx * 0.87, cy + 8),
            [
                ((cx - rx * 0.53, cy - 16), (cx - rx * 0.33, cy + 22), (cx, cy + 29)),
                ((cx + rx * 0.42, cy + 18), (cx + rx * 0.56, cy - 16), (cx + rx * 0.87, cy + 8)),
                (
                    (cx + rx * 0.93, cy + ry * 0.69),
                    (cx + rx * 0.4, cy + ry * 0.83),
                    (cx, cy + ry * 0.83),
                ),
                (
                    (cx - rx * 0.56, cy + ry * 0.84),
                    (cx - rx * 0.93, cy + ry * 0.56),
                    (cx - rx * 0.87, cy + 8),
                ),
            ],
            cream,
            False,
        )
    if family == "PANDA":
        for side in (-1, 1):
            p.ellipse(
                (cx + side * 52 - 24, cy - 28, cx + side * 52 + 24, cy + 22), (105, 98, 103), False
            )


def _face(p, c, cx, cy, rx, cream):
    expr = c["expression"]
    ink = (79, 65, 67)
    gap = rx * 0.37
    eye_y = cy + 5
    for side in (-1, 1):
        x = cx + side * gap
        if expr == "CONTENT" or (expr == "WINK" and side == 1):
            p.path(
                (x - 12, eye_y + 4),
                [((x - 5, eye_y - 5), (x + 5, eye_y - 5), (x + 12, eye_y + 4))],
                outline=ink,
                width=5,
            )
        elif expr == "DELIGHT":
            p.path(
                (x - 13, eye_y + 4),
                [((x - 4, eye_y - 14), (x + 4, eye_y - 14), (x + 13, eye_y + 4))],
                outline=ink,
                width=5,
            )
        else:
            p.ellipse((x - 15, eye_y - 21, x + 15, eye_y + 19), ink, False)
            p.ellipse((x - 10, eye_y - 15, x - 1, eye_y - 5), (255, 252, 240), False)
            p.ellipse((x + 5, eye_y + 9, x + 9, eye_y + 13), (230, 190, 149), False)
        p.ellipse(
            (cx + side * rx * 0.67 - 22, cy + 28, cx + side * rx * 0.67 + 22, cy + 48),
            (235, 168, 166),
            False,
        )
        p.line(
            [(cx + side * rx * 0.67 - 6, cy + 34), (cx + side * rx * 0.67 - 9, cy + 41)],
            (223, 144, 143),
            1.8,
        )
    if c["bodyFamily"] in ("BIRD", "PENGUIN"):
        p.path(
            (cx - 15, cy + 29),
            [
                ((cx - 7, cy + 18), (cx + 8, cy + 18), (cx + 16, cy + 29)),
                ((cx + 8, cy + 42), (cx - 7, cy + 42), (cx - 15, cy + 29)),
            ],
            (239, 177, 97),
            outline=(145, 108, 85),
            width=2.4,
        )
    else:
        p.ellipse((cx - 5, cy + 22, cx + 5, cy + 29), (137, 100, 99), False)
        if expr == "CURIOUS":
            p.ellipse((cx - 7, cy + 38, cx + 8, cy + 51), (136, 84, 92), False)
            p.path(
                (cx - gap - 13, cy - 29),
                [((cx - gap - 4, cy - 35), (cx - gap + 5, cy - 33), (cx - gap + 11, cy - 26))],
                outline=(141, 113, 105),
                width=2.4,
            )
        elif expr == "DELIGHT":
            p.path(
                (cx - 15, cy + 39),
                [((cx - 7, cy + 62), (cx + 10, cy + 60), (cx + 16, cy + 39))],
                (136, 84, 92),
                outline=ink,
                width=2,
            )
            p.ellipse((cx - 6, cy + 49, cx + 9, cy + 56), (238, 157, 160), False)
        else:
            p.path(
                (cx - 16, cy + 38),
                [
                    ((cx - 12, cy + 49), (cx - 3, cy + 49), (cx, cy + 40)),
                    ((cx + 4, cy + 50), (cx + 13, cy + 48), (cx + 17, cy + 38)),
                ],
                outline=ink,
                width=3.1,
            )
    # A tiny brow tilt supplies confidence without changing to an adult face.
    if c["purpose"]["role"] == "BUSINESS":
        p.line([(cx - gap - 10, cy - 27), (cx - gap + 7, cy - 25)], (141, 113, 105), 2.8)
        p.line([(cx + gap - 7, cy - 25), (cx + gap + 10, cy - 27)], (141, 113, 105), 2.8)


def _destination_token(p, c, x, y, accent):
    """A destination-shaped satchel changes the silhouette, not the skin surface."""
    kind = c["destination"]["landmark"]
    cream = (255, 246, 223)
    light = _mix(accent, cream, 0.55)
    dark = _mix(accent, (104, 80, 76), 0.25)
    # A visible strap attaches the keepsake to the costume/float ring.
    p.path(
        (x - 25, y - 22),
        [((x - 31, y - 70), (x + 31, y - 70), (x + 26, y - 23))],
        outline=dark,
        width=6,
    )
    if kind == "STATION_CLOCK":
        # Seoul Station: a clock-front souvenir purse, with a ticket attached.
        p.roundrect((x + 14, y - 8, x + 55, y + 43), 4, cream, outline=dark, width=2)
        for offset in (-1, 11, 23):
            p.line([(x + 25, y + offset), (x + 44, y + offset)], accent, 3)
        p.ellipse((x - 48, y - 42, x + 43, y + 49), light, outline=dark, width=3)
        p.ellipse((x - 36, y - 31, x + 31, y + 36), cream, outline=dark, width=3)
        for dx, dy in ((0, -24), (24, 0), (0, 24), (-24, 0)):
            p.ellipse((x + dx - 5, y + dy - 1, x + dx, y + dy + 4), dark, False)
        p.line([(x - 3, y - 18), (x - 3, y + 3), (x + 14, y + 13)], dark, 4)
        p.ellipse((x - 7, y - 1, x + 1, y + 7), accent, False)
    elif kind == "RAIL_WINDOW":
        # Suwon/other stations: a little train-shaped luggage silhouette.
        p.roundrect((x - 46, y - 35, x + 46, y + 43), 17, light, outline=dark, width=3)
        p.roundrect((x - 35, y - 25, x + 35, y + 12), 8, cream, outline=dark, width=3)
        p.line([(x, y - 24), (x, y + 10)], accent, 3)
        p.roundrect((x - 20, y - 42, x + 20, y - 32), 4, accent, False)
        for side in (-1, 1):
            p.ellipse(
                (x + side * 25 - 7, y + 22, x + side * 25 + 7, y + 35), cream, outline=dark, width=2
            )
            p.ellipse((x + side * 29 - 7, y + 40, x + side * 29 + 7, y + 53), dark, False)
        p.line([(x - 15, y + 25), (x + 15, y + 25)], accent, 3)
    elif kind == "SHELL":
        # A scalloped shell bag is readable even without the destination caption.
        p.path(
            (x - 43, y + 10),
            [
                ((x - 65, y - 16), (x - 44, y - 42), (x - 27, y - 26)),
                ((x - 28, y - 55), (x + 4, y - 56), (x + 7, y - 31)),
                ((x + 26, y - 58), (x + 54, y - 36), (x + 41, y - 12)),
                ((x + 68, y - 10), (x + 53, y + 22), (x + 31, y + 26)),
                ((x + 13, y + 48), (x - 20, y + 47), (x - 43, y + 10)),
            ],
            light,
            outline=dark,
            width=3,
        )
        for dx, dy in ((-35, -15), (-17, -30), (8, -29), (30, -17)):
            p.path(
                (x, y + 32),
                [((x + dx * 0.4, y + 12), (x + dx, y - 2), (x + dx, y + dy))],
                outline=accent,
                width=3,
            )
        p.ellipse((x - 9, y + 25, x + 9, y + 43), cream, outline=dark, width=2)
    elif kind in ("LEAF", "COFFEE_BEAN"):
        if kind == "LEAF":
            p.path(
                (x - 36, y + 26),
                [
                    ((x - 61, y - 20), (x + 8, y - 54), (x + 39, y - 41)),
                    ((x + 59, y + 11), (x + 6, y + 57), (x - 36, y + 26)),
                ],
                light,
                outline=dark,
                width=3,
            )
            p.path(
                (x - 37, y + 35),
                [((x - 10, y + 12), (x + 16, y - 10), (x + 31, y - 30))],
                outline=dark,
                width=3,
            )
            p.line([(x - 11, y + 13), (x - 23, y - 11)], accent, 3)
            p.line([(x + 5, y - 1), (x + 29, y + 1)], accent, 3)
        else:
            p.ellipse((x - 43, y - 41, x + 43, y + 45), light, outline=dark, width=3)
            p.path(
                (x + 9, y - 30),
                [((x - 29, y - 4), (x + 27, y + 2), (x - 11, y + 32))],
                outline=dark,
                width=5,
            )
    elif kind == "MOUNTAIN":
        p.path(
            (x - 52, y + 28),
            [
                ((x - 39, y + 3), (x - 19, y - 41), (x - 7, y - 39)),
                ((x + 7, y - 31), (x + 15, y - 8), (x + 20, y - 13)),
                ((x + 37, y - 44), (x + 45, y + 8), (x + 53, y + 29)),
                ((x + 38, y + 49), (x - 41, y + 49), (x - 52, y + 28)),
            ],
            light,
            outline=dark,
            width=3,
        )
        p.polygon(
            [
                (x - 24, y - 10),
                (x - 7, y - 37),
                (x + 11, y - 11),
                (x, y - 14),
                (x - 7, y - 6),
                (x - 15, y - 14),
            ],
            cream,
            False,
        )
        p.line([(x - 29, y + 23), (x + 31, y + 23)], accent, 3)
    elif kind == "MOON":
        p.ellipse((x - 46, y - 42, x + 46, y + 47), light, outline=dark, width=3)
        p.ellipse((x - 29, y - 26, x + 19, y + 28), cream, False)
        p.ellipse((x - 11, y - 34, x + 34, y + 11), light, False)
        p.star(x + 22, y + 22, 14, cream, outline=False)
    elif kind in ("GATE", "CITY_WINDOW", "ART_FRAME", "BOOK"):
        p.roundrect((x - 43, y - 31, x + 43, y + 43), 8, light, outline=dark, width=3)
        if kind == "GATE":
            p.path(
                (x - 51, y - 19),
                [
                    ((x - 21, y - 25), (x - 22, y - 34), (x, y - 42)),
                    ((x + 19, y - 33), (x + 24, y - 24), (x + 51, y - 19)),
                ],
                dark,
            )
            p.roundrect((x - 15, y + 1, x + 15, y + 43), 13, cream, outline=dark, width=2)
        elif kind == "ART_FRAME":
            p.roundrect((x - 32, y - 20, x + 32, y + 30), 3, cream, outline=accent, width=5)
            p.polygon(
                [
                    (x - 25, y + 21),
                    (x - 5, y - 5),
                    (x + 13, y + 17),
                    (x + 24, y + 3),
                    (x + 25, y + 23),
                ],
                accent,
                False,
            )
        elif kind == "BOOK":
            p.line([(x - 23, y - 25), (x - 23, y + 36)], dark, 4)
            p.polygon(
                [
                    (x + 5, y - 29),
                    (x + 24, y - 29),
                    (x + 24, y + 1),
                    (x + 14, y - 8),
                    (x + 5, y + 1),
                ],
                cream,
                False,
            )
        else:
            for dx in (-20, 20):
                for dy in (-12, 16):
                    p.roundrect((x + dx - 11, y + dy - 8, x + dx + 11, y + dy + 8), 3, cream, False)
    else:
        p.roundrect((x - 45, y - 32, x + 45, y + 43), 17, light, outline=dark, width=3)
        if kind == "WAVE":
            for offset in (-8, 12):
                p.path(
                    (x - 31, y + offset),
                    [((x - 12, y - 19 + offset), (x + 11, y + 19 + offset), (x + 31, y + offset))],
                    outline=cream,
                    width=5,
                )
        else:
            p.star(x, y + 5, 29, cream, outline=dark)


def _prop(p, c, x, y, accent, cream, fur):
    prop = c["prop"]["id"]
    dark = _mix(accent, (79, 72, 84), 0.32)
    if prop in ("BRIEFCASE", "TROLLEY"):
        height = 78 if prop == "TROLLEY" else 57
        p.roundrect(
            (x - 19, y - height / 2 - 17, x + 19, y - height / 2 + 4),
            7,
            cream,
            outline=dark,
            width=4,
        )
        p.roundrect(
            (x - 45, y - height / 2, x + 45, y + height / 2), 11, _mix(accent, (158, 111, 85), 0.36)
        )
        p.line([(x - 44, y - 1), (x + 43, y - 1)], dark, 2.5)
        p.roundrect((x - 7, y - 8, x + 7, y + 9), 3, (239, 198, 126), outline=dark, width=2)
        if prop == "TROLLEY":
            for dx in (-28, 28):
                p.ellipse(
                    (x + dx - 6, y + height / 2 - 2, x + dx + 6, y + height / 2 + 10), dark, False
                )
    elif prop in (
        "DOCUMENT",
        "NOTEBOOK",
        "SKETCHBOOK",
        "TRAIL_MAP",
        "STAR_MAP",
        "POSTCARD",
        "HEART_LETTER",
        "ART_FRAME",
    ):
        p.roundrect((x - 37, y - 43, x + 37, y + 43), 6, cream)
        if prop == "HEART_LETTER":
            p.line([(x - 34, y - 25), (x, y + 4), (x + 34, y - 25)], accent, 3)
            p.star(x, y + 2, 12, (219, 137, 147), points=4, inner=0.65, outline=False)
        elif prop in ("TRAIL_MAP", "STAR_MAP"):
            p.line(
                [(x - 14, y - 37), (x - 14, y + 36), (x + 12, y + 39), (x + 12, y - 38)],
                _mix(accent, cream, 0.5),
                2,
            )
            if prop == "TRAIL_MAP":
                p.line(
                    [(x - 27, y + 22), (x - 20, y - 8), (x + 3, y + 6), (x + 23, y - 25)], accent, 4
                )
            else:
                for dx, dy in ((-20, 8), (8, -18), (22, 17)):
                    p.star(x + dx, y + dy, 6, accent, outline=False)
                p.line([(x - 20, y + 8), (x + 8, y - 18), (x + 22, y + 17)], accent, 1)
        elif prop == "ART_FRAME":
            p.roundrect(
                (x - 29, y - 33, x + 29, y + 33),
                2,
                _mix(accent, cream, 0.6),
                outline=accent,
                width=4,
            )
            p.polygon(
                [
                    (x - 26, y + 24),
                    (x - 7, y - 9),
                    (x + 11, y + 12),
                    (x + 23, y - 6),
                    (x + 25, y + 26),
                ],
                accent,
                False,
            )
        else:
            for n, length in enumerate((42, 30, 38)):
                p.line([(x - 23, y - 18 + n * 15), (x - 23 + length, y - 18 + n * 15)], accent, 3)
    elif prop == "LAPTOP":
        p.roundrect((x - 43, y - 39, x + 43, y + 12), 6, accent)
        p.star(x, y - 13, 10, cream, points=4, outline=False)
        p.polygon(
            [(x - 43, y + 12), (x + 43, y + 12), (x + 52, y + 27), (x - 52, y + 27)],
            _mix(accent, cream, 0.45),
        )
    elif prop in ("FLOAT_RING", "DUCK_FLOAT", "BEACH_BALL"):
        p.ellipse((x - 48, y - 34, x + 48, y + 34), (246, 194, 124))
        p.ellipse((x - 23, y - 16, x + 23, y + 16), cream)
        for side in (-1, 1):
            p.line([(x + side * 34, y - 22), (x + side * 40, y + 15)], (255, 233, 193), 8)
        if prop == "DUCK_FLOAT":
            p.ellipse((x + 21, y - 61, x + 62, y - 21), (250, 205, 127))
            p.ellipse((x + 43, y - 49, x + 48, y - 43), (87, 70, 65), False)
            p.polygon([(x + 59, y - 42), (x + 72, y - 37), (x + 59, y - 32)], (224, 143, 94))
        elif prop == "BEACH_BALL":
            p.ellipse((x + 19, y - 66, x + 72, y - 13), cream)
            p.path(
                (x + 45, y - 65),
                [((x + 13, y - 40), (x + 45, y - 14), (x + 45, y - 14))],
                _mix(accent, cream, 0.25),
                False,
            )
            p.path(
                (x + 45, y - 65),
                [((x + 71, y - 47), (x + 71, y - 27), (x + 45, y - 14))],
                (237, 159, 156),
                False,
            )
    elif prop == "SURFBOARD":
        p.path(
            (x, y - 90),
            [
                ((x - 43, y - 65), (x - 35, y + 62), (x - 6, y + 85)),
                ((x + 35, y + 72), (x + 38, y - 58), (x, y - 90)),
            ],
            cream,
        )
        p.path(
            (x, y - 75),
            [((x - 9, y - 20), (x + 10, y + 12), (x, y + 64))],
            outline=accent,
            width=16,
        )
    elif prop in ("TEACUP", "COFFEE"):
        if prop == "TEACUP":
            p.ellipse((x + 18, y - 18, x + 43, y + 8), cream, outline=accent, width=5)
            p.path(
                (x - 32, y - 24),
                [
                    ((x - 31, y + 20), (x - 20, y + 29), (x, y + 28)),
                    ((x + 29, y + 30), (x + 31, y + 1), (x + 31, y - 24)),
                ],
                cream,
            )
            p.ellipse((x - 31, y - 31, x + 31, y - 13), (171, 122, 99), outline=accent, width=3)
        else:
            p.polygon(
                [(x - 28, y - 29), (x + 28, y - 29), (x + 21, y + 35), (x - 21, y + 35)], cream
            )
            p.roundrect((x - 31, y - 35, x + 31, y - 23), 5, accent)
            p.polygon(
                [(x - 25, y - 5), (x + 25, y - 5), (x + 22, y + 17), (x - 22, y + 17)],
                accent,
                False,
            )
        for dx in (-13, 13):
            p.path(
                (x + dx, y - 45),
                [((x + dx - 12, y - 56), (x + dx + 10, y - 66), (x + dx, y - 77))],
                outline=_mix(accent, cream, 0.45),
                width=3,
            )
    elif prop in ("OPEN_BOOK", "BOOK_STACK"):
        if prop == "BOOK_STACK":
            p.roundrect((x - 43, y - 24, x + 43, y + 28), 5, accent)
            p.roundrect((x - 39, y - 7, x + 43, y + 6), 2, cream, False)
        else:
            p.path(
                (x, y - 27),
                [
                    ((x - 17, y - 39), (x - 36, y - 35), (x - 47, y - 31)),
                    ((x - 49, y - 4), (x - 47, y + 29), (x - 44, y + 34)),
                    ((x - 26, y + 27), (x - 13, y + 29), (x, y + 39)),
                    ((x + 15, y + 29), (x + 31, y + 26), (x + 44, y + 34)),
                    ((x + 49, y + 7), (x + 47, y - 14), (x + 47, y - 31)),
                    ((x + 31, y - 38), (x + 12, y - 38), (x, y - 27)),
                ],
                cream,
            )
            p.line([(x, y - 24), (x, y + 36)], accent, 2)
            for side in (-1, 1):
                for dy in (-12, 3, 18):
                    p.line([(x + side * 10, y + dy), (x + side * 34, y + dy - 3)], accent, 2)
    elif prop in ("FLOWER", "BOUQUET"):
        for dx, dy in ((0, -45), (-20, -23), (23, -21)) if prop == "BOUQUET" else ((0, -42),):
            p.line([(x, y + 38), (x + dx, y + dy)], (124, 160, 121), 5)
            for a in range(5):
                xx = x + dx + math.cos(a * math.tau / 5) * 15
                yy = y + dy + math.sin(a * math.tau / 5) * 15
                p.ellipse((xx - 12, yy - 12, xx + 12, yy + 12), (239, 177, 180), outline=False)
            p.ellipse((x + dx - 9, y + dy - 9, x + dx + 9, y + dy + 9), (244, 204, 129), False)
        p.polygon([(x - 29, y + 5), (x + 29, y + 5), (x + 8, y + 47), (x - 8, y + 47)], cream)
        p.line([(x - 13, y + 25), (x + 14, y + 25)], accent, 6)
    elif prop in ("PALETTE", "PAINTBRUSH", "PENCIL", "CHEF_SPOON", "TREKKING_POLE", "LEAF_FAN"):
        if prop == "PALETTE":
            p.ellipse((x - 45, y - 33, x + 45, y + 33), (230, 191, 144))
            p.ellipse((x + 18, y - 15, x + 30, y - 3), cream)
            for dx, dy, color in (
                (-24, -10, (223, 140, 144)),
                (-15, 14, (142, 174, 143)),
                (6, 17, (123, 158, 182)),
                (4, -20, (240, 204, 122)),
            ):
                p.ellipse((x + dx - 7, y + dy - 7, x + dx + 7, y + dy + 7), color, False)
        elif prop == "LEAF_FAN":
            p.path(
                (x, y + 13),
                [
                    ((x - 60, y - 7), (x - 22, y - 75), (x + 9, y - 69)),
                    ((x + 52, y - 47), (x + 40, y - 5), (x, y + 13)),
                ],
                (162, 193, 142),
            )
            p.line([(x, y + 40), (x, y - 53)], (104, 139, 101), 4)
        elif prop == "TREKKING_POLE":
            p.line([(x + 4, y - 65), (x - 8, y + 93)], dark, 6)
            p.roundrect((x - 8, y - 75, x + 15, y - 35), 6, accent)
        elif prop == "CHEF_SPOON":
            p.line([(x - 10, y + 57), (x + 7, y - 26)], (185, 142, 99), 10)
            p.ellipse((x - 12, y - 65, x + 30, y - 13), (208, 166, 116))
        else:
            p.line([(x - 22, y + 46), (x + 20, y - 45)], (205, 161, 110), 12)
            p.polygon([(x + 13, y - 39), (x + 28, y - 32), (x + 35, y - 70)], accent)
    elif prop in ("GIFT", "BENTO", "PICNIC_BASKET", "CAKE", "DESSERT", "SANDWICH", "CROISSANT"):
        if prop in ("GIFT", "BENTO", "PICNIC_BASKET"):
            p.roundrect(
                (x - 44, y - 23, x + 44, y + 32),
                7,
                (228, 184, 141) if prop == "PICNIC_BASKET" else _mix(accent, cream, 0.4),
            )
            p.roundrect((x - 47, y - 30, x + 47, y - 14), 5, accent)
            if prop == "GIFT":
                p.line([(x, y - 31), (x, y + 31)], cream, 12)
                p.path(
                    (x, y - 31),
                    [
                        ((x - 40, y - 70), (x - 39, y - 18), (x, y - 31)),
                        ((x + 36, y - 64), (x + 42, y - 22), (x, y - 31)),
                    ],
                    cream,
                )
            elif prop == "PICNIC_BASKET":
                p.path(
                    (x - 28, y - 28),
                    [((x - 32, y - 71), (x + 33, y - 72), (x + 28, y - 28))],
                    outline=(163, 124, 88),
                    width=7,
                )
                for dx in (-24, -8, 8, 24):
                    p.line([(x + dx, y - 7), (x + dx, y + 25)], (185, 146, 106), 2)
            else:
                p.ellipse((x - 26, y - 39, x - 3, y - 17), (243, 222, 159), False)
                p.ellipse((x + 5, y - 36, x + 28, y - 15), (164, 188, 133), False)
        elif prop in ("CAKE", "DESSERT"):
            p.ellipse((x - 51, y + 18, x + 51, y + 38), cream)
            p.roundrect((x - 34, y - 16, x + 34, y + 25), 6, (242, 197, 174))
            p.ellipse((x - 34, y - 25, x + 34, y - 6), cream)
            p.line([(x, y - 21), (x, y - 47)], accent, 6)
            p.ellipse((x - 5, y - 59, x + 5, y - 43), (246, 199, 112), False)
        elif prop == "SANDWICH":
            p.polygon([(x - 45, y + 31), (x + 44, y + 31), (x - 7, y - 44)], (225, 173, 111))
            p.polygon([(x - 36, y + 23), (x + 31, y + 23), (x - 7, y - 31)], cream, False)
            p.line([(x - 26, y + 8), (x + 17, y + 8)], (146, 175, 115), 7)
        else:
            p.path(
                (x - 48, y + 14),
                [
                    ((x - 28, y - 48), (x + 30, y - 49), (x + 48, y + 14)),
                    ((x + 28, y + 2), (x + 19, y + 31), (x, y + 30)),
                    ((x - 19, y + 30), (x - 27, y + 2), (x - 48, y + 14)),
                ],
                (231, 180, 115),
            )
            for dx in (-19, 19):
                p.line([(x + dx * 0.6, y - 20), (x + dx, y + 20)], (188, 140, 91), 3)
    elif prop in (
        "STAR_LANTERN",
        "MOON_LANTERN",
        "TOY_STAR",
        "BALLOON",
        "GARLAND",
        "KITE",
        "PINWHEEL",
        "BUBBLES",
    ):
        p.line([(x, y + 51), (x, y - 8)], accent, 4)
        if prop == "BALLOON":
            p.ellipse((x - 34, y - 77, x + 34, y + 4), (234, 169, 177))
            p.polygon([(x, y + 1), (x - 6, y + 10), (x + 6, y + 10)], (234, 169, 177))
        elif prop == "KITE":
            p.polygon([(x, y - 82), (x + 36, y - 40), (x, y + 3), (x - 36, y - 40)], cream)
            p.polygon([(x, y - 82), (x + 36, y - 40), (x, y - 40)], accent, False)
            p.polygon([(x, y - 40), (x - 36, y - 40), (x, y + 3)], (237, 166, 166), False)
        elif prop == "PINWHEEL":
            for dx, dy, color in (
                (-30, -30, accent),
                (30, -30, (239, 166, 164)),
                (30, 30, (244, 207, 133)),
                (-30, 30, (155, 185, 143)),
            ):
                p.polygon([(x, y - 28), (x + dx, y - 28), (x + dx, y - 28 + dy)], color)
            p.ellipse((x - 6, y - 34, x + 6, y - 22), cream)
        elif prop == "BUBBLES":
            p.ellipse((x - 23, y - 48, x + 23, y - 2), None, outline=accent, width=5)
            p.ellipse(
                (x + 27, y - 80, x + 55, y - 52), None, outline=_mix(accent, cream, 0.35), width=2
            )
        elif prop == "GARLAND":
            p.line([(x - 46, y - 50), (x + 46, y - 36)], accent, 3)
            for dx in (-32, -6, 20):
                p.polygon(
                    [(x + dx, y - 47), (x + dx + 19, y - 44), (x + dx + 8, y - 19)], (237, 177, 151)
                )
        elif prop == "MOON_LANTERN":
            p.ellipse((x - 29, y - 68, x + 29, y - 10), (248, 221, 153))
            p.ellipse((x - 8, y - 72, x + 34, y - 31), cream, False)
        else:
            p.star(x, y - 36, 39, (246, 217, 145))
    elif prop in ("CUSHION", "TRAVEL_PILLOW"):
        p.roundrect((x - 50, y - 35, x + 50, y + 35), 25, _mix(accent, cream, 0.45))
        if prop == "TRAVEL_PILLOW":
            p.ellipse((x - 21, y - 21, x + 21, y + 17), cream)
        else:
            p.star(x, y, 20, cream, points=4, outline=False)
    elif prop in ("CAMERA", "BINOCULARS", "TELESCOPE", "COMPASS", "CANTEEN"):
        if prop == "CAMERA":
            p.roundrect((x - 42, y - 26, x + 42, y + 30), 8, accent)
            p.roundrect((x - 24, y - 37, x - 1, y - 22), 4, dark)
            p.ellipse((x - 16, y - 18, x + 27, y + 23), cream)
            p.ellipse((x - 10, y - 12, x + 21, y + 17), dark)
        elif prop == "BINOCULARS":
            for dx in (-22, 22):
                p.roundrect((x + dx - 15, y - 32, x + dx + 15, y + 24), 8, accent)
                p.ellipse((x + dx - 17, y + 11, x + dx + 17, y + 35), dark)
            p.line([(x - 8, y - 4), (x + 8, y - 4)], dark, 13)
        elif prop == "TELESCOPE":
            p.line([(x - 41, y + 10), (x + 37, y - 30)], accent, 25)
            p.line([(x + 31, y - 34), (x + 46, y - 26)], dark, 30)
        elif prop == "COMPASS":
            p.ellipse((x - 35, y - 35, x + 35, y + 35), cream, outline=accent, width=6)
            p.polygon([(x, y - 25), (x - 9, y + 4), (x + 9, y + 4)], (214, 133, 137))
            p.polygon([(x, y + 25), (x - 9, y + 4), (x + 9, y + 4)], accent)
        else:
            p.roundrect((x - 23, y - 39, x + 23, y + 43), 12, accent)
            p.roundrect((x - 12, y - 51, x + 12, y - 36), 4, dark)
            p.line([(x - 12, y - 11), (x + 12, y - 11)], cream, 5)


def render_character(plan, direction="STORYBOOK"):
    """Render a full outfit and readable action on a transparent matte art layer."""
    c = plan["characterPlan"]
    p = Painter(direction)
    role = c["purpose"]["role"]
    accent = _rgb(c["destination"]["accent"])
    role_colors = {
        "BUSINESS": (107, 126, 154),
        "SWIM": (110, 181, 181),
        "HIKING": (137, 164, 117),
        "PLAY": (228, 164, 117),
        "STUDY": (167, 146, 113),
        "DATE": (202, 145, 159),
        "ART": (160, 143, 183),
        "CAFE": (184, 146, 112),
        "NIGHT": (135, 142, 185),
        "CELEBRATE": (219, 154, 144),
        "FOOD": (201, 159, 114),
        "REST": (156, 177, 162),
        "EXPLORE": (143, 163, 177),
    }
    cloth = _mix(role_colors[role], accent, 0.18)
    dark = _mix(cloth, (81, 70, 80), 0.36)
    cream = (255, 245, 222)
    family = c["bodyFamily"]
    furs = {
        "BUNNY": (247, 228, 209),
        "BEAR": (226, 191, 152),
        "CAT": (241, 214, 181),
        "OTTER": (203, 171, 148),
        "FOX": (230, 180, 140),
        "PUP": (235, 208, 175),
        "BIRD": (239, 220, 156),
        "SEAL": (209, 225, 222),
        "PANDA": (244, 236, 218),
        "DEER": (221, 186, 148),
        "MOUSE": (211, 207, 215),
        "PENGUIN": (159, 177, 191),
    }
    fur = furs[family]
    pose = c["pose"]
    prop_side = c["composition"]["propSide"]
    proportion = c["composition"]["bodyProportion"]
    rx = {"PETITE": 139, "ROUND": 148, "TALL": 135, "WIDE": 158}[proportion]
    ry = {"PETITE": 119, "ROUND": 131, "TALL": 121, "WIDE": 116}[proportion]
    if direction == "SOFT_TOY":
        rx *= 1.06
        ry *= 1.08
    elif direction == "FOLK_CHIBI":
        rx *= 0.89
        ry *= 0.90
    cx = 384 + c["routeInfluence"]["earLean"] * 0.5
    cy = 346 + (17 if pose == "SIT" else 0)
    by = 523 + (8 if pose == "SIT" else 0)
    bw = {"PETITE": 76, "ROUND": 92, "TALL": 78, "WIDE": 99}[proportion]
    bh = 89 if pose == "SIT" else 115 if proportion == "TALL" else 102
    if direction == "FOLK_CHIBI":
        bh *= 1.12
    cut = c["outfit"]["cut"]
    cut_delta = {"CLASSIC": 0, "ROUND": 12, "CROPPED": -20, "LONG": 22, "ASYMMETRIC": 8}[cut]
    # Route curl is an actual external appendage with a clean uninterrupted face.
    curl = c["routeInfluence"]["tailCurl"]
    tail_x = cx - prop_side * (bw + 10)
    tail_y = by + 43
    if family in ("CAT", "FOX", "OTTER", "PUP", "MOUSE"):
        p.path(
            (tail_x, tail_y + 25),
            [
                (
                    (tail_x - prop_side * (66 + curl * 14), tail_y + 40),
                    (tail_x - prop_side * (83 + curl * 12), tail_y - 47),
                    (tail_x - prop_side * 42, tail_y - 53),
                ),
                (
                    (tail_x - prop_side * 64, tail_y - 20),
                    (tail_x - prop_side * 31, tail_y + 4),
                    (tail_x, tail_y - 9),
                ),
            ],
            fur,
        )
    elif family in ("BUNNY", "BEAR", "PANDA", "DEER"):
        p.ellipse((tail_x - 24, tail_y - 14, tail_x + 24, tail_y + 34), fur)
    # Backpack/cape has a visible outer silhouette rather than a printed icon.
    if role in ("HIKING", "PLAY", "EXPLORE"):
        p.roundrect(
            (cx - bw - 26, by - 67, cx + bw + 26, by + 60), 29, _mix(cloth, (157, 115, 85), 0.3)
        )
        for side in (-1, 1):
            p.roundrect(
                (cx + side * bw - 13, by - 19, cx + side * bw + 13, by + 34),
                9,
                _mix(cloth, cream, 0.2),
            )
    if role == "NIGHT":
        p.path(
            (cx - bw * 0.6, by - 108),
            [
                ((cx - bw * 1.35, by - 48), (cx - bw * 1.55, by + 59), (cx - bw * 1.25, by + 90)),
                ((cx - bw * 0.4, by + 109), (cx + bw * 0.7, by + 107), (cx + bw * 1.31, by + 83)),
                ((cx + bw * 1.43, by + 26), (cx + bw, by - 77), (cx + bw * 0.5, by - 108)),
            ],
            _mix(cloth, (96, 93, 141), 0.12),
        )
    if role == "SWIM":
        p.ellipse((cx - 145, by - 17, cx + 145, by + 78), None, outline=(245, 198, 124), width=29)
        p.ellipse(
            (cx - 162, by + 54, cx + 158, by + 94), None, outline=(157, 212, 211, 130), width=3
        )
    # Distinct weight-bearing leg placement: seated, stepping and tiptoes.
    legs = [(-49, by + bh - 9), (49, by + bh - 9)]
    if pose == "STEP":
        legs = [(-61, by + bh - 20), (54, by + bh + 10)]
    elif pose == "TIPTOE":
        legs = [(-37, by + bh + 5), (45, by + bh - 18)]
    elif pose == "SIT":
        legs = [(-89, by + bh - 8), (89, by + bh - 8)]
    elif pose in ("PADDLE", "SPLASH", "WAVE"):
        legs = [(-85, by + bh - 15), (73, by + bh + 6)]
    elif pose in ("FLOAT_KICK", "BACK_FLOAT", "DIVE"):
        legs = [(-78, by + bh + 6), (91, by + bh - 26)]
    for dx, ly in legs:
        footfur = cream if role in ("SWIM", "REST") else _mix(cloth, (139, 109, 92), 0.34)
        if role in ("BUSINESS", "HIKING", "PLAY", "STUDY", "EXPLORE", "SWIM"):
            leg_fill = fur if role == "SWIM" else _mix(cloth, (207, 186, 151), 0.55)
            leg_x = cx + dx * 0.65
            p.path(
                (leg_x - 26, by + 43),
                [
                    ((leg_x - 29, by + 79), (cx + dx - 29, ly - 16), (cx + dx - 25, ly + 1)),
                    ((cx + dx - 2, ly + 9), (cx + dx + 24, ly + 3), (cx + dx + 25, ly - 11)),
                    ((leg_x + 29, by + 76), (leg_x + 26, by + 45), (leg_x + 26, by + 43)),
                ],
                leg_fill,
            )
            if role != "SWIM":
                p.line([(cx + dx - 25, ly - 10), (cx + dx + 24, ly - 10)], cream, 5)
        p.ellipse((cx + dx - 30, ly - 22, cx + dx + 31, ly + 17), footfur)
        if role not in ("SWIM", "REST"):
            p.path(
                (cx + dx - 25, ly + 6),
                [((cx + dx - 7, ly + 14), (cx + dx + 13, ly + 14), (cx + dx + 26, ly + 6))],
                outline=cream,
                width=4,
            )
            p.line([(cx + dx - 7, ly - 7), (cx + dx + 8, ly - 5)], cream, 2.5)
    # Torso underneath a real garment. The head overlaps the shoulder naturally.
    body_bottom = by + bh * (
        0.60 if role in ("BUSINESS", "HIKING", "PLAY", "STUDY", "EXPLORE", "SWIM") else 0.90
    )
    p.path(
        (cx - bw * 0.75, by - bh),
        [
            (
                (cx - bw * 1.04, by - bh * 0.45),
                (cx - bw * 1.12, body_bottom - 21),
                (cx - bw * 0.69, body_bottom),
            ),
            (
                (cx - bw * 0.29, body_bottom + 12),
                (cx + bw * 0.41, body_bottom + 12),
                (cx + bw * 0.73, body_bottom),
            ),
            (
                (cx + bw * 1.11, body_bottom - 25),
                (cx + bw * 0.97, by - bh * 0.59),
                (cx + bw * 0.69, by - bh),
            ),
        ],
        fur,
    )
    top = by - bh + 19
    hem = by + bh - 12 + cut_delta * 0.45
    if role in ("BUSINESS", "HIKING", "PLAY", "STUDY", "EXPLORE"):
        hem = by + bh * 0.43 + cut_delta * 0.5
    elif role == "SWIM":
        hem = by + bh * 0.55 + cut_delta * 0.2
    gw = bw + (10 if cut == "ROUND" else -5 if cut == "CROPPED" else 0)
    garment = cloth
    p.path(
        (cx - gw * 0.79, top),
        [
            ((cx - gw * 0.96, by - 24), (cx - gw * 1.09, hem - 16), (cx - gw * 0.78, hem)),
            (
                (cx - gw * 0.21, hem + 13),
                (cx + gw * 0.42, hem + 12),
                (cx + gw * 0.81, hem + (8 if cut == "ASYMMETRIC" else 0)),
            ),
            ((cx + gw * 1.02, by + 31), (cx + gw * 0.97, top + 28), (cx + gw * 0.75, top)),
        ],
        garment,
    )
    # A small secondary tone gives cloth a single fold, not glossy volume.
    p.path(
        (cx + gw * 0.72, top + 28),
        [
            ((cx + gw * 0.90, by + 25), (cx + gw * 0.94, hem - 11), (cx + gw * 0.65, hem + 3)),
            ((cx + gw * 0.79, by + 24), (cx + gw * 0.62, top + 25), (cx + gw * 0.72, top + 28)),
        ],
        _mix(cloth, dark, 0.25),
        False,
    )
    if role == "BUSINESS":
        p.polygon(
            [(cx - 39, top + 3), (cx + 39, top + 3), (cx + 19, hem - 8), (cx - 17, hem - 8)], cream
        )
        p.polygon(
            [
                (cx - 51, top - 4),
                (cx - 14, top + 26),
                (cx - 32, top + 62),
                (cx - 10, top + 88),
                (cx - 61, top + 39),
            ],
            _mix(cloth, cream, 0.22),
        )
        p.polygon(
            [
                (cx + 51, top - 4),
                (cx + 14, top + 26),
                (cx + 32, top + 62),
                (cx + 10, top + 88),
                (cx + 61, top + 39),
            ],
            _mix(cloth, cream, 0.22),
        )
        p.polygon(
            [
                (cx - 12, top + 16),
                (cx + 12, top + 16),
                (cx + 7, top + 31),
                (cx + 15, top + 68),
                (cx, top + 79),
                (cx - 14, top + 67),
                (cx - 6, top + 31),
            ],
            (205, 132, 128),
            outline=(144, 98, 99),
            width=2,
        )
        if cut == "ROUND":
            for dx in (-17, 17):
                for dy in (92, 115):
                    p.ellipse((cx + dx - 3, top + dy - 3, cx + dx + 3, top + dy + 3), cream, False)
        else:
            for dy in (97, 121):
                p.ellipse((cx + 20, top + dy - 3, cx + 26, top + dy + 3), cream, False)
        p.line([(cx - 58, by + 45), (cx - 31, by + 45)], dark, 3)
        p.polygon([(cx + 43, top + 49), (cx + 64, top + 49), (cx + 60, top + 36)], cream, False)
    elif role == "SWIM":
        p.path(
            (cx - 45, top),
            [((cx - 36, top + 42), (cx + 34, top + 42), (cx + 45, top))],
            outline=cream,
            width=8,
        )
        p.line([(cx - 38, top - 7), (cx - 38, top + 24)], cream, 8)
        p.line([(cx + 38, top - 7), (cx + 38, top + 24)], cream, 8)
        p.path(
            (cx - gw * 0.83, by + 30),
            [((cx - 27, by + 43), (cx + 33, by + 13), (cx + gw * 0.83, by + 29))],
            outline=cream,
            width=14,
        )
        p.star(cx + 6, by - 3, 15, (246, 209, 135), outline=False)
    elif role == "PLAY":
        p.roundrect((cx - 46, top + 21, cx + 46, by + 31), 10, _mix(cloth, cream, 0.15))
        for dx in (-38, 38):
            p.line([(cx + dx, top - 10), (cx + dx, top + 33)], _mix(cloth, cream, 0.35), 15)
            p.ellipse(
                (cx + dx - 5, top + 24, cx + dx + 5, top + 34),
                (247, 220, 154),
                outline=dark,
                width=1.5,
            )
        p.roundrect((cx - 21, by - 4, cx + 21, by + 24), 5, cream, outline=dark, width=2)
        p.line([(cx, by + 51), (cx, hem + 4)], dark, 3)
    elif role in ("ART", "FOOD"):
        p.roundrect((cx - 49, top + 13, cx + 49, hem), 10, _mix(cloth, cream, 0.12))
        for dx in (-38, 38):
            p.line([(cx + dx, top - 11), (cx + dx, top + 24)], cream, 10)
        p.roundrect((cx - 31, by + 21, cx + 31, by + 56), 6, cream, outline=dark, width=2)
        if role == "ART":
            for dx, color in ((-15, (224, 153, 153)), (1, (157, 184, 140)), (16, (151, 173, 194))):
                p.line([(cx + dx, by + 27), (cx + dx + 4, by + 44)], color, 6)
        else:
            p.polygon([(cx - 25, top), (cx, top + 32), (cx + 25, top)], cream)
    elif role == "HIKING":
        p.line([(cx, top + 1), (cx, hem)], cream, 4)
        for side in (-1, 1):
            p.roundrect(
                (cx + side * 42 - 19, by - 2, cx + side * 42 + 19, by + 28),
                5,
                _mix(cloth, cream, 0.18),
            )
            p.line([(cx + side * 42 - 14, by + 5), (cx + side * 42 + 14, by + 5)], dark, 2)
        p.polygon(
            [
                (cx - 34, top - 5),
                (cx, top + 19),
                (cx + 34, top - 5),
                (cx + 25, top + 39),
                (cx, top + 23),
                (cx - 24, top + 39),
            ],
            cream,
        )
    elif role in ("REST", "CAFE", "STUDY"):
        if role == "CAFE":
            p.line([(cx, top), (cx, hem)], cream, 5)
            for dy in (-13, 13, 39, 65):
                p.ellipse((cx + 11, by + dy, cx + 17, by + dy + 6), cream, False)
        for dx in range(-55, 56, 18):
            p.line([(cx + dx, hem - 12), (cx + dx, hem)], _mix(cloth, dark, 0.24), 2)
        p.path(
            (cx - 47, top + 3),
            [((cx - 30, top + 34), (cx + 31, top + 34), (cx + 47, top + 3))],
            outline=cream,
            width=8,
        )
        if role == "STUDY":
            for dx in (-27, 27):
                p.polygon(
                    [
                        (cx + dx, by - 8),
                        (cx + dx + 13, by + 10),
                        (cx + dx, by + 28),
                        (cx + dx - 13, by + 10),
                    ],
                    _mix(cloth, cream, 0.35),
                    False,
                )
    elif role in ("DATE", "CELEBRATE"):
        p.path(
            (cx - 47, top + 2),
            [
                ((cx - 37, top + 28), (cx - 11, top + 31), (cx, top + 13)),
                ((cx + 10, top + 31), (cx + 39, top + 28), (cx + 47, top + 2)),
            ],
            cream,
        )
        p.polygon([(cx, top + 21), (cx - 25, top + 11), (cx - 25, top + 37)], (207, 119, 135))
        p.polygon([(cx, top + 21), (cx + 25, top + 11), (cx + 25, top + 37)], (207, 119, 135))
        p.ellipse((cx - 7, top + 17, cx + 7, top + 31), (244, 197, 163))
        for dy in (48, 74, 100):
            p.ellipse((cx - 3, top + dy, cx + 3, top + dy + 6), cream, False)
    elif role == "NIGHT":
        for dx, dy in ((-35, 10), (37, 41), (-18, 65)):
            p.star(cx + dx, by + dy, 11, cream, outline=False)
    else:
        p.line([(cx + 48, top - 10), (cx - 56, hem - 10)], cream, 13)
        p.roundrect((cx - 61, by + 17, cx - 4, by + 68), 9, _mix(cloth, (171, 124, 87), 0.32))
    # Arms carry meaningful gestures. Prop hand and greeting hand stay separate.
    arm_y = by - 36
    prop_hand = (cx + prop_side * (bw + 29), by + 14)
    for side in (-1, 1):
        shoulder = (cx + side * (bw - 5), arm_y - 8)
        if side == prop_side:
            hand = prop_hand
        elif pose in ("HELLO", "WAVE", "SPLASH"):
            hand = (cx + side * (bw + 74), by - 107)
        elif pose in ("PADDLE", "FLOAT_KICK", "BACK_FLOAT", "DIVE"):
            hand = (cx + side * (bw + 78), by - 46)
        elif pose == "TIPTOE":
            hand = (cx + side * (bw + 71), by - 54)
        elif pose == "HUG":
            hand = (cx + side * 47, by + 21)
        elif pose == "PRESENT":
            hand = (cx + side * (bw + 70), by + 6)
        else:
            hand = (cx + side * (bw + 42), by + 38)
        elbow = (cx + side * (bw + 37), arm_y + 7)
        p.path(
            (shoulder[0] - side * 13, shoulder[1]),
            [
                (
                    (elbow[0], elbow[1] - 14),
                    (hand[0] + side * 15, hand[1] - 13),
                    (hand[0] + side * 15, hand[1] + 2),
                ),
                (
                    (hand[0] + side * 12, hand[1] + 26),
                    (hand[0] - side * 15, hand[1] + 25),
                    (hand[0] - side * 21, hand[1] + 6),
                ),
                (
                    (elbow[0] - side * 19, elbow[1] + 21),
                    (shoulder[0] - side * 7, shoulder[1] + 43),
                    (shoulder[0] - side * 13, shoulder[1]),
                ),
            ],
            fur if role == "SWIM" else cloth,
        )
        p.ellipse((hand[0] - 20, hand[1] - 13, hand[0] + 20, hand[1] + 23), fur)
        p.line(
            [(hand[0] + side * 7, hand[1] + 10), (hand[0] + side * 3, hand[1] + 15)],
            _mix(fur, p.ink, 0.40),
            1.7,
        )
    _head(p, c, cx, cy, fur, cream, accent, rx, ry)
    _face(p, c, cx, cy, rx, cream)
    # Role accessories sit on the head and never replace the readable costume.
    if role == "SWIM":
        gy = cy - ry * 0.56
        p.path(
            (cx - rx * 0.91, gy + 2),
            [((cx - rx * 0.44, gy - 20), (cx + rx * 0.49, gy - 20), (cx + rx * 0.91, gy + 2))],
            outline=cloth,
            width=10,
        )
        for side in (-1, 1):
            x = cx + side * 42
            p.roundrect((x - 32, gy - 24, x + 32, gy + 14), 14, cream, outline=cloth, width=7)
            p.roundrect((x - 24, gy - 16, x + 24, gy + 6), 10, (168, 214, 214), False)
            p.line([(x - 15, gy - 9), (x + 2, gy - 9)], cream, 3)
        p.line([(cx - 10, gy - 5), (cx + 10, gy - 5)], cloth, 6)
    elif role == "ART":
        p.path(
            (cx - rx * 0.67, cy - ry + 20),
            [
                (
                    (cx - rx * 0.92, cy - ry - 28),
                    (cx + rx * 0.21, cy - ry - 63),
                    (cx + rx * 0.71, cy - ry - 11),
                ),
                (
                    (cx + rx * 0.84, cy - ry + 17),
                    (cx - rx * 0.35, cy - ry + 32),
                    (cx - rx * 0.67, cy - ry + 20),
                ),
            ],
            cloth,
        )
        p.line([(cx + 11, cy - ry - 36), (cx + 16, cy - ry - 48)], dark, 7)
        p.line([(cx - rx * 0.63, cy - ry + 17), (cx + rx * 0.64, cy - ry + 3)], dark, 4)
    elif role == "HIKING":
        hy = cy - ry + 13
        p.path(
            (cx - 79, hy),
            [((cx - 74, hy - 74), (cx + 63, hy - 69), (cx + 75, hy))],
            _mix(cloth, cream, 0.20),
        )
        p.ellipse((cx - 110, hy - 10, cx + 114, hy + 23), cloth)
        p.line([(cx - 69, hy - 17), (cx + 67, hy - 17)], cream, 9)
    elif role == "STUDY":
        for side in (-1, 1):
            x = cx + side * rx * 0.37
            p.ellipse((x - 27, cy - 19, x + 27, cy + 33), None, outline=(151, 115, 99), width=3)
        p.path(
            (cx - 23, cy + 2),
            [((cx - 9, cy - 8), (cx + 9, cy - 8), (cx + 23, cy + 2))],
            outline=(151, 115, 99),
            width=3,
        )
    elif role == "CELEBRATE":
        hx = cx + rx * 0.61
        p.polygon(
            [(hx - 30, cy - ry + 21), (hx + 28, cy - ry + 10), (hx - 14, cy - ry - 67)],
            _mix(cloth, cream, 0.22),
        )
        p.ellipse((hx - 23, cy - ry - 78, hx - 4, cy - ry - 59), cream)
        p.line([(hx - 23, cy - ry - 5), (hx + 12, cy - ry - 11)], cream, 8)
    elif role == "DATE":
        hx = cx + rx * 0.79
        hy = cy - ry * 0.65
        p.polygon([(hx, hy), (hx - 35, hy - 22), (hx - 32, hy + 21)], cloth)
        p.polygon([(hx, hy), (hx + 28, hy - 27), (hx + 31, hy + 15)], cloth)
        p.ellipse((hx - 9, hy - 10, hx + 9, hy + 10), cream)
    # Prop remains beside the lower body; eyes, tie, and major costume cues remain clear.
    if role == "SWIM":
        # Front half of the swim ring overlaps the waist while preserving legs.
        p.path(
            (cx - 145, by + 21),
            [
                ((cx - 144, by + 86), (cx + 146, by + 86), (cx + 145, by + 21)),
                ((cx + 127, by + 59), (cx - 124, by + 59), (cx - 145, by + 21)),
            ],
            (246, 200, 127),
        )
        for dx in (-97, -35, 35, 97):
            p.line([(cx + dx, by + 52), (cx + dx + 6, by + 67)], cream, 9)
        if c["prop"]["id"] in ("FLOAT_RING", "DUCK_FLOAT"):
            # A ring is worn, not held like an unrelated accessory.
            if c["prop"]["id"] == "DUCK_FLOAT":
                p.ellipse(
                    (cx + prop_side * 117 - 24, by - 10, cx + prop_side * 117 + 24, by + 37),
                    (246, 200, 127),
                )
                p.ellipse(
                    (cx + prop_side * 127 - 3, by + 1, cx + prop_side * 127 + 3, by + 7),
                    p.ink,
                    False,
                )
            prop_render = False
        else:
            prop_render = True
    else:
        prop_render = True
    px = cx + prop_side * (bw + 55)
    py = by + 30
    if pose == "HUG" and c["prop"]["id"] in ("CUSHION", "OPEN_BOOK", "GIFT", "BENTO"):
        px = cx
        py = by + 50
    # These grips are measured in _prop's local coordinates: the midpoint of
    # the diagonal pencil/brush shaft, or the centre of the pole handle.
    grip = {
        "PAINTBRUSH": (-1, 0.5),
        "PENCIL": (-1, 0.5),
        "TREKKING_POLE": (3.5, -55),
    }.get(c["prop"]["id"])
    if grip:
        px, py = prop_hand[0] - grip[0], prop_hand[1] + 5 - grip[1]
    if prop_render:
        _prop(p, c, px, py, accent, cream, fur)
        if grip:
            # The palm covers the shaft so this reads as a grip, not a line
            # painted across the hand. All other accessories keep their layout.
            hx, hy = prop_hand
            p.ellipse((hx - 20, hy - 13, hx + 20, hy + 23), fur)
            p.line(
                [(hx + prop_side * 7, hy + 10), (hx + prop_side * 3, hy + 15)],
                _mix(fur, p.ink, 0.40),
                1.7,
            )
    # Connected travel charm: destination evidence is a real part of the accessory.
    token_x = cx - prop_side * (bw + 3)
    _destination_token(p, c, token_x, by + 21, accent)
    # Composition is an actual global tilt, not only a hash difference.
    tilt = character_tilt(c)
    if tilt:
        p.image = p.image.rotate(
            tilt, resample=Image.Resampling.BICUBIC, center=(cx * SCALE, 430 * SCALE)
        )
    if c["composition"]["facing"] == -1:
        p.image = p.image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    image = p.image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    # Only a restrained ground shadow; no opaque background cards around avatars.
    shadow = Image.new("RGBA", (SIZE, SIZE))
    sd = ImageDraw.Draw(shadow)
    bottom = min(690, by + bh + 25)
    sd.ellipse((cx - 132, bottom - 12, cx + 132, bottom + 14), fill=(91, 83, 87, 28))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    return Image.alpha_composite(shadow, image)


def silhouette_contour(image, center=(384, 430), count=192):
    """Read the actual rendered opaque alpha to drive matching formation effects."""
    alpha = image.getchannel("A")
    pixels = alpha.load()
    points = []
    for i in range(count - 1):
        theta = i * math.tau / (count - 1)
        dx, dy = math.cos(theta), math.sin(theta)
        found = center
        for distance in range(346, 0, -1):
            x = round(center[0] + dx * distance)
            y = round(center[1] + dy * distance)
            if 0 <= x < SIZE and 0 <= y < SIZE and pixels[x, y] > 190:
                found = (x, y)
                break
        points.append([round(found[0] / SIZE, 7), round(found[1] / SIZE, 7)])
    return points + points[:1]
