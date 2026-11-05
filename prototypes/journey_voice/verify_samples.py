#!/usr/bin/env python3
"""Verify saved real WAV assets/provenance, without substituting human listening."""
import argparse
import array
import hashlib
import json
from pathlib import Path
import sys
import wave

HERE = Path(__file__).resolve().parent


def verify(manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["providerId"] == "supertonic3-local-catalog"
    assert len(manifest["clips"]) == 6
    common = [c for c in manifest["clips"] if c["category"] == "common"]
    assert len(common) == 3
    assert len({c["speakerId"] for c in common}) == 3
    assert len({c["profileId"] for c in common}) == 3
    assert len({c["text"] for c in common}) == 1
    assert len({c["audioSha256"] for c in common}) == 3
    checks = []
    for clip in manifest["clips"]:
        assert clip["textSha256"] == hashlib.sha256(clip["text"].encode("utf-8")).hexdigest()
        path = manifest_path.parent / clip["audioPath"]
        assert path.resolve().parent == manifest_path.parent.resolve()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == clip["audioSha256"]
        with wave.open(str(path), "rb") as handle:
            assert handle.getnchannels() == clip["channels"] == 1
            assert handle.getsampwidth() == clip["sampleWidthBytes"] == 2
            assert handle.getframerate() == clip["sampleRateHz"]
            duration = round(handle.getnframes() * 1000 / handle.getframerate())
            assert duration == clip["durationMs"] and 0 < duration <= 30000
            pcm = array.array("h", handle.readframes(handle.getnframes()))
            if sys.byteorder != "little":
                pcm.byteswap()
            assert max(abs(v) for v in pcm) > 100
            assert len(set(pcm)) > 100
        assert clip["binding"]["speakerId"] == clip["speakerId"]
        assert clip["binding"]["profileId"] == clip["profileId"]
        assert clip["audibleQualityAssessed"] is False
        checks.append({"clipId": clip["clipId"], "speakerId": clip["speakerId"], "durationMs": duration, "audioSha256": clip["audioSha256"]})
    return {"status": "PASS", "verifiedRealWavClips": len(checks), "threeDifferentSpeakerAssets": True, "humanListeningEvaluated": False, "clips": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=HERE / "samples/manifest.json")
    print(json.dumps(verify(parser.parse_args().manifest), indent=2))
