#!/usr/bin/env python3
"""Exercise publication/retry with a deterministic fake generator, not a quality claim.

Run in the voice runtime for numpy/soundfile. The test deliberately never loads
Metal or real models; separate 200-case verification runs actual inference.
"""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import numpy as np
from nunti.avatar_studio.voice_design import build_voice_design
from nunti.avatar_studio.voice_render import LocalVoiceRenderer


def run():
    seeds = []
    core = ModuleType("mlx.core")
    core.random = SimpleNamespace(seed=seeds.append)
    core.clear_cache = lambda: None
    mlx = ModuleType("mlx")
    mlx.core = core
    data = {"requestId": "retry-test", "destination": {"name": "서울역"}, "purpose": "출장"}
    plan = build_voice_design(data)
    waveform = (.1 * np.sin(np.arange(144000) * 2 * np.pi * 220 / 24000)).astype(np.float32)

    class Generator:
        def __init__(self, always_fail=False):
            self.calls = 0
            self.always_fail = always_fail

        def generate_voice_design(self, **settings):
            self.calls += 1
            rejected = self.always_fail or self.calls == 1
            yield SimpleNamespace(audio=waveform, sample_rate=24000,
                                  token_count=settings["max_tokens"] if rejected else 75)

    with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {"mlx": mlx, "mlx.core": core}), \
            patch("nunti.avatar_studio.voice_render._gpu_lock", nullcontext):
        renderer = LocalVoiceRenderer()
        generator = Generator()
        with patch.object(renderer, "_load", return_value=generator):
            result = renderer.render(plan, Path(tmp) / "success")
            assert len(result["attempts"]) == 2
            assert result["attempts"][0]["rejectedReason"] == "VOICE_TOKEN_LIMIT_REACHED"
            assert result["attempts"][1]["accepted"]
            assert result["seed"] != result["planSeed"]
            assert generator.calls == 2
            again = renderer.render(plan, Path(tmp) / "success")
            assert again["cacheHit"] and again["audioSha256"] == result["audioSha256"]
            assert generator.calls == 2
        renderer = LocalVoiceRenderer()
        generator = Generator(always_fail=True)
        with patch.object(renderer, "_load", return_value=generator):
            try:
                renderer.render(plan, Path(tmp) / "failure")
                raise AssertionError("Exhausted generation was incorrectly published")
            except ValueError as exc:
                assert str(exc).startswith("VOICE_QUALITY_RETRIES_EXHAUSTED")
        final_path = Path(tmp) / "failure" / plan["profileId"] / hashlib.sha256(plan["greeting"].encode()).hexdigest()
        assert not final_path.exists()
        rejected = list(final_path.parent.glob("rejected-*"))
        assert len(rejected) == 1 and generator.calls == 3
        assert len(json.loads((rejected[0] / "attempts.json").read_text())) == 3
        assert len(list((rejected[0] / "attempts").glob("*.wav"))) == 3
    print(json.dumps({"status": "PASS", "checks": ["retry_before_publication", "deterministic_new_seed",
                     "accepted_wav_immutable", "three_attempt_bound", "rejected_evidence_preserved"],
                     "realModelInference": False, "audioQualityVerified": False}))


if __name__ == "__main__":
    run()
