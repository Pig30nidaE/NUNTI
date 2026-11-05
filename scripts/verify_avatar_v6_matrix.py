#!/usr/bin/env python3
"""Render and audit 200 destination/purpose combinations without network or paid APIs.

Run with the backend Python environment. This is a procedural-render audit: it
does not claim that 200 AI images or 200 audio clips were generated. Pixel hashes,
semantic structure and visual similarity are reported separately.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import math
import os
import sys
import time
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
MANIFEST = ROOT / "docs/design/avatar-v6/cases.json"
OUTPUT = ROOT / ".local/avatar-v6/matrix"
FIXED_SEED = "nunti-v6-semantic-control-fixed-fine-details"
PURPOSES = [
    ("BUSINESS", "출장 회의에서 발표하기. 자신감 있는 직장인 동반자", "출장"),
    ("SWIM", "수영과 물놀이. 수영복과 튜브를 챙긴 동반자", "수영"),
    ("HIKING", "등산과 트레킹. 등산복을 입고 산길 걷기", "등산"),
    ("DATE", "설레는 데이트. 꽃을 들고 연인 만나기", "데이트"),
    ("PLAY", "아이와 놀이터 소풍. 장난스럽고 앳된 가상 캐릭터", "아이와 놀이"),
    ("ART", "미술 전시 관람. 그림을 감상하고 스케치하기", "미술 관람"),
    ("CAFE", "카페에서 커피를 마시며 여유 즐기기", "카페"),
    ("NIGHT", "야경과 별 보기. 일몰 뒤 밤 풍경 감상하기", "야경"),
    ("CELEBRATE", "생일 축하 파티. 선물을 들고 기념일 축하하기", "축하"),
    ("REST", "휴식과 힐링. 조용히 쉬며 마음을 회복하기", "휴식"),
]
DESTINATIONS = [
    ("서울역", "", "STATION"),
    ("수원역", "", "STATION"),
    ("을왕리해수욕장", "", "COAST"),
    ("서울시청", "도심, 광장", "CITY"),
    ("판교테크노밸리", "업무 단지, 도시", "CITY"),
    ("국립중앙박물관", "전시, 역사, 박물관", "MUSEUM"),
    ("동대문디자인플라자", "디자인 전시, 도시 건축", "MUSEUM"),
    ("올림픽공원", "잔디, 공원, 나무", "PARK"),
    ("북한산국립공원", "산, 등산로, 숲", "MOUNTAIN"),
    ("서울식물원", "식물, 정원, 온실", "GARDEN"),
    ("강릉 안목해변", "해변, 커피, 파도", "COAST"),
    ("속초해수욕장", "동해, 바다, 해변", "COAST"),
    ("전주한옥마을", "한옥, 전통, 역사", "HERITAGE"),
    ("경주 첨성대", "유적, 역사, 밤하늘", "HERITAGE"),
    ("부산 광안리해수욕장", "해변, 광안대교", "COAST"),
    ("인천 송도센트럴파크", "공원, 수변, 도심", "PARK"),
    ("대전 국립중앙과학관", "과학 전시, 탐구", "MUSEUM"),
    ("제주 협재해수욕장", "바다, 해변, 섬", "COAST"),
    ("남산서울타워", "전망대, 도시, 야경", "CITY"),
    ("춘천 레고랜드", "놀이공원, 가족, 놀이", "PLAYGROUND"),
]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def make_manifest() -> dict:
    """Snapshot cached paths once; subsequent runs need no local navigation cache."""
    cached = []
    for name in ("native", "seoul", "coast"):
        path = ROOT / f".local/navigation-integration/live/{name}-plan.json"
        if not path.exists():
            raise FileNotFoundError(f"Cached route fixture is required to rebuild manifest: {path}")
        plan = json.loads(path.read_text())
        cached.append({
            "fixture": name,
            "points": plan["routePoints"],
            "source": {
                "provider": plan["geometry"]["provider"],
                "planId": plan["planId"],
                "origin": plan["origin"]["name"],
                "destination": plan["destination"]["name"],
                "rawGeometrySha256": plan["geometry"]["rawSha256"],
                "capturedFileSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            },
        })
    routes = {}
    cases = []
    for index, (destination, traits, expected_place) in enumerate(DESTINATIONS):
        route_id = f"qa-route-{index + 1:02d}"
        source = cached[index % len(cached)]
        # The same path/seed is held fixed across all ten purposes at a place.
        # Transforms increase geometric coverage without making network calls.
        angle = (index // 3) * 0.29
        points = []
        for x, y in source["points"]:
            x, y = x - 0.5, y - 0.5
            points.append([
                x * math.cos(angle) - y * math.sin(angle),
                x * math.sin(angle) + y * math.cos(angle),
            ])
        min_x, max_x = min(p[0] for p in points), max(p[0] for p in points)
        min_y, max_y = min(p[1] for p in points), max(p[1] for p in points)
        span = max(max_x - min_x, max_y - min_y, 0.001)
        points = [[round(0.1 + (x - min_x) / span * 0.8, 6),
                   round(0.1 + (y - min_y) / span * 0.8, 6)] for x, y in points]
        routes[route_id] = {
            "points": points,
            "inputOrigin": "TEST_ROUTE",
            "sourceLabel": "저장 도로 경로의 명시적 합성 QA 변형 — 해당 목적지의 실제 경로 아님",
            "confirmed": True,
            "provenance": {
                "kind": "SYNTHETIC_QA_TRANSFORM",
                "isRouteToNamedDestination": False,
                "source": source["source"],
                "transform": {"rotationRadians": angle, "normalizedMargin": 0.1},
            },
        }
        for role, purpose, label in PURPOSES:
            case_id = f"{index + 1:02d}-{role.lower()}"
            cases.append({
                "id": case_id,
                "requestId": str(uuid.uuid5(uuid.NAMESPACE_URL, "nunti:v6:matrix:" + case_id)),
                "destination": {"name": destination, "traits": traits},
                "purpose": purpose,
                "purposeLabel": label,
                "expectedPurposeRole": role,
                "expectedDestinationFamily": expected_place,
                "routeId": route_id,
                "renderSeed": FIXED_SEED,
                "scenarioKind": "SYNTHETIC_COUNTERFACTUAL_QA",
            })
    return {
        "schemaVersion": "nunti-v6-matrix-1",
        "description": "20개 장소 × 10개 명시 목적. 목적 효과를 고정 경로·고정 seed로 비교한다.",
        "routeDisclaimer": "전부 합성 QA 경로이며 장소의 실제 도로 안내가 아니다. 원 경로 출처를 보존한다.",
        "activityDisclaimer": "역에서 수영 같은 비현실적 조합도 목적 우선순위를 검증하는 반사실 QA다.",
        "networkCallsRequired": 0,
        "paidCallsRequired": 0,
        "routes": routes,
        "cases": cases,
    }


def structural_fields(plan: dict) -> dict:
    """Exclude seed, hashes, color, labels and numeric micro-variation from diversity."""
    outfit, prop = plan.get("outfit", {}), plan.get("prop", {})
    composition = plan.get("composition", {})
    return {
        "bodyFamily": plan.get("bodyFamily"),
        "outfit": outfit.get("id"),
        "outfitCut": outfit.get("cut"),
        "pose": plan.get("pose"),
        "action": plan.get("action"),
        "prop": prop.get("id"),
        "expression": plan.get("expression"),
        "facing": composition.get("facing"),
    }


def accepted_destination_kinds(case: dict) -> list[str]:
    """Allow legitimate place readings, but catch UNKNOWN or broad-word shadowing."""
    name = case["destination"]["name"]
    if name == "동대문디자인플라자":
        return ["CITY", "MUSEUM"]
    if name == "경주 첨성대":
        return ["HERITAGE", "NIGHT"]
    if name == "남산서울타워":
        return ["CITY", "NIGHT"]
    return [{"COAST": "BEACH", "PARK": "GARDEN"}.get(
        case["expectedDestinationFamily"], case["expectedDestinationFamily"])]


def pixel_features(image: Image.Image) -> dict:
    """Compute a real low-frequency DCT pHash and opaque silhouette without numpy."""
    image = image.convert("RGBA")
    background = Image.new("RGBA", image.size, (250, 247, 241, 255))
    background.alpha_composite(image)
    rgb = background.convert("RGB").resize((32, 32), Image.Resampling.LANCZOS)
    gray = rgb.convert("L").tobytes()
    cosines = [[math.cos((2 * x + 1) * u * math.pi / 64) for x in range(32)]
               for u in range(8)]
    rows = [[sum(gray[y * 32 + x] * cosines[u][x] for x in range(32))
             for u in range(8)] for y in range(32)]
    coefficients = [sum(rows[y][u] * cosines[v][y] for y in range(32))
                    for v in range(8) for u in range(8)]
    ordered = sorted(coefficients[1:])
    median = ordered[len(ordered) // 2]
    phash = sum(1 << i for i, value in enumerate(coefficients[1:]) if value > median)
    opaque = image.getchannel("A").point(lambda v: 255 if v >= 200 else 0)
    mask = opaque.resize((64, 64), Image.Resampling.NEAREST)
    bits = sum(1 << i for i, value in enumerate(mask.tobytes()) if value)
    return {"phash": phash, "silhouette": bits, "rgb": bytes(rgb.tobytes()),
            "opaqueFraction": sum(opaque.histogram()[1:]) / (image.width * image.height)}


def similarity(a: dict, b: dict) -> dict:
    union = (a["silhouette"] | b["silhouette"]).bit_count()
    iou = (a["silhouette"] & b["silhouette"]).bit_count() / max(union, 1)
    hamming = (a["phash"] ^ b["phash"]).bit_count()
    rgb_difference = sum(abs(x - y) for x, y in zip(a["rgb"], b["rgb"], strict=True)) / len(a["rgb"])
    return {"pHashDistance": hamming, "opaqueSilhouetteIoU": round(iou, 5),
            "meanRgbDifference": round(rgb_difference, 4)}


def is_near_duplicate(metrics: dict) -> bool:
    # Conservative triage: only three agreeing measurements flag a pair.
    return (metrics["pHashDistance"] <= 6 and metrics["opaqueSilhouetteIoU"] >= 0.985
            and metrics["meanRgbDifference"] < 12)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in ("/System/Library/Fonts/AppleSDGothicNeo.ttc",
                 "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def contact_sheets(rows: list[dict], output: Path) -> list[str]:
    paths = []
    for start in range(0, len(rows), 25):
        batch = rows[start:start + 25]
        sheet = Image.new("RGB", (1200, 1535), "#f8f5ee")
        draw = ImageDraw.Draw(sheet)
        draw.text((24, 18), f"NUNTI · V6   {start + 1:03d}–{start + len(batch):03d}",
                  fill="#302e38", font=font(25))
        draw.text((24, 51), "목적·장소 조합 / 고정 seed / 합성 QA 경로 / LOCAL_RENDER",
                  fill="#655e73", font=font(17))
        for index, row in enumerate(batch):
            x, y = (index % 5) * 240, 92 + (index // 5) * 286
            draw.rounded_rectangle((x + 8, y, x + 232, y + 274), 14, fill="white")
            with Image.open(output / row["image"]) as img:
                thumb = img.convert("RGBA").resize((216, 216), Image.Resampling.LANCZOS)
                sheet.paste(thumb, (x + 12, y + 1), thumb)
            draw.text((x + 17, y + 215), row["destination"], fill="#302e38", font=font(16))
            draw.text((x + 17, y + 236), f'{row["id"]} · {row["purposeLabel"]}',
                      fill="#766c83", font=font(14))
            if row["failures"]:
                draw.text((x + 17, y + 254), "확인 필요", fill="#aa274a", font=font(12))
        relative = f"contact-sheets/{start // 25 + 1:02d}.jpg"
        (output / relative).parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output / relative, quality=92)
        paths.append(relative)
    return paths


def write_gallery(rows: list[dict], report: dict, output: Path) -> None:
    cards = []
    for row in rows:
        sound = (f'<audio controls preload="none" src="{html.escape(row["audio"]["path"], quote=True)}"></audio>'
                 f'<p>{html.escape(row["audio"]["description"])}</p>' if row.get("audio") else "")
        cards.append(f'''<article id="{row['id']}" data-role="{row['expectedPurposeRole']}">
          <img src="{row['image']}" alt="{html.escape(row['destination'] + ' ' + row['purposeLabel'])}">
          <b>{html.escape(row['destination'])} · {html.escape(row['purposeLabel'])}</b>
          <p>{html.escape(row['id'])} / {html.escape(str(row['structure']['bodyFamily']))}
          / {html.escape(str(row['structure']['outfit']))}</p>
          <a href="{row['metadata']}">실제 생성 metadata</a>{sound}</article>''')
    warning = ("200장의 실제 렌더 PNG. AI 생성·TTS 재생·미적 품질 승인과 구분됩니다. "
               "동일 seed를 사용해 목적 효과를 비교합니다. 표시 경로는 합성 QA 변형입니다.")
    output.joinpath("index.html").write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8">
      <meta name="viewport" content="width=device-width"><title>Nunti V6 200-case audit</title>
      <style>body{{margin:32px;background:#f6f3ed;color:#332c3e;font:16px system-ui}}
      h1{{font-size:28px}}header{{max-width:1000px}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
      article{{background:white;border-radius:20px;padding:16px}}img{{width:100%;aspect-ratio:1}}p{{font-size:12px;color:#766b82}}
      button{{margin:4px;padding:9px 14px;border:1px solid #d5cddd;background:white;border-radius:20px;cursor:pointer}}
      a{{font-size:12px;color:#554277}}audio{{display:block;width:100%;margin-top:12px}}[hidden]{{display:none}}</style><header>
      <h1>눈티 · 200개 여정 디자인 검증</h1><p>{warning}</p>
      <p>상태: {report['status']} · 실제 이미지 {len(rows)} · 구조 {report['counts']['distinctStructuralDesigns']}
      · 근접 중복 후보 {report['counts']['nearDuplicatePairs']}쌍 · <a href="report.json">전체 보고서</a></p>
      <nav><button onclick="show('')">전체 200</button>{''.join(f'<button onclick="show(\'{role}\')">{label}</button>' for role, _, label in PURPOSES)}</nav></header>
      <main>{''.join(cards)}</main><script>function show(role){{for(const e of document.querySelectorAll('article'))e.hidden=!!role&&e.dataset.role!==role}}</script></html>''', encoding="utf-8")


def attach_voice_results(output: Path, voice_results: Path) -> dict:
    """Bind real checked WAVs to gallery cards; never synthesize or autoplay."""
    from nunti.avatar_studio.voice_design import build_voice_design, validate_voice_plan
    from nunti.avatar_studio.voice_render import inspect_wav

    report = json.loads((output / "report.json").read_text())
    inputs = {case["id"]: case for case in json.loads((output / "voice-input.json").read_text())["cases"]}
    result_bytes = voice_results.read_bytes()
    results = json.loads(result_bytes)
    by_id = {case["id"]: case for case in results}
    expected_roles = {"BUSINESS": "professional", "SWIM": "swimmer", "HIKING": "explorer",
                      "DATE": "celebration", "PLAY": "playful", "ART": "artist",
                      "CAFE": "foodie", "NIGHT": "restful", "CELEBRATE": "celebration",
                      "REST": "restful"}
    failures, attached = [], []
    for row in report["cases"]:
        row.pop("audio", None)
        result = by_id.get(row["id"])
        if not result or not result.get("audio"):
            continue
        try:
            if hashlib.sha256((output / row["image"]).read_bytes()).hexdigest() != row["imageSha256"]:
                raise ValueError("actual PNG differs from the rendered case record")
            plan, audio = result["voicePlan"], result["audio"]
            validate_voice_plan(plan)
            expected = build_voice_design(inputs[row["id"]]["input"], inputs[row["id"]]["design"])
            if plan != expected or audio["profileId"] != plan["profileId"]:
                raise ValueError("voice plan does not belong to this image/input")
            if plan["role"] != expected_roles[row["expectedPurposeRole"]]:
                raise ValueError("voice role does not match avatar activity")
            if audio["text"] != plan["greeting"]:
                raise ValueError("audio greeting text differs from stored voice plan")
            path = Path(audio["audioPath"])
            actual = inspect_wav(path)
            if actual["audioSha256"] != audio["audioSha256"]:
                raise ValueError("actual WAV hash differs from synthesis record")
            if actual["fullScaleSamples"]:
                raise ValueError("audio contains full-scale clipping")
            if audio.get("automaticPlayback") or plan.get("automaticPlayback"):
                raise ValueError("explicit playback contract violated")
            row["audio"] = {"path": os.path.relpath(path, output),
                            "profileId": plan["profileId"], "role": plan["role"],
                            "description": plan["description"], "greeting": plan["greeting"],
                            **actual}
            attached.append(row["id"])
        except (ValueError, KeyError, OSError) as exc:
            failures.append({"id": row["id"], "error": str(exc)})
    source_changed = hashlib.sha256(voice_results.read_bytes()).hexdigest() != hashlib.sha256(result_bytes).hexdigest()
    if source_changed:
        failures.append({"id": "RESULTS", "error": "voice results changed during binding; rerun after synthesis completes"})
    binding = {
        "status": "FAIL" if failures else "PASS" if len(attached) == 200 else "PARTIAL",
        "expected": len(report["cases"]), "actualWavsBoundToImages": len(attached),
        "source": str(voice_results.resolve()), "failures": failures,
        "sourceSha256": hashlib.sha256(result_bytes).hexdigest(),
        "sourceChangedDuringVerification": source_changed,
        "uniqueVerifiedWavHashes": len({row["audio"]["audioSha256"] for row in report["cases"] if row.get("audio")}),
        "automaticPlayback": False, "audioSynthesisPerformedByThisCommand": False,
        "perceptuallyUniqueSpeakersVerified": False, "humanListeningVerified": False,
    }
    report["voiceBindingVerification"] = binding
    write_json(output / "report.json", report)
    write_json(output / "voice-binding-verification.json", binding)
    write_gallery(report["cases"], report, output)
    return binding


def repeat_control(manifest: dict, output: Path) -> dict:
    """Ten new journeys with identical semantic input, plus an exact retry."""
    from nunti.avatar_studio.illustration import render_avatar

    case = next((case for case in manifest["cases"] if case["id"] == "03-swim"),
                manifest["cases"][0])
    points = manifest["routes"][case["routeId"]]["points"]
    output = output / "repeat-control"
    (output / "images").mkdir(parents=True, exist_ok=True)
    rows, features = [], []
    first_result = None
    for index in range(10):
        seed = f"nunti-v6-repeat-new-journey-{index:02d}"
        png, design = render_avatar(points, case["destination"]["name"],
                                    case["destination"]["traits"], case["purpose"], seed)
        if first_result is None:
            first_result = (png, design)
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        case_id = f"repeat-{index + 1:02d}"
        relative = f"images/{case_id}.png"
        (output / relative).write_bytes(png)
        write_json(output / f"metadata/{case_id}.json", design)
        structure = structural_fields(design.get("characterPlan", {}))
        rows.append({"id": case_id, "destination": case["destination"]["name"],
                     "purposeLabel": f"같은 수영 여정 · 새 생성 {index + 1}",
                     "image": relative, "failures": [], "structure": structure,
                     "pixelSha256": hashlib.sha256(image.tobytes()).hexdigest(),
                     "structureSha256": digest(structure)})
        features.append(pixel_features(image))
    retry = render_avatar(points, case["destination"]["name"],
                          case["destination"]["traits"], case["purpose"],
                          "nunti-v6-repeat-new-journey-00")
    duplicates = []
    for a in range(10):
        for b in range(a + 1, 10):
            metrics = similarity(features[a], features[b])
            if is_near_duplicate(metrics):
                duplicates.append({"a": rows[a]["id"], "b": rows[b]["id"], **metrics})
    exact_count = len({row["pixelSha256"] for row in rows})
    structure_count = len({row["structureSha256"] for row in rows})
    report = {
        "case": case["id"], "destination": case["destination"], "purpose": case["purpose"],
        "count": 10, "allInputsIdenticalExceptJourneySeed": True,
        "retryReturnsIdenticalPngAndMetadata": retry == first_result,
        "distinctExactImages": exact_count, "distinctStructuralDesigns": structure_count,
        "newJourneyChangesStructure": structure_count > 1,
        "allTenStructuresDifferent": structure_count == 10,
        "nearDuplicatePairs": duplicates,
        "status": ("STRUCTURAL_VARIATION" if structure_count > 1 and exact_count == 10
                   else "NO_STRUCTURAL_VARIATION"),
        "cases": rows,
        "contactSheets": contact_sheets(rows, output),
    }
    write_json(output / "report.json", report)
    return report


def audit(manifest: dict, output: Path, limit: int | None = None) -> dict:
    source_paths = [Path(__file__), MANIFEST,
                    ROOT / "backend/nunti/avatar_studio/design_intent.py",
                    ROOT / "backend/nunti/avatar_studio/illustration.py",
                    ROOT / "backend/nunti/avatar_studio/journey_language.py",
                    ROOT / "backend/nunti/avatar_studio/journey_art.py"]
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in source_paths if path.exists()}
    from nunti.avatar_studio.illustration import render_avatar

    output.mkdir(parents=True, exist_ok=True)
    rows, features, voice_inputs = [], [], []
    started = time.monotonic()
    cases = manifest["cases"][:limit] if limit else manifest["cases"]
    for index, case in enumerate(cases):
        route = manifest["routes"][case["routeId"]]
        png, metadata = render_avatar(route["points"], case["destination"]["name"],
                                     case["destination"]["traits"], case["purpose"], case["renderSeed"])
        plan = metadata.get("characterPlan", {})
        fields = structural_fields(plan)
        failures = []
        for key in ("bodyFamily", "outfit", "pose", "action", "prop", "expression"):
            if not fields[key]:
                failures.append(f"missing-structural-field:{key}")
        if plan.get("purpose", {}).get("role") != case["expectedPurposeRole"]:
            failures.append("purpose-role-mismatch")
        if not plan.get("destination", {}).get("evidence"):
            failures.append("missing-destination-evidence")
        if plan.get("destination", {}).get("kind") not in accepted_destination_kinds(case):
            failures.append("destination-kind-mismatch")
        if not plan.get("renderParts"):
            failures.append("missing-render-parts")
        if not plan.get("motionTheme") or not plan.get("voiceRole"):
            failures.append("missing-motion-or-voice-role")
        if metadata.get("visualIntent", {}).get("surfaceRouteMarking") != "NONE":
            failures.append("route-painted-on-body")
        image_path, metadata_path = f"images/{case['id']}.png", f"metadata/{case['id']}.json"
        (output / image_path).parent.mkdir(parents=True, exist_ok=True)
        (output / image_path).write_bytes(png)
        write_json(output / metadata_path, metadata)
        image = Image.open(io.BytesIO(png))
        if image.mode != "RGBA" or image.size != (768, 768):
            failures.append("invalid-image-contract")
        pixel = pixel_features(image)
        if pixel["opaqueFraction"] < 0.06:
            failures.append("nearly-empty-character")
        features.append(pixel)
        rows.append({
            "id": case["id"], "destination": case["destination"]["name"],
            "purposeLabel": case["purposeLabel"], "expectedPurposeRole": case["expectedPurposeRole"],
            "actualPurposeRole": plan.get("purpose", {}).get("role"),
            "actualDestinationKind": plan.get("destination", {}).get("kind"),
            "acceptedDestinationKinds": accepted_destination_kinds(case),
            "routeId": case["routeId"], "image": image_path, "metadata": metadata_path,
            "imageSha256": hashlib.sha256(png).hexdigest(),
            "pixelSha256": hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest(),
            "structure": fields, "structureSha256": digest(fields),
            "pHash": f"{pixel['phash']:016x}", "failures": failures,
            "mediaOrigin": metadata.get("mediaOrigin"),
            "motionTheme": plan.get("motionTheme"), "voiceRole": plan.get("voiceRole"),
        })
        voice_inputs.append({"id": case["id"], "input": {
            "requestId": case["requestId"], "destination": case["destination"],
            "purpose": case["purpose"], "route": {key: route[key] for key in
                ("points", "inputOrigin", "sourceLabel", "confirmed")}, "renderMode": "LOCAL_RENDER",
        }, "design": metadata})
        if (index + 1) % 10 == 0:
            print(f"Rendered {index + 1}/{len(cases)}", flush=True)
    groups, core_groups, family_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rows:
        groups[row["structureSha256"]].append(row["id"])
        core = tuple(row["structure"][key] for key in ("bodyFamily", "outfit", "outfitCut", "prop"))
        core_groups[core].append(row["id"])
        family_groups[core[:2]].append(row["id"])
    collisions = [ids for ids in groups.values() if len(ids) > 1]
    near_duplicates = []
    closest = []
    for a in range(len(rows)):
        nearest = None
        for b in range(a + 1, len(rows)):
            metrics = similarity(features[a], features[b])
            pair = {"a": rows[a]["id"], "b": rows[b]["id"], **metrics}
            if is_near_duplicate(metrics):
                near_duplicates.append(pair)
            score = metrics["pHashDistance"] + metrics["meanRgbDifference"] + (1 - metrics["opaqueSilhouetteIoU"]) * 100
            if nearest is None or score < nearest[0]:
                nearest = (score, pair)
        if nearest:
            closest.append(nearest)
    counts = {
        "requestedCases": len(manifest["cases"]), "renderedImages": len(rows),
        "distinctExactImages": len({row["pixelSha256"] for row in rows}),
        "distinctStructuralDesigns": len(groups), "structuralCollisionGroups": len(collisions),
        "distinctBodyWardrobePropCombinations": len(core_groups),
        "distinctBodyWardrobeFamilies": len(family_groups),
        "nearDuplicatePairs": len(near_duplicates),
        "casesWithContractFailure": sum(bool(row["failures"]) for row in rows),
        "actualAiImages": sum(row["mediaOrigin"] == "LOCAL_MODEL" for row in rows),
        "actualAudioClips": 0, "networkCalls": 0, "paidApiCalls": 0,
    }
    changed_sources = [name for name, before in source_hashes.items()
                       if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != before]
    all_rendered = len(rows) == 200 and len(rows) == len(manifest["cases"])
    technical_pass = (all_rendered and not counts["casesWithContractFailure"]
                      and counts["distinctExactImages"] == len(rows) and not changed_sources)
    distinct_pass = technical_pass and not collisions and not near_duplicates
    report = {
        "schemaVersion": "nunti-v6-matrix-result-1",
        "createdAt": datetime.now(UTC).isoformat(),
        "status": ("AUTOMATED_DIVERSITY_PASS_VISUAL_REVIEW_REQUIRED" if distinct_pass else
                   "NEEDS_DIVERSITY_REVIEW" if technical_pass else "FAIL"),
        "technicalRenderPass": technical_pass,
        "automatedStructuralAndSimilarityPass": distinct_pass,
        "humanVisualReview": "NOT_YET_RECORDED",
        "claim": "실제 절차형 PNG 렌더 검증. AI 200회·TTS 200회·200개 미적 품질 승인을 뜻하지 않음.",
        "counts": counts,
        "rules": {
            "allCasesUseSameFineSeed": len({case["renderSeed"] for case in cases}) == 1,
            "structuralFields": list(structural_fields({})),
            "ignoredForStructuralUniqueness": ["seed", "hash", "palette", "labels", "numeric micro-variation"],
            "nearDuplicateThresholds": {"pHashDistanceMax": 6, "opaqueSilhouetteIoUMin": 0.985, "meanRgbDifferenceMaxExclusive": 12},
            "perceptualMethodLimit": "이미지 근접도는 검토 후보 탐지이며 품질·의상 가독성의 자동 판정이 아님",
        },
        "durationSeconds": round(time.monotonic() - started, 2),
        "sourceSha256": source_hashes,
        "canonicalManifestSha256": digest(manifest),
        "sourceChangedDuringRender": changed_sources,
        "bodyFamilyCounts": dict(Counter(row["structure"]["bodyFamily"] for row in rows)),
        "motionThemeCounts": dict(Counter(row["motionTheme"] for row in rows)),
        "voiceRoleCounts": dict(Counter(row["voiceRole"] for row in rows)),
        "structuralCollisions": collisions,
        "bodyWardrobePropCollisions": [ids for ids in core_groups.values() if len(ids) > 1],
        "compositionDisclosure": "12종 동물형 몸과 목적별 의상·소품·자세를 조합한다. 구조 200종은 200종의 독립 원화 기본형이라는 뜻이 아니다.",
        "nearDuplicatePairs": near_duplicates,
        "closestPairsForReview": [pair for _, pair in sorted(closest, key=lambda v: v[0])[:30]],
        "cases": rows,
    }
    report["contactSheets"] = contact_sheets(rows, output)
    # This separate set never inflates the 200-case render/design counts.
    if not limit:
        report["sameInputNewJourneys"] = repeat_control(manifest, output)
    report["durationSeconds"] = round(time.monotonic() - started, 2)
    write_json(output / "report.json", report)
    write_json(output / "voice-input.json", {"cases": voice_inputs})
    write_gallery(rows, report, output)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true", help="Rebuild committed 200-case fixture from 3 cached road paths")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--limit", type=int, help="Smoke-test only; never a 200-case PASS")
    parser.add_argument("--attach-voices", type=Path, help="Check existing real WAV results and add explicit-play controls to gallery")
    args = parser.parse_args()
    if args.attach_voices:
        binding = attach_voice_results(args.output, args.attach_voices)
        print(json.dumps(binding, ensure_ascii=False))
        return 0 if binding["status"] == "PASS" else 1
    if args.write_manifest:
        write_json(args.manifest, make_manifest())
        print(f"Wrote {args.manifest}")
        return 0
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = audit(manifest, args.output, args.limit)
    print(json.dumps({"status": report["status"], "counts": report["counts"],
                      "report": str(args.output / "report.json"),
                      "gallery": str(args.output / "index.html")}, ensure_ascii=False))
    return 0 if report["automatedStructuralAndSimilarityPass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
