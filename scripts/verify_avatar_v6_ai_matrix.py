#!/usr/bin/env python3
"""Resumable, offline, real FLUX audit of a selected set of character plans.

The worker reuses one installed FLUX.2 Klein model across different prompts and
reference images. No extra model/package downloads, paid APIs or recordings.
This exercises the production prompt/reference/cutout stages, not fresh HTTP jobs.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
RUNTIME = ROOT / ".local/avatar-quality-v4/local-image"
INPUT = ROOT / ".local/avatar-v6/matrix/voice-input.json"
OUTPUT = ROOT / ".local/avatar-v6/ai-matrix-final"
SUBSET = ROOT / "docs/design/avatar-v6/ai-cases-30.json"
MODEL = "mlx-community/FLUX.2-Klein-4B-4bit"
REVISION = "1cebb9b45c21ece14a42615b16bf5fa4de9b56da"
SETTINGS = {"width": 512, "height": 512, "steps": 4, "guidance": 1.0,
            "scheduler": "flow_match_euler_discrete", "quantizationBits": 4,
            "smallTextEncoder": False, "smallDecoder": False,
            "cacheLimitBytes": 1_000_000_000, "keepTextEncoder": True,
            "keepTransformer": True}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def select_cases(cases, subset):
    selection = json.loads(Path(subset).read_text())
    identifiers = selection["caseIds"] if isinstance(selection, dict) else selection
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Subset contains duplicate case ids")
    by_id = {case["id"]: case for case in cases}
    unknown = sorted(set(identifiers) - set(by_id))
    if unknown:
        raise ValueError(f"Unknown subset cases: {unknown}")
    if isinstance(selection, dict) and selection.get("expectedCases", len(identifiers)) != len(identifiers):
        raise ValueError("Subset expectedCases differs from selected id count")
    return [by_id[case_id] for case_id in identifiers]


def prepare(source: Path, output: Path, style_edge: int | None = None, subset: Path = SUBSET):
    from types import SimpleNamespace

    from nunti.avatar_studio.local_model import (
        PROMPT_VERSION,
        STYLE,
        local_model_manifest,
        references_and_prompt,
    )

    config = SimpleNamespace(local_model_enabled=True,
                             local_model_binary=RUNTIME / "venv/bin/mflux-generate-flux2-edit",
                             local_model_weights=RUNTIME / "model")
    manifest = local_model_manifest(config)
    cases = select_cases(json.loads(source.read_text())["cases"], subset)
    paths = [Path(__file__), ROOT / "backend/nunti/avatar_studio/local_model.py",
             ROOT / "backend/nunti/avatar_studio/semantic_reference.py",
             ROOT / "backend/nunti/avatar_studio/matte_cutout.py",
             ROOT / "backend/nunti/avatar_studio/design_intent.py",
             ROOT / "backend/nunti/avatar_studio/journey_language.py",
             ROOT / "backend/nunti/avatar_studio/journey_art.py",
             ROOT / "backend/nunti/avatar_studio/illustration.py"]
    source_hashes = {str(path.relative_to(ROOT)): file_sha(path) for path in paths}
    jobs = []
    for case in cases:
        case_id = case["id"]
        if not case_id or any(c not in "0123456789abcdefghijklmnopqrstuvwxyz-" for c in case_id):
            raise ValueError("Case id must be a plain path component")
        folder = output / "cases" / case_id
        folder.mkdir(parents=True, exist_ok=True)
        value, design = case["input"], case["design"]
        prompt, references = references_and_prompt(value, design)
        if style_edge is not None:
            adjusted = []
            for name, data in references:
                if name == "style-reference.png":
                    with Image.open(io.BytesIO(data)) as style_image:
                        style_image.thumbnail((style_edge, style_edge), Image.Resampling.LANCZOS)
                        stream = io.BytesIO()
                        style_image.save(stream, "PNG")
                        data = stream.getvalue()
                adjusted.append((name, data))
            references = adjusted
        seed = int(sha(value["requestId"].encode())[:8], 16)
        identity = {"input": value, "design": design, "prompt": prompt,
                    "references": [{"name": name, "sha256": sha(data)} for name, data in references],
                    "model": MODEL, "revision": REVISION, "settings": SETTINGS, "seed": seed}
        fingerprint = sha(canonical(identity).encode())
        result_file = folder / "result.json"
        if result_file.exists():
            old = json.loads(result_file.read_text())
            if old["jobFingerprint"] != fingerprint:
                raise ValueError(f"{case_id}: prepared input changed; use a new --output directory")
        save_json(folder / "input.json", value)
        save_json(folder / "design.json", design)
        (folder / "prompt.txt").write_text(prompt)
        for name, data in references:
            (folder / name).write_bytes(data)
        jobs.append({"id": case_id, "folder": str(folder.resolve()),
                     "jobFingerprint": fingerprint, "seed": seed,
                     "destination": value["destination"]["name"], "purpose": value["purpose"],
                     "purposeRole": design["characterPlan"]["purpose"]["role"],
                     "promptSha256": sha(prompt.encode()), "referenceImages": identity["references"],
                     "sourceSha256": source_hashes})
    prepared = {
        "version": "nunti-v6-ai-matrix-1", "createdAt": datetime.now(UTC).isoformat(),
        "source": str(source.resolve()), "sourceSha256": file_sha(source),
        "subset": str(subset.resolve()), "subsetSha256": file_sha(subset),
        "expectedCases": len(cases),
        "coverage": {
            "destinations": len({case["input"]["destination"]["name"] for case in cases}),
            "purposeRoles": dict(Counter(case["design"]["characterPlan"]["purpose"]["role"] for case in cases)),
            "bodyFamilies": dict(Counter(case["design"]["characterPlan"]["bodyFamily"] for case in cases)),
        },
        "model": MODEL, "revision": REVISION, "weightsPath": str(RUNTIME / "model"),
        "weightsManifestSha256": file_sha(RUNTIME / "model-manifest.json"),
        "weightsBytes": manifest["bytes"], "promptVersion": PROMPT_VERSION,
        "styleSha256": file_sha(STYLE), "settings": SETTINGS,
        "styleReferenceEdgeOverride": style_edge,
        "scope": f"{len(cases)} selected fixed character plans through production references/prompt + actual FLUX + production matte cutout; not fresh HTTP requests",
        "voiceBinding": "Reuse the original prepared character voice; changing rendering engine does not create another character in this audit",
        "networkCalls": 0, "paidApiCalls": 0, "jobs": jobs,
    }
    save_json(output / "jobs.json", prepared)
    return prepared


def verify_saved_result(job, record):
    if record.get("jobFingerprint") != job["jobFingerprint"]:
        raise ValueError("Saved job identity differs from prepared input")
    folder = Path(job["folder"])
    if record.get("rawSha256") and file_sha(folder / "original-rgb.png") != record["rawSha256"]:
        raise ValueError("Saved raw image changed")
    if record.get("status") == "READY" and file_sha(folder / "avatar.png") != record["rgbaSha256"]:
        raise ValueError("Saved RGBA image changed")


def worker(jobs_path: Path, limit=None, retry_failed=False):
    # Imported only in the already-installed image environment; no installation path.
    import gc
    from importlib.metadata import version

    import mlx.core as mx
    from mflux.callbacks.instances.battery_saver import BatterySaver
    from mflux.callbacks.instances.memory_saver import MemorySaver
    from mflux.models.common.config.model_config import ModelConfig
    from mflux.models.flux2.variants import Flux2KleinEdit
    from nunti.avatar_studio.matte_cutout import MatteCutoutError, cutout_matte_rgb

    prepared = json.loads(jobs_path.read_text())
    jobs = prepared["jobs"][:limit] if limit else prepared["jobs"]
    output = jobs_path.parent
    lock_path = RUNTIME / "inference.lock"
    # The shared production lock prevents concurrent TTS/FLUX GPU allocations.
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("GPU_BUSY: wait for the current TTS/FLUX job, then rerun", flush=True)
            return 2
        model = None
        load_seconds = 0
        settings = prepared["settings"]
        all_started = time.monotonic()
        for index, job in enumerate(jobs):
            if (output / "STOP_AFTER_CURRENT").exists():
                print("STOP_AFTER_CURRENT: current output is saved; remove marker before resume", flush=True)
                return 0
            folder = Path(job["folder"])
            saved = folder / "result.json"
            if saved.exists():
                old = json.loads(saved.read_text())
                verify_saved_result(job, old)
                if old["status"] == "READY" or (
                    old["status"] in {"CUTOUT_FAILED", "GENERATION_FAILED"} and not retry_failed
                ):
                    print(json.dumps({"index": index + 1, "total": len(jobs), "id": job["id"],
                                      "status": old["status"], "restored": True}), flush=True)
                    continue
            record = {"id": job["id"], "jobFingerprint": job["jobFingerprint"],
                      "status": "RUNNING", "model": prepared["model"],
                      "revision": prepared["revision"], "seed": job["seed"],
                      "settings": settings, "sourceSha256": job["sourceSha256"],
                      "promptSha256": job["promptSha256"], "referenceImages": job["referenceImages"],
                      "modelLoadedOnceForBatch": True, "networkCalls": 0, "paidApiCalls": 0,
                      "packages": {name: version(name) for name in ("mflux", "mlx", "Pillow")},
                      "humanQualityApproved": False, "semanticImageReview": "UNREVIEWED"}
            save_json(saved, record)
            start = time.monotonic()
            loaded_this_image = False
            try:
                raw_path = folder / "original-rgb.png"
                checkpoint = folder / "raw-checkpoint.json"
                reuse_raw = False
                if checkpoint.exists() and raw_path.exists():
                    checkpoint_data = json.loads(checkpoint.read_text())
                    reuse_raw = (checkpoint_data["jobFingerprint"] == job["jobFingerprint"]
                                 and checkpoint_data["sha256"] == file_sha(raw_path))
                if not reuse_raw:
                    if model is None:
                        load_start = time.monotonic()
                        model = Flux2KleinEdit(model_config=ModelConfig.flux2_klein_4b(),
                                              model_path=prepared["weightsPath"])
                        model.callbacks.register(BatterySaver(battery_percentage_stop_limit=5))
                        model.callbacks.register(MemorySaver(
                            model=model, keep_transformer=True, keep_text_encoder=True,
                            cache_limit_bytes=settings["cacheLimitBytes"], num_seeds=len(jobs)))
                        load_seconds = time.monotonic() - load_start
                        loaded_this_image = True
                        print(json.dumps({"event": "MODEL_LOADED", "seconds": round(load_seconds, 2),
                                          "bits": model.bits}), flush=True)
                    prompt = (folder / "prompt.txt").read_text()
                    if sha(prompt.encode()) != job["promptSha256"]:
                        raise ValueError("Prepared prompt changed")
                    paths = []
                    for reference in job["referenceImages"]:
                        path = folder / reference["name"]
                        if file_sha(path) != reference["sha256"]:
                            raise ValueError("Prepared reference image changed")
                        paths.append(path)
                    generated = model.generate_image(
                        seed=job["seed"], prompt=prompt, width=settings["width"],
                        height=settings["height"], guidance=settings["guidance"],
                        image_paths=paths, num_inference_steps=settings["steps"],
                        scheduler=settings["scheduler"])
                    generated.save(path=raw_path, export_json_metadata=True, overwrite=True)
                    del generated
                    save_json(checkpoint, {"jobFingerprint": job["jobFingerprint"],
                                           "sha256": file_sha(raw_path)})
                raw = raw_path.read_bytes()
                record["rawSha256"] = sha(raw)
                record["rawRestored"] = reuse_raw
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != "PNG" or image.mode != "RGB" or image.size != (512, 512):
                        raise ValueError("Actual model output violates RGB/512 PNG contract")
                value = json.loads((folder / "input.json").read_text())
                rgba, formation, cutout = cutout_matte_rgb(raw, value["route"]["points"])
                (folder / "avatar.png").write_bytes(rgba)
                save_json(folder / "formation.json", formation)
                record.update({"status": "READY", "rgbaSha256": sha(rgba), "cutout": cutout,
                               "formationSource": formation.get("source")})
            except MatteCutoutError as exc:
                record.update({"status": "CUTOUT_FAILED", "errorCode": exc.code, "error": str(exc)})
            except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
                record.update({"status": "GENERATION_FAILED", "errorCode": type(exc).__name__,
                               "error": str(exc)[:1000]})
            finally:
                record.update({"elapsedSeconds": round(time.monotonic() - start, 3),
                               "modelLoadSeconds": round(load_seconds, 3),
                               "loadedModelForThisImage": loaded_this_image,
                               "workerModelLoadCount": 1 if model is not None else 0,
                               "textEncoderRetained": model is not None and model.text_encoder is not None,
                               "transformerRetained": model is not None and model.transformer is not None,
                               "peakMlxMemoryBytes": mx.get_peak_memory(),
                               "createdAt": datetime.now(UTC).isoformat()})
                save_json(saved, record)
                gc.collect()
                mx.clear_cache()
            print(json.dumps({"index": index + 1, "total": len(jobs), "id": job["id"],
                              "status": record["status"], "seconds": record["elapsedSeconds"],
                              "elapsedSeconds": round(time.monotonic() - all_started)},
                             ensure_ascii=False), flush=True)
            if record["status"] == "GENERATION_FAILED" and model is None:
                # Loading failures are global; avoid repeating the same failing 4.6GB load.
                print("MODEL_LOAD_FAILED: remaining cases stay pending for a corrected resume", flush=True)
                return 1
            if model is not None and not (record["textEncoderRetained"] and record["transformerRetained"]):
                print("MODEL_REUSE_STATE_RELEASED: current artifact saved, remaining cases stay pending", flush=True)
                return 1
        save_json(output / "worker-complete.json", {"completedAt": datetime.now(UTC).isoformat(),
                                                    "processedJobLimit": len(jobs),
                                                    "elapsedSeconds": round(time.monotonic() - all_started)})
    return 0


def verified_reviews(review, records):
    """A review applies only to the exact rendered pixels that were inspected."""
    actual = {record["id"]: record for record in records}
    reviews, rejected = {}, []
    duplicate_ids = {case_id for case_id, count in Counter(
        case["id"] for case in review.get("cases", [])
    ).items() if count > 1}
    for case in review.get("cases", []):
        case_id = case["id"]
        record = actual.get(case_id)
        key = "rgbaSha256" if record and record["status"] == "READY" else "rawSha256"
        if (case_id in duplicate_ids or record is None or not record.get(key)
                or case.get(key) != record[key]):
            rejected.append({"id": case_id, "reason": "DUPLICATE_OR_STALE_IMAGE_REVIEW"})
            continue
        reviews[case_id] = case
    return reviews, rejected


def assemble_selection(output: Path, sources: list[Path]):
    """Publish inspected choices without changing or hiding any source attempt."""
    if output.exists() and any(output.iterdir()):
        raise ValueError("Selection output must be new or empty; preserve prior selections")
    attempts = []
    baseline = None
    for source in sources:
        source = source.resolve()
        prepared = json.loads((source / "jobs.json").read_text())
        baseline = baseline or prepared
        records = []
        for job in prepared["jobs"]:
            record = json.loads((Path(job["folder"]) / "result.json").read_text())
            verify_saved_result(job, record)
            records.append(record)
        review = json.loads((source / "visual-review.json").read_text())
        reviews, rejected = verified_reviews(review, records)
        if rejected:
            raise ValueError(f"Unverified visual review in {source}: {rejected}")
        attempts.append((source, prepared, {record["id"]: record for record in records}, reviews))
    if baseline is None:
        raise ValueError("At least one source is required")
    output.mkdir(parents=True, exist_ok=True)
    selected_jobs, selected_reviews, decisions = [], [], []
    for base_job in baseline["jobs"]:
        case_id = base_job["id"]
        candidates = []
        for source, prepared, records, reviews in attempts:
            if case_id in records:
                job = next(job for job in prepared["jobs"] if job["id"] == case_id)
                for name in ("input.json", "design.json"):
                    if file_sha(Path(job["folder"]) / name) != file_sha(Path(base_job["folder"]) / name):
                        raise ValueError(f"{case_id}: changed character {name}; cannot reuse its review or voice")
                candidates.append((source, job, records[case_id], reviews.get(case_id)))
        passed = [candidate for candidate in candidates
                  if candidate[2]["status"] == "READY" and candidate[3]
                  and candidate[3].get("overallPass", False)]
        source, job, record, review = (passed or candidates)[-1]
        folder = output / "cases" / case_id
        shutil.copytree(Path(job["folder"]), folder)
        selected_jobs.append({**job, "folder": str(folder.resolve()), "selectedFrom": str(source)})
        if review:
            selected_reviews.append({**review, "selectedFrom": str(source)})
        decisions.append({"id": case_id, "selectedFrom": str(source),
                          "selectionRule": "LATEST_EXACT_IMAGE_CORE_PASS_OR_LAST_UNRESOLVED",
                          "attempts": [{"source": str(s), "status": r["status"],
                                        "rawSha256": r.get("rawSha256"),
                                        "rgbaSha256": r.get("rgbaSha256"),
                                        "coreReviewPass": bool(v and v.get("overallPass", False))}
                                       for s, _, r, v in candidates]})
    metadata = {**baseline, "version": "nunti-v6-ai-selection-1",
                "createdAt": datetime.now(UTC).isoformat(), "jobs": selected_jobs,
                "promptVersion": "PER_CASE_SOURCE_ATTEMPT",
                "scope": f"{len(selected_jobs)} inspected character choices from preserved real-model attempts; not fresh HTTP requests",
                "selectionSources": [str(source) for source, *_ in attempts]}
    save_json(output / "jobs.json", metadata)
    save_json(output / "visual-review.json", {
        "reviewerType": "AI_ASSISTANT", "humanApproval": False,
        "method": "Exact-SHA reviews copied from their preserved source attempts",
        "cases": selected_reviews,
    })
    save_json(output / "selection.json", {
        "expectedCases": len(selected_jobs),
        "actualModelAttemptsInTheseMatrixRuns": sum(bool(record.get("rawSha256"))
            for _, _, records, _ in attempts for record in records.values()),
        "noNewModelInferenceDuringSelection": True,
        "sourceFailuresPreserved": True, "decisions": decisions,
    })
    return metadata


def summarize(output: Path):
    from nunti.avatar_studio.voice_design import build_voice_design
    from verify_avatar_v6_matrix import (
        font,
        is_near_duplicate,
        pixel_features,
        similarity,
    )

    prepared = json.loads((output / "jobs.json").read_text())
    records, pixels = [], []
    for job in prepared["jobs"]:
        folder = Path(job["folder"])
        saved = folder / "result.json"
        record = json.loads(saved.read_text()) if saved.exists() else {"status": "PENDING"}
        if saved.exists():
            verify_saved_result(job, record)
        record.update({"id": job["id"], "destination": job["destination"],
                       "purposeRole": job["purposeRole"], "purpose": job["purpose"]})
        if record["status"] == "READY":
            image = Image.open(folder / "avatar.png").convert("RGBA")
            record["pixelSha256"] = sha(image.tobytes())
            pixels.append((job["id"], pixel_features(image)))
        records.append(record)
    near, review_candidates = [], []
    for i, (a, first) in enumerate(pixels):
        for b, second in pixels[i + 1:]:
            metrics = similarity(first, second)
            if is_near_duplicate(metrics):
                near.append({"a": a, "b": b, **metrics})
            if (metrics["pHashDistance"] <= 12 and metrics["opaqueSilhouetteIoU"] >= 0.94
                    and metrics["meanRgbDifference"] < 5):
                review_candidates.append({"a": a, "b": b, **metrics})
    statuses = Counter(record["status"] for record in records)
    raw_count = sum(bool(record.get("rawSha256")) for record in records)
    review_file = output / "visual-review.json"
    review = json.loads(review_file.read_text()) if review_file.exists() else {"cases": []}
    reviews, rejected_reviews = verified_reviews(review, records)
    semantic_failures = [case for case in reviews.values() if not case.get("overallPass", False)]
    report = {
        "status": "ALL_GENERATED_VISUAL_REVIEW_REQUIRED" if statuses["READY"] == len(records) else "INCOMPLETE_OR_FAILED",
        "actualModelRgbImages": raw_count, "actualRgbaAvatars": statuses["READY"],
        "distinctRgbaPixelImages": len({record["pixelSha256"] for record in records if record.get("pixelSha256")}),
        "cases": len(records), "statusCounts": dict(statuses), "nearDuplicatePairs": near,
        "expectedCases": len(prepared["jobs"]), "coverage": prepared.get("coverage"),
        "coverageScope": "INPUT_CHARACTER_PLANS; actual species fidelity is assessed separately in visual review",
        "visualReviewCandidatePairs": review_candidates,
        "visualReviewCandidateThresholds": {"pHashDistanceMax": 12, "opaqueSilhouetteIoUMin": 0.94,
                                            "meanRgbDifferenceMaxExclusive": 5},
        "visualSimilarityCaveat": "pHash/alpha similarity only nominates close pairs. Different pixels do not establish different character identities or correct costumes.",
        "visualReviewCount": len(reviews),
        "rejectedVisualReviews": rejected_reviews,
        "visualReviewPassCount": sum(case.get("overallPass", False) for case in reviews.values()),
        "humanQualityApproved": False,
        "semanticReviewFailures": semantic_failures,
        "semanticReviewPending": [record["id"] for record in records if record["id"] not in reviews],
        "scope": prepared["scope"], "voiceBinding": prepared["voiceBinding"],
        "model": prepared["model"], "revision": prepared["revision"],
        "paidApiCalls": 0, "networkCalls": 0, "records": records,
    }
    if statuses["READY"] == len(records) and len(reviews) == len(records) and not rejected_reviews:
        report["status"] = ("GENERATED_WITH_SEMANTIC_FAILURES" if semantic_failures else
                            "AI_CORE_REVIEW_PASS_DETAILS_REMAIN")
    if (output / "selection.json").exists():
        report["selection"] = json.loads((output / "selection.json").read_text())
    sheets = []
    for start in range(0, len(records), 25):
        sheet = Image.new("RGB", (1200, 1535), "#f8f5ee")
        draw = ImageDraw.Draw(sheet)
        draw.text((24, 18), f"NUNTI · 실제 FLUX   {start + 1:03d}–{min(start + 25, len(records)):03d}",
                  fill="#302e38", font=font(25))
        draw.text((24, 51), "실제 모델 생성 · 실패/누락도 그대로 표시 · 합성 QA 경로", fill="#655e73", font=font(17))
        for index, record in enumerate(records[start:start + 25]):
            x, y = (index % 5) * 240, 92 + (index // 5) * 286
            draw.rounded_rectangle((x + 8, y, x + 232, y + 274), 14, fill="white")
            folder = output / "cases" / record["id"]
            path = folder / ("avatar.png" if record["status"] == "READY" else "original-rgb.png")
            if path.exists():
                with Image.open(path) as image:
                    thumb = image.convert("RGBA").resize((216, 216), Image.Resampling.LANCZOS)
                    sheet.paste(thumb, (x + 12, y + 1), thumb)
            draw.text((x + 17, y + 215), record["destination"], fill="#302e38", font=font(16))
            draw.text((x + 17, y + 236), record["id"], fill="#766c83", font=font(14))
            reviewed = reviews.get(record["id"])
            visual_label = (" · 의미 PASS" if reviewed["overallPass"] else " · 의미 FAIL") if reviewed else ""
            draw.text((x + 17, y + 254), record["status"] + visual_label,
                      fill="#447666" if reviewed and reviewed["overallPass"] else "#aa274a", font=font(12))
        relative = f"contact-sheets/{start // 25 + 1:02d}.jpg"
        (output / relative).parent.mkdir(exist_ok=True)
        sheet.save(output / relative, quality=92)
        sheets.append(relative)
    report["contactSheets"] = sheets
    save_json(output / "report.json", report)
    cards, voice_binding_failures = [], []
    verified_voice_bindings = 0
    bound_voices = {}
    voice_report_path = output.parent / "matrix/report.json"
    if voice_report_path.exists():
        voice_report = json.loads(voice_report_path.read_text())
        bound_voices = {case["id"]: case["audio"] for case in voice_report["cases"] if case.get("audio")}
    for record in records:
        prefix = f"cases/{record['id']}"
        image_name = "avatar.png" if record["status"] == "READY" else "original-rgb.png"
        picture = f'<img src="{prefix}/{image_name}">' if record.get("rawSha256") else '<div class="pending">대기</div>'
        sound = ""
        reviewed = reviews.get(record["id"])
        review_note = '<p>실제 이미지 의미 검토 대기</p>'
        if reviewed:
            purpose_pass = "PASS" if reviewed["purposeOutfitReadable"] else "FAIL"
            place_pass = reviewed.get("destinationKeepsakeMatch", "UNREVIEWED")
            overall = "PASS" if reviewed["overallPass"] else "FAIL"
            review_note = (f'<p><strong>AI 시각 검토 {overall}</strong> · 목적 의상 {purpose_pass} · '
                           f'장소 상징 {html.escape(place_pass)}</p>'
                           f'<p>{html.escape(reviewed.get("notes", ""))}</p>')
        if record["id"] in bound_voices:
            audio = bound_voices[record["id"]]
            case_folder = output / "cases" / record["id"]
            expected = build_voice_design(json.loads((case_folder / "input.json").read_text()),
                                          json.loads((case_folder / "design.json").read_text()))
            if (audio["profileId"], audio["greeting"], audio["role"]) != (
                expected["profileId"], expected["greeting"], expected["role"]
            ):
                voice_binding_failures.append(record["id"])
            else:
                verified_voice_bindings += 1
                audio_path = os.path.relpath((voice_report_path.parent / audio["path"]).resolve(), output)
                sound = (f'<audio controls preload="none" src="{html.escape(audio_path, quote=True)}"></audio>'
                         f'<p>{html.escape(audio["description"])}</p>')
        cards.append(f'<article><b>{html.escape(record["destination"])} · {record["purposeRole"]}</b>'
                     f'<div class="compare"><figure><img src="{prefix}/structure-reference.png"><figcaption>구조 참조</figcaption></figure><figure>{picture}<figcaption>실제 AI</figcaption></figure></div><p>{record["id"]} · {record["status"]}</p>'
                     f'<a href="{prefix}/structure-reference.png">구조 참조</a> · '
                     f'<a href="{prefix}/original-rgb.png">실제 원본</a> · '
                     f'<a href="{prefix}/result.json">생성 기록</a>{review_note}{sound}</article>')
    output.joinpath("index.html").write_text(f'''<!doctype html><html lang="ko"><meta charset="utf-8">
      <meta name="viewport" content="width=device-width"><title>실제 AI 눈티 {len(records)}</title><style>
      body{{margin:30px;background:#f6f3ed;color:#332c3e;font:16px system-ui}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(390px,1fr));gap:16px}}
      article{{background:white;border-radius:20px;padding:16px}}img{{width:100%;aspect-ratio:1}}p,a,figcaption{{font-size:12px}}.pending{{height:200px;display:grid;place-items:center;color:#888}}.compare{{display:grid;grid-template-columns:1fr 1fr}}figure{{margin:0}}audio{{width:100%;margin-top:12px}}</style>
      <h1>실제 FLUX · {len(records)}개 여정</h1><p>실제 모델 원본 {raw_count}/{len(records)} · 투명 이미지 {statuses['READY']}/{len(records)} · 시각 검토 {len(reviews)}/{len(records)} · 핵심 의미 통과 {report['visualReviewPassCount']}/{len(records)}</p>
      <p>고정된 캐릭터 플랜과 실제 생성 모델의 대조. AI의 이미지 검토이며 신규 HTTP 요청, 사람의 미적 승인, 모든 작은 소품의 완벽한 재현을 뜻하지 않습니다.</p>
      <p><a href="../matrix/index.html">절차형 구조와 같은 캐릭터의 음성 비교</a> · <a href="report.json">전체 보고서</a></p><main>{''.join(cards)}</main></html>''')
    report["voiceBindings"] = {"verified": verified_voice_bindings,
                                "mismatches": voice_binding_failures, "automaticPlayback": False}
    save_json(output / "report.json", report)
    return report


def status(output: Path):
    prepared = json.loads((output / "jobs.json").read_text())
    records = []
    for job in prepared["jobs"]:
        path = Path(job["folder"]) / "result.json"
        if path.exists():
            records.append(json.loads(path.read_text()))
    statuses = Counter(record["status"] for record in records)
    finished = [record for record in records if record["status"] != "RUNNING"]
    actual = [record for record in finished if record.get("rawSha256") and not record.get("rawRestored")]
    warm = [max(0, record["elapsedSeconds"] - (record["modelLoadSeconds"]
                 if record.get("loadedModelForThisImage") else 0)) for record in actual]
    mean = sum(warm) / len(warm) if warm else None
    result = {"requested": len(prepared["jobs"]), "finished": len(finished),
              "statusCounts": dict(statuses),
              "lastFinished": finished[-1]["id"] if finished else None,
              "meanInferenceAndCutoutSeconds": round(mean, 2) if mean is not None else None,
              "estimatedRemainingMinutes": round(mean * (len(prepared["jobs"]) - len(finished)) / 60, 1)
              if mean is not None else None,
              "stopAfterCurrentRequested": (output / "STOP_AFTER_CURRENT").exists()}
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=INPUT)
    parser.add_argument("--subset", type=Path, default=SUBSET)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop-after-current", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--style-edge", type=int, choices=(256, 512),
                        help="Controlled experiment only: resize the face-style reference; structure/output remain 512px")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--select-from", type=Path, nargs="+",
                        help="Assemble exact-SHA reviewed choices from preserved attempt directories")
    args = parser.parse_args()
    if args.status:
        status(args.output)
        return 0
    if args.stop_after_current:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "STOP_AFTER_CURRENT").write_text(datetime.now(UTC).isoformat())
        print("Current image will finish; the worker will stop before its next image.")
        return 0
    if args.worker:
        return worker(args.worker, args.limit, args.retry_failed)
    args.output = args.output.resolve()
    if args.select_from:
        assemble_selection(args.output, args.select_from)
        args.summarize = True
    if args.prepare or args.run:
        prepared = prepare(args.source, args.output, args.style_edge, args.subset)
        print(json.dumps({"status": "PREPARED", "cases": len(prepared["jobs"]),
                          "output": str(args.output)}, ensure_ascii=False), flush=True)
    if args.run:
        from nunti.avatar_studio.local_model import offline_environment
        # Each resumed worker has a new isolated HOME; image evidence stays in output.
        execution_dir = Path(tempfile.mkdtemp(prefix="worker-env-", dir=args.output))
        environment = offline_environment(execution_dir)
        command = [str(RUNTIME / "venv/bin/python"), str(Path(__file__).resolve()),
                   "--worker", str(args.output / "jobs.json")]
        if args.limit:
            command += ["--limit", str(args.limit)]
        if args.retry_failed:
            command += ["--retry-failed"]
        if sys.platform == "darwin" and Path("/usr/bin/caffeinate").exists():
            command = ["/usr/bin/caffeinate", "-i", *command]
        with (args.output / "worker.log").open("ab") as log:
            result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                                    stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            print(f"Worker exited {result.returncode}; see {args.output / 'worker.log'}")
            return result.returncode
    if args.summarize or args.run:
        report = summarize(args.output)
        print(json.dumps({key: report[key] for key in (
            "status", "actualModelRgbImages", "actualRgbaAvatars", "distinctRgbaPixelImages",
            "cases", "statusCounts", "visualReviewCount", "voiceBindings")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
