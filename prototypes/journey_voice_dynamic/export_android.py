"""Export verified local character WAVs to a separate Debug-only Android catalog."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from voice_cli import read_json, require, inspect_wav, fsync_directory, ROOT


def publish(path, data, replace=False):
    descriptor, temporary = tempfile.mkstemp(prefix=".dynamic-export-", dir=path.parent.parent)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def output_lock_path(output):
    return ROOT / ".local/journey-voice-dynamic/export-locks" / (hashlib.sha256(str(output.resolve()).encode()).hexdigest() + ".lock")


def export(state, output):
    lock_path = output_lock_path(output)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _export(state, output)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _export(state, output):
    clips = []
    files = {}
    names = []
    for path in sorted((state / "characters").glob("*/character.json")):
        artifact = read_json(path)
        voice = artifact["voiceBinding"]
        require(voice["providerId"] == "qwen3-tts-sohee-local" and voice["speaker"] == "Sohee", "UNSUPPORTED_EXPORT_SOURCE")
        source = {"kind": "directed-sohee-v1", "sourceModelRevision": voice["engineIdentity"]["revision"],
                  "bindingId": voice["bindingId"], "engineFingerprint": voice["engineFingerprint"],
                  "directionSha256": hashlib.sha256(voice["direction"].encode()).hexdigest(), "seed": voice["seed"]}
        names.append({"characterId": artifact["characterId"], "displayName": artifact["displayName"]})
        for category, entry in artifact["clips"].items():
            audio = (path.parent / entry["audioPath"]).resolve()
            require(audio.is_relative_to((path.parent / "clips").resolve()), "INVALID_SOURCE_AUDIO_PATH")
            metadata = read_json(audio.with_name("metadata.json"))
            actual = inspect_wav(audio)
            require(all(metadata.get(key) == value for key, value in actual.items()), "SOURCE_AUDIO_CHANGED")
            require(metadata["bindingId"] == voice["bindingId"] and metadata["direction"] == voice["direction"] and
                    metadata["engineFingerprint"] == voice["engineFingerprint"], "SOURCE_BINDING_CHANGED")
            require(metadata["textSha256"] == hashlib.sha256(entry["text"].encode()).hexdigest() and
                    metadata["audioSha256"] == entry["audioSha256"], "SOURCE_MANIFEST_CHANGED")
            clip_id = artifact["characterId"] + "-" + category
            filename = clip_id + ".wav"
            files[filename] = audio.read_bytes()
            clips.append({"clipId": clip_id, "characterId": artifact["characterId"], "profileId": voice["profileId"],
                          "speakerId": voice["speaker"], "locale": voice["locale"], "text": entry["text"],
                          "textSha256": metadata["textSha256"], "audioPath": filename, "source": source, **actual})
    require(0 < len(clips) <= 100, "EXPORT_REQUIRES_1_TO_100_CLIPS")
    manifest = {"schemaVersion": 2, "providerId": "qwen3-tts-sohee-local", "characters": names,
                "scope": "DEBUG_ONLY; generated WAV playback, not Android model inference or a new avatar renderer",
                "clips": clips}
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    license_source = ROOT / "prototypes/qwen_sohee_audition/licenses"
    if license_source.is_dir():
        for source in sorted(license_source.glob("*")):
            if source.is_file():
                files["LICENSE-" + source.name] = source.read_bytes()
    if output.exists():
        previous = read_json(output / "manifest.json")
        require(previous["schemaVersion"] == 2 and previous["providerId"] == manifest["providerId"], "EXPORT_PROVIDER_CHANGED")
        current_by_id = {clip["clipId"]: clip for clip in clips}
        require(all(current_by_id.get(clip["clipId"]) == clip for clip in previous["clips"]), "EXISTING_CHARACTER_EXPORT_CHANGED")
        actual_names = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
        require(actual_names <= set(files), "EXPORT_TARGET_HAS_UNMANAGED_FILES")
        require(all(name == "manifest.json" or (output / name).read_bytes() == files[name] for name in actual_names), "EXPORTED_ASSET_CHANGED")
        for name, data in files.items():
            if name != "manifest.json" and name not in actual_names:
                publish(output / name, data)
        if previous != manifest:
            publish(output / "manifest.json", files["manifest.json"], replace=True)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".dynamic-export-", dir=output.parent))
        try:
            for name, data in files.items():
                (temporary / name).write_bytes(data)
            temporary.rename(output)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return {"characters": len(names), "clips": len(clips), "manifest": str(output / "manifest.json"), "audioBytesPreserved": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.state_dir.resolve(), args.output_dir.resolve()), ensure_ascii=False, indent=2))
