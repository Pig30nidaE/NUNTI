"""Check real output, then restart the generator and prove identity drift is rejected."""
from __future__ import annotations

import array
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import wave

from generate import canonical, digest, HERE, ROOT, TEXTS, validate_cached_metadata
from verify_cache_provenance import run_provenance_probes


def main() -> None:
    binding = json.loads((HERE / "binding.json").read_text())
    expected_sha = hashlib.sha256(canonical(binding["binding"])).hexdigest()
    assert binding["bindingSha256"] == expected_sha
    assert binding["bindingId"] == "qvi-" + expected_sha[:32]
    assert binding["binding"]["reference"]["audioSha256"] == digest(HERE / "reference.wav")
    assert binding["binding"]["reference"]["realPersonReference"] is False
    lock = json.loads((HERE / "model-lock.json").read_text())
    assert lock["newDownloadBytes"] < 3_000_000_000
    assert binding["binding"]["baseModel"]["modelLockSha256"] == digest(HERE / "model-lock.json")
    clips = []
    for clip_id, text in TEXTS.items():
        audio = HERE / "samples" / (clip_id + ".wav")
        metadata = json.loads(audio.with_suffix(".json").read_text())
        validate_cached_metadata(clip_id, text, binding, audio, metadata)
        assert metadata["bindingId"] == binding["bindingId"]
        assert metadata["bindingSha256"] == binding["bindingSha256"]
        assert metadata["referenceAudioSha256"] == digest(HERE / "reference.wav")
        assert metadata["referenceText"] == binding["binding"]["reference"]["text"]
        assert metadata["text"] == text
        assert metadata["textSha256"] == hashlib.sha256(text.encode()).hexdigest()
        assert metadata["audioSha256"] == digest(audio)
        assert metadata["baseRevision"] == lock["revision"]
        assert metadata["voiceIdentityAcrossTextsVerified"] is False
        with wave.open(str(audio), "rb") as source:
            assert source.getnchannels() == 1
            assert source.getsampwidth() == 2
            assert source.getframerate() == 24000
            assert source.getnframes() == metadata["frames"]
            values = array.array("h", source.readframes(source.getnframes()))
        if sys.byteorder != "little":
            values.byteswap()
        assert values and any(values)
        clipped = sum(value in {-32768, 32767} for value in values)
        assert clipped == 0
        clips.append({"clipId": clip_id, "audioSha256": digest(audio),
                      "durationSeconds": len(values) / 24000, "fullScaleSamples": clipped,
                      "sameBinding": True, "sameReference": True, "exactTextMetadata": True})
    protected = [HERE / "binding.json", HERE / "reference.wav", HERE / "model-lock.json"]
    protected.extend(sorted((HERE / "samples").glob("*")))
    before = {str(path.relative_to(HERE)): digest(path) for path in protected}
    command = [sys.executable, str(HERE / "generate.py")]
    run = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    events = [json.loads(line) for line in run.stdout.splitlines()]
    assert sum(event["event"] == "cache-hit" for event in events) == 2
    assert events[-1] == {"event": "all-cached", "modelLoaded": False}
    after = {str(path.relative_to(HERE)): digest(path) for path in protected}
    assert before == after
    changes = []
    altered_ref = ROOT / ".local/journey-voice-v3-identity/changed-reference-negative-probe.wav"
    altered = bytearray((HERE / "reference.wav").read_bytes())
    altered[-2] ^= 1
    altered_ref.write_bytes(altered)
    for label, arguments, reason in [
        ("changed temperature", ["--temperature", "0.71"], "BINDING_CHANGED"),
        ("changed reference audio", ["--reference", str(altered_ref)], "REFERENCE_CHANGED"),
        ("changed reference transcript", ["--reference-text", "다른 문장입니다."], "BINDING_CHANGED"),
    ]:
        rejection = subprocess.run(command + arguments, capture_output=True, text=True, timeout=60)
        assert rejection.returncode != 0
        assert reason in rejection.stderr
        assert '"event": "loading"' not in rejection.stdout
        changes.append({"case": label, "returnCode": rejection.returncode,
                        "reason": reason, "rejectedBeforeModelLoad": True})
    assert before == {str(path.relative_to(HERE)): digest(path) for path in protected}
    original_environment = json.loads((HERE / "environment-before.json").read_text())
    current_packages = sorted([d.metadata["Name"], d.version] for d in importlib.metadata.distributions())
    assert current_packages == original_environment["packages"]
    assert digest(HERE.parent / "requirements.lock.txt") == original_environment["originalRequirementsLockSha256"]
    provenance = run_provenance_probes()
    result = {
        "status": "PASSED_REAL_AUDIO_REFERENCE_BINDING_RESTART_CACHE_AND_DRIFT_REJECTION",
        "bindingId": binding["bindingId"], "clips": clips,
        "processRestart": {"returnCode": run.returncode, "events": events,
                           "allSevenImmutableFileHashesUnchanged": before == after,
                           "fileHashesBefore": before, "fileHashesAfter": after},
        "driftRejections": changes, "existingQwenPackageInventoryUnchanged": True,
        "metadataProvenanceRejections": {"caseCount": provenance["caseCount"],
                                        "report": "cache-provenance-verification.json",
                                        "modelLoads": 0, "newInferences": 0},
        "humanListeningVerified": False, "crossTextVoiceIdentityVerified": False,
        "doesNotProve": ["perceptual speaker identity", "Korean phoneme accuracy",
                         "naturalness of new Base clips", "production readiness"],
    }
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "clips": len(clips),
                      "cacheHits": 2, "driftRejections": len(changes)}, indent=2))


if __name__ == "__main__":
    main()
