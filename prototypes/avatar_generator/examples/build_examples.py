"""Rebuild three synthetic route screenshots and their paired screen-coordinate ground truth.

No real map data, geocoder, navigation provider, model, network, recording, or character catalog.
"""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 960, 640
ROUTE_COLOR = "#2478ec"
CASES = [
    {
        "id": "synthetic-city",
        "title": "합성 내비 시험 · 도심의 굽은 경로",
        "destination": {
            "name": "작은 미술관",
            "traits": "도심에서 조용히 그림을 보는 곳",
        },
        "purpose": "주말 전시를 보며 쉬기",
        "path": [
            (278, 490),
            (278, 420),
            (358, 420),
            (358, 330),
            (487, 330),
            (487, 239),
            (621, 239),
            (697, 171),
            (836, 171),
        ],
        "mapLabel": "CITY ROUTE / synthetic streets",
        "destinationLabel": "Little art gallery",
    },
    {
        "id": "synthetic-coast",
        "title": "합성 내비 시험 · 해안처럼 휘는 경로",
        "destination": {
            "name": "물빛 전망대",
            "traits": "바다 풍경을 떠올리게 하는 가상의 전망대",
        },
        "purpose": "경치를 보며 기분 전환하기",
        "path": [
            (274, 502),
            (325, 455),
            (389, 441),
            (443, 399),
            (463, 339),
            (514, 296),
            (590, 280),
            (661, 236),
            (742, 226),
            (823, 172),
        ],
        "mapLabel": "COAST-LIKE ROUTE / synthetic landscape",
        "destinationLabel": "Waterlight lookout",
    },
    {
        "id": "synthetic-hills",
        "title": "합성 내비 시험 · 구릉처럼 굽이치는 경로",
        "destination": {
            "name": "숲속 찻집",
            "traits": "숲에서 따뜻한 차를 즐기는 가상의 장소",
        },
        "purpose": "잠시 쉬며 차 마시기",
        "path": [
            (267, 494),
            (351, 470),
            (408, 411),
            (381, 360),
            (421, 301),
            (505, 300),
            (553, 343),
            (623, 320),
            (671, 254),
            (649, 205),
            (729, 157),
            (834, 181),
        ],
        "mapLabel": "HILLS-LIKE ROUTE / synthetic landscape",
        "destinationLabel": "Forest tea house",
    },
]


def font(size):
    for file in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(file).exists():
            return ImageFont.truetype(file, size)
    return ImageFont.load_default(size=size)


def create(case):
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f3f2ed")
    d = ImageDraw.Draw(image)
    # Deliberately generated blocks and roads, not a screenshot of a live map.
    for x in range(245, 955, 94):
        for y in range(114, 584, 78):
            d.rounded_rectangle(
                (x + 5, y + 5, x + 73, y + 56), radius=7, fill="#e8e5de"
            )
    if case["id"] == "synthetic-coast":
        d.polygon(
            [
                (670, 90),
                (960, 90),
                (960, 640),
                (550, 640),
                (610, 500),
                (680, 388),
                (720, 270),
            ],
            fill="#d4e6e8",
        )
    elif case["id"] == "synthetic-hills":
        d.ellipse((390, 100, 960, 560), fill="#dde5d3")
        for inset in range(0, 110, 24):
            d.arc(
                (430 + inset, 132 + inset, 906 - inset, 510 - inset),
                10,
                330,
                fill="#cbd7c0",
                width=2,
            )
    for x in range(245, 961, 94):
        d.line([(x, 80), (x, 640)], fill="white", width=14)
    for y in range(114, 640, 78):
        d.line([(224, y), (960, y)], fill="white", width=14)
    d.line([(233, 582), (473, 484), (690, 505), (960, 375)], fill="#d6d5d0", width=22)
    d.line([(233, 582), (473, 484), (690, 505), (960, 375)], fill="white", width=17)
    # Header / destination card make this usable as a screenshot extraction trial.
    d.rectangle((0, 0, 960, 76), fill="#294f4b")
    d.text((22, 15), "NUNTI  /  ROUTE INPUT TEST", fill="white", font=font(23))
    d.text(
        (22, 46), "SYNTHETIC MAP - NO LIVE NAVIGATION", fill="#d9e9e2", font=font(15)
    )
    d.rectangle((0, 76, 224, 640), fill="#fffefa")
    d.text((20, 101), "Destination", fill="#52635d", font=font(17))
    label = case["destinationLabel"].split(" ")
    for i in range(0, len(label), 2):
        d.text(
            (20, 137 + i // 2 * 27),
            " ".join(label[i : i + 2]),
            fill="#263d38",
            font=font(21),
        )
    d.text((20, 232), "Route preview", fill="#52635d", font=font(17))
    d.text((20, 266), "A  Start", fill="#333333", font=font(16))
    d.text((20, 295), "B  Destination", fill="#333333", font=font(16))
    d.text((20, 369), "Illustrative route", fill="#52635d", font=font(15))
    d.text((20, 397), "No GPS coordinates", fill="#52635d", font=font(14))
    d.text((20, 420), "No real distance", fill="#52635d", font=font(14))
    d.text((20, 443), "No road data", fill="#52635d", font=font(14))
    path = case["path"]
    d.line(path, fill="white", width=21, joint="curve")
    d.line(path, fill=ROUTE_COLOR, width=12, joint="curve")
    for x, y in path:
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=ROUTE_COLOR)
    for label, (x, y) in zip(("A", "B"), (path[0], path[-1])):
        d.rounded_rectangle((x - 42, y - 43, x - 18, y - 17), radius=5, fill="#343e3a")
        d.text((x - 36, y - 42), label, fill="white", font=font(19))
    d.rectangle((224, 591, 960, 640), fill="#fffefa")
    d.text((242, 603), case["mapLabel"], fill="#52635d", font=font(17))
    file = ROOT / f"{case['id']}.png"
    image.save(file, optimize=True)
    points = [[round(x / WIDTH, 7), round(y / HEIGHT, 7)] for x, y in path]
    metadata = {key: case[key] for key in ("id", "title", "destination", "purpose")}
    metadata.update(
        {
            "imageFile": file.name,
            "route": {
                "points": points,
                "inputOrigin": "TEST_ROUTE",
                "sourceLabel": "직접 그린 합성 내비 시험 이미지. 실제 지도·GPS·도로 정보 없음.",
                "confirmed": True,
            },
            "provenance": {
                "kind": "SYNTHETIC_NAVIGATION_SCREENSHOT",
                "generator": "build_examples.py",
                "license": "project-authored synthetic test fixture",
                "realMapData": False,
                "liveNavigation": False,
                "imageSha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            },
            "groundTruth": {
                "coordinateSpace": "WHOLE_IMAGE_NORMALIZED_XY",
                "imageWidth": WIDTH,
                "imageHeight": HEIGHT,
                "routeColor": ROUTE_COLOR,
                "pixelPoints": path,
                "confirmation": "paired with the exact path used by the deterministic screenshot generator",
            },
        }
    )
    (ROOT / f"{case['id']}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
    )
    return metadata


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    entries = [create(case) for case in CASES]
    (ROOT / "index.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        "Created three SYNTHETIC route PNG/JSON pairs. No map service or character assets used."
    )
