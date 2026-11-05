#!/usr/bin/env python3
"""Generate character-specific Korean voice assets from a journey, fully offline."""
import argparse
from contextlib import contextmanager, redirect_stdout
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "prototypes/journey_characters"))
import recipe_cli as recipes
from settings import canonical, character_plan, digest

DEFAULT_STATE = ROOT / ".local/journey-voice-dynamic/state"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".dynamic-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def owning_lane(state):
    """One writer owns recipe history, plans, model execution, and commits per state."""
    state.mkdir(parents=True, exist_ok=True)
    with (state / ".pipeline.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def character_directory(state, character_id):
    require(isinstance(character_id, str) and re.fullmatch(r"nunti-[0-9a-f]{24}", character_id), "INVALID_CHARACTER_ID")
    return state / "characters" / character_id


def validate_plan(plan, recipe, engine):
    body = {key: value for key, value in plan.items() if key != "planSha256"}
    require(plan.get("planSha256") == digest(body), "VOICE_PLAN_CHANGED")
    voice = plan["voice"]
    require(voice["bindingId"] == "dvb-" + digest({key: value for key, value in voice.items() if key != "bindingId"})[:32], "VOICE_BINDING_CHANGED")
    require(plan["recipeSha256"] == digest(recipe) and plan["characterId"] == voice["characterId"] == recipe["characterId"]
            and plan["journeyId"] == voice["journeyId"] == recipe["journeyId"], "CHARACTER_RECIPE_CHANGED")
    require(voice["engineFingerprint"] == engine.fingerprint and voice["engineIdentity"] == engine.identity, "BOUND_ENGINE_UNAVAILABLE_NO_MIGRATION")
    require(voice["speaker"] == "Sohee" and voice["locale"] == "ko-KR" and voice["postprocessing"] == "none", "UNSUPPORTED_VOICE_BINDING")
    return plan


def inspect_wav(path):
    with wave.open(str(path), "rb") as source:
        require((source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) == (1, 2, 24000, "NONE"), "INVALID_AUDIO_FORMAT")
        frames = source.getnframes()
        require(0 < frames <= 24000 * 30, "INVALID_AUDIO_DURATION")
        raw = source.readframes(frames)
        require(len(raw) == frames * 2 and any(raw), "INVALID_AUDIO_CONTENT")
    return {"sampleRateHz": 24000, "channels": 1, "sampleWidthBytes": 2, "frames": frames,
            "durationMs": round(frames * 1000 / 24000), "audioSha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def clip_fields(plan, text):
    require(isinstance(text, str) and 0 < len(text) <= 100 and text.strip(), "TEXT_MUST_BE_1_TO_100_CHARACTERS")
    require(re.fullmatch(r"[가-힣ㄱ-ㅎㅏ-ㅣA-Za-z0-9 \t\n.,!?;:'\"()%\-]+", text), "UNSUPPORTED_TEXT_CHARACTER")
    voice = plan["voice"]
    text_sha = hashlib.sha256(text.encode()).hexdigest()
    return {"schemaVersion": 1, "characterId": voice["characterId"], "journeyId": voice["journeyId"],
            "bindingId": voice["bindingId"], "profileId": voice["profileId"],
            "providerId": voice["providerId"], "speaker": voice["speaker"], "locale": voice["locale"],
            "engineFingerprint": voice["engineFingerprint"], "direction": voice["direction"],
            "text": text, "textSha256": text_sha,
            "seed": int(hashlib.sha256((str(voice["seed"]) + text_sha).encode()).hexdigest()[:8], 16),
            "referenceAudio": None, "postprocessing": "none"}


def synthesize(plan, text, directory, engine):
    fields = clip_fields(plan, text)
    key = digest(fields)
    final = directory / "clips" / key
    index_path = directory / "clip-index.json"
    index = read_json(index_path) if index_path.exists() else {}
    require(isinstance(index, dict), "INVALID_CLIP_INDEX")
    if key in index:
        require(final.is_dir(), "COMMITTED_AUDIO_MISSING")
    if final.exists():
        metadata = read_json(final / "metadata.json")
        for name, value in fields.items():
            require(metadata.get(name) == value, "CACHED_PROVENANCE_CHANGED:" + name)
        actual = inspect_wav(final / "audio.wav")
        require(all(metadata.get(name) == value for name, value in actual.items()), "CACHED_AUDIO_CHANGED")
        entry = {"bindingId": fields["bindingId"], "textSha256": fields["textSha256"], "audioSha256": actual["audioSha256"]}
        require(key not in index or index[key] == entry, "CLIP_INDEX_CHANGED")
        if key not in index:
            index[key] = entry
            atomic_json(index_path, index)
        return {"cacheKey": key, "audioPath": str(final / "audio.wav"), "metadata": metadata}, True
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="." + key + ".pending-", dir=final.parent))
    try:
        audio = temporary / "audio.wav"
        with redirect_stdout(sys.stderr):
            metrics = engine.render(text, fields["direction"], fields["seed"], audio)
        actual = inspect_wav(audio)
        require(all(metrics.get(name) == value for name, value in actual.items()), "RENDER_METADATA_MISMATCH")
        metadata = {**metrics, **fields, **actual}
        with audio.open("rb") as handle:
            os.fsync(handle.fileno())
        atomic_json(temporary / "metadata.json", metadata)
        fsync_directory(temporary)
        os.rename(temporary, final)
        fsync_directory(final.parent)
        index[key] = {"bindingId": fields["bindingId"], "textSha256": fields["textSha256"], "audioSha256": actual["audioSha256"]}
        atomic_json(index_path, index)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {"cacheKey": key, "audioPath": str(final / "audio.wav"), "metadata": metadata}, False


def persisted_plan(recipe, state, engine):
    directory = character_directory(state, recipe["characterId"])
    path = directory / "plan.json"
    if path.exists():
        return validate_plan(read_json(path), recipe, engine), directory
    require(not directory.exists() or all(path.is_file() and path.name.startswith(".dynamic-")
                                         for path in directory.iterdir()), "CHARACTER_DIRECTORY_WITHOUT_PLAN")
    plan = character_plan(recipe, engine)
    validate_plan(plan, recipe, engine)
    atomic_json(path, plan)
    return plan, directory


def generate(request_paths, state, engine, plan_only=False):
    results = []
    with owning_lane(state):
        registry = read_json(recipes.REGISTRY_PATH)
        for path in request_paths:
            request = recipes.normalize_request(read_json(path), registry)
            ledger_path = state / "recipes.json"
            ledger = recipes.load_ledger(ledger_path)
            recipe, changed = recipes.generate(request, ledger, registry)
            if changed:
                recipes.save_atomic(ledger_path, ledger)
            plan, directory = persisted_plan(recipe, state, engine)
            record = {"characterId": plan["characterId"], "journeyId": plan["journeyId"],
                      "displayName": plan["displayName"], "bindingId": plan["voice"]["bindingId"],
                      "planPath": str(directory / "plan.json"), "clips": {}, "cacheHits": 0}
            if not plan_only:
                artifact_path = directory / "character.json"
                if artifact_path.exists():
                    committed = read_json(artifact_path)
                    require(committed["characterId"] == plan["characterId"] and committed["planSha256"] == plan["planSha256"], "COMMITTED_CHARACTER_CHANGED")
                    for category, text in plan["utterances"].items():
                        expected_key = digest(clip_fields(plan, text))
                        require(committed["clips"][category]["cacheKey"] == expected_key and
                                (directory / "clips" / expected_key).is_dir(), "COMMITTED_AUDIO_MISSING")
                clips = {}
                for category, text in plan["utterances"].items():
                    clip, hit = synthesize(plan, text, directory, engine)
                    record["cacheHits"] += int(hit)
                    relative = str(Path(clip["audioPath"]).relative_to(directory))
                    clips[category] = {"audioPath": relative, "cacheKey": clip["cacheKey"], "text": text,
                                       "audioSha256": clip["metadata"]["audioSha256"],
                                       "textSha256": clip["metadata"]["textSha256"], "durationMs": clip["metadata"]["durationMs"]}
                artifact = {"schemaVersion": 1, "status": "VOICE_READY_AVATAR_RECIPE_ONLY", "creativeRecipe": recipe,
                            "characterId": plan["characterId"], "journeyId": plan["journeyId"],
                            "displayName": plan["displayName"], "voiceBinding": plan["voice"],
                            "planSha256": plan["planSha256"], "clips": clips,
                            "imageGenerated": False, "androidConnected": False,
                            "qualityScope": "Prototype continuation authorized; no final Sohee casting or individual direction quality approval is claimed."}
                if artifact_path.exists():
                    require(read_json(artifact_path) == artifact, "COMMITTED_CHARACTER_CHANGED")
                else:
                    atomic_json(artifact_path, artifact)
                record["clips"] = clips
                record["artifactPath"] = str(artifact_path)
            results.append(record)
    return {"characters": results, "modelLoaded": engine.model_loaded}


def speak(character_id, text, state, engine):
    with owning_lane(state):
        directory = character_directory(state, character_id)
        plan = read_json(directory / "plan.json")
        require(plan["characterId"] == character_id, "CHARACTER_PLAN_WRONG_DIRECTORY")
        ledger = recipes.load_ledger(state / "recipes.json")
        recipe = ledger["journeys"][plan["journeyId"]]["recipe"]
        validate_plan(plan, recipe, engine)
        clip, hit = synthesize(plan, text, directory, engine)
        return {**clip, "cacheHit": hit, "modelLoaded": engine.model_loaded}


def render_listen(state):
    cards = []
    for path in sorted((state / "characters").glob("*/character.json")):
        value = read_json(path)
        text = '<section><h2>' + html.escape(value["displayName"]) + '</h2><p>' + html.escape(value["creativeRecipe"]["creativeInspiration"]["purpose"] or "목적 미지정") + '</p>'
        for category in ("greeting", "arrival", "common"):
            clip = value["clips"][category]
            src = str((path.parent / clip["audioPath"]).relative_to(state))
            text += '<p>' + html.escape({"greeting": "인사", "arrival": "도착용 대사", "common": "같은 문장 비교"}[category]) + '</p><audio controls preload="none" src="' + html.escape(src) + '"></audio><p>' + html.escape(clip["text"]) + '</p>'
        cards.append(text + '</section>')
    body = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Nunti 여정별 목소리</title><style>body{max-width:1100px;margin:32px auto;padding:0 20px;font-family:system-ui;line-height:1.7;background:#f5f3ed;color:#243935}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}section{background:white;padding:24px;border-radius:20px}audio{width:100%}</style><h1>여정에서 생성된 캐릭터와 목소리</h1><p>목적과 캐릭터 형태에 따라 연기 지시와 대사가 달라집니다. 같은 문장도 비교해 보세요. 현재 한국어 Sohee 한 화자 안에서 표현을 조절합니다. 재생은 직접 누를 때 시작합니다.</p><main>' + ''.join(cards) + '</main><p>캐릭터 그림·실시간 차량 입력·앱 자동 재생은 아직 연결하지 않았습니다. 도착용 대사는 미리 준비한 문구입니다.</p></html>'
    (state / "listen.html").write_text(body, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("generate")
    command.add_argument("--input", type=Path, required=True, nargs="+")
    command.add_argument("--plan-only", action="store_true")
    command = commands.add_parser("speak")
    command.add_argument("--character-id", required=True)
    texts = command.add_mutually_exclusive_group(required=True)
    texts.add_argument("--text")
    texts.add_argument("--text-file", type=Path)
    args = parser.parse_args()
    try:
        from engine import SoheeSynthesizer
        engine = SoheeSynthesizer()
        state = args.state_dir.resolve()
        if args.command == "generate":
            result = generate(args.input, state, engine, args.plan_only)
            if not args.plan_only:
                with owning_lane(state):
                    render_listen(state)
        else:
            text = args.text if args.text is not None else args.text_file.read_bytes().decode("utf-8")
            result = speak(args.character_id, text, state, engine)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, TypeError, RuntimeError, wave.Error) as error:
        print("journey voice error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
