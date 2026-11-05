"""Bounded intent rules and English art descriptions, with explicit uncertainty.

This is not a general language model. Activity mentions that are locally negated
are excluded; undecided alternatives and unsupported text remain UNKNOWN.
"""

from __future__ import annotations

import re

ALIASES = {
    "BUSINESS": ("거래처", "고객사", "프레젠테이션", "제안서", "계약서", "면접", "회사", "일하"),
    "SWIM": ("헤엄", "첨벙", "파도를 타", "바다에 들어", "물에 들어", "물에 떠"),
    "HIKING": ("산 정상", "능선", "정상에 오르", "산을 오르"),
    "PLAY": ("바람개비", "비눗방울", "장난감", "어린 아이 캐릭터", "꼬마 캐릭터"),
    "STUDY": ("책을 읽", "책 읽", "책읽", "자격증", "학업"),
    "DATE": ("소개팅", "프로포즈"),
    "ART": ("스케치", "그림을 감상", "작품 감상"),
    "CAFE": ("라떼", "아메리카노", "찻집", "차 한 잔"),
    "NIGHT": ("별 관측", "밤하늘", "천체", "일몰"),
    "CELEBRATE": ("생신", "돌잔치", "졸업식"),
    "FOOD": ("식당", "도시락", "피크닉", "브런치"),
    "REST": ("쉬러", "쉬고", "쉬는", "쉬며", "쉬어", "쉬기", "쉬겠", "쉼", "재충전", "멍때"),
    "EXPLORE": ("탐험", "탐방", "둘러보", "둘러볼", "구경", "여행 기록", "explore", "sightseeing"),
}

_NEGATED_AFTER = re.compile(
    r"^\s*(?:은|는|을|를|이|가|도|에)?\s*"
    r"(?:(?:하(?:러|는|기|지|고)?|보(?:러|는|기|지)?)\s*)?"
    r"(?:지\s*)?"
    r"(?:가(?:는|기|지)?\s*)?(?:건|것은|게)?\s*"
    r"(?:아니|아님|안\s*(?:하|할|해|합|한|가|갈)|못\s*(?:하|할|해|가|갈)|않|취소|말고)"
)
_NEGATED_BEFORE = re.compile(r"(?:\bnot|\bno|\bwithout)\s+(?:(?:on|a|doing)\s+)*$", re.I)
_UNDECIDED = re.compile(
    r"(?:미정|아직\s*(?:모르|정하지|고민)|인지.{0,45}인지|either.{0,40}or)", re.I
)


def _occurrences(text, word):
    if word.isascii():
        # Only documented inflections; 'workout' must not become business work.
        endings = {
            "swim": "(?:ming|s)?",
            "surf": "(?:ing|s)?",
            "work": "(?:ing|s)?",
            "relax": "(?:ing|ation|ed)?",
            "explor": "(?:e|ing|ation)?",
            "stargaz": "(?:e|ing)?",
            "celebrat": "(?:e|ing|ion)?",
            "play": "(?:ing|s)?",
            "walk": "(?:ing|s)?",
            "rest": "(?:ing|ed)?",
        }
        pattern = r"(?<![a-z])" + re.escape(word) + endings.get(word, "") + r"(?![a-z])"
    else:
        pattern = re.escape(word)
    yield from re.finditer(pattern, text)


def resolve_purpose(text, specifications):
    lower = text.lower()
    candidates, excluded = [], []
    for values in specifications:
        role, words = values[:2]
        # Bare age words or parts of unrelated words do not assert an activity.
        words = tuple(w for w in words if w not in ("아이", "어린", "꼬마", "별", "쉬", "먹"))
        for word in (*words, *ALIASES.get(role, ())):
            for match in _occurrences(lower, word):
                prefix, suffix = (
                    lower[max(0, match.start() - 24) : match.start()],
                    lower[match.end() : match.end() + 36],
                )
                if _NEGATED_AFTER.search(suffix) or _NEGATED_BEFORE.search(prefix):
                    excluded.append({"role": role, "word": word, "reason": "LOCAL_NEGATION"})
                    continue
                candidates.append((values, word))
    roles = list(dict.fromkeys(values[0] for values, _ in candidates))
    if candidates and not (len(roles) > 1 and _UNDECIDED.search(lower)):
        values, word = candidates[0]
        return (
            values,
            word,
            {"resolution": "MATCHED", "candidateRoles": roles, "excluded": excluded},
        )
    # Exploration is a presentation fallback, not a claim about inferred intent.
    status = "UNDECIDED" if candidates else "NO_SUPPORTED_ACTIVITY"
    return (
        None,
        "",
        {"resolution": "UNKNOWN", "reason": status, "candidateRoles": roles, "excluded": excluded},
    )


WARDROBES_EN = {
    "BUSINESS": "a tailored business suit with lapels, collared shirt, tie and two trouser legs",
    "SWIM": "a one-piece swimsuit and swim goggles",
    "HIKING": "a hiking vest, hiking boots, brimmed hiking hat and backpack",
    "PLAY": "childlike dungarees, a little backpack and sneakers",
    "STUDY": "a knitted vest and round spectacles",
    "DATE": "a ribbon-collar coat with a soft bow",
    "ART": "a painter's apron and beret",
    "CAFE": "a cozy cardigan and small scarf",
    "NIGHT": "a little star-button cape",
    "CELEBRATE": "a bow-tie party vest and tiny party hat",
    "FOOD": "a tiny apron and neckerchief",
    "REST": "an oversized soft sweater and scarf",
    "EXPLORE": "a neutral travel vest and crossbody strap",
}

PROPS_EN = {
    "BRIEFCASE": "a professional briefcase",
    "DOCUMENT": "a folder of presentation papers",
    "LAPTOP": "an open miniature laptop",
    "TROLLEY": "a small rolling business suitcase",
    "FLOAT_RING": "a round inflatable swim ring worn around the waist",
    "DUCK_FLOAT": "a duck-shaped inflatable swim ring worn around the waist",
    "SURFBOARD": "a miniature surfboard beside a waist-worn swim ring",
    "BEACH_BALL": "a striped beach ball and a waist-worn swim ring",
    "TREKKING_POLE": "a trekking pole",
    "COMPASS": "a round hiking compass",
    "CANTEEN": "a hiking water bottle",
    "TRAIL_MAP": "a folded route map held in the hands",
    "PINWHEEL": "a colorful paper pinwheel",
    "KITE": "a small diamond-shaped kite",
    "TOY_STAR": "a toy star on a stick",
    "BUBBLES": "a bubble-blowing wand",
    "OPEN_BOOK": "an open reading book",
    "NOTEBOOK": "a study notebook",
    "PENCIL": "a big pencil",
    "BOOK_STACK": "a stack of two books",
    "FLOWER": "one flower",
    "BOUQUET": "a small flower bouquet",
    "HEART_LETTER": "a folded love letter",
    "PICNIC_BASKET": "a small woven picnic basket",
    "PALETTE": "a paint palette with a brush",
    "SKETCHBOOK": "a small sketchbook",
    "PAINTBRUSH": "a painter's brush",
    "ART_FRAME": "a tiny framed drawing",
    "TEACUP": "a warm teacup",
    "COFFEE": "a takeaway coffee cup",
    "CROISSANT": "a small croissant",
    "DESSERT": "a dessert on a plate",
    "STAR_LANTERN": "a star-shaped lantern",
    "TELESCOPE": "a miniature telescope",
    "MOON_LANTERN": "a moon-shaped lantern",
    "STAR_MAP": "an unfolded star chart",
    "GIFT": "a wrapped gift with a bow",
    "CAKE": "a small birthday cake",
    "BALLOON": "one celebration balloon",
    "GARLAND": "a tiny festive pennant garland",
    "BENTO": "a small lunchbox",
    "SANDWICH": "a triangular sandwich",
    "CHEF_SPOON": "a wooden cooking spoon",
    "CUSHION": "a soft star-embroidered cushion",
    "LEAF_FAN": "a leaf-shaped hand fan",
    "TRAVEL_PILLOW": "a soft travel neck pillow",
    "CAMERA": "a small travel camera",
    "BINOCULARS": "a pair of binoculars",
    "POSTCARD": "a travel postcard",
}

ACTIONS_EN = {
    "BUSINESS": "greeting a colleague with calm confidence, ready for a professional visit",
    "SWIM": "enjoying water play with visible paddling or kicking limbs",
    "HIKING": "taking a purposeful little hiking step",
    "PLAY": "playing with youthful curiosity and lively energy",
    "STUDY": "concentrating gently during a reading break",
    "DATE": "greeting a companion with affectionate anticipation",
    "ART": "observing and creating art with quiet curiosity",
    "CAFE": "enjoying a warm cafe break",
    "NIGHT": "looking up in wonder during a night-sky outing",
    "CELEBRATE": "sharing a joyful celebration",
    "FOOD": "enjoying a small food outing",
    "REST": "settling into a peaceful resting moment",
    "EXPLORE": "accompanying the journey without assuming a specific activity",
}

POSES_EN = {
    "HELLO": "one hand raised in a clear greeting wave",
    "STEP": "one foot stepping forward and the other supporting the body",
    "HUG": "hands drawn close to the chest in a hugging gesture",
    "TIPTOE": "one lifted heel and a small buoyant tiptoe gesture",
    "SIT": "a seated pose with little feet spread outward",
    "PRESENT": "one arm extending outward to present the selected prop",
    "PADDLE": "paddling sideways with one arm extended and alternating kicking feet",
    "SPLASH": "one arm raised while the feet kick outward through a playful splash",
    "FLOAT_KICK": "leaning diagonally in the float ring with one leg kicking forward",
    "BACK_FLOAT": "floating almost horizontally on the back with spread little feet",
    "WAVE": "waving from the swim ring while the feet paddle below",
    "DIVE": "a playful diagonal diving lean with extended limbs and visible swim gear",
}

KEEPSAKES_EN = {
    "STATION_CLOCK": "a prominent round station-clock purse with an attached rail ticket",
    "RAIL_WINDOW": "a prominent train-shaped satchel with two windows and tiny wheels",
    "SHELL": "a prominent scalloped seashell-shaped bag",
    "LEAF": "a leaf-shaped satchel",
    "COFFEE_BEAN": "a coffee-bean-shaped purse",
    "MOUNTAIN": "a mountain-ridge-shaped satchel",
    "MOON": "a moon-and-star purse",
    "GATE": "a traditional tiled-gate-shaped satchel",
    "CITY_WINDOW": "a city-window satchel",
    "ART_FRAME": "a framed-painting-shaped satchel",
    "BOOK": "a book-shaped bag",
    "WAVE": "a wave-decorated river satchel",
    "STAR": "a playful star purse",
    "JOURNEY_STAR": "a neutral journey-star keepsake bag",
}
