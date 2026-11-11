#!/usr/bin/env python3
"""Audit the exported Figma foundation colors without network access or Figma edits.

Writes a deterministic JSON contrast report and a Korean token table. Text
decisions use unrounded WCAG sRGB ratios. Exit 1 means a required text/active
button check failed; subtle decorative borders are reported separately.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs/redesign/pleos-ui-v1"
SURFACES = ("background", "surface", "soft", "tint")
TEXT_ROLES = ("ink", "muted", "accent", "warm", "info")
MODES = {"Day": 0, "Night": 1}
SOURCES = {
    "text": "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html",
    "nonText": "https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html",
}


def foundation_from_tool_result(value: dict) -> dict:
    if isinstance(value.get("roles"), dict):
        return value
    structured = value.get("structuredContent")
    if isinstance(structured, dict) and isinstance(structured.get("roles"), dict):
        return structured
    for block in value.get("content", []):
        if block.get("type") != "text":
            continue
        try:
            candidate = json.loads(block["text"])
        except (KeyError, json.JSONDecodeError):
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("roles"), dict):
            return candidate
    raise ValueError("The input does not contain a Figma foundation roles snapshot")


def luminance(hex_color: str) -> float:
    if not isinstance(hex_color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", hex_color):
        raise ValueError(f"Expected an opaque six-digit sRGB color, got {hex_color!r}")
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(foreground: str, background: str) -> float:
    low, high = sorted((luminance(foreground), luminance(background)))
    return (high + 0.05) / (low + 0.05)


def path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def check_pair(roles: dict, mode: str, foreground: str, background: str,
               threshold: float, purpose: str) -> dict:
    index = MODES[mode]
    front, back = roles[foreground][index], roles[background][index]
    ratio = contrast(front, back)
    return {
        "mode": mode,
        "foregroundRole": foreground,
        "backgroundRole": background,
        "foreground": front,
        "background": back,
        "foregroundLuminance": luminance(front),
        "backgroundLuminance": luminance(back),
        "contrastRatio": ratio,
        "displayRatio": f"{ratio:.4f}:1",
        "threshold": threshold,
        "meetsThreshold": ratio >= threshold,
        "purpose": purpose,
    }


def audit(source: Path) -> tuple[dict, dict]:
    raw = source.read_bytes()
    foundation = foundation_from_tool_result(json.loads(raw))
    roles = foundation["roles"]
    for role in (*SURFACES, *TEXT_ROLES, "onAccent", "border"):
        values = roles.get(role)
        if not isinstance(values, list) or len(values) < 2:
            raise ValueError(f"Missing Day/Night values for {role}")
        for index in MODES.values():
            luminance(values[index])

    # Reference anchors also catch accidentally applying the wrong transfer curve.
    assert math.isclose(contrast("#000000", "#FFFFFF"), 21.0)
    assert math.isclose(contrast("#FFFFFF", "#FFFFFF"), 1.0)
    assert contrast("#767676", "#FFFFFF") >= 4.5
    assert contrast("#777777", "#FFFFFF") < 4.5

    text = [
        check_pair(roles, mode, front, back, 4.5, "body_or_label_text")
        for mode in MODES for front in TEXT_ROLES for back in SURFACES
    ]
    text += [
        check_pair(roles, mode, "onAccent", "accent", 4.5, "active_button_label")
        for mode in MODES
    ]
    active = [
        check_pair(roles, mode, "accent", back, 3.0, "active_fill_or_focus_indicator")
        for mode in MODES for back in SURFACES
    ]
    borders = [
        check_pair(roles, mode, "border", back, 3.0, "decorative_divider_only")
        for mode in MODES for back in SURFACES
    ]
    separation = [
        check_pair(roles, mode, front, back, 3.0, "surface_separation_not_a_sole_state_cue")
        for mode in MODES for front, back in itertools.combinations(SURFACES, 2)
    ]
    failures = [pair for pair in text + active if not pair["meetsThreshold"]]
    worst = min(text, key=lambda pair: pair["contrastRatio"])
    typography = foundation.get("typography", {})
    metrics = foundation.get("metrics", {})
    report = {
        "schemaVersion": "nunti.ui.token-contrast/1",
        "status": "PASS" if not failures else "FAIL",
        "source": path_label(source),
        "sourceSha256": hashlib.sha256(raw).hexdigest(),
        "sourceKind": "FIGMA_FOUNDATION_TOOL_RESPONSE_SNAPSHOT",
        "figmaPageId": foundation.get("pageId"),
        "method": {
            "colorSpace": "sRGB, opaque 8-bit hex",
            "linearizationThreshold": 0.04045,
            "luminanceWeights": [0.2126, 0.7152, 0.0722],
            "ratio": "(lighter relative luminance + 0.05) / (darker relative luminance + 0.05)",
            "textThreshold": 4.5,
            "activeNonTextThreshold": 3.0,
            "compareUnroundedRatios": True,
            "largeTextExemptionUsed": False,
            "networkRequests": 0,
        },
        "summary": {
            "textChecks": len(text),
            "textPassed": sum(pair["meetsThreshold"] for pair in text),
            "activeNonTextChecks": len(active),
            "activeNonTextPassed": sum(pair["meetsThreshold"] for pair in active),
            "requiredFailures": len(failures),
            "lowestTextPair": worst,
            "decorativeBorderChecks": len(borders),
            "bordersBelow3": sum(not pair["meetsThreshold"] for pair in borders),
        },
        "roles": roles,
        "textChecks": text,
        "activeNonTextChecks": active,
        "decorativeBorderChecks": borders,
        "surfaceSeparationChecks": separation,
        "requiredFailures": failures,
        "typography": {"fontFamily": foundation.get("font"), "styles": typography},
        "metrics": metrics,
        "limitations": [
            "Design tokens are proposals, not existing production Kotlin classes or API contracts.",
            "This audits the saved token snapshot, not a fresh Figma variable readback or each node binding.",
            "Opaque token colors only: rendered opacity, disabled states, gradients, images, and antialiasing need screen review.",
            "Border is decorative only. Do not use it for text, a sole control boundary, focus, or a required state indicator.",
            "Subtle surface changes cannot be the only selected/error/focus cue; use a sufficient-contrast icon, text, or accent outline.",
            "Figma units do not establish Android dp/sp sizes or official Pleos approval; verify actual display scale and runtime restrictions.",
        ],
        "sources": SOURCES,
    }
    return foundation, report


def token_table(foundation: dict, report: dict) -> str:
    summary = report["summary"]
    worst = summary["lowestTextPair"]
    lines = [
        "# Pleos UI 제안 토큰과 대비 검증",
        "",
        "이 표는 Figma foundation snapshot에서 자동 생성했다. 디자인 제안이며 현재 Kotlin token class나 API가 이미 존재한다는 뜻이 아니다. production 코드와 Figma 변수는 이 스크립트가 수정하지 않는다.",
        "",
        "## 색상",
        "",
        "| Semantic role | Day | Night | 기존 CSS 이름 또는 제안 연결 |",
        "|---|---|---|---|",
    ]
    for role, values in foundation["roles"].items():
        lines.append(f"| `{role}` | `{values[0]}` | `{values[1]}` | `{values[2] if len(values) > 2 else '미정'}` |")
    lines += [
        "",
        "## 실제 대비 결과",
        "",
        f"텍스트 {summary['textPassed']}/{summary['textChecks']}쌍은 일반 텍스트 기준 4.5:1, 활성 버튼·focus 후보 {summary['activeNonTextPassed']}/{summary['activeNonTextChecks']}쌍은 3:1을 통과했다. 전체 필수 검사 결과는 `{report['status']}`다.",
        f"최저 텍스트 조합은 {worst['mode']} `{worst['foregroundRole']}` on `{worst['backgroundRole']}`의 **{worst['contrastRatio']:.4f}:1**이다. 합격 판정에는 반올림 전 값을 사용한다.",
        "",
        "| 모드 | 텍스트 | surface | background | soft | tint |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for mode in MODES:
        for role in TEXT_ROLES:
            matches = {p["backgroundRole"]: p for p in report["textChecks"]
                       if p["mode"] == mode and p["foregroundRole"] == role}
            cells = [f"{matches[back]['contrastRatio']:.2f}" + (" 실패" if not matches[back]["meetsThreshold"] else "")
                     for back in ("surface", "background", "soft", "tint")]
            lines.append(f"| {mode} | `{role}` | " + " | ".join(cells) + " |")
    for mode in MODES:
        button = next(p for p in report["textChecks"] if p["mode"] == mode and p["foregroundRole"] == "onAccent")
        lines += ["", f"{mode} 활성 버튼의 `onAccent` on `accent`는 {button['contrastRatio']:.4f}:1이다."]
    lines += [
        "",
        "`border`는 양 모드 모두 3:1에 미달하는 조합이 있으므로 장식용 구분선으로만 사용한다. 입력 컨트롤을 알아볼 유일한 테두리, focus, 선택 표시, 본문 글자로 쓰지 않는다. 필요한 상태 표시는 충분한 대비의 `accent`와 텍스트 또는 아이콘으로 표현한다. `soft/tint` 배경 차이만으로 선택이나 오류를 알리지 않는다.",
        "",
        f"일반 텍스트와 큰 글자의 기준은 [WCAG 2.2 대비 설명]({SOURCES['text']})을 확인했다. 이 검사는 큰 글자 예외를 적용하지 않고 모든 제안 텍스트에 4.5:1을 적용한다. 의미를 전달하는 컨트롤·focus와 장식 구분선의 차이는 [WCAG 비텍스트 대비 설명]({SOURCES['nonText']})을 따른다.",
        "",
        "## 타이포그래피",
        "",
        f"글꼴은 `{foundation.get('font', '미정')}`다. 아래 숫자는 Figma 설계 단위이며 Android의 실제 sp 렌더링과 글자 확대는 별도 확인한다.",
        "",
        "| Style | 크기 | 행 높이 | 굵기 | 행 높이/크기 |",
        "|---|---:|---:|---|---:|",
    ]
    for name, values in foundation.get("typography", {}).items():
        size, height, weight = values
        lines.append(f"| {name} | {size} | {height} | {weight} | {height / size:.2f} |")
    sizes = {name: values[0] for name, values in foundation.get("typography", {}).items()}
    prose = [size for name, size in sizes.items() if name != "Number"]
    if prose:
        lines += ["", f"일반 문구는 {min(prose)}~{max(prose)} 범위다. Caption도 {sizes.get('Caption', '미정')}로 유지한다."]
    if "Number" in sizes:
        lines += [f"`Number` {sizes['Number']}는 점수 등 짧은 숫자를 위한 별도 예외다. 본문 또는 긴 안내문에 사용하지 않는다."]
    metrics = foundation.get("metrics", {})
    spaces = [v for k, v in metrics.items() if k.startswith("space/")]
    lines += [
        "",
        "## 간격·모서리·컨트롤",
        "",
        "| Token | 값 |",
        "|---|---:|",
    ]
    lines += [f"| `{name}` | {value} |" for name, value in metrics.items()]
    lines += [
        "",
        "간격은 " + ", ".join(str(value) for value in spaces) + "이다. 12를 포함하는 4단위 배수 체계이며 모든 값을 8단위 격자라고 설명하지 않는다.",
        f"기본 버튼 높이 {metrics.get('control/height', '미정')}, compact 높이 {metrics.get('control/compact', '미정')}를 제안한다. 창이 좁다고 버튼이나 글자를 임의 축소하기보다 여백과 부가 정보 배치를 조정한다. 실제 hit area, 글자 확대, 다중 창과 공식 Pleos component 규격을 함께 검증해야 한다.",
        "",
        "## 재현",
        "",
        "```sh",
        "python3 scripts/verify_nunti_ui_tokens.py",
        "```",
        "",
        "입력은 `figma-state.json`, 결과는 `token-contrast.json`과 이 문서다. script는 네트워크나 이미지 생성 없이 저장된 HEX 색상의 sRGB 상대 휘도를 계산한다. 필수 텍스트·활성 버튼 검사 실패 시 결과 파일을 남기고 exit code 1을 반환한다.",
        "",
        f"검사 입력 SHA256: `{report['sourceSha256']}`.",
        "",
        "실제 노드의 variable binding, opacity, gradient, disabled 상태, 이미지 위 글자, 글꼴 가장자리와 차량 화면의 가독성은 이 숫자 검사에 포함되지 않는다. 최종 Figma screenshot과 emulator 비교가 필요하다.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_DIR / "figma-state.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "token-contrast.json")
    parser.add_argument("--table", type=Path, default=DEFAULT_DIR / "token-table.md")
    args = parser.parse_args()
    foundation, report = audit(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.table.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    args.table.write_text(token_table(foundation, report))
    print(json.dumps({"status": report["status"], "summary": report["summary"],
                      "report": path_label(args.output), "table": path_label(args.table)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
