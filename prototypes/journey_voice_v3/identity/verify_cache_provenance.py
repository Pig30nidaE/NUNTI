"""Reject tampered copies through the real cache path, with inference imports forbidden."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from generate import CACHE, HERE, digest


RUNNER = """
import json, sys
from pathlib import Path
class NoInferenceImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'mlx', 'mlx_audio', 'numpy', 'soundfile'}:
            raise RuntimeError('FORBIDDEN_INFERENCE_IMPORT: ' + fullname)
sys.meta_path.insert(0, NoInferenceImports())
import generate as subject
subject.HERE = Path(sys.argv[1])
sys.argv = [subject.__file__]
try:
    subject.main()
finally:
    loaded = [name for name in sys.modules if name.split('.')[0] in {'mlx', 'mlx_audio', 'numpy', 'soundfile'}]
    print(json.dumps({'event': 'inference-import-audit', 'imported': loaded}), flush=True)
"""


def protected_files() -> list[Path]:
    return [HERE / "binding.json", HERE / "reference.wav", HERE / "model-lock.json",
            *sorted((HERE / "samples").glob("*"))]


def run_provenance_probes() -> dict:
    protected = protected_files()
    before = {str(path.relative_to(HERE)): digest(path) for path in protected}
    previous = json.loads((HERE / "verification.json").read_text())
    assert before == previous["processRestart"]["fileHashesBefore"]
    cases = [
        ("generation.temperature", 0.71, "CACHED_PROVENANCE_CHANGED"),
        ("generation.topP", 0.9, "CACHED_PROVENANCE_CHANGED"),
        ("referenceAudioSha256", "0" * 64, "CACHED_PROVENANCE_CHANGED"),
        ("referenceText", "다른 참조 전사입니다.", "CACHED_PROVENANCE_CHANGED"),
        ("baseModelId", "different/base-model", "CACHED_PROVENANCE_CHANGED"),
        ("baseRevision", "0" * 40, "CACHED_PROVENANCE_CHANGED"),
        ("voiceDesignModelId", "different/voice-design", "CACHED_PROVENANCE_CHANGED"),
        ("voiceDesignRevision", "0" * 40, "CACHED_PROVENANCE_CHANGED"),
        ("postprocessing", "pitch shifted", "CACHED_PROVENANCE_CHANGED"),
        ("text", "다른 출력 문장입니다.", "CACHED_PROVENANCE_CHANGED"),
        ("textSha256", "0" * 64, "CACHED_PROVENANCE_CHANGED"),
        ("previewId", "different-preview", "CACHED_PROVENANCE_CHANGED"),
        ("clipId", "different-clip", "CACHED_PROVENANCE_CHANGED"),
        ("audioPath", "different.wav", "CACHED_PROVENANCE_CHANGED"),
        ("audioSha256", "0" * 64, "CACHED_AUDIO_CHANGED"),
        ("sampleRateHz", 22050, "CACHED_AUDIO_METADATA_CHANGED"),
        ("channels", 2, "CACHED_AUDIO_METADATA_CHANGED"),
        ("frames", 1, "CACHED_AUDIO_METADATA_CHANGED"),
        ("durationSeconds", 1.0, "CACHED_AUDIO_METADATA_CHANGED"),
        ("humanListeningVerified", True, "CACHED_PROVENANCE_CHANGED"),
        ("voiceIdentityAcrossTextsVerified", True, "CACHED_PROVENANCE_CHANGED"),
        ("WAV bytes", None, "CACHED_AUDIO_CHANGED"),
    ]
    results = []
    CACHE.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cache-provenance-", dir=CACHE) as temporary:
        workspace = Path(temporary)
        for relative in before:
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / relative, destination)
        copied_bytes = sum(path.stat().st_size for path in workspace.rglob("*") if path.is_file())
        for field, replacement, expected_reason in cases:
            # Each case starts from fresh copies. Original artifacts are read only.
            for relative in before:
                shutil.copy2(HERE / relative, workspace / relative)
            metadata = workspace / "samples/comfort.json"
            record = json.loads(metadata.read_text())
            original_binding_id = record["bindingId"]
            if field == "WAV bytes":
                audio = workspace / "samples/comfort.wav"
                body = bytearray(audio.read_bytes())
                body[-2] ^= 1
                audio.write_bytes(body)
            else:
                target = record
                parts = field.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = replacement
                metadata.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
            assert json.loads(metadata.read_text())["bindingId"] == original_binding_id
            assert digest(workspace / "binding.json") == before["binding.json"]
            run = subprocess.run([sys.executable, "-c", RUNNER, str(workspace)],
                                 cwd=HERE, capture_output=True, text=True, timeout=60)
            assert run.returncode != 0, field
            assert expected_reason in run.stderr, (field, run.stderr)
            assert "FORBIDDEN_INFERENCE_IMPORT" not in run.stderr, (field, run.stderr)
            events = [json.loads(line) for line in run.stdout.splitlines()]
            assert events[-1] == {"event": "inference-import-audit", "imported": []}, field
            assert not any(event["event"] in {"loading", "loaded", "generating"} for event in events)
            results.append({"changedField": field, "returnCode": run.returncode,
                            "reason": run.stderr.splitlines()[-1],
                            "sameBindingIdRetained": True, "bindingFileUnchanged": True,
                            "inferenceModulesImported": events[-1]["imported"]})
    after = {str(path.relative_to(HERE)): digest(path) for path in protected}
    assert before == after
    result = {
        "status": "PASSED_ALL_COPIED_ARTIFACT_PROVENANCE_TAMPERING_REJECTIONS",
        "cases": results, "caseCount": len(results), "copiedArtifactBytes": copied_bytes,
        "originalSevenFilesUnchanged": before == after,
        "matchesOriginalPreReviewHashes": before == previous["processRestart"]["fileHashesBefore"],
        "originalFileHashesBefore": before, "originalFileHashesAfter": after,
        "inferenceImportsForbiddenByProbe": True, "modelLoads": 0, "newInferences": 0,
    }
    (HERE / "cache-provenance-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = run_provenance_probes()
    print(json.dumps({"status": result["status"], "cases": result["caseCount"],
                      "newInferences": result["newInferences"],
                      "originalFilesUnchanged": result["originalSevenFilesUnchanged"]}, indent=2))
