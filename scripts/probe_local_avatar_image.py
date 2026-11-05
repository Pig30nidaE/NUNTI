#!/usr/bin/env python3
"""Reproduce one isolated, offline FLUX.2 Klein MLX image probe. No API or login path."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".local/avatar-quality-v4/local-image"
STYLE = ROOT / "docs/design/avatar-quality-v4/assets/concept-a-v2.png"
PROMPT_BASE = (
    "A single full-body mascot alone, centered with empty margin on plain warm off-white. "
    "Make a travel companion in opaque pastel matte 2.5D illustration. "
    "Reference image 1 supplies material, gentle facial expression and shallow pastel shading only. "
    "Do not copy its anatomy. Reference image 2 alone controls the character's large body structure: "
    "follow its gray silhouette, rounded extremities and continuous body-flow curve. "
    "{meaning} "
    "Use large gentle dark eyes, a tiny mouth, softly integrated little feet and a lovable relaxed "
    "expression. Keep one clear distinctive silhouette, opaque color planes and only a few soft "
    "shadows. Favor a hand-drawn flat illustration over a dimensional toy render. "
    "Keep the entire result devoted to this one mascot. The references guide the design and are "
    "not separate objects to reproduce. Leave the surrounding background completely empty. "
    "No glass, refraction, gloss, transparent body, deep volumetric lighting, scenery, panels, "
    "diagrams, labels, symbols, lettering, watermark or extra objects."
)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def private_environment():
    # Do not read/copy API or Hub credentials, nor the user's shared HF cache.
    allowed = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")
    values = {key: os.environ[key] for key in allowed if key in os.environ}
    values.update(
        HF_HOME=str(WORK / "hf-home"),
        HF_HUB_CACHE=str(WORK / "hf-home/hub"),
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        MPLCONFIGDIR=str(WORK / "matplotlib-cache"),
        PYTHONUNBUFFERED="1",
    )
    return values


def prepare(style, case):
    from PIL import Image, ImageDraw

    sys.path.insert(0, str(ROOT / "backend"))
    from nunti.avatar_studio.illustration import render_avatar

    value = {
        "requestId": "8849a3a7-47f9-4ba8-a6c4-2f8f6f730002",
        "destination": {"name": "작은 해변", "traits": "잔잔한 해변과 겹치는 파도"},
        "purpose": "가족과 휴식",
        "route": {
            "points": [
                [0.10, 0.82],
                [0.25, 0.64],
                [0.38, 0.30],
                [0.57, 0.48],
                [0.73, 0.25],
                [0.86, 0.15],
            ],
            "inputOrigin": "TEST_ROUTE",
            "sourceLabel": "합성 여정 시험선",
            "confirmed": True,
        },
    }
    if case == "garden":
        value.update(
            requestId="8849a3a7-47f9-4ba8-a6c4-2f8f6f730003",
            destination={"name": "작은 정원", "traits": "숲과 잎, 씨앗을 품은 정원"},
            purpose="정원 산책과 나들이",
        )
        value["route"]["points"] = [
            [0.85, 0.82],
            [0.72, 0.60],
            [0.79, 0.36],
            [0.51, 0.43],
            [0.30, 0.18],
            [0.12, 0.24],
        ]
        meaning = (
            "The destination is a forest garden and the purpose is a quiet walk. "
            "Make the body itself a plump seed embraced by two broad integrated leaf lobes, "
            "following the alternate route's flowing axis. Leaves must form the major anatomy, "
            "not a little hat. Use pale sage, butter cream and one warm peach accent."
        )
    else:
        meaning = (
            "The destination is a calm beach and the purpose is family rest. "
            "Let overlapping wave-shaped body masses, a rounded curling tail and low relaxed "
            "posture express this journey. These curves belong to the body itself, not a line "
            "painted on the belly. Use powder blue, pale mint and one restrained cream accent."
        )
    prompt = PROMPT_BASE.format(meaning=meaning)
    stem = case + "-no-inset"
    _, design = render_avatar(
        value["route"]["points"],
        value["destination"]["name"],
        value["destination"]["traits"],
        value["purpose"],
        value["requestId"],
    )
    (WORK / (stem + "-input.json")).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    (WORK / (stem + "-design.json")).write_text(
        json.dumps(design, ensure_ascii=False, indent=2) + "\n"
    )
    (WORK / (stem + "-prompt.txt")).write_text(prompt + "\n")
    with Image.open(style) as image:
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 250, 255))
        image = Image.alpha_composite(background, image).convert("RGB")
        image.thumbnail((512, 512), Image.Resampling.LANCZOS)
        image.save(WORK / (stem + "-style.png"))
    formation = design["formation"]
    canvas = Image.new("RGB", (512, 512), "#faf9f4")
    drawing = ImageDraw.Draw(canvas)
    points = [(round(x * 511), round(y * 511)) for x, y in formation["contour"]]
    drawing.polygon(points, fill="#c9d7d1", outline="#627970")
    drawing.line(
        [(round(x * 511), round(y * 511)) for x, y in formation["spine"]],
        fill="#5e9b9c",
        width=5,
    )
    canvas.save(WORK / (stem + "-structure.png"))
    return value, prompt, stem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("edit", "text"), default="edit")
    parser.add_argument("--case", choices=("coast", "garden"), default="coast")
    parser.add_argument("--style", type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    output = WORK / ("nunti-local-" + args.case + "-no-inset-" + args.mode + ".png")
    if output.exists():
        raise SystemExit("OUTPUT_EXISTS_CHOOSE_A_NEW_EXPERIMENT")
    manifest = json.loads((WORK / "model-manifest.json").read_text())
    if manifest["gated"] or manifest["private"] or manifest["bytes"] > 5_000_000_000:
        raise SystemExit("MODEL_ACCESS_OR_SIZE_NOT_ALLOWED")
    missing = [
        f["path"]
        for f in manifest["files"]
        if not (WORK / "model" / f["path"]).is_file()
        or (WORK / "model" / f["path"]).stat().st_size != f["size"]
    ]
    if missing:
        raise SystemExit("LOCAL_MODEL_INCOMPLETE: " + ", ".join(missing))
    style = args.style or (
        ROOT / "docs/design/avatar-quality-v4/assets/concept-c-v2.png"
        if args.case == "garden"
        else STYLE
    )
    value, prompt, stem = prepare(style.resolve(), args.case)
    if args.prepare_only:
        print(json.dumps({"status": "INPUTS_PREPARED", "paidCalls": 0}))
        return
    executable = (
        WORK
        / "venv/bin"
        / (
            "mflux-generate-flux2-edit"
            if args.mode == "edit"
            else "mflux-generate-flux2"
        )
    )
    seed = 7373 if args.case == "garden" else 4243
    command = [
        str(executable),
        "--model",
        str(WORK / "model"),
        "--base-model",
        "flux2-klein-4b",
        "--steps",
        "4",
        "--seed",
        str(seed),
        "--width",
        "512",
        "--height",
        "512",
        "--low-ram",
        "--metadata",
        "--prompt-file",
        str(WORK / (stem + "-prompt.txt")),
        "--output",
        str(output),
    ]
    if args.mode == "edit":
        command += [
            "--image-paths",
            str(WORK / (stem + "-style.png")),
            str(WORK / (stem + "-structure.png")),
        ]
    start = time.monotonic()
    result = {
        "mode": args.mode,
        "paidCalls": 0,
        "loginUsed": False,
        "offlineInference": True,
        "model": manifest["repo"],
        "revision": manifest["revision"],
        "quantizationBits": 4,
        "requestedSize": [512, 512],
        "steps": 4,
        "seed": seed,
        "case": args.case,
        "styleSource": str(style),
        "styleSha256": sha(style.read_bytes()),
        "input": value,
        "promptSha256": sha(prompt.encode()),
        "promptWords": len(prompt.split()),
        "command": command,
    }
    try:
        with (WORK / (stem + "-" + args.mode + "-inference.log")).open("w") as log:
            completed = subprocess.run(
                command,
                check=False,
                env=private_environment(),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=min(args.timeout, 600),
            )
        result["exitCode"] = completed.returncode
        result["status"] = (
            "GENERATED" if completed.returncode == 0 and output.is_file() else "FAILED"
        )
        if result["status"] == "GENERATED":
            from PIL import Image

            with Image.open(output) as image:
                result.update(
                    width=image.width, height=image.height, imageMode=image.mode
                )
            result.update(
                output=str(output),
                pngSha256=sha(output.read_bytes()),
                outputBytes=output.stat().st_size,
            )
    except subprocess.TimeoutExpired:
        result["status"] = "TIMEOUT_STOPPED"
    result["elapsedSeconds"] = round(time.monotonic() - start, 2)
    (WORK / (stem + "-" + args.mode + "-result.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("status", "mode", "elapsedSeconds", "paidCalls")
            }
        )
    )
    if result["status"] != "GENERATED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
