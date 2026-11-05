"""Verify actual WAV identity/format and build a local, script-free listening board."""
import hashlib
import html
import json
from pathlib import Path
import wave
import numpy as np

HERE = Path(__file__).resolve().parent
config = json.loads((HERE / "styles.json").read_text())
lock = json.loads((HERE / "model-lock.json").read_text())
clips = []
for style in config["styles"]:
    for sentence in config["sentences"]:
        clip_id = f'{style["id"]}-{sentence["id"]}'
        record = json.loads((HERE / "samples" / f"{clip_id}.json").read_text())
        path = HERE / "samples" / record["audioPath"]
        assert record["clipId"] == clip_id
        assert record["text"] == sentence["text"]
        assert record["instruct"] == style["instruct"]
        assert record["textSha256"] == hashlib.sha256(sentence["text"].encode()).hexdigest()
        assert record["audioSha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert record["revision"] == lock["revision"]
        assert record["generation"] == config["generation"]
        assert record["postprocessing"] == config["postprocessing"]
        with wave.open(str(path)) as wav:
            assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
            assert wav.getframerate() == record["sampleRateHz"] == 24000
            assert wav.getnframes() == record["frames"]
            values = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64)
        assert len(values) > 0 and np.count_nonzero(values) > 0
        record["pcmMetrics"] = {"peak": int(np.max(np.abs(values))), "rms": float(np.sqrt(np.mean(values * values))), "fullScaleSamples": int(np.count_nonzero((values == -32768) | (values == 32767)))}
        clips.append(record)
report = {"schemaVersion": 1, "status": "SIX_REAL_WAV_FILES_HASH_AND_PCM_VERIFIED", "humanNaturalnessVerified": False, "koreanTranscriptAccuracyVerified": False, "crossTextVoiceIdentityVerified": False, "noPitchOrSpeedPostprocessing": True, "modelId": lock["modelId"], "revision": lock["revision"], "clips": clips}
(HERE / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
cards = []
for style in config["styles"]:
    audios = []
    for sentence in config["sentences"]:
        clip_id = f'{style["id"]}-{sentence["id"]}'
        audios.append(f'<p>{html.escape(sentence["text"])}</p><audio controls preload="none" src="samples/{clip_id}.wav"></audio>')
    cards.append('<section><h2>' + html.escape(style["label"]) + '</h2>' + ''.join(audios) + '</section>')
(HERE / "listen.html").write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Nunti · 자연스러운 목소리 비교</title><style>body{max-width:1080px;margin:48px auto;padding:0 20px;background:#f5f1e9;color:#283a3c;font-family:system-ui,sans-serif}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}section{background:#fffefa;padding:24px;border:1px solid #ddd8c7;border-radius:24px}h1{font-weight:650}h2{font-size:22px}p{line-height:1.7}audio{width:100%}aside{padding:20px 0;color:#536365;line-height:1.8}</style><h1>Nunti · 새로운 목소리 비교</h1><p>Qwen3-TTS VoiceDesign · 한국어 · 3가지 캐릭터 지시 · 피치·속도 후처리 없음</p><main>''' + ''.join(cards) + '''</main><aside>실제 모델 합성 후보입니다. 자연스러움·귀여움·문장 간 같은 목소리인지는 사람의 청취 평가가 남아 있습니다. 성우·실인물 음성은 복제하지 않았습니다. 독립 VoiceDesign 추론이므로 고정된 화자 ID를 보장하지 않습니다.</aside></html>''')
print(json.dumps({"status": report["status"], "clips": len(clips), "durations": [round(c["durationSeconds"], 3) for c in clips]}, ensure_ascii=False, indent=2))
