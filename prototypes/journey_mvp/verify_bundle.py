#!/usr/bin/env python3
"""Read and verify the MVP bundle against committed recipes, plans and actual WAVs."""
import argparse
import hashlib
import json
from pathlib import Path
from worker import DEFAULT_WORKSPACE, SOURCE, bootstrap, digest, dynamic, file_sha, read, require, validate_voice_join, visual_from_recipe


def verify(workspace, expected_characters=None, expected_bodies=None):
    state = bootstrap(workspace)
    bundle = read(workspace / "bundle/bundle.json")
    require(bundle["schemaVersion"] == 1, "BAD_BUNDLE_SCHEMA")
    require(read(workspace / "bundle-receipt.json")["bundleSha256"] == digest(bundle), "BUNDLE_CHANGED")
    voice = read(workspace / "bundle/voice/manifest.json")
    require(voice["schemaVersion"] == 2 and voice["providerId"] == "qwen3-tts-sohee-local", "BAD_VOICE_SCHEMA")
    clips = {c["clipId"]: c for c in voice["clips"]}
    require(len(clips) == len(voice["clips"]) == 3 * len(bundle["characters"]), "DUPLICATE_OR_MISSING_CLIPS")
    ledger = read(state / "recipes.json")
    rows = []
    for entry in bundle["characters"]:
        directory = state / "characters" / entry["characterId"]
        artifact, plan = read(directory / "character.json"), read(directory / "plan.json")
        recipe = ledger["journeys"][entry["journeyId"]]["recipe"]
        require(entry["visual"] == visual_from_recipe(recipe) and entry["visualSha256"] == digest(entry["visual"]), "VISUAL_HASH_OR_SOURCE_CHANGED")
        require(entry["recipeSha256"] == digest(recipe) == plan["recipeSha256"] and artifact["creativeRecipe"] == recipe, "RECIPE_HASH_CHANGED")
        require(plan["planSha256"] == digest({k: v for k, v in plan.items() if k != "planSha256"}) == entry["sourcePlanSha256"], "PLAN_HASH_CHANGED")
        binding = plan["voice"]
        require(binding["bindingId"] == "dvb-" + digest({k: v for k, v in binding.items() if k != "bindingId"})[:32], "BINDING_HASH_CHANGED")
        require(artifact["voiceBinding"] == binding and binding["bindingId"] == entry["bindingId"] and binding["profileId"] == entry["voiceProfileId"], "BOUND_CHARACTER_CHANGED")
        require(entry["directionSha256"] == hashlib.sha256(binding["direction"].encode()).hexdigest(), "DIRECTION_HASH_CHANGED")
        validate_voice_join(entry, voice)
        for category, clip_id in entry["clipIds"].items():
            clip = clips[clip_id]
            source_entry = artifact["clips"][category]
            source_audio = directory / source_entry["audioPath"]
            exported = workspace / "bundle/voice" / clip["audioPath"]
            require(exported.resolve().parent == (workspace / "bundle/voice").resolve(), "BAD_AUDIO_PATH")
            actual = dynamic.inspect_wav(exported)
            require(all(clip[k] == v for k, v in actual.items()), "EXPORTED_WAV_CHANGED")
            require(file_sha(source_audio) == file_sha(exported) == source_entry["audioSha256"], "SOURCE_WAV_BYTES_CHANGED")
            require(clip["text"] == plan["utterances"][category] == source_entry["text"] and clip["textSha256"] == hashlib.sha256(clip["text"].encode()).hexdigest(), "EXACT_TEXT_CHANGED")
        rows.append({"caseId": entry["caseId"], "characterId": entry["characterId"], "displayName": entry["displayName"],
                     "bodyFamily": entry["visual"]["bodyFamily"], "motif": entry["visual"]["motif"], "purpose": entry["visual"]["purpose"],
                     "visualSha256": entry["visualSha256"], "bindingId": entry["bindingId"]})
    families = sorted({c["visual"]["bodyFamily"] for c in bundle["characters"]})
    if expected_characters is not None:
        require(len(rows) == expected_characters, "UNEXPECTED_CHARACTER_COUNT")
    if expected_bodies is not None:
        require(len(families) == expected_bodies, "UNEXPECTED_BODY_COUNT")
    original_ids = {read(p)["characterId"] for p in (SOURCE / "characters").glob("*/character.json")}
    return {"status": "PASS", "bundleId": bundle["bundleId"], "characters": len(rows), "bodyFamilies": families,
            "actualWavClips": len(clips), "originalCharactersReused": len(original_ids),
            "newCharactersGenerated": len(set(c["characterId"] for c in rows) - original_ids),
            "exportPreservesSourceWavBytes": True, "visualSourceIdentityVerified": True,
            "humanCutenessOrCollectibilityEvaluated": False, "androidRuntimeVerifiedHere": False, "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--expected-characters", type=int)
    parser.add_argument("--expected-bodies", type=int)
    args = parser.parse_args()
    print(json.dumps(verify(args.workspace.resolve(), args.expected_characters, args.expected_bodies), ensure_ascii=False, indent=2))
