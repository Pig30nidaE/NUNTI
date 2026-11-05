#!/usr/bin/env python3
"""Offline PC worker: journey -> pinned Sohee assets -> append-only MVP bundle."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DYNAMIC = ROOT / "prototypes/journey_voice_dynamic"
sys.path.insert(0, str(DYNAMIC))
import voice_cli as dynamic
import export_android
from settings import canonical, digest

DEFAULT_WORKSPACE = ROOT / ".local/journey-mvp"
SOURCE = DYNAMIC / "demo"
RENDERER_VERSION = "journey-keepsake-canvas-1"
MAX_CHARACTERS = 32  # Three clips per character gives 96, below the voice limit of 100.
CASE_TEXT_LIMITS = {"caseId": 120, "label": 60, "summary": 240}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_hashes(path):
    return {str(p.relative_to(path)): file_sha(p) for p in sorted(path.rglob("*")) if p.is_file() and not p.name.endswith(".lock")}


def encoded_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def exact_tree(path, expected):
    return path.is_dir() and not path.is_symlink() and not any(p.is_symlink() for p in path.rglob("*")) and tree_hashes(path) == expected


def fsync_tree(path):
    for item in path.rglob("*"):
        if item.is_file():
            with item.open("rb") as handle:
                os.fsync(handle.fileno())
    for directory in sorted((p for p in path.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        dynamic.fsync_directory(directory)
    dynamic.fsync_directory(path)


def crash_at(point):
    """Process-exit injection for transaction tests; never changes generation identity."""
    if os.environ.get("NUNTI_MVP_CRASH_AT") == point:
        os._exit(86)


def remove_journal(path):
    path.unlink()
    dynamic.fsync_directory(path.parent)


def publish_journal(path, body):
    require(not path.exists(), "PENDING_TRANSACTION_ALREADY_EXISTS")
    dynamic.atomic_json(path, dict(body, journalSha256=digest(body)))


def read_journal(path, kind):
    value = read(path)
    require(isinstance(value, dict), "PENDING_JOURNAL_CHANGED")
    body = {k: v for k, v in value.items() if k != "journalSha256"}
    require(value.get("journalSha256") == digest(body) and body.get("schemaVersion") == 1 and body.get("kind") == kind, "PENDING_JOURNAL_CHANGED")
    return body


def recover_bootstrap(workspace, original):
    journal_path = workspace / "bootstrap-pending.json"
    if not journal_path.exists():
        return
    pending = read_journal(journal_path, "bootstrap")
    receipt = pending["receipt"]
    require(receipt["sourceFileSha256"] == original, "PENDING_BOOTSTRAP_SOURCE_CHANGED")
    staging_name = pending["stagingDirectory"]
    require(isinstance(staging_name, str) and staging_name.startswith(".state-") and Path(staging_name).name == staging_name, "INVALID_PENDING_STATE_PATH")
    staging, state = workspace / staging_name, workspace / "state"
    receipt_path = workspace / "bootstrap-receipt.json"
    require(not (staging.exists() and state.exists()), "AMBIGUOUS_PENDING_STATE")
    if state.exists():
        require(exact_tree(state, original), "PENDING_STATE_CHANGED")
    else:
        # A receipt can only be committed after state publication. Its missing
        # state is corruption, even if an old journal happens to remain.
        require(not receipt_path.exists(), "COMMITTED_STATE_MISSING")
        require(exact_tree(staging, original), "PENDING_STATE_MISSING_OR_CHANGED")
        staging.rename(state)
        dynamic.fsync_directory(workspace)
        crash_at("bootstrap-after-state")
    if receipt_path.exists():
        require(receipt_path.read_bytes() == encoded_json(receipt), "PENDING_BOOTSTRAP_RECEIPT_CHANGED")
    else:
        dynamic.atomic_json(receipt_path, receipt)
        crash_at("bootstrap-after-receipt")
    remove_journal(journal_path)


@contextmanager
def lane(workspace):
    workspace.mkdir(parents=True, exist_ok=True)
    with (workspace / ".worker.lock").open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def bootstrap(workspace):
    """Copy original committed bytes once; subsequently verify the immutable subset."""
    workspace.mkdir(parents=True, exist_ok=True)
    state = workspace / "state"
    receipt_path = workspace / "bootstrap-receipt.json"
    original = tree_hashes(SOURCE)
    require(original and not any(p.is_symlink() for p in SOURCE.rglob("*")), "INVALID_ORIGINAL_DEMO")
    recover_bootstrap(workspace, original)
    if not state.exists():
        require(not receipt_path.exists(), "STATE_MISSING_NO_AUTOMATIC_REPLACEMENT")
        temporary = Path(tempfile.mkdtemp(prefix=".state-", dir=workspace))
        try:
            shutil.copytree(SOURCE, temporary, dirs_exist_ok=True)
            require(tree_hashes(temporary) == original, "COPY_BYTES_CHANGED")
            fsync_tree(temporary)
            receipt = {"schemaVersion": 1, "source": str(SOURCE.relative_to(ROOT)), "sourceFileSha256": original,
                       "reusedCharacterCount": 4, "reusedPrimaryClipCount": 12, "scope": "Copied original demo, not new synthesis"}
            publish_journal(workspace / "bootstrap-pending.json", {"schemaVersion": 1, "kind": "bootstrap", "stagingDirectory": temporary.name, "receipt": receipt})
            crash_at("bootstrap-after-journal")
            recover_bootstrap(workspace, original)
        finally:
            if temporary.exists() and not (workspace / "bootstrap-pending.json").exists():
                shutil.rmtree(temporary)
    require(receipt_path.is_file(), "STATE_WITHOUT_ORIGINAL_RECEIPT")
    receipt = read(receipt_path)
    require(receipt["sourceFileSha256"] == original, "ORIGINAL_DEMO_CHANGED")
    for relative, expected in original.items():
        if relative not in ("recipes.json", "listen.html"):
            require((state / relative).is_file() and file_sha(state / relative) == expected, "COPIED_ORIGINAL_CHANGED:" + relative)
    original_ledger, current_ledger = read(SOURCE / "recipes.json"), read(state / "recipes.json")
    for section in ("journeys", "requests"):
        require(all(current_ledger[section].get(k) == v for k, v in original_ledger[section].items()), "ORIGINAL_RECIPE_CHANGED")
    return state


def case_definitions():
    return read(HERE / "cases/index.json")["cases"]


def all_case_paths():
    return [HERE / "cases" / item["input"] for item in case_definitions()]


def bounded_case_text(value, name):
    # Kotlin String.length counts UTF-16 code units, including two for emoji.
    # Char.isWhitespace includes Java space characters but excludes U+0085.
    nonblank = isinstance(value, str) and any(not (c.isspace() and c != "\u0085") for c in value)
    require(nonblank and len(value.encode("utf-16-le")) // 2 <= CASE_TEXT_LIMITS[name], "INVALID_CASE_TEXT:" + name)
    return value


def validate_case_texts(entry):
    for name in CASE_TEXT_LIMITS:
        bounded_case_text(entry.get(name), name)


def preflight(workspace, paths, label=None, summary=None):
    """Match Android input bounds before identity writes or any model construction."""
    require(len(paths) == 1 or (label is None and summary is None), "CUSTOM_LABEL_REQUIRES_ONE_INPUT")
    for name, value in (("label", label), ("summary", summary)):
        if value is not None:
            bounded_case_text(value, name)
    registry = read(dynamic.recipes.REGISTRY_PATH)
    requests = [dynamic.recipes.normalize_request(read(path), registry) for path in paths]
    ledger = dynamic.recipes.load_ledger(workspace / "state/recipes.json")
    unique_journeys = set(ledger["journeys"]) | {request["journeyId"] for request in requests}
    require(0 < len(unique_journeys) <= MAX_CHARACTERS, "INVALID_CASE_COUNT:maximum_32_characters")
    index_path = workspace / "cases.json"
    if index_path.exists():
        index = read(index_path)
        require(index.get("schemaVersion") == 1 and isinstance(index.get("cases"), dict), "INVALID_CASE_INDEX")
        for entry in index["cases"].values():
            validate_case_texts(entry)


def register_cases(workspace, paths, label=None, summary=None):
    path = workspace / "cases.json"
    index = read(path) if path.exists() else {"schemaVersion": 1, "cases": {}}
    require(index.get("schemaVersion") == 1 and isinstance(index.get("cases"), dict), "INVALID_CASE_INDEX")
    known = {v["journeyId"]: v for v in case_definitions()}
    require(len(paths) == 1 or (label is None and summary is None), "CUSTOM_LABEL_REQUIRES_ONE_INPUT")
    for name, value in (("label", label), ("summary", summary)):
        if value is not None:
            bounded_case_text(value, name)
    registry = read(dynamic.recipes.REGISTRY_PATH)
    for input_path in paths:
        request = dynamic.recipes.normalize_request(read(input_path), registry)
        journey = request["journeyId"]
        definition = known.get(journey)
        if definition:
            entry = {k: definition[k] for k in ("caseId", "label", "summary", "journeyId", "origin")}
        else:
            entry = {"caseId": "trip-" + digest(journey)[:16], "label": label or "새 여정",
                     "summary": summary or "내가 추가한 이동", "journeyId": journey, "origin": "USER_PC_WORKER"}
        validate_case_texts(entry)
        previous = index["cases"].get(journey)
        if previous:
            validate_case_texts(previous)
            # A retry/reroute preserves its initial display identity as well.
            continue
        require(entry["caseId"] not in {v["caseId"] for v in index["cases"].values()}, "DUPLICATE_CASE_ID")
        index["cases"][journey] = entry
    dynamic.atomic_json(path, index)
    return index


def visual_from_recipe(recipe):
    registry = read(dynamic.recipes.REGISTRY_PATH)
    creative, design = recipe["creativeInspiration"], recipe["design"]
    family = next((b for b in registry["bodies"] if b["family"] == design["bodyFamily"]), None)
    require(family is not None and design["shapeId"] in family["shapes"], "UNKNOWN_BODY_OR_SHAPE")
    motif = next((s["tag"] for s in registry["destinationStyles"] if s["tag"] in creative["destinationTags"]), "unspecified")
    pattern = next((s["tag"] for s in registry["routeInteriorStyles"] if s["tag"] in creative["routeSemanticTags"]), "unspecified")
    proportions = design["routeProportions"]
    return {"characterId": recipe["characterId"], "seed": recipe["seed"], "bodyFamily": design["bodyFamily"],
            "shapeId": design["shapeId"], "palette": design["palette"],
            "widthMultiplier": proportions["widthMultiplier"], "heightMultiplier": proportions["heightMultiplier"],
            "motif": motif, "routePattern": pattern, "purpose": creative["purpose"] or "unspecified"}


def validate_voice_join(entry, voice_manifest):
    clips = {c["clipId"]: c for c in voice_manifest["clips"]}
    for clip_id in entry["clipIds"].values():
        clip = clips[clip_id]
        require(clip["characterId"] == entry["characterId"] and clip["profileId"] == entry["voiceProfileId"], "VOICE_CHARACTER_JOIN_CHANGED")
        require(clip["source"]["bindingId"] == entry["bindingId"] and clip["source"]["directionSha256"] == entry["directionSha256"], "VOICE_BINDING_JOIN_CHANGED")


def committed_bundle(workspace, current_by_id):
    path, receipt_path = workspace / "bundle/bundle.json", workspace / "bundle-receipt.json"
    if not path.exists():
        require(not receipt_path.exists(), "COMMITTED_BUNDLE_MISSING")
        return None
    previous = read(path)
    require(receipt_path.exists() and read(receipt_path) == {"schemaVersion": 1, "bundleSha256": digest(previous), "bundleId": previous["bundleId"]}, "BUNDLE_MANIFEST_CHANGED")
    require(all(current_by_id.get(e["characterId"]) == e for e in previous["characters"]), "EXISTING_VISUAL_OR_IDENTITY_CHANGED")
    return previous


def bundle_pair_state(workspace, pending):
    paths = (workspace / "bundle/bundle.json", workspace / "bundle-receipt.json")
    require(all(not path.is_symlink() for path in paths), "INVALID_BUNDLE_TRANSACTION_PATH")
    actual = tuple(file_sha(path) if path.exists() else None for path in paths)
    old = (pending["oldBundleFileSha256"], pending["oldReceiptFileSha256"])
    new = (hashlib.sha256(encoded_json(pending["newBundle"])).hexdigest(), hashlib.sha256(encoded_json(pending["newReceipt"])).hexdigest())
    require((old[0] is None) == (old[1] is None), "INVALID_OLD_BUNDLE_PAIR")
    require(actual in (old, (new[0], old[1]), new), "PENDING_BUNDLE_FILES_MISSING_OR_CHANGED")
    return actual, old, new


def pending_bundle(workspace, current_by_id):
    path = workspace / "bundle-pending.json"
    if not path.exists():
        return None
    pending = read_journal(path, "bundle")
    value = pending["newBundle"]
    content = {"schemaVersion": 1, "rendererVersion": RENDERER_VERSION, "characters": value["characters"]}
    require(value == dict(content, bundleId="journey-mvp-" + digest(content)[:20]), "INVALID_PENDING_BUNDLE")
    require(pending["newReceipt"] == {"schemaVersion": 1, "bundleSha256": digest(value), "bundleId": value["bundleId"]}, "INVALID_PENDING_BUNDLE_RECEIPT")
    require(all(current_by_id.get(e["characterId"]) == e for e in value["characters"]), "PENDING_BUNDLE_SOURCE_IDENTITY_CHANGED")
    bundle_pair_state(workspace, pending)
    return pending


def recover_bundle(workspace, pending):
    actual, old, new = bundle_pair_state(workspace, pending)
    if actual[0] != new[0]:
        dynamic.atomic_json(workspace / "bundle/bundle.json", pending["newBundle"])
        crash_at("bundle-after-manifest")
    if actual[1] != new[1]:
        dynamic.atomic_json(workspace / "bundle-receipt.json", pending["newReceipt"])
        crash_at("bundle-after-receipt")
    require(bundle_pair_state(workspace, pending)[0] == new, "BUNDLE_TRANSACTION_DID_NOT_COMMIT")
    remove_journal(workspace / "bundle-pending.json")


def build_bundle(workspace, engine):
    state = bootstrap(workspace)
    cases = read(workspace / "cases.json")["cases"]
    entries = []
    ledger = dynamic.recipes.load_ledger(state / "recipes.json")
    for artifact_path in sorted((state / "characters").glob("*/character.json")):
        artifact = read(artifact_path)
        recipe = ledger["journeys"][artifact["journeyId"]]["recipe"]
        plan = dynamic.validate_plan(read(artifact_path.parent / "plan.json"), recipe, engine)
        require(artifact["creativeRecipe"] == recipe and artifact["planSha256"] == plan["planSha256"] and artifact["voiceBinding"] == plan["voice"], "SOURCE_CHARACTER_CHANGED")
        case = cases[recipe["journeyId"]]
        visual = visual_from_recipe(recipe)
        entries.append({"caseId": case["caseId"], "label": case["label"], "summary": case["summary"],
                        "characterId": recipe["characterId"], "journeyId": recipe["journeyId"], "displayName": plan["displayName"],
                        "visual": visual, "visualSha256": digest(visual), "recipeSha256": digest(recipe),
                        "sourcePlanSha256": plan["planSha256"], "bindingId": plan["voice"]["bindingId"],
                        "voiceProfileId": plan["voice"]["profileId"],
                        "directionSha256": hashlib.sha256(plan["voice"]["direction"].encode()).hexdigest(),
                        "clipIds": {c: recipe["characterId"] + "-" + c for c in ("greeting", "arrival", "common")}})
    entries.sort(key=lambda e: e["caseId"])
    require(0 < len(entries) <= MAX_CHARACTERS and len({e["caseId"] for e in entries}) == len(entries), "INVALID_BUNDLE_CASES")
    for entry in entries:
        validate_case_texts(entry)
    content = {"schemaVersion": 1, "rendererVersion": RENDERER_VERSION, "characters": entries}
    bundle = dict(content, bundleId="journey-mvp-" + digest(content)[:20])
    output = workspace / "bundle"
    receipt_path = workspace / "bundle-receipt.json"
    current_by_id = {e["characterId"]: e for e in entries}
    pending = pending_bundle(workspace, current_by_id)
    if pending is None:
        committed_bundle(workspace, current_by_id)
    output.mkdir(parents=True, exist_ok=True)
    # The worker-wide output lock replaces the exporter's default lock location.
    # Reuse its unchanged byte-preserving publication algorithm in our own workspace.
    result = export_android._export(state, output / "voice")
    voice_manifest = read(output / "voice/manifest.json")
    require(voice_manifest["schemaVersion"] == 2, "VOICE_SCHEMA_CHANGED")
    for entry in entries:
        validate_voice_join(entry, voice_manifest)
    # Finish only a documented old/new byte pair, after validating its source
    # identities and every actual voice asset. A missing committed file without
    # a pending transaction is never treated as a normal interrupted write.
    if pending is not None:
        recover_bundle(workspace, pending)
    previous = committed_bundle(workspace, current_by_id)
    if previous != bundle:
        new_receipt = {"schemaVersion": 1, "bundleSha256": digest(bundle), "bundleId": bundle["bundleId"]}
        publish_journal(workspace / "bundle-pending.json", {
            "schemaVersion": 1, "kind": "bundle",
            "oldBundleFileSha256": file_sha(output / "bundle.json") if previous is not None else None,
            "oldReceiptFileSha256": file_sha(receipt_path) if previous is not None else None,
            "newBundle": bundle, "newReceipt": new_receipt,
        })
        crash_at("bundle-after-journal")
        recover_bundle(workspace, pending_bundle(workspace, current_by_id))
    return {"bundleId": bundle["bundleId"], "bundle": str(output / "bundle.json"),
            "characters": len(entries), "bodyFamilies": sorted({e["visual"]["bodyFamily"] for e in entries}), "voice": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap")
    for name in ("plan", "generate"):
        command = commands.add_parser(name)
        command.add_argument("--input", nargs="+", type=Path)
        command.add_argument("--label")
        command.add_argument("--summary")
    commands.add_parser("bundle")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    try:
        with lane(workspace):
            state = bootstrap(workspace)
            if args.command == "bootstrap":
                result = {"state": str(state), "copiedOriginalCharacters": 4, "newSynthesisCount": 0}
            else:
                if args.command in ("plan", "generate"):
                    paths = args.input or all_case_paths()
                    preflight(workspace, paths, args.label, args.summary)
                else:
                    preflight(workspace, [])
                from engine import SoheeSynthesizer
                engine = SoheeSynthesizer()
                if args.command in ("plan", "generate"):
                    register_cases(workspace, all_case_paths())
                    register_cases(workspace, paths, args.label, args.summary)
                    result = dynamic.generate(paths, state, engine, plan_only=args.command == "plan")
                    if args.command == "generate":
                        result["bundle"] = build_bundle(workspace, engine)
                else:
                    register_cases(workspace, all_case_paths())
                    result = build_bundle(workspace, engine)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, TypeError, RuntimeError) as exc:
        print("journey MVP worker error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
