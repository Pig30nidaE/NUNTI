#!/usr/bin/env python3
"""Compare real fresh generation, independent restart and reroute CLI evidence."""
import json
from worker import DEFAULT_WORKSPACE, HERE, SOURCE, file_sha, read, require


def verify():
    fresh = read(HERE / "generation-result.json")
    restart = read(HERE / "restart-result.json")
    reroute = read(HERE / "reroute-result.json")
    require(fresh["modelLoaded"] and len(fresh["characters"]) == 4, "EXPECTED_FOUR_NEW_GENERATED_CHARACTERS")
    require(sum(c["cacheHits"] for c in fresh["characters"]) == 0, "FRESH_GENERATION_WAS_CACHED")
    require(not restart["modelLoaded"] and len(restart["characters"]) == 8 and sum(c["cacheHits"] for c in restart["characters"]) == 24, "RESTART_DID_NOT_REUSE_ALL_CLIPS")
    require(not reroute["modelLoaded"] and len(reroute["characters"]) == 1 and reroute["characters"][0]["cacheHits"] == 3, "REROUTE_DID_NOT_REUSE_CLIPS")
    current = {c["characterId"]: c for c in restart["characters"]}
    inference = []
    for entry in fresh["characters"]:
        previous = current[entry["characterId"]]
        require(all(previous[k] == entry[k] for k in ("characterId", "journeyId", "displayName", "bindingId", "clips")), "RESTART_IDENTITY_CHANGED")
        for category, clip in entry["clips"].items():
            path = DEFAULT_WORKSPACE / "state/characters" / entry["characterId"] / clip["audioPath"]
            metadata = read(path.with_name("metadata.json"))
            require(file_sha(path) == clip["audioSha256"] == metadata["audioSha256"], "FRESH_WAV_CHANGED")
            require(metadata["inferenceSeconds"] > 0 and metadata["tokenCount"] > 0 and not metadata["termination"]["tokenLimitReached"], "NOT_ACTUAL_COMPLETED_MODEL_GENERATION")
            inference.append({"characterId": entry["characterId"], "category": category, "durationMs": metadata["durationMs"],
                              "inferenceSeconds": metadata["inferenceSeconds"], "audioSha256": metadata["audioSha256"],
                              "pcmFullScaleSamples": metadata["pcmFullScaleSamples"]})
    r = reroute["characters"][0]
    require(all(r[k] == current[r["characterId"]][k] for k in ("characterId", "journeyId", "displayName", "bindingId", "clips")), "REROUTE_IDENTITY_CHANGED")
    require(fresh["bundle"]["bundleId"] == restart["bundle"]["bundleId"] == reroute["bundle"]["bundleId"], "BUNDLE_CHANGED_AFTER_RESTART_OR_REROUTE")
    for path in (SOURCE / "characters").glob("*/character.json"):
        original = read(path)
        require(original["clips"] == current[original["characterId"]]["clips"], "ORIGINAL_PRIMARY_CLIPS_CHANGED")
    return {"status": "PASS", "newModelProcesses": 1, "newCharactersActuallyGenerated": 4, "newWavClipsActuallySynthesized": 12,
            "originalCharactersCopied": 4, "originalPrimaryClipsReused": 12,
            "restartModelLoaded": False, "restartClipCacheHits": 24, "rerouteModelLoaded": False, "rerouteClipCacheHits": 3,
            "initialBundleIdPreserved": fresh["bundle"]["bundleId"], "bindingAndAudioHashesPreserved": True,
            "humanKoreanListeningEvaluated": False, "newGeneration": inference}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
