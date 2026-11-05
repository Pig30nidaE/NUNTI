"""Bind a fictional Korean voice to the same journey meaning as its illustration.

This is a synthesis instruction, not evidence that listeners hear a unique speaker.
The binding belongs to one avatar and is stable when that avatar is reopened.
"""

from __future__ import annotations

import hashlib
import json
import re

VERSION = "journey-voice-design-6"

# Purpose has precedence over place: a business trip to a beach still wears a suit.
ROLES = {
    "professional": (
        "자신감 있는 출장 동반자",
        "adult",
        (
            "A polished adult Korean voice, compact and warm, with composed "
            "confidence, a smiling lower-middle register and crisp but relaxed "
            "conversational phrasing. Sound like a friendly capable colleague, never "
            "a newsreader."
        ),
        "오늘 일정, 차근차근 함께해요.",
        0.97,
        0.99,
    ),
    "playful": (
        "장난스러운 꼬마 판타지 동반자",
        "youthful-fictional",
        (
            "An original tiny youthful fantasy creature, performed by a Korean voice "
            "actor. A light bright youthful timbre, lively rounded vowels, "
            "spontaneous playful curiosity and a small genuine smile. Clear relaxed "
            "Korean; charming and sprightly without squeaks or exaggerated baby talk."
        ),
        "우리 오늘 어떤 재미를 만날까?",
        1.02,
        1.18,
    ),
    "swimmer": (
        "물놀이를 좋아하는 꼬마 동반자",
        "youthful-fictional",
        (
            "An original little aquatic fantasy companion, performed by a Korean "
            "voice actor. Youthful buoyant timbre, sunny playfulness, sparkling clear "
            "articulation and an easy friendly smile. Light and bouncy but "
            "conversational, without squeaks or forced cuteness."
        ),
        "파도랑 인사하러 가자!",
        1.03,
        1.16,
    ),
    "explorer": (
        "씩씩하고 호기심 많은 탐험 동반자",
        "young-adult",
        (
            "A youthful Korean adventure companion with a clear rounded middle "
            "register, an eager curious smile and friendly grounded energy. Confident "
            "and lively with naturally connected sentences, as if discovering "
            "something together."
        ),
        "새로운 풍경을 같이 찾아봐요.",
        0.99,
        1.08,
    ),
    "restful": (
        "포근하고 다정한 휴식 동반자",
        "adult",
        (
            "A soft compact Korean adult voice with warm rounded resonance, a quiet "
            "natural smile and unhurried reassuring phrasing. Gentle ordinary "
            "conversation at normal volume, clear consonants and smooth vowels; no "
            "whispering or breathy ASMR."
        ),
        "오늘은 조금 천천히 쉬어가요.",
        0.91,
        1.04,
    ),
    "artist": (
        "섬세하고 감성적인 예술 동반자",
        "young-adult",
        (
            "A softly expressive young Korean adult voice with delicate clear "
            "resonance and thoughtful curious melody. Intimate friendly conversation, "
            "quietly delighted, with natural varied phrasing and a subtle smile."
        ),
        "마음에 드는 장면을 같이 담아요.",
        0.95,
        1.09,
    ),
    "celebration": (
        "밝고 설레는 축하 동반자",
        "young-adult",
        (
            "A bright rounded young Korean adult voice with a joyful genuine smile, "
            "affectionate excitement and flowing conversational rhythm. Enthusiastic "
            "but comfortable and never shouted, with clear native Korean "
            "articulation."
        ),
        "오늘의 기쁜 순간을 함께할게요!",
        1.01,
        1.12,
    ),
    "foodie": (
        "맛있는 발견을 좋아하는 동반자",
        "young-adult",
        (
            "A friendly rounded Korean voice with a cozy smile and playful "
            "anticipation, rich warm vowels and expressive natural conversational "
            "pauses. Delighted curiosity, never a commercial announcer."
        ),
        "맛있는 기억을 하나 만들어봐요.",
        0.97,
        1.1,
    ),
    "companion": (
        "작고 맑은 여행 동반자",
        "young-adult",
        (
            "A compact rounded young Korean adult voice with a sincere natural smile, "
            "friendly warmth, clear native articulation and naturally flowing "
            "conversational intonation. A lovable small animated companion speaking "
            "to one close friend."
        ),
        "오늘의 길을 함께 걸어볼까요?",
        0.97,
        1.09,
    ),
}

_PURPOSE_RULES = (
    (
        "professional",
        ("출장", "회의", "미팅", "출근", "업무", "면접", "business", "work", "meeting"),
    ),
    ("swimmer", ("수영", "물놀이", "해수욕", "서핑", "다이빙", "swim", "surf")),
    (
        "playful",
        (
            "아이",
            "어린",
            "놀이",
            "동심",
            "가족",
            "소풍",
            "키즈",
            "피크닉",
            "play",
            "family",
            "picnic",
        ),
    ),
    (
        "celebration",
        ("생일", "축하", "기념", "결혼", "공연", "축제", "콘서트", "festival", "celebrat"),
    ),
    ("foodie", ("맛집", "먹", "식사", "미식", "카페", "디저트", "시장", "food", "cafe", "dining")),
    (
        "artist",
        (
            "전시",
            "미술",
            "박물관",
            "사진",
            "촬영",
            "예술",
            "독서",
            "도서",
            "museum",
            "art",
            "photo",
        ),
    ),
    (
        "explorer",
        ("등산", "캠핑", "탐험", "트레킹", "자전거", "운동", "모험", "hike", "camp", "explor"),
    ),
    ("restful", ("휴식", "힐링", "산책", "쉬", "명상", "온천", "rest", "relax", "walk")),
)

_ILLUSTRATION_ROLES = {
    "BUSINESS": "professional",
    "SWIM": "swimmer",
    "PLAY": "playful",
    "HIKING": "explorer",
    "EXPLORE": "explorer",
    "ART": "artist",
    "CAFE": "foodie",
    "FOOD": "foodie",
    "REST": "restful",
    "NIGHT": "restful",
    "CELEBRATE": "celebration",
    "DATE": "celebration",
    "STUDY": "professional",
}

# Only age words attached to an explicitly fictional character qualify. An
# accompanying child's age and destination traits never describe the avatar.
_CHARACTER_AGE = re.compile(
    r"(?P<age>어린아이|어린이|초등학생|꼬마|성인|어른)"
    r"(?:가상|판타지|합성)?(?:캐릭터|눈티|아바타)"
)
_CHARACTER_PLACE = re.compile(r"^(?:박물관|도서관|공원|학교|전시관|매장|센터|체험관)")
_PRECEDING_AGE = re.compile(
    r"(어린아이|어린이|초등학생|꼬마|성인|어른)(?:같은|느낌의|목소리의|이면서)?$"
)
_AGE_PARTICLE = r"(?:으로는|로는|으로|은|는|이|가|을|를|로|도)?"
_AGE_NEGATION = re.compile(
    r"^" + _AGE_PARTICLE + r"(?:절대|전혀|별로|더는|이제)?"
    r"(?:(?:만들|하|보이)(?:지|고|기)?|원(?:하지|치))?"
    r"(?:아니|아님|말고|제외|빼|안|않|말아|말자|마(?=$|[.!?,]|세요|라|줘|요)|싫)"
)
_AGE_UNDECIDED = re.compile(
    r"^" + _AGE_PARTICLE + r"(?:인지|일지|일까|할까|할지|정할지|만들지|갈지|"
    r"(?:아직)?(?:미정|정하지|모르|고민))"
)
_AGE_ACTING = {
    "professional": "Composed and quietly confident, with clear relaxed phrasing.",
    "playful": "Playful curiosity with a small genuine smile and lively rounded vowels.",
    "swimmer": "Sunny aquatic playfulness, buoyant phrasing and a friendly smile.",
    "explorer": "Curious, friendly and eager to discover a new landscape together.",
    "restful": "Gentle reassurance, clear consonants and calm conversational pauses.",
    "artist": "Thoughtful curiosity and delicate delight while noticing art together.",
    "celebration": "Affectionate excitement and joyful, comfortable conversation.",
    "foodie": "Cozy anticipation and curiosity about a delicious discovery.",
    "companion": "Sincere warmth and a small natural smile, speaking to one close friend.",
}


def _character_age(purpose: str) -> dict | None:
    compact = re.sub(r"\s+", "", purpose)
    mentions = [
        match
        for match in _CHARACTER_AGE.finditer(compact)
        if not _CHARACTER_PLACE.match(compact[match.end() :])
    ]
    if not mentions:
        return None
    values = {"ADULT" if m["age"] in {"성인", "어른"} else "CHILD" for m in mentions}
    evidence = []
    for mention in mentions:
        preceding = _PRECEDING_AGE.search(compact[: mention.start()])
        if preceding:
            values.add("ADULT" if preceding[1] in {"성인", "어른"} else "CHILD")
        start = preceding.start() if preceding else mention.start()
        evidence.append(compact[start : mention.end()])
    negative = any(
        _AGE_NEGATION.match(compact[m.end() :])
        or re.search(r"(?:아닌|원하지않는|제외한|아니게)$", compact[: m.start()])
        for m in mentions
    )
    undecided = any(_AGE_UNDECIDED.match(compact[m.end() :]) for m in mentions)
    reason = "CONFLICTING_AGES" if len(values) > 1 else "NEGATED" if negative else "UNDECIDED"
    matched = len(values) == 1 and not negative and not undecided
    return {
        "resolution": "MATCHED" if matched else "UNKNOWN",
        "value": next(iter(values)) if matched else None,
        "source": "EXPLICIT_FICTIONAL_CHARACTER",
        "evidence": evidence,
        **({} if matched else {"reason": reason}),
    }


def _age_direction(age, chosen, illustrated_role, label, line):
    acting = _AGE_ACTING[chosen]
    if illustrated_role == "STUDY":
        acting = "Gentle bookish curiosity and clear attentive phrasing during a reading adventure."
        line = "책 속의 이야기를 같이 만나봐요."
    if age["value"] == "CHILD":
        description = (
            "책을 좋아하는 꼬마 판타지 동반자"
            if illustrated_role == "STUDY"
            else "앳된 판타지 " + label
        )
        return (
            description,
            "youthful-fictional",
            "An original fictional childlike Korean character performed by an adult voice actor. "
            "A light youthful timbre, clear native Korean articulation and a small natural smile. "
            "No imitation of an actual child, no squeaks and no exaggerated baby talk. " + acting,
            line,
            0.99,
            1.16,
        )
    if age["value"] == "ADULT":
        return (
            "차분한 성인 판타지 동반자",
            "adult",
            "An original adult Korean fantasy companion with warm clear resonance and natural "
            "conversational flow. A composed adult timbre without imitating a real person. "
            + acting,
            line,
            0.97,
            1.02,
        )
    return (
        "나이 인상을 정하지 않은 판타지 동반자",
        "unspecified",
        "An original fictional Korean companion with an age-unspecified timbre. "
        "Use clear, friendly natural conversation without assigning a child or adult identity. "
        + acting,
        line,
        0.97,
        1.06,
    )


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def select_voice_role(destination: str, traits: str, purpose: str) -> str:
    for source in (purpose.casefold(), (destination + " " + traits).casefold()):
        for role, words in _PURPOSE_RULES:
            if any(word in source for word in words):
                return role
    return "companion"


def _profile_id(plan):
    identity = {k: v for k, v in plan.items() if k != "profileId"}
    return "nv6-" + hashlib.sha256(canonical(identity).encode()).hexdigest()


def _with_particle(name: str) -> str:
    last = ord(name[-1]) if name else 0
    has_final = 0xAC00 <= last <= 0xD7A3 and (last - 0xAC00) % 28 != 0
    return name + ("이랑" if has_final else "랑")


def build_voice_design(data: dict, design: dict | None = None, *, role: str | None = None) -> dict:
    """Use validated AvatarInput-shaped data; returned plan can be stored verbatim."""
    design = design or {}
    destination = data["destination"]["name"]
    traits = data["destination"].get("traits", "")
    purpose = data.get("purpose", "")
    illustrated_role = design.get("characterPlan", {}).get("purpose", {}).get("role")
    chosen = (
        role
        or _ILLUSTRATION_ROLES.get(illustrated_role)
        or select_voice_role(destination, traits, purpose)
    )
    if chosen not in ROLES:
        raise ValueError("VOICE_ROLE_UNKNOWN")
    label, impression, direction, line, rate, pitch = ROLES[chosen]
    character_age = _character_age(purpose)
    if character_age is not None:
        label, impression, direction, line, rate, pitch = _age_direction(
            character_age, chosen, illustrated_role, label, line
        )
    fingerprint = hashlib.sha256(
        canonical({"version": VERSION, "input": data, "role": chosen}).encode()
    ).hexdigest()
    seed = int(fingerprint[:8], 16)
    resonance = (
        "rounded and softly resonant",
        "light and clear with a warm core",
        "velvety and gently bright",
        "crisp and mellow",
    )[int(fingerprint[8:10], 16) % 4]
    rhythm = ("gently lilting", "smoothly connected", "lightly animated", "calmly assured")[
        int(fingerprint[10:12], 16) % 4
    ]
    name = design.get("displayName", "눈티")
    # Keep a full short sentence to support intelligibility and an eventual ICL reference.
    greeting = f"{destination} 가는 길, {_with_particle(name)} 함께해요. {line}"
    plan = {
        "schemaVersion": 1,
        "version": VERSION,
        "role": chosen,
        "ageImpression": impression,
        "description": label,
        "language": "Korean",
        "seed": seed,
        "instruct": (
            f"{direction} The tone is {resonance}, the phrase rhythm is {rhythm}. "
            "Speak only the provided text in fluent Korean. "
            "Ordinary conversational volume; no singing, no sound effects, no robotic cadence. "
            "This is an invented character, not an imitation of any real person."
        ),
        "greeting": greeting[:180],
        "displayName": name,
        "destination": destination,
        "purpose": purpose,
        "rate": rate,
        "pitch": pitch,
        "modelFamily": "Qwen3-TTS-VoiceDesign",
        "synthetic": True,
        "realPersonReference": False,
        "automaticPlayback": False,
        "humanListeningVerified": False,
        "speakerUniquenessVerified": False,
    }
    if character_age is not None:
        plan["characterAge"] = character_age
    plan["profileId"] = _profile_id(plan)
    return plan


def validate_voice_plan(value: dict) -> None:
    """Validate the serialized job boundary before paths or GPU state are touched."""
    if not isinstance(value, dict) or value.get("version") != VERSION:
        raise ValueError("VOICE_PLAN_VERSION_UNSUPPORTED")
    if value.get("role") not in ROLES or value.get("profileId") != _profile_id(value):
        raise ValueError("VOICE_BINDING_MISMATCH")
    if type(value.get("seed")) is not int or not 0 <= value["seed"] <= 0xFFFFFFFF:
        raise ValueError("VOICE_SEED_INVALID")
    for key, limit in (("instruct", 2000), ("greeting", 180)):
        item = value.get(key)
        if (
            not isinstance(item, str)
            or not item.strip()
            or len(item) > limit
            or any(ord(c) < 32 for c in item)
        ):
            raise ValueError("VOICE_TEXT_INVALID")
