#!/usr/bin/env python3
"""Export reproducible local layer samples and an unchanged-image review board.

Run from the repository with its backend Python environment. The exporter uses
the production compositor, emits its PNG bytes unchanged, and makes no network
or image-generation calls. The sample coordinates are synthetic screen-space
points, not geographic coordinates or observed Pleos navigation data.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from nunti.avatar_studio.layered_render import ASSET_ROOT, render_layered_avatar
from nunti.avatar_studio.models import AvatarInput, Route, canonical
from nunti.avatar_studio.variant_spec import (
    ASSET_VERSION,
    MAPPING_VERSION,
    LayeredAvatarSpec,
    VariantContext,
)
from PIL import Image, ImageChops
from PIL import __version__ as PILLOW_VERSION

MOODS = {"calm": "차분함", "curious": "호기심", "adventurous": "모험심"}
PROFILES = {
    "coast": {
        "label": "바다",
        "motif": "물결 장식 · 푸른 스카프 포인트",
        "roadType": "highway",
        "roadLabel": "고속도로",
        "color": "#5595B0",
        "points": [
            [0.10, 0.82],
            [0.25, 0.68],
            [0.40, 0.54],
            [0.61, 0.40],
            [0.84, 0.18],
        ],
    },
    "mountain": {
        "label": "산",
        "motif": "능선 장식 · 이끼색 스카프 포인트",
        "roadType": "rural",
        "roadLabel": "일반 교외도로",
        "color": "#709260",
        "points": [
            [0.10, 0.82],
            [0.29, 0.69],
            [0.17, 0.53],
            [0.54, 0.43],
            [0.37, 0.25],
            [0.84, 0.12],
        ],
    },
    "city": {
        "label": "도시",
        "motif": "창문 장식 · 라일락 스카프 포인트",
        "roadType": "urban",
        "roadLabel": "도심도로",
        "color": "#9780B1",
        "points": [
            [0.15, 0.85],
            [0.15, 0.57],
            [0.42, 0.57],
            [0.42, 0.31],
            [0.82, 0.31],
            [0.82, 0.12],
        ],
    },
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


def route_for(category):
    profile = PROFILES[category]
    return Route.model_validate(
        {
            "points": profile["points"],
            "inputOrigin": "TEST_ROUTE",
            "sourceLabel": f"MOCK {profile['label']} 비교용 합성 경로 · 지리 좌표 아님",
            "confirmed": True,
        }
    )


def context_for(category, mood):
    return VariantContext(
        routeId=f"mock-nunti-{category}-v1",
        routeRevision=1,
        seed="0",
        destinationCategory=category,
        roadType=PROFILES[category]["roadType"],
        userSelectedMood=mood,
        provenance={
            "routeId": "mock",
            "routeRevision": "mock",
            "routeGeometry": "mock",
            "destinationCategory": "mock",
            "roadType": "mock",
            "userSelectedMood": "mock",
        },
    )


def request_for(category, context, route):
    value = {
        "renderMode": "LOCAL_LAYERS",
        "destination": {
            "name": "기본 눈티"
            if category == "base"
            else f"{PROFILES[category]['label']} 합성 시나리오",
            "traits": "MOCK 검토 입력. 실제 GPS·지형·SDK 분류 근거가 아닙니다.",
        },
        "purpose": "레이어 변형 검토",
        "variantContext": context.model_dump(),
    }
    if route is not None:
        value["route"] = route.model_dump()
    value["requestId"] = str(
        uuid5(NAMESPACE_URL, "nunti-layer-sample:" + canonical(value))
    )
    AvatarInput.model_validate(value)
    return value


def export_sample(output, sample_id, category, mood, context, route):
    folder = output / "samples" / sample_id
    folder.mkdir(parents=True, exist_ok=True)
    png, design = render_layered_avatar(context, route)
    spec = design["avatarSpec"]
    LayeredAvatarSpec.model_validate(spec)
    if design["renderStatus"] != "COMPOSITED":
        raise RuntimeError(f"Expected complete local bundle for {sample_id}")
    with Image.open(io.BytesIO(png)) as image:
        if image.size != (768, 768) or image.mode != "RGBA":
            raise RuntimeError("Unexpected generated image format")
    request = request_for(category, context, route)
    (folder / "character.png").write_bytes(png)
    write_json(folder / "AvatarSpec.json", spec)
    write_json(folder / "request.json", request)
    write_json(folder / "render-metadata.json", design)
    return {
        "sampleId": sample_id,
        "category": category,
        "mood": mood,
        "image": f"samples/{sample_id}/character.png",
        "imageSha256": sha(png),
        "avatarSpec": f"samples/{sample_id}/AvatarSpec.json",
        "request": f"samples/{sample_id}/request.json",
        "metadata": f"samples/{sample_id}/render-metadata.json",
        "requestId": request["requestId"],
        "variantId": spec["variantId"],
        "routeId": spec["routeId"],
        "routeFingerprint": spec["routeFingerprint"],
        "layerAssets": design["layerAssets"],
    }


CSS = """
*{box-sizing:border-box}body{margin:0;background:#f3f4ee;color:#2a4039;font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif}h1,h2,h3,p{margin:0}
.board{width:2240px;height:2360px;padding:56px 64px 42px}.header{height:148px;border-bottom:1px solid #cdd9cd;display:flex;justify-content:space-between}.kicker{font-size:18px;font-weight:650;letter-spacing:3px;color:#668576}h1{font-size:52px;letter-spacing:-1.5px;margin-top:8px;font-weight:700}.subtitle{font-size:23px;line-height:1.5;margin-top:12px}.meta{font-size:17px;text-align:right;line-height:1.8;color:#60766b;padding-top:8px}
.main{height:1288px;margin-top:26px;display:grid;grid-template-columns:360px 1fr;gap:28px}.base{background:#e4ede2;border-radius:24px;padding:28px;display:flex;flex-direction:column;align-items:center;border:1px solid #cfddce}.tag{font-size:16px;letter-spacing:2px;font-weight:650;color:#68826d}.base h2{font-size:34px;margin-top:13px;letter-spacing:-1px}.base .description{font-size:21px;line-height:1.6;margin-top:16px}.base figure{margin:28px -12px 18px;width:328px;height:414px;background:#f6f7f0;border-radius:22px;display:flex;align-items:center;justify-content:center}.base ul{padding-left:22px;font-size:21px;line-height:1.85;margin:16px 0 0}.base .fixed{margin-top:24px;padding-top:24px;border-top:1px solid #bdcdbb;width:100%}.base .fallback{margin-top:auto;padding:22px 0 5px;border-top:1px solid #bdcdbb;font-size:21px;line-height:1.65}.base .colors{display:flex;gap:14px;margin-top:24px}.swatch{width:36px;height:36px;border-radius:50%;border:1px solid #00000010}
.matrix{display:grid;grid-template-rows:52px repeat(3,392px);gap:20px}.moods{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;align-items:center}.moods h2{font-size:28px;text-align:center;font-weight:650}.row{display:grid;grid-template-rows:40px 352px}.row-label{display:flex;align-items:center;gap:16px;font-size:25px;font-weight:680}.row-label small{font-size:18px;font-weight:400;color:#63786c}.dot{width:10px;height:10px;border-radius:50%}.cells{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.card{background:white;border:1px solid #dce4d9;border-radius:20px;display:flex;align-items:center;flex-direction:column;justify-content:center}.card svg{display:block}.card-label{font-size:18px;color:#5f7669;margin-top:2px}
.shared{margin-top:32px;height:270px}.section-title{display:flex;align-items:baseline;gap:22px;height:48px}.section-title h2{font-size:29px;letter-spacing:-.8px}.section-title p{font-size:20px;color:#627b6d}.layers{display:grid;grid-template-columns:repeat(6,1fr);gap:20px}.layer{height:210px;background:#e8eee3;border:1px solid #d7e1d2;border-radius:16px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:7px}.layer p{font-size:19px;font-weight:600}.layer .frame{width:166px;height:166px;background:repeating-conic-gradient(#fff 0% 25%,#f0f3ec 0% 50%) 50% / 16px 16px;border-radius:8px}
.display{margin-top:20px;height:264px}.display-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.display-card{height:208px;background:#e9eee5;border:1px solid #d5dfd2;border-radius:18px;display:flex;align-items:center;justify-content:space-evenly;gap:16px;padding:18px}.display-card h3{font-size:22px;width:145px;line-height:1.45}.mini{display:flex;align-items:center;flex-direction:column;gap:9px;font-size:15px;color:#607468}.mini .surface{width:140px;height:140px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:#f6f4ef}.mini .surface.night{background:#263c38}.closing{margin-top:20px;background:#edf1e8;border:1px solid #cddbc8;border-radius:18px;padding:23px 27px;display:grid;grid-template-columns:1.1fr 1fr;gap:42px;height:128px}.closing h3{font-size:24px}.closing p{font-size:20px;line-height:1.6;margin-top:7px}.footnote{margin-top:18px;font-size:15px;color:#6b8072;display:flex;justify-content:space-between}
"""


def review_board(output, samples):
    image_paths = {s["sampleId"]: output / s["image"] for s in samples}
    core_names = {
        "body": "몸",
        "head": "후드와 얼굴 바탕",
        "sprout": "새싹",
        "scarf": "스카프",
        "bag": "가방",
        "badge": "기본 배지",
    }
    image_paths.update(
        {"core-" + name: ASSET_ROOT / "core" / (name + ".png") for name in core_names}
    )
    definitions = "".join(
        f'<image id="art-{key}" width="768" height="768" href="data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"/>'
        for key, path in image_paths.items()
    )

    def art(key, width, height=None):
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height or width}" viewBox="0 0 768 768" role="img" aria-label="{key}"><use href="#art-{key}"/></svg>'

    rows = []
    for category, profile in PROFILES.items():
        cards = "".join(
            f'<div class="card">{art(category + "-" + mood, 310)}<p class="card-label">{profile["label"]} · {label}</p></div>'
            for mood, label in MOODS.items()
        )
        rows.append(
            f'<section class="row"><div class="row-label"><span class="dot" style="background:{profile["color"]}"></span>{profile["label"]}<small>{profile["motif"]} · 경로 예시 {profile["roadLabel"]}</small></div><div class="cells">{cards}</div></section>'
        )
    layers = "".join(
        f'<div class="layer"><div class="frame">{art("core-" + name, 166)}</div><p>{label}</p></div>'
        for name, label in core_names.items()
    )
    display_cards = []
    for key, title in (
        ("coast-curious", "바다 · 호기심"),
        ("mountain-calm", "산 · 차분함"),
        ("city-adventurous", "도시 · 모험심"),
    ):
        display_cards.append(
            f'<div class="display-card"><h3>{title}</h3><div class="mini"><div class="surface">{art(key, 128)}</div><span>밝은 배경 · 128 px</span></div><div class="mini"><div class="surface night">{art(key, 128)}</div><span>어두운 배경 · 128 px</span></div></div>'
        )
    mood_heads = "".join(f"<h2>{label}</h2>" for label in MOODS.values())
    colors = "".join(
        f'<span class="swatch" style="background:{color}"></span>'
        for color in ("#F5E6D8", "#ACDABF", "#B6D1E4", "#FED7C6", "#90614C")
    )
    return f"""<!doctype html><html lang="ko"><meta charset="utf-8"><title>눈티 공통 레이어 변형 비교</title><style>{CSS}</style>
<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" style="position:absolute"><defs>{definitions}</defs></svg>
<main class="board"><header class="header"><div><div class="kicker">NUNTI · SHARED LAYER VARIANTS 01</div><h1>기본 눈티 하나에서, 아홉 가지 여행 표현</h1><p class="subtitle">바다 / 산 / 도시 × 차분함 / 호기심 / 모험심 · 같은 원화와 얼굴 기준점을 재사용합니다.</p></div><div class="meta">A · Matte Form 기준<br>정적 변형 시스템 검토<br>합성 경로 3종 · 실제 지리 정보 아님</div></header>
<div class="main"><aside class="base"><div class="tag">SHARED MASTER</div><h2>기본 눈티</h2><p class="description">모든 변형의 출발점이자<br>데이터 누락 시의 기본 외형</p><figure>{art("base", 328)}</figure><div class="colors">{colors}</div><div class="fixed"><h3 style="font-size:25px">계속 같은 눈티</h3><ul><li>둥근 후드와 몸의 비율</li><li>새싹과 한쪽 앞머리</li><li>눈·입의 기준 위치</li><li>스카프·가방·기본 배지</li></ul></div><p class="description" style="width:100%;margin-top:28px">목적지는 작은 장식과 색 포인트로,<br>경로는 스카프의 한 줄 무늬로,<br>기분은 얼굴 표정으로 표현합니다.</p><div class="fallback">경로가 없으면 기본 눈티.<br>모르는 목적지·기분은 해당 표현만 기본값으로 돌아갑니다.</div></aside>
<section class="matrix"><div class="moods">{mood_heads}</div>{"".join(rows)}</section></div>
<section class="shared"><div class="section-title"><h2>아홉 변형이 공유하는 원화 레이어 6개</h2><p>각 PNG는 같은 768×768 좌표계에 정렬되어 있습니다. 표정과 장식만 별도 레이어로 합성합니다.</p></div><div class="layers">{layers}</div></section>
<section class="display"><div class="section-title"><h2>밝은 배경과 어두운 배경</h2><p>동일한 투명 PNG · 표시 영역 128×128 px · 실제 차량 화면 검증은 별도입니다.</p></div><div class="display-grid">{"".join(display_cards)}</div></section>
<footer class="closing"><div><h3>같은 입력에는 같은 외형</h3><p>경로·시드·매핑 버전이 같으면 PNG와 AvatarSpec이 동일합니다.<br>모든 샘플은 공통 core 레이어의 같은 해시를 사용합니다.</p></div><div><h3>원화 전체를 다시 생성하지 않습니다</h3><p>로컬 레이어 조합으로 동작하며, 주행마다 이미지 생성 API를 호출하지 않습니다.<br>누락·손상 레이어는 독립적으로 보관한 기본 눈티로 복구합니다.</p></div></footer>
<div class="footnote"><span>검토용 합성 입력 · 미지원 SDK 분류를 추정하지 않음 · 기분은 선택값이며 차량 신호로 추론하지 않음</span><span>{MAPPING_VERSION} · {ASSET_VERSION} · 2240×2360</span></div></main></html>"""


def export(output):
    output.mkdir(parents=True, exist_ok=True)
    samples = [export_sample(output, "base", "base", "base", VariantContext(), None)]
    for category in PROFILES:
        for mood in MOODS:
            samples.append(
                export_sample(
                    output,
                    f"{category}-{mood}",
                    category,
                    mood,
                    context_for(category, mood),
                    route_for(category),
                )
            )
    manifest = json.loads((ASSET_ROOT / "manifest.json").read_text())
    expected_core = {
        "core/" + name + ".png": manifest["files"]["core/" + name + ".png"]["sha256"]
        for name in manifest["coreOrder"]
    }
    common_core = all(
        all(
            s["layerAssets"].get(path) == value for path, value in expected_core.items()
        )
        for s in samples
    )
    with (
        Image.open(output / samples[0]["image"]) as actual,
        Image.open(ASSET_ROOT / "base.png") as expected,
    ):
        base_exact = (
            ImageChops.difference(actual, expected).getbbox(alpha_only=False) is None
        )
    unique_count = len({s["imageSha256"] for s in samples[1:]})
    if not common_core or not base_exact or unique_count != 9:
        raise RuntimeError("Export consistency check failed")
    # A second render verifies the exported PNG and spec against the real renderer.
    stable = True
    for sample in samples:
        request = AvatarInput.model_validate_json(
            (output / sample["request"]).read_text()
        )
        png, design = render_layered_avatar(request.variantContext, request.route)
        stable &= sha(png) == sample["imageSha256"]
        stable &= design["avatarSpec"] == json.loads(
            (output / sample["avatarSpec"]).read_text()
        )
    if not stable:
        raise RuntimeError("Repeat rendering changed an exported artifact")
    report = {
        "schemaVersion": "nunti.layer-consistency/1",
        "mappingVersion": MAPPING_VERSION,
        "assetVersion": ASSET_VERSION,
        "sampleCount": 10,
        "variantCount": 9,
        "distinctVariantPngCount": unique_count,
        "allSamplesReuseCoreHashes": common_core,
        "sharedCoreHashes": expected_core,
        "noRouteMatchesBasePixels": base_exact,
        "secondRenderPngAndSpecIdentical": stable,
        "renderer": "LOCAL_LAYERS",
        "networkPolicy": "socket.create_connection and urllib.request.urlopen blocked during export",
        "imageGenerationCalls": 0,
        "inputProvenance": "MOCK synthetic normalized screen-space routes",
        "pythonVersion": sys.version.split()[0],
        "pillowVersion": PILLOW_VERSION,
        "faceAnchors": manifest["fixedFaceAnchors"],
        "limitations": [
            "Static artifact checks, not emulator/performance certification",
            "Three road stripe alternatives can be shared by different routes",
        ],
    }
    write_json(output / "samples" / "consistency-report.json", report)
    write_json(
        output / "samples" / "index.json",
        {
            "schemaVersion": "nunti.layer-samples/1",
            "pathsRelativeTo": "docs/redesign/route-variants-v1",
            "mappingVersion": MAPPING_VERSION,
            "assetVersion": ASSET_VERSION,
            "canvas": [768, 768],
            "allInputsSynthetic": True,
            "sampleSeed": "0",
            "samples": samples,
        },
    )
    write_json(output / "AvatarSpec.schema.json", LayeredAvatarSpec.model_json_schema())
    (output / "comparison-board.html").write_text(review_board(output, samples))
    print(
        json.dumps(
            {
                "output": str(output),
                "samples": len(samples),
                "uniqueVariants": unique_count,
                "sharedCore": common_core,
                "boardSize": [2240, 2360],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/redesign/route-variants-v1"
    )
    args = parser.parse_args()

    def network_forbidden(*_args, **_kwargs):
        raise RuntimeError("Network use is forbidden for local variant export")

    with (
        patch("socket.create_connection", network_forbidden),
        patch("urllib.request.urlopen", network_forbidden),
    ):
        export(args.output.resolve())
