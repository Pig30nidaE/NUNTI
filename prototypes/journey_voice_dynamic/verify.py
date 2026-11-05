"""Independently inspect four committed demo plans and twelve WAVs, without ML imports."""
from __future__ import annotations

import argparse
import array
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL_LOCK = ROOT / "prototypes/qwen_sohee_audition/model-lock.json"
REQUIREMENTS = ROOT / "prototypes/journey_voice_v3/requirements.lock.txt"
EXPECTED_COMMON = "안녕. 오늘은 나랑 같이 가자."
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(value: bool, label: str) -> None:
    checks.append({"name": label, "passed": bool(value)})
    if not value:
        raise ValueError(label)


def pcm(path: Path) -> dict:
    with wave.open(str(path), "rb") as source:
        rate, channels, width, frames = source.getframerate(), source.getnchannels(), source.getsampwidth(), source.getnframes()
        require((rate, channels, width, source.getcomptype()) == (24000, 1, 2, "NONE"), str(path.relative_to(ROOT)) + ": PCM16 mono 24kHz header")
        body = source.readframes(frames)
    require(0 < frames <= 720000 and len(body) == frames * 2, "PCM data is complete and within thirty seconds")
    values = array.array("h", body)
    if sys.byteorder != "little":
        values.byteswap()
    peak = max(abs(value) for value in values)
    clipped = sum(value in (-32768, 32767) for value in values)
    require(peak > 0 and clipped == 0, "PCM is nonzero and has zero full-scale samples")
    return {"sampleRateHz": rate, "channels": channels, "sampleWidthBytes": width,
            "frames": frames, "durationMs": round(frames * 1000 / rate),
            "audioSha256": sha(path), "pcmPeak": peak, "pcmFullScaleSamples": clipped}


def inspect(state: Path) -> dict:
    ledger = read(state / "recipes.json")
    model_lock = read(MODEL_LOCK)
    requirements = dict(line.split("==", 1) for line in REQUIREMENTS.read_text().splitlines() if line and not line.startswith("#"))
    sites = list((ROOT / ".local/journey-voice-v3/venv/lib").glob("python*/site-packages"))
    require(len(sites) == 1, "Existing TTS environment is unambiguous")
    normalize_package = lambda name: name.lower().replace("_", "-").replace(".", "-")
    installed = {normalize_package(distribution.metadata["Name"]): distribution.version
                 for distribution in importlib.metadata.distributions(path=[str(sites[0])])}
    runtime = sites[0] / "mlx_audio/tts/models/qwen3_tts/qwen3_tts.py"
    require(all(installed.get(normalize_package(name)) == version for name, version in requirements.items()), "Existing installed packages match recorded requirements")
    paths = sorted((state / "characters").glob("*/character.json"))
    require(len(paths) == 4, "Four committed character artifacts exist")
    originals = [state / "recipes.json", MODEL_LOCK, REQUIREMENTS, HERE / "engine.py", runtime]
    for path in paths:
        originals.extend([path, path.with_name("plan.json")])
        record = read(path)
        for clip in record["clips"].values():
            audio = (path.parent / clip["audioPath"]).resolve()
            require(audio.is_relative_to(path.parent.resolve()), "Audio path remains inside its character directory")
            originals.extend([audio, audio.with_name("metadata.json")])
    before = {str(path.relative_to(ROOT)): sha(path) for path in originals}
    records, clips, identities, common = [], [], [], []
    for path in paths:
        artifact = read(path)
        plan = read(path.with_name("plan.json"))
        recipe = artifact["creativeRecipe"]
        voice = plan["voice"]
        identity = voice["engineIdentity"]
        character = artifact["characterId"]
        require(path.parent.name == character == plan["characterId"] == recipe["characterId"] == voice["characterId"], "Character IDs agree across directory, plan, recipe and binding")
        require(artifact["journeyId"] == plan["journeyId"] == recipe["journeyId"] == voice["journeyId"], "Journey IDs agree across artifact and source")
        require(recipe == ledger["journeys"][recipe["journeyId"]]["recipe"], "Artifact uses the first committed ledger recipe")
        require(plan["recipeSha256"] == digest(recipe), "Actual recipe digest matches plan")
        require(plan["planSha256"] == artifact["planSha256"] == digest({key: value for key, value in plan.items() if key != "planSha256"}), "Actual canonical plan digest matches artifact")
        require(voice["bindingId"] == "dvb-" + digest({key: value for key, value in voice.items() if key != "bindingId"})[:32], "Binding ID is derived from the complete voice specification")
        require(artifact["voiceBinding"] == voice, "Character binding is exactly the committed plan binding")
        require(voice["identityKey"] == recipe["voiceIntent"]["identityKey"] and voice["seed"] == int(recipe["seed"], 16) % (2 ** 32), "Voice identity and deterministic seed come from the committed recipe")
        require(voice["requestedCharacterTraits"] == recipe["voiceIntent"]["requested"], "Requested character traits are preserved")
        require(voice["profileId"] == "journey-sohee-" + hashlib.sha256(character.encode()).hexdigest()[:20], "Profile is character scoped")
        require(identity["modelId"] == model_lock["modelId"] == "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit" and identity["revision"] == model_lock["revision"] == "41d3337e8b7f2843a75841595fc14e4b9a7a4b96", "Actual model lock and declared model revision agree")
        require(identity["speaker"] == voice["speaker"] == "Sohee" and identity["speakerId"] == 2864 and identity["languageId"] == 2064 and voice["locale"] == "ko-KR", "Native Korean Sohee preset is explicit")
        require(identity["providerId"] == voice["providerId"] == "qwen3-tts-sohee-local", "Provider identity agrees")
        require(identity["modelLockSha256"] == sha(MODEL_LOCK) and identity["runtimePin"]["requirementsLockSha256"] == sha(REQUIREMENTS) and identity["runtimePin"]["qwenCodeSha256"] == sha(runtime), "Pinned model lock, runtime source and requirements match actual files")
        require(identity["runtimePin"]["packages"] == requirements, "Recorded engine package pins match original requirements")
        require(voice["engineFingerprint"] == digest({"identity": identity, "adapterSha256": sha(HERE / "engine.py")}), "Engine fingerprint includes actual adapter source and identity")
        require(identity["generation"] == {"temperature": 0.7, "topP": 0.95, "topK": 50, "repetitionPenalty": 1.05, "maxTokens": 375}, "Generation settings match the accepted Sohee baseline")
        require(identity["defaults"]["referenceAudio"] is None and voice["postprocessing"] == "none", "No reference audio or DSP is bound")
        require(set(plan["utterances"]) == set(artifact["clips"]) == {"greeting", "arrival", "common"}, "Each character exposes exactly the three prepared categories")
        require(plan["utterances"]["common"] == EXPECTED_COMMON, "Common comparison text is identical")
        require(artifact["displayName"] == plan["displayName"], "Generated display name is preserved")
        require(artifact["imageGenerated"] is False and artifact["androidConnected"] is False, "Artifacts do not claim rendered avatar or Android integration")
        purpose = recipe["creativeInspiration"]["purpose"]
        keywords = {"rest": "calm warmth", "camping": "warm curiosity", "exhibition": "quiet delight"}
        require(purpose in keywords and keywords[purpose] in voice["direction"] and voice["direction"].startswith("Native Korean conversational speech with a small smile"), "Committed purpose is reflected in the synthesis direction")
        for category, item in artifact["clips"].items():
            text = plan["utterances"][category]
            text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            seed = int(hashlib.sha256((str(voice["seed"]) + text_sha).encode()).hexdigest()[:8], 16)
            fields = {"schemaVersion": 1, "characterId": character, "journeyId": plan["journeyId"],
                      "bindingId": voice["bindingId"], "profileId": voice["profileId"], "providerId": voice["providerId"],
                      "speaker": "Sohee", "locale": "ko-KR", "engineFingerprint": voice["engineFingerprint"],
                      "direction": voice["direction"], "text": text, "textSha256": text_sha, "seed": seed,
                      "referenceAudio": None, "postprocessing": "none"}
            key = digest(fields)
            require(item["cacheKey"] == key and item["audioPath"] == "clips/" + key + "/audio.wav", "Cache path derives from complete clip provenance")
            audio = path.parent / item["audioPath"]
            metadata_path = audio.with_name("metadata.json")
            metadata = read(metadata_path)
            require(all(metadata.get(key) == expected for key, expected in fields.items()), "All actual metadata identity, text, seed and direction fields match the plan")
            metrics = pcm(audio)
            require(all(metadata.get(key) == value for key, value in metrics.items() if key != "pcmPeak"), "Actual WAV header, frame count, duration, hash and clipping match metadata")
            require(item["text"] == text and item["textSha256"] == text_sha and item["audioSha256"] == metrics["audioSha256"] and item["durationMs"] == metrics["durationMs"], "Character clip pointer agrees with actual audio and original text")
            require(type(metadata["tokenCount"]) is int and 0 < metadata["tokenCount"] < 375 and metadata["termination"]["maxTokens"] == 375 and metadata["termination"]["tokenLimitReached"] is False and metadata["termination"]["directEosObserved"] is False, "Reported token count stays below cap without claiming direct EOS observation")
            require(math.isfinite(metadata["rawFloatPeak"]) and 0 < metadata["rawFloatPeak"] < 1 and metadata["rawSamplesAtOrAboveFullScale"] == 0, "Recorded raw waveform has no full-scale samples")
            clips.append({"characterId": character, "category": category, "file": str(audio.relative_to(ROOT)),
                          "audioSha256": metrics["audioSha256"], "metadataSha256": sha(metadata_path),
                          "text": text, "textSha256": text_sha, "direction": metadata["direction"],
                          "seed": seed, "tokenCount": metadata["tokenCount"], "actualPcm": metrics})
            if category == "common":
                common.append(metrics["audioSha256"])
        identities.append(identity)
        records.append({"characterId": character, "journeyId": plan["journeyId"], "displayName": plan["displayName"],
                        "planSha256": plan["planSha256"], "bindingId": voice["bindingId"],
                        "direction": voice["direction"], "seed": voice["seed"], "recipe": recipe})
    require(len(clips) == 12, "Twelve actual demo WAVs were inspected")
    require(all(identity == identities[0] for identity in identities), "All characters use the same fixed Sohee engine")
    require(len({row["characterId"] for row in records}) == len({row["bindingId"] for row in records}) == len({row["planSha256"] for row in records}) == 4, "Four character, binding and plan identities are distinct")
    coast = [row for row in records if row["journeyId"] in {"synthetic-coast-001", "synthetic-coast-002"}]
    require(len(coast) == 2 and coast[0]["recipe"]["creativeInspiration"] == coast[1]["recipe"]["creativeInspiration"], "Two independent journeys have identical semantic route, destination and purpose inputs")
    require(coast[0]["direction"] != coast[1]["direction"] and coast[0]["seed"] != coast[1]["seed"] and coast[0]["recipe"]["design"]["bodyFamily"] != coast[1]["recipe"]["design"]["bodyFamily"], "New journey body history changes the bound delivery direction and seed")
    after = {str(path.relative_to(ROOT)): sha(path) for path in originals}
    require(before == after, "Read-only inspection preserves all original demo and pinned runtime bytes")
    return {"characters": [{key: value for key, value in record.items() if key != "recipe"} for record in records],
            "clips": clips, "engineIdentity": identities[0], "protectedFileHashesBefore": before,
            "protectedFileHashesAfter": after, "commonText": EXPECTED_COMMON,
            "commonWaveformsHaveDifferentHashes": len(set(common)) == 4,
            "waveformDifferenceInterpretation": "Different encoded bytes are not evidence of perceptually distinct speakers or cuteness."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=HERE / "demo")
    args = parser.parse_args()
    result = {"checkedAt": datetime.now(timezone.utc).isoformat(), "providerRequestsPerformed": 0,
              "modelLoads": 0, "newInferences": 0, "humanQualityApprovedByThisTool": False,
              "doesNotProve": ["perceptually distinct voices", "naturalness or cuteness of each new direction",
                               "pronunciation accuracy", "image generation", "Android playback or integration"]}
    try:
        result.update(inspect(args.state_dir.resolve()))
        success = True
    except (OSError, ValueError, KeyError, TypeError, wave.Error) as error:
        success = False
        result["error"] = {"type": type(error).__name__, "message": str(error)}
    result.update(status="파일정합성 통과" if success else "파일정합성 확인 실패",
                  checks=checks, checksTotal=len(checks), checksPassed=sum(item["passed"] for item in checks))
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "checksPassed", "checksTotal", "modelLoads", "newInferences")}, ensure_ascii=False))
    if not success:
        print(json.dumps(result["error"], ensure_ascii=False))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
