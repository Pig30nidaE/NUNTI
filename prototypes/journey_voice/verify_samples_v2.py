#!/usr/bin/env python3
"""Verify real v2 source/processed WAVs and preservation of the v1 baseline."""
import json
from pathlib import Path
import wave
from voice_cli import HERE, read_json, sha


def verify():
    baseline = read_json(HERE / "v1-baseline-hashes.json")
    for relative, digest in baseline["sha256"].items():
        assert sha((HERE / relative).read_bytes()) == digest, f"v1 changed: {relative}"
    manifest_path = HERE / "samples-v2/manifest.json"
    manifest = read_json(manifest_path)
    assert manifest["candidateVersion"] == 2 and len(manifest["clips"]) == 6
    assert len(manifest["comparisonClips"]) == 3
    common = [c for c in manifest["clips"] if c["category"] == "common"]
    assert [c["speakerId"] for c in common] == ["F3", "F4", "F5"]
    assert all(c["profileId"].endswith("-v2") for c in common)
    assert len({c["audioSha256"] for c in common}) == 3
    assert len({c["text"] for c in common}) == 1
    assert common[0]["text"] == read_json(HERE / "samples/manifest.json")["commonComparisonText"]
    checks = []
    for clip in manifest["clips"]:
        assert clip["textSha256"] == sha(clip["text"].encode("utf-8"))
        processed = manifest_path.parent / clip["audioPath"]
        raw = manifest_path.parent / clip["sourceRawAudioPath"]
        assert processed.parent == raw.parent == manifest_path.parent
        assert sha(processed.read_bytes()) == clip["audioSha256"]
        assert sha(raw.read_bytes()) == clip["sourceRawAudioSha256"]
        assert clip["audioSha256"] != clip["sourceRawAudioSha256"]
        with wave.open(str(processed), "rb") as output, wave.open(str(raw), "rb") as source:
            assert output.getnframes() == source.getnframes() > 0
            assert output.getframerate() == source.getframerate() == clip["sampleRateHz"] == 44100
            assert output.getsampwidth() == source.getsampwidth() == 2
            assert output.getnchannels() == source.getnchannels() == 1
            assert round(output.getnframes() / output.getframerate() * 1000) == clip["durationMs"] <= 30000
        assert clip["frameCountPreserved"] is True
        assert clip["postprocess"]["semitones"] == clip["binding"]["postprocess"]["semitones"] == 3.0
        assert clip["outputSignalMetrics"]["fullScaleClippedSampleCount"] == 0
        assert clip["outputSignalMetrics"]["rmsAmplitude"] > 0.001
        assert clip["firstSyllableListeningAssessed"] is False
        assert clip["koreanIntelligibilityAssessed"] is False
        checks.append({"clipId": clip["clipId"], "speakerId": clip["speakerId"], "durationMs": clip["durationMs"], "pitchSemitones": 3, "framesPreserved": True, "clippedSamples": 0})
    for comparison in manifest["comparisonClips"]:
        assert sha((manifest_path.parent / comparison["audioPath"]).read_bytes()) == comparison["audioSha256"]
        assert comparison["postprocess"] is None
    return {"status": "PASS", "v1BaselineFilesPreserved": len(baseline["sha256"]), "processedWavClips": 6, "matchedSourceWavClips": 6, "sourceSpeakerComparisonPairs": 3, "humanCutenessEvaluated": False, "koreanIntelligibilityEvaluated": False, "firstSyllableListeningEvaluated": False, "dspArtifactsListeningEvaluated": False, "clips": checks}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
