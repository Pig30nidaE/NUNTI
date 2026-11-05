"""Verify the produced audition artifacts, not subjective voice quality."""
from __future__ import annotations

import array
import hashlib
import json
from pathlib import Path
import sys
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED_TEXT = {
    "hello": "안녕하세요. 오늘의 여행도 함께할게요.",
    "comfort": "천천히 가도 괜찮아. 나는 네 옆에 있을게.",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    lock = json.loads((HERE / "model-lock.json").read_text())
    download = json.loads((HERE / "download-verification.json").read_text())
    assert download["revision"] == lock["modelRevision"]
    assert download["totalBytes"] < 10_000_000_000
    assert len(download["files"]) == 6
    clips = []
    for condition in ["builtin", "qwen-reference"]:
        for text_id, text in EXPECTED_TEXT.items():
            clip_id = condition + "-" + text_id
            audio = HERE / "samples" / (clip_id + ".wav")
            metadata = json.loads(audio.with_suffix(".json").read_text())
            assert metadata["text"] == text
            assert metadata["textSha256"] == hashlib.sha256(text.encode()).hexdigest()
            assert metadata["upstreamNormalizedText"] == text
            assert metadata["modelRevision"] == lock["modelRevision"]
            assert metadata["codeRevision"] == lock["codeRevision"]
            assert metadata["variant"] == "Chatterbox-Multilingual-V3"
            assert metadata["audioSha256"] == digest(audio)
            assert metadata["humanListeningVerified"] is False
            assert metadata["voiceIdentityAcrossTextsVerified"] is False
            with wave.open(str(audio), "rb") as source:
                assert source.getnchannels() == 1
                assert source.getsampwidth() == 2
                assert source.getframerate() == metadata["sampleRateHz"] == 24000
                assert source.getnframes() == metadata["frames"]
                samples = array.array("h", source.readframes(source.getnframes()))
            if sys.byteorder != "little":
                samples.byteswap()
            assert samples and any(samples)
            full_scale = sum(value in {-32768, 32767} for value in samples)
            assert full_scale == 0
            if condition == "qwen-reference":
                ref = metadata["syntheticReference"]
                assert ref["realPersonReference"] is False
                assert digest(ROOT / ref["path"]) == ref["audioSha256"]
            clips.append({
                "clipId": clip_id, "audioSha256": digest(audio),
                "durationSeconds": len(samples) / 24000, "fullScaleSamples": full_scale,
                "textExact": True, "referenceVerified": condition == "qwen-reference",
            })
    result = {
        "status": "PASSED_AUDIO_IDENTITY_FORMAT_AND_EXACT_TEXT_METADATA",
        "clips": clips, "humanListeningVerified": False,
        "doesNotProve": ["Korean pronunciation accuracy", "naturalness", "cuteness",
                         "speaker consistency", "superiority over Qwen or commercial models"],
    }
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
