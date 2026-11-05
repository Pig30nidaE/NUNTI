#!/usr/bin/env python3
"""Exercise exact text-file input, process restart and reroute through real ONNX CLI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from voice_cli import DEFAULT_STATE, HERE, ROOT, sha


def main():
    DEFAULT_STATE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verify-runtime-", dir=DEFAULT_STATE.parent) as temporary:
        directory = Path(temporary)
        recipe = json.loads((ROOT / "prototypes/journey_characters/sample-output.json").read_text())["recipes"][0]
        recipe_path = directory / "recipe.json"
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        text = "안녕하세요.\n  오늘의 여행도 함께할게요.\n"
        text_path = directory / "speech.txt"
        text_path.write_bytes(text.encode("utf-8"))
        command = [sys.executable, str(HERE / "voice_cli.py"), "--recipe", str(recipe_path), "--state-dir", str(directory / "state"), "--text-file", str(text_path)]

        def run():
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            value = json.loads(result.stdout)
            assert value["text"].encode("utf-8") == text_path.read_bytes()
            assert value["textSha256"] == sha(text_path.read_bytes())
            return value, Path(value["audioPath"]).read_bytes()

        first, original = run()
        assert first["cacheHit"] is False
        restarted, restarted_bytes = run()
        assert restarted["cacheHit"] is True and restarted_bytes == original
        recipe["voiceIntent"]["requested"]["affect"] = "quiet_delight"
        recipe["creativeInspiration"]["destinationTags"] = ["city"]
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        rerouted, rerouted_bytes = run()
        assert rerouted["cacheHit"] is True and rerouted_bytes == original
        assert first["bindingId"] == restarted["bindingId"] == rerouted["bindingId"]
        assert first["speakerId"] == restarted["speakerId"] == rerouted["speakerId"] == "F1"
        print(json.dumps({"status": "PASS", "realCliProcesses": 3, "freshRealOnnxSynthesis": 1, "processRestartCacheHit": True, "rerouteCacheHit": True, "exactUtf8TextFilePreserved": True, "savedAudioBytesPreserved": True, "bindingId": first["bindingId"], "audioSha256": first["audioSha256"], "durationMs": first["durationMs"], "audibleQualityAssessed": False}, indent=2))


if __name__ == "__main__":
    main()
