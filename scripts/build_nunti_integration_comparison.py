#!/usr/bin/env python3
"""Compare actual before/after Pleos captures and approved Figma frames.

Only existing screenshot pixels are cropped and composed. This script never
operates the device or substitutes a browser fixture for an Android capture.
The capture map supplies observed app bounds; missing inputs fail atomically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "docs/redesign/pleos-ui-v1"
OUT = ROOT / "docs/redesign/integration-v1/comparison"
APP_BOX = (853, 90, 2535, 1300)
APP_SIZE = (1682, 1210)
STATES = (
    ("pre-trip", "PRE_TRIP", "production-pre-trip.png"),
    ("reveal-parked", "REVEAL_PARKED", "production-reveal-settled.png"),
    ("driving-restricted", "DRIVING_RESTRICTED", "production-driving-active.png"),
    ("post-trip", "POST_TRIP", "production-post-trip.png"),
)
MOODS = (("calm", "차분하게"), ("curious", "호기심 있게"), ("adventurous", "씩씩하게"))
DESTINATIONS = (("coast", "바다"), ("mountain", "산"), ("city", "도시"))


def relative(path):
    return str(path.resolve().relative_to(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_image(path):
    with Image.open(path) as source:
        source.load()
        rgba = source.convert("RGBA")
        if rgba.getchannel("A").getextrema() != (255, 255):
            raise ValueError(f"Complete opaque screenshot required: {path}")
        return rgba.convert("RGB")


def actual_record(path, key, state, role, bounds, metadata):
    image = read_image(path)
    box = tuple(bounds)
    if len(box) != 4 or any(not isinstance(x, int) for x in box):
        raise ValueError(f"Integer XYXY app bounds required: {key}")
    left, top, right, bottom = box
    if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
        raise ValueError(f"App bounds outside actual source: {key}, {image.size}, {box}")
    cropped = image.crop(box)
    # Never stretch an unexpected runtime viewport to look like the reference.
    if cropped.size != APP_SIZE:
        raise ValueError(f"Wide source must provide actual {APP_SIZE} app area; got {cropped.size}: {key}")
    record = {
        "id": key, "state": state, "role": role,
        "sourceKind": "ACTUAL_ANDROID_EMULATOR", "path": relative(path),
        "sha256": digest(path), "sourcePixels": list(image.size),
        "cropBoxXYXY": list(box), "cropPixels": list(cropped.size),
        "normalization": "LOSSLESS_PIXEL_CROP", "capture": metadata,
    }
    for field in ("statePath", "xmlPath", "carUxPath"):
        if metadata.get(field):
            evidence = ROOT / metadata[field]
            record[field + "Sha256"] = digest(evidence)
    return cropped, record


def load_inputs(capture_map):
    metadata = json.loads((DESIGN / "exports/frame-sources.json").read_text())
    images, records = {}, []
    captures = capture_map["captures"]
    for slug, state, old_name in STATES:
        capture = captures[slug]
        if capture.get("sourceKind") != "ACTUAL_ANDROID_EMULATOR":
            raise ValueError(f"Explicit actual Android provenance required: {slug}")
        if capture.get("displayMode") != "day":
            raise ValueError(f"The four-state primary board requires observed day mode: {slug}")
        if slug == "driving-restricted" and "visiblePlatformBlock" not in capture:
            raise ValueError("Record actual platform block visibility for driving")
        for role, path, bounds, source in (
            ("before", DESIGN / "baseline" / old_name, APP_BOX,
             {"displayMode": "day", "visiblePlatformBlock": slug == "driving-restricted",
              "package": "ai.nunti.avatar.demo", "serial": "emulator-5554"}),
            ("after", ROOT / capture["path"], capture["appBoundsXYXY"], capture),
        ):
            key = f"{slug}-{role}"
            images[key], record = actual_record(path, key, state, role.upper(), bounds, source)
            records.append(record)
        path = DESIGN / "exports" / f"{slug}-day.png"
        image = read_image(path)
        if image.size != APP_SIZE:
            raise ValueError(f"Exact 1x Figma export required: {path}, {image.size}")
        key = f"{slug}-figma"
        images[key] = image
        records.append({
            "id": key, "state": state, "role": "DESIGN_REFERENCE",
            "sourceKind": "FIGMA_APPROVED_DESIGN", "path": relative(path),
            "sha256": digest(path), "sourcePixels": list(image.size),
            "normalization": "UNCHANGED_PIXELS", "figmaFileKey": metadata["fileKey"],
            "frame": metadata["frames"][path.name],
            "drivingRuntimeVisibilityApproved": False if slug == "driving-restricted" else None,
        })
    return images, records


def board(images, capture_map, font_path, figma):
    margin, gap, width, height = 40, 32, 841, 605
    top, row_height, label_height = 144, 744, 80
    image = Image.new("RGB", (2 * margin + 2 * width + gap, top + 4 * row_height + 24), "#F4F3EE")
    draw = ImageDraw.Draw(image)

    def text(x, y, content, size=24, color="#253E3E"):
        font = ImageFont.truetype(str(font_path), size)
        try:
            font.set_variation_by_axes([700 if size >= 30 else 500])
        except OSError:
            pass  # A caller may provide an installed static font instead.
        draw.text((x, y), content, font=font, fill=color)

    title = "눈티 · Figma와 실제 앱 비교" if figma else "눈티 · 실제 앱 이전과 이후"
    text(margin, 20, title, 38)
    text(margin, 78, "동일한 1682 × 1210 앱 영역 · 원본 픽셀 자르기 · 보드에서만 50% 축소", 24)
    for index, (slug, state, _) in enumerate(STATES):
        y = top + index * row_height
        text(margin, y, f"0{index + 1}  {state}", 26)
        for column in range(2):
            x = margin + column * (width + gap)
            role = "after" if column else "figma" if figma else "before"
            blocked = slug == "driving-restricted" and role != "figma" and (
                role == "before" or capture_map["captures"][slug]["visiblePlatformBlock"])
            header = "승인 Figma" if role == "figma" else "이전 실제 앱" if role == "before" else "이후 실제 앱"
            note = "실제 시스템 차단 화면 · 숨겨진 앱 화면을 합성하지 않음" if blocked else (
                "주행 표시 허용은 검증되지 않은 디자인 제안" if slug == "driving-restricted" and role == "figma"
                else "원본 캡처의 정보·캐릭터 차이는 그대로 보존")
            fill = "#803E36" if blocked else "#925238" if role == "figma" else "#355C4B"
            draw.rectangle((x, y + 44, x + width - 1, y + 44 + label_height - 1), fill=fill)
            text(x + 16, y + 47, header, 26, "white")
            text(x + 16, y + 84, note, 18, "white")
            thumbnail = images[f"{slug}-{role}"].resize((width, height), Image.Resampling.LANCZOS)
            image.paste(thumbnail, (x, y + 44 + label_height))
    return image


def character_matrix(map_path, output, font_path):
    """Compose approved base + actual endpoint captures; verify their provenance."""
    mapping = json.loads(map_path.read_text())
    images, records = {}, []
    base_path = ROOT / mapping["approvedBase"]
    with Image.open(base_path) as image:
        images["base"] = image.convert("RGBA")
    if images["base"].size != (768, 768):
        raise ValueError("Approved base must retain its original 768px canvas")
    records.append({"id": "base", "sourceKind": "APPROVED_BUNDLED_ASSET",
                    "path": relative(base_path), "sha256": digest(base_path)})
    for mood, _ in MOODS:
        for destination, _ in DESTINATIONS:
            slug = f"{destination}-{mood}"
            entry = mapping["captures"][slug]
            artifact_path = ROOT / entry["artifactsPath"]
            entries = json.loads(artifact_path.read_text())
            artifact = next(item["artifact"] for item in entries if item["slug"] == slug)
            spec = artifact["design"]["avatarSpec"]
            if artifact["mediaOrigin"] != "LOCAL_LAYERS" or artifact["design"]["renderStatus"] != "COMPOSITED":
                raise ValueError(f"Actual local compositor artifact required: {slug}")
            if spec["destinationMotif"] != destination or spec["expression"] != mood:
                raise ValueError(f"Artifact input does not match matrix position: {slug}")
            path, reference = ROOT / entry["path"], ROOT / entry["browserReferencePath"]
            with Image.open(path) as image:
                actual = image.convert("RGBA")
            with Image.open(reference) as image:
                expected = image.convert("RGBA")
            if actual.size != (768, 768) or actual.size != expected.size or actual.tobytes() != expected.tobytes():
                raise ValueError(f"Endpoint differs from the same browser's decoded final asset: {slug}")
            if entry.get("endpointReportPath"):
                evidence_path = ROOT / entry["endpointReportPath"]
                report = json.loads(evidence_path.read_text())
                check = next(item for item in report["checks"] if item["name"] == slug)
                if report["status"] != "PASS" or check["status"] != "PASS" or not check["browserDecodedPixelsExact"] or check["serverImageSha256"] != artifact["visual"]["sha256"]:
                    raise ValueError(f"Final production endpoint report does not match artifact: {slug}")
                evidence = {"endpointReportPath": relative(evidence_path),
                            "endpointReportSha256": digest(evidence_path), "endpointCheck": slug,
                            "captureScript": entry["captureScript"],
                            "captureScriptSha256": digest(ROOT / entry["captureScript"])}
            else:
                evidence_path = ROOT / entry["statePath"]
                state = json.loads(evidence_path.read_text())
                if state["artifact"] != artifact["characterId"] or state["motion"]["elapsedMs"] != 4000:
                    raise ValueError(f"Actual capture state does not identify the final artifact: {slug}")
                evidence = {"statePath": relative(evidence_path), "stateSha256": digest(evidence_path)}
            images[slug] = actual
            records.append({"id": slug, "sourceKind": "ACTUAL_PRODUCTION_WEBVIEW_CANVAS",
                            "path": relative(path), "sha256": digest(path), "pixels": list(actual.size),
                            "rgbaPixelsSha256": hashlib.sha256(actual.tobytes()).hexdigest(),
                            "browserReferencePath": relative(reference), "browserReferenceSha256": digest(reference),
                            "browserDecodedFinalPixelsExact": True,
                            **evidence,
                            "artifactsPath": relative(artifact_path), "artifactsSha256": digest(artifact_path),
                            "characterId": artifact["characterId"], "visualSha256": artifact["visual"]["sha256"],
                            "variantId": spec["variantId"], "assetVersion": spec["assetVersion"],
                            "destinationMotif": destination, "expression": mood, "roadMotif": spec["roadMotif"],
                            "inputProvenance": spec["provenance"]})
    # The only compositing is a common board background and proportionate scale.
    # Original source PNGs, alpha, silhouettes and colors are never overwritten.
    result = Image.new("RGB", (1856, 2312), "#F4F3EE")
    draw = ImageDraw.Draw(result)

    def text(x, y, value, size=26, color="#253E3E", weight=500):
        font = ImageFont.truetype(str(font_path), size)
        try:
            font.set_variation_by_axes([weight])
        except OSError:
            pass
        draw.text((x, y), value, font=font, fill=color)

    def picture(image, box):
        size = box[2]
        tile = image.resize((size, size), Image.Resampling.LANCZOS)
        result.paste(tile, (box[0], box[1]), tile.getchannel("A"))

    picture(images["base"], (40, 48, 320))
    text(408, 64, "눈티 A · 실제 앱의 9가지 모습", 46, weight=700)
    text(408, 146, "승인 기본형에서 같은 몸과 얼굴을 이어가요.", 32)
    text(408, 208, "바다 · 산 · 도시 × 직접 고른 세 가지 기분", 30)
    text(408, 266, "아래 9개는 실제 앱이 그린 변신 완료 모습입니다.", 26, "#56675E")
    text(408, 310, "합성 시험 경로 사용 · 이미지 생성 API 호출 없음", 26, "#56675E")
    text(92, 368, "승인 기본 눈티 A", 26)
    for row, (mood, mood_label) in enumerate(MOODS):
        for column, (destination, destination_label) in enumerate(DESTINATIONS):
            x, y = 32 + column * 608, 440 + row * 608
            draw.rounded_rectangle((x, y, x + 576, y + 584), radius=28, fill="#FFFEF9", outline="#CCD6C9", width=1)
            picture(images[f"{destination}-{mood}"], (x + 32, y + 8, 512))
            text(x + 32, y + 528, f"{destination_label} · {mood_label}", 30)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "character-runtime-matrix.png"
    result.save(path)
    manifest = {"schemaVersion": 1, "sourceImagesModified": False,
                "sourceMap": {"path": relative(map_path), "sha256": digest(map_path)},
                "baseIsRuntimeCapture": False, "variantCount": 9,
                "allVariantEndpointsMatchBrowserDecodedFinal": True,
                "boardBackground": "#F4F3EE", "tileBackground": "#FFFEF9", "resampling": "LANCZOS",
                "baseDisplayPixels": [320, 320], "variantDisplayPixels": [512, 512],
                "inputs": records, "output": {"path": relative(path), "pixels": list(result.size), "sha256": digest(path)}}
    (output / "character-runtime-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-map", type=Path, default=OUT / "capture-map.json")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--font", type=Path, default=ROOT / "prototypes/avatar_generator/assets/fonts/noto-sans-kr.ttf")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--characters-map", type=Path)
    parser.add_argument("--characters-only", action="store_true")
    args = parser.parse_args()
    if args.characters_only:
        if not args.characters_map:
            parser.error("--characters-only requires --characters-map")
        result = character_matrix(args.characters_map, args.output, args.font)
        print(json.dumps({"status": "WRITTEN", "actualVariantCaptures": result["variantCount"]}))
        return 0
    capture_map = json.loads(args.capture_map.read_text())
    # Read and validate all inputs before producing any output.
    images, records = load_inputs(capture_map)
    if args.check_only:
        print(json.dumps({"status": "SOURCE_FILES_VALID", "sources": len(records),
                          "acceptedForFinalComparison": capture_map.get("acceptedForFinalComparison") is True}))
        return 0
    if capture_map.get("acceptedForFinalComparison") is not True:
        raise ValueError("Inspect actual captures and mark acceptedForFinalComparison before creating final boards")
    args.output.mkdir(parents=True, exist_ok=True)
    normalized = args.output / "app-crops"
    normalized.mkdir(exist_ok=True)
    outputs = []
    for key, image in images.items():
        path = normalized / f"{key}.png"
        image.save(path)
        outputs.append({"path": relative(path), "pixels": list(image.size), "sha256": digest(path), "sourceId": key})
    for filename, figma in (("before-after-actual-day.png", False), ("figma-vs-actual-day.png", True)):
        path = args.output / filename
        image = board(images, capture_map, args.font, figma)
        image.save(path)
        outputs.append({"path": relative(path), "pixels": list(image.size), "sha256": digest(path)})
    characters = ROOT / "docs/redesign/route-variants-v1/comparison-board.png"
    manifest = {
        "schemaVersion": 1, "purpose": "ACTUAL_IMPLEMENTATION_SCREENSHOT_REVIEW",
        "script": {"path": relative(Path(__file__)), "sha256": digest(Path(__file__))},
        "captureMap": {"path": relative(args.capture_map), "sha256": digest(args.capture_map)},
        "pillowVersion": PILLOW_VERSION, "font": {"path": relative(args.font), "sha256": digest(args.font)},
        "appPixels": list(APP_SIZE), "boardScale": 0.5, "boardResampling": "LANCZOS",
        "sourceImagesModified": False, "syntheticCurrentScreens": False,
        "characterBoard": {"path": relative(characters), "sha256": digest(characters), "reusedApprovedArtifact": True},
        "limits": [
            "Historical before artwork and runtime trip values differ; no content was substituted.",
            "Driving Figma is a conditional proposal. Actual platform blocking remains visible in evidence.",
            "Pixel equality is not claimed for dynamic text, routes, scores or content-dependent wrapping.",
            "App crop excludes the real platform chrome without modifying its source screenshot.",
        ],
        "inputs": records, "outputs": outputs,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    if args.characters_map:
        character_matrix(args.characters_map, args.output, args.font)
    print(json.dumps({"status": "WRITTEN", "sources": len(records), "outputs": len(outputs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
