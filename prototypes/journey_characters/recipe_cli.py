#!/usr/bin/env python3
"""A single-writer, offline recipe prototype. Python 3.9+, standard library only."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile


REGISTRY_PATH = Path(__file__).with_name("registry.json")
SCHEMA_VERSION = 1


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def require_keys(value, required, optional, label):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    missing = set(required) - set(value)
    extra = set(value) - set(required) - set(optional)
    if missing or extra:
        raise ValueError("{}: missing {}; unsupported {}".format(label, sorted(missing), sorted(extra)))


def identifier(value, label):
    if (not isinstance(value, str) or not value or len(value) > 120
            or any(not (c.isascii() and (c.isalnum() or c in "-_:.")) for c in value)):
        raise ValueError(label + " must be a 1..120 character ASCII opaque identifier")
    return value


def tags(value, allowed, label):
    if not isinstance(value, list) or any(not isinstance(x, str) or x not in allowed for x in value):
        raise ValueError(label + " must be a list of registry semantic tags")
    return sorted(set(value))


def normalize_request(raw, registry):
    """Parse this prototype's narrow input boundary; exact addresses/GPS are unsupported."""
    require_keys(raw, ["requestId", "journeyId", "destination", "route"], ["purpose"], "request")
    require_keys(raw["destination"], ["semanticTags"], [], "destination")
    route = raw["route"]
    require_keys(route, ["distanceKm", "semanticTags", "verifiedRoadFacts"], [], "route")
    distance = route["distanceKm"]
    if (isinstance(distance, bool) or not isinstance(distance, (int, float))
            or not math.isfinite(distance) or not 0 <= distance <= 10000):
        raise ValueError("route.distanceKm must be a finite number in 0..10000")
    facts = route["verifiedRoadFacts"]
    require_keys(facts, ["status", "roadTypes", "source"], [], "verifiedRoadFacts")
    if facts["status"] not in ("UNKNOWN", "VERIFIED"):
        raise ValueError("verifiedRoadFacts.status must be UNKNOWN or VERIFIED")
    road_types = tags(facts["roadTypes"], ["HIGHWAY", "ARTERIAL", "LOCAL"], "roadTypes")
    if facts["status"] == "UNKNOWN":
        if road_types or facts["source"] is not None:
            raise ValueError("UNKNOWN road facts must have empty roadTypes and null source")
    elif (not road_types or not isinstance(facts["source"], str) or not facts["source"]
          or len(facts["source"]) > 240):
        raise ValueError("VERIFIED road facts require roadTypes and an evidence source")
    purpose = raw.get("purpose")
    allowed_purposes = set(registry["purposes"]) - {"unspecified"}
    if purpose is not None and (not isinstance(purpose, str) or purpose not in allowed_purposes):
        raise ValueError("purpose must be a registry purpose or null; missing means UNSPECIFIED")
    destination_tags = [x["tag"] for x in registry["destinationStyles"] if x["tag"] != "unspecified"]
    return {
        "requestId": identifier(raw["requestId"], "requestId"),
        "journeyId": identifier(raw["journeyId"], "journeyId"),
        "destination": {"semanticTags": tags(raw["destination"]["semanticTags"], destination_tags, "destination.semanticTags")},
        "route": {"distanceKm": float(distance),
                  "semanticTags": tags(route["semanticTags"], registry["routeTags"], "route.semanticTags"),
                  "verifiedRoadFacts": {"status": facts["status"], "roadTypes": road_types, "source": facts["source"]}},
        "purpose": purpose,
    }


def select_body(seed, route_tags, history, registry):
    """History dominates semantic affinity so a new hat cannot count as novelty."""
    candidates = []
    for body in registry["bodies"]:
        family_uses = sum(x["design"]["bodyFamily"] == body["family"] for x in history)
        affinity = len(set(body["routeAffinity"]) & set(route_tags))
        for shape in body["shapes"]:
            shape_uses = sum(x["design"]["shapeId"] == shape for x in history)
            tie = int(digest([seed, shape])[:8], 16) / float(2 ** 32)
            score = (family_uses, shape_uses, -affinity, tie)
            candidates.append((score, body, shape, family_uses, shape_uses))
    _, body, shape, family_uses, shape_uses = min(candidates, key=lambda item: item[0])
    return body, shape, family_uses, shape_uses


def build_recipe(request, history, registry):
    """Pure recipe construction. It creates no image, animation, audio or driving score."""
    journey_id = request["journeyId"]
    seed = digest(["nunti-journey-v1", journey_id])[:16]
    character_id = "nunti-" + digest(["character-v1", journey_id])[:24]
    body, shape, family_uses, shape_uses = select_body(seed, request["route"]["semanticTags"], history, registry)
    destination_tags = request["destination"]["semanticTags"]
    style = next((x for x in registry["destinationStyles"] if x["tag"] in destination_tags), registry["destinationStyles"][-1])
    route_tags = request["route"]["semanticTags"]
    interior_route = next((x for x in registry["routeInteriorStyles"] if x["tag"] in route_tags), registry["routeInteriorStyles"][-1])
    purpose_key = request["purpose"] or "unspecified"
    purpose = registry["purposes"][purpose_key]
    distance = request["route"]["distanceKm"]
    if distance < 40:
        distance_form = {"distanceBand": "short", "widthMultiplier": 1.08, "heightMultiplier": 0.94}
    elif distance <= 160:
        distance_form = {"distanceBand": "medium", "widthMultiplier": 1.0, "heightMultiplier": 1.0}
    else:
        distance_form = {"distanceBand": "long", "widthMultiplier": 0.96, "heightMultiplier": 1.06}
    root = style["nameRoots"][int(seed, 16) % len(style["nameRoots"])]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "registryVersion": registry["version"],
        "status": "RECIPE_ONLY",
        "characterId": character_id,
        "journeyId": journey_id,
        "seed": seed,
        "world": registry["world"],
        "design": {
            "bodyFamily": body["family"], "silhouette": body["silhouette"], "shapeId": shape,
            "routeProportions": distance_form,
            "materialIntent": style["material"], "palette": style["palette"],
            "interiorIntent": {
                "destinationMotif": style["interiorMotif"],
                "routePattern": interior_route["pattern"],
                "light": registry["purposeLights"][purpose_key],
                "motionIntent": "STATIC_ONLY",
                "renderingStatus": "NOT_RENDERED",
            },
            "personalityIntent": purpose["personality"],
            "nameDirection": {"rootSuggestion": root, "tone": purpose["nameEnding"], "finalName": None},
        },
        "voiceIntent": {
            "identityKey": "voice-" + character_id,
            "status": "UNBOUND_INTENT", "provider": None,
            "requested": purpose["voice"], "confirmedSupportedControls": [],
            "fallback": {
                "strategy": "same_character_asset_else_pending_or_silent",
                "assetMatchRequirement": "same_character_voice_binding_and_same_utterance",
                "assetAvailability": "UNVERIFIED",
                "implementationStatus": "PROPOSAL_ONLY",
                "characterVoiceIdentityGuaranteed": False,
            },
        },
        "creativeInspiration": {
            "destinationTags": destination_tags,
            "routeSemanticTags": request["route"]["semanticTags"],
            "routeDistanceKm": distance,
            "purpose": request["purpose"],
            "purposeStatus": "USER_SUPPLIED" if request["purpose"] else "UNSPECIFIED",
            "axisOwnership": {
                "destination": "translucent material, palette, inner motif, name root",
                "route": "body affinity, width and height proportions, inner pattern layout",
                "purpose": "personality, inner light, name tone, requested voice delivery",
                "history": "body-family and shape repetition penalty",
            },
            "interpretation": "Creative hints only. Tags and distance do not establish road safety facts or rewards.",
        },
        "verifiedRoadFacts": request["route"]["verifiedRoadFacts"],
        "verifiedRoadFactsScope": "CREATION_SNAPSHOT_NOT_CURRENT_DRIVING_STATE",
        "novelty": {
            "priorCharacterCount": len(history), "priorBodyFamilyUses": family_uses,
            "priorShapeUses": shape_uses,
            "method": "minimize prior body-family uses, then shape uses; route affinity and seeded tie-break follow",
            "repetitionAfterRegistryExhaustion": True,
        },
        "providers": {"image": "UNCONNECTED", "animation": "UNCONNECTED", "tts": "UNCONNECTED"},
        "qualityStatus": {
            "renderedAvatar": False, "cutenessTested": False, "collectibilityTested": False,
            "drivingImprovementTested": False,
        },
    }


def load_ledger(path):
    if not path.exists():
        return {"schemaVersion": SCHEMA_VERSION, "journeys": {}, "requests": {}}
    with path.open(encoding="utf-8") as handle:
        ledger = json.load(handle)
    require_keys(ledger, ["schemaVersion", "journeys", "requests"], [], "ledger")
    if (ledger["schemaVersion"] != SCHEMA_VERSION or not isinstance(ledger["journeys"], dict)
            or not isinstance(ledger["requests"], dict)):
        raise ValueError("unsupported or malformed ledger; refusing to overwrite it")
    for journey_id, record in ledger["journeys"].items():
        require_keys(record, ["originalRequestDigest", "recipe"], [], "ledger journey")
        recipe = record["recipe"]
        if not isinstance(recipe, dict) or recipe.get("journeyId") != journey_id or not isinstance(recipe.get("design"), dict):
            raise ValueError("malformed persisted recipe; refusing to overwrite ledger")
        if not all(key in recipe["design"] for key in ("bodyFamily", "shapeId")):
            raise ValueError("persisted recipe lacks body identity")
    for record in ledger["requests"].values():
        require_keys(record, ["journeyId", "firstRequestDigest"], [], "ledger request")
        if record["journeyId"] not in ledger["journeys"]:
            raise ValueError("request points to missing journey; refusing to overwrite ledger")
    return ledger


def save_atomic(path, ledger, crash_at=None):
    """One CLI writer only. Atomic replace protects readers from partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "." + path.name + ".tmp-"
    # Stale files from our own interrupted atomic writes are safe to remove only
    # because this prototype explicitly excludes concurrent CLI writers.
    for stale in path.parent.glob(prefix + "*"):
        if stale.is_file():
            stale.unlink()
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=prefix,
                                         dir=str(path.parent), delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(ledger, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if crash_at == "before-replace":
            os._exit(86)
        os.replace(str(temp_path), str(path))
        temp_path = None
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if crash_at == "after-replace":
            os._exit(86)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def generate(request, ledger, registry):
    """First committed journey wins, including changed inputs from a reroute."""
    journey_id, request_id = request["journeyId"], request["requestId"]
    prior_request = ledger["requests"].get(request_id)
    if prior_request is not None and prior_request["journeyId"] != journey_id:
        raise ValueError("requestId already belongs to another journeyId")
    changed = False
    if journey_id not in ledger["journeys"]:
        history = [entry["recipe"] for entry in ledger["journeys"].values()]
        ledger["journeys"][journey_id] = {
            "originalRequestDigest": digest(request),
            "recipe": build_recipe(request, history, registry),
        }
        changed = True
    if prior_request is None:
        ledger["requests"][request_id] = {"journeyId": journey_id, "firstRequestDigest": digest(request)}
        changed = True
    return ledger["journeys"][journey_id]["recipe"], changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("generate", help="create or return a persisted journey recipe")
    command.add_argument("--input", required=True, type=Path)
    command.add_argument("--ledger", required=True, type=Path)
    command.add_argument("--simulate-crash", choices=["before-replace", "after-replace"],
                         help="test hook: exit 86 at an atomic-save boundary")
    args = parser.parse_args()
    try:
        with REGISTRY_PATH.open(encoding="utf-8") as handle:
            registry = json.load(handle)
        with args.input.open(encoding="utf-8") as handle:
            request = normalize_request(json.load(handle), registry)
        ledger = load_ledger(args.ledger)
        recipe, changed = generate(request, ledger, registry)
        if changed:
            save_atomic(args.ledger, ledger, args.simulate_crash)
        print(json.dumps(recipe, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("recipe error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
