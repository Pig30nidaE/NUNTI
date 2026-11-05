#!/usr/bin/env python3
"""Generate three speaker comparisons and three journey greetings, with provenance."""
import argparse
import json
from pathlib import Path
from voice_cli import DEFAULT_MODELS, DEFAULT_STATE, HERE, ROOT, PROVIDER, LocalSynthesizer, atomic_write, load_recipe, synthesize

COMMON = "안녕하세요. 오늘의 여행도 함께할게요."
GREETINGS = [
    ("coast", "안녕, 나는 파도빛이야. 바다를 만나러 가는 오늘, 네 곁에서 함께할게."),
    ("mountain", "안녕, 나는 이끼별이야. 숲으로 떠나는 오늘, 작은 발견을 함께 모아 보자."),
    ("city", "안녕, 나는 조각빛이야. 전시를 만나러 가는 오늘, 네 눈에 담긴 색이 궁금해."),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipes", type=Path, default=ROOT / "prototypes/journey_characters/sample-output.json")
    parser.add_argument("--output-dir", type=Path, default=HERE / "samples")
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODELS)
    args = parser.parse_args()
    engine = LocalSynthesizer(args.model_dir)
    clips = []
    for index, (slug, greeting) in enumerate(GREETINGS):
        recipe = load_recipe(args.recipes, index)
        for category, text in (("common", COMMON), ("greeting", greeting)):
            audio, metadata, hit = synthesize(recipe, text, args.state_dir, args.model_dir, engine)
            clip_id = slug + "-" + category
            target = args.output_dir / (clip_id + ".wav")
            atomic_write(target, audio.read_bytes())
            atomic_write(target.with_suffix(".json"), json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
            clips.append(dict(metadata, clipId=clip_id, category=category, audioPath=target.name, generationCacheHit=hit))
            print(f"{clip_id}: {metadata['speakerId']}, {metadata['durationMs']}ms, cache={hit}")
    manifest = {
        "schemaVersion": 1, "providerId": PROVIDER,
        "status": "GENERATED_LISTENING_CANDIDATES_NOT_PRODUCT_APPROVED",
        "commonComparisonText": COMMON,
        "quality": {"koreanListeningEvaluated": False, "cutenessEvaluated": False, "speakerDistinctionHumanEvaluated": False, "drivingBehaviorEffectEvaluated": False},
        "generationScope": "Offline development machine synthesis; no Android/Pleos runtime claim.",
        "clips": clips,
    }
    atomic_write(args.output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    if args.output_dir.resolve() == (HERE / "samples").resolve():
        from render_listen import render
        render()


if __name__ == "__main__":
    main()
