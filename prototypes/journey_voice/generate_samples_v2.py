#!/usr/bin/env python3
"""Generate v2 small-character candidates and matched raw-source A/B comparisons."""
import json
from pathlib import Path
from generate_samples import COMMON
from voice_cli import HERE, ROOT, PROVIDER, atomic_write, load_recipe, sha
from voice_v2 import STATE_V2, SynthesizerV2, synthesize_v2

GREETINGS = [
    ("coast", "안녕! 나는 파도빛이야. 오늘 바다에 가는구나. 나도 같이 갈래."),
    ("mountain", "안녕! 나는 이끼별이야. 숲에는 뭐가 있을까? 우리 같이 찾아보자."),
    ("city", "안녕! 나는 조각빛이야. 오늘은 어떤 색을 만날까? 나도 궁금해."),
]


def main():
    engine = SynthesizerV2()
    output = HERE / "samples-v2"
    clips, comparisons = [], []
    for index, (slug, greeting) in enumerate(GREETINGS):
        recipe = load_recipe(ROOT / "prototypes/journey_characters/sample-output.json", index)
        for category, text in (("common", COMMON), ("greeting", greeting)):
            audio, metadata, hit = synthesize_v2(recipe, text, engine=engine)
            raw = audio.parent / metadata["sourceRawAudioCacheName"]
            if not raw.exists() or sha(raw.read_bytes()) != metadata["sourceRawAudioSha256"]:
                raise ValueError("Raw comparison source missing or modified; no automatic regeneration.")
            clip_id = slug + "-" + category
            atomic_write(output / (clip_id + ".wav"), audio.read_bytes())
            atomic_write(output / (clip_id + "-raw.wav"), raw.read_bytes())
            portable = {k: v for k, v in metadata.items() if k != "sourceRawAudioCacheName"}
            portable.update(clipId=clip_id, category=category, audioPath=clip_id + ".wav", sourceRawAudioPath=clip_id + "-raw.wav", candidateVersion=2, variant="B_LIGHT_SPEAKER_PLUS_MILD_PITCH")
            atomic_write(output / (clip_id + ".json"), json.dumps(portable, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
            clips.append(portable)
            if category == "common":
                comparisons.append({
                    "clipId": slug + "-raw", "characterId": metadata["characterId"],
                    "profileId": metadata["profileId"] + "-raw", "speakerId": metadata["speakerId"],
                    "locale": metadata["locale"], "text": text, "textSha256": metadata["textSha256"],
                    "audioPath": clip_id + "-raw.wav", "audioSha256": metadata["sourceRawAudioSha256"],
                    "sampleRateHz": metadata["sampleRateHz"], "sampleWidthBytes": 2, "channels": 1,
                    "durationMs": metadata["durationMs"], "sourceModelRevision": metadata["sourceModelRevision"],
                    "variant": "A_LIGHT_SOURCE_SPEAKER_ONLY", "postprocess": None,
                    "sourceGenerationBindingId": metadata["bindingId"], "signalMetrics": metadata["sourceRawSignalMetrics"],
                    "humanListeningEvaluated": False,
                })
            print(clip_id, metadata["speakerId"], metadata["durationMs"], "cache=" + str(hit))
    manifest = {
        "schemaVersion": 1, "providerId": PROVIDER, "candidateVersion": 2,
        "status": "SMALL_CHARACTER_LISTENING_CANDIDATES_NOT_PRODUCT_APPROVED",
        "selection": {"proposedVariant": "B_LIGHT_SPEAKER_PLUS_MILD_PITCH", "semitones": 3.0, "humanCutenessEvaluation": "PENDING", "rationale": "User requested a smaller, cuter character impression. Source speaker replacement and mild duration-preserving pitch lift are explicit audition changes, not a proven improvement."},
        "commonComparisonText": COMMON,
        "quality": {"koreanListeningEvaluated": False, "cutenessEvaluated": False, "firstSyllableListeningEvaluated": False, "dspArtifactsListeningEvaluated": False, "drivingBehaviorEffectEvaluated": False},
        "generationScope": "Offline development machine synthesis; v1 assets and bindings preserved; no Android/Pleos runtime claim.",
        "clips": clips, "comparisonClips": comparisons,
    }
    atomic_write(output / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    from render_listen_v2 import render
    render()


if __name__ == "__main__":
    main()
