"""Verify actual preset files and restart-cache behavior; do not infer voice quality."""
from __future__ import annotations

import array
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import wave

from generate import HERE, ROOT, digest, expected, validate


def main() -> None:
    config = json.loads((HERE / "config.json").read_text())
    lock = json.loads((HERE / "model-lock.json").read_text())
    assert config["speaker"] == "Sohee" and config["language"] == "Korean"
    assert lock["speakerId"] == 2864 and lock["languageId"] == 2064
    assert config["referenceAudio"] is None
    clips = []
    protected = [HERE / "config.json", HERE / "model-lock.json"]
    for condition in config["conditions"]:
        for sentence in config["sentences"]:
            clip_id = condition["id"] + "-" + sentence["id"]
            audio = HERE / "samples" / (clip_id + ".wav")
            metadata = audio.with_suffix(".json")
            record = json.loads(metadata.read_text())
            validate(audio, record, expected(clip_id, sentence, condition, config, lock))
            assert record["postprocessing"] == "none; raw model waveform only encoded as PCM16 WAV"
            with wave.open(str(audio), "rb") as source:
                values = array.array("h", source.readframes(source.getnframes()))
            if sys.byteorder != "little":
                values.byteswap()
            assert values and any(values)
            full_scale = sum(value in {-32768, 32767} for value in values)
            assert full_scale == 0
            protected.extend([audio, metadata])
            clips.append({"clipId": clip_id, "audioSha256": digest(audio), "fullScaleSamples": full_scale,
                          "durationSeconds": record["durationSeconds"], "speakerId": record["speakerId"],
                          "exactTextMetadata": True, "noReferenceAudio": True})
    before = {str(path.relative_to(HERE)): digest(path) for path in protected}
    restart = subprocess.run([sys.executable, str(HERE / "generate.py")],
                             capture_output=True, text=True, timeout=60)
    assert restart.returncode == 0, restart.stderr
    events = [json.loads(line) for line in restart.stdout.splitlines()]
    assert sum(event["event"] == "cache-hit" for event in events) == 4
    assert events[-1] == {"event": "all-cached", "modelLoaded": False}
    after = {str(path.relative_to(HERE)): digest(path) for path in protected}
    assert before == after
    environment = json.loads((HERE / "environment-before.json").read_text())
    assert sorted([item.metadata["Name"], item.version] for item in importlib.metadata.distributions()) == environment["packages"]
    assert digest(ROOT / "prototypes/journey_voice_v3/requirements.lock.txt") == environment["existingRequirementsLockSha256"]
    result = {"status": "PASSED_REAL_SOHEE_PRESET_AUDIO_FORMAT_IDENTITY_AND_CACHE",
              "clips": clips, "restart": {"events": events, "filesUnchanged": before == after,
                                           "fileHashesBefore": before, "fileHashesAfter": after},
              "existingQwenEnvironmentPackagesUnchanged": True,
              "humanListeningVerified": False, "productQualityApproved": False,
              "doesNotProve": ["natural Korean pronunciation", "naturalness", "cuteness", "quality approval"]}
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "clips": len(clips), "cacheHits": 4,
                      "filesUnchanged": before == after}, indent=2))


if __name__ == "__main__":
    main()
