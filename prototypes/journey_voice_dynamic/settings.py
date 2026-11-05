"""Pure mapping from a committed character recipe to a frozen voice direction."""
import hashlib
import json

VERSION = "journey-sohee-directions-1"
COMMON_TEXT = "안녕. 오늘은 나랑 같이 가자."
PURPOSES = {
    "rest": ("calm warmth and clear unhurried phrasing", "오늘은 느긋하게 함께 가자.", "같이 천천히 바라보자."),
    "camping": ("warm curiosity and a steady natural pace", "어떤 작은 발견이 기다릴까?", "우리 천천히 둘러보자."),
    "exhibition": ("quiet delight and light clear phrasing", "어떤 색을 만나게 될까?", "마음에 드는 색을 찾아보자."),
    "commute": ("friendly composure and concise clear phrasing", "오늘도 함께 갈게.", "잠깐 쉬어 가도 좋아."),
    "visit": ("gentle welcoming warmth and a steady natural pace", "반가운 마음으로 함께 가자.", "좋은 시간을 보내면 좋겠어."),
    "errand": ("bright consideration and concise clear phrasing", "오늘 할 일을 함께 보러 가자.", "이제 한숨 돌려도 좋겠어."),
    "unspecified": ("gentle composure and a natural conversational pace", "오늘의 이동을 함께할게.", "여기서 어떤 기억을 만나게 될까?"),
}
DESTINATIONS = (
    ("art", "전시 보러 가는 날이네.", "어떤 작품을 만나게 될까?"),
    ("coastal_city", "바다 보러 가는 날이네.", "어떤 바다를 만나게 될까?"),
    ("mountain", "산을 만나러 가는 날이네.", "산빛을 조금 담아둘까?"),
    ("forest", "숲을 만나러 가는 날이네.", "초록빛을 조금 담아둘까?"),
    ("lakeside", "물빛을 만나러 가는 날이네.", "물빛을 조금 담아둘까?"),
    ("city", "오늘은 도시로 가는 날이네.", "어떤 골목을 만나게 될까?"),
)
BODY_DELIVERY = {
    "pebble": "a soft airy tone", "droplet": "a light fluid tone",
    "bean": "a warm rounded tone", "sprout": "a clear gently curious tone",
    "pillow": "a soft rounded tone", "lantern": "a clear warm tone",
    "cloud": "a soft light tone", "acorn": "a gently resonant rounded tone",
}
SUFFIXES = {"pebble": "몽", "droplet": "방울", "bean": "콩", "sprout": "토리",
            "pillow": "몽", "lantern": "별", "cloud": "몽", "acorn": "토리"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def character_plan(recipe, engine):
    """Read only the first committed recipe. Engine identity is pinned, not inferred."""
    creative = recipe["creativeInspiration"]
    purpose = creative["purpose"] or "unspecified"
    if purpose not in PURPOSES:
        raise ValueError("UNSUPPORTED_CHARACTER_PURPOSE")
    family = recipe["design"]["bodyFamily"]
    if family not in BODY_DELIVERY:
        raise ValueError("UNSUPPORTED_BODY_FAMILY")
    delivery, greeting_end, arrival_end = PURPOSES[purpose]
    destination_tags = creative["destinationTags"]
    destination = next((entry for entry in DESTINATIONS if entry[0] in destination_tags), None)
    greeting_start, arrival_start = destination[1:] if destination else ("안녕.", "도착했네.")
    root = recipe["design"]["nameDirection"]["rootSuggestion"]
    name = root + SUFFIXES[family]
    voice = {
        "providerId": engine.identity["providerId"], "engineIdentity": engine.identity,
        "engineFingerprint": engine.fingerprint,
        "characterId": recipe["characterId"], "journeyId": recipe["journeyId"],
        "identityKey": recipe["voiceIntent"]["identityKey"],
        "profileId": "journey-sohee-" + hashlib.sha256(recipe["characterId"].encode()).hexdigest()[:20],
        "speaker": "Sohee", "locale": "ko-KR",
        "seed": int(recipe["seed"], 16) % (2**32),
        "direction": "Native Korean conversational speech with a small smile, " + delivery + ", and " + BODY_DELIVERY[family] + ".",
        "requestedCharacterTraits": recipe["voiceIntent"]["requested"],
        "variationScope": "Delivery variation within native Korean Sohee; not a newly cloned or unique speaker.",
        "postprocessing": "none",
    }
    voice["bindingId"] = "dvb-" + digest(voice)[:32]
    plan = {"schemaVersion": 1, "settingsVersion": VERSION,
            "characterId": recipe["characterId"], "journeyId": recipe["journeyId"],
            "recipeSha256": digest(recipe), "displayName": name,
            "nameOrigin": "Generated from the committed name root and body family",
            "voice": voice,
            "utterances": {"greeting": greeting_start + " " + greeting_end,
                           "arrival": arrival_start + " " + arrival_end,
                           "common": COMMON_TEXT},
            "arrivalPlayback": "Prepared text only; no arrival detection or automatic playback."}
    plan["planSha256"] = digest(plan)
    return plan
