"""Verify real new WAVs and baseline preservation; generate the local listening board."""
import hashlib
import html
import json
from pathlib import Path
import wave
import numpy as np
from generate import HERE, ROOT, UPSTREAM, environment, protected_hashes, read_expected

config, lock, source, original, items = read_expected()
baseline = json.loads((HERE / "baseline.json").read_text())
assert baseline == {"protectedFiles": protected_hashes(), "packages": environment()}
tokenizer_path = ROOT / lock["cacheRelativePath"] / "speech_tokenizer/config.json"
tokenizer = json.loads(tokenizer_path.read_text())
upsample = tokenizer["decode_upsample_rate"]
clips = []
for fields in items:
    wav = HERE / "samples" / fields["audioPath"]
    metadata = json.loads(wav.with_suffix(".json").read_text())
    original.validate(wav, metadata, fields)
    with wave.open(str(wav)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 24000)
        pcm = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(np.float64)
    assert pcm.size > 0 and np.count_nonzero(pcm) > 0
    clips.append({"clipId": fields["clipId"], "audioPath": "samples/" + wav.name, "audioSha256": metadata["audioSha256"], "textSha256": metadata["textSha256"], "durationSeconds": metadata["durationSeconds"], "generationSeconds": metadata["generationSeconds"], "modelLoadSeconds": metadata["modelLoadSeconds"], "peakMlxMemoryBytes": metadata["peakMlxMemoryBytes"], "pcm": {"sampleRateHz": 24000, "channels": 1, "sampleWidthBytes": 2, "frames": len(pcm), "peak": int(np.max(np.abs(pcm))), "rms": float(np.sqrt(np.mean(pcm * pcm))), "fullScaleSamples": int(np.count_nonzero((pcm == -32768) | (pcm == 32767))), "last250msRms": float(np.sqrt(np.mean(pcm[-6000:] ** 2)))}, "tokenBudgetEvidence": {"maxTokens": fields["generation"]["maxTokens"], "decodeUpsampleRate": upsample, "pcmFramesDividedByUpsample": len(pcm) / upsample, "nominalBudgetSeconds": fields["generation"]["maxTokens"] * upsample / 24000, "directGeneratedTokenCountCaptured": False, "directEOSObserved": False, "terminationReason": "not captured by this run; do not infer exact EOS or cap status solely from waveform duration", "note": "Codec-frame equivalence is indirect: tokenizer valid-length trimming can affect output. Preserve the first outputs rather than resynthesize to improve evidence."}})
report = {"status": "TWO_REAL_WAVS_HASH_PCM_SOURCE_TEXT_AND_BASELINE_VERIFIED", "sourceTextMetadataPath": "prototypes/voice_audition/commercial/elevenlabs-anna-journey.json", "sourceTextSha256": source["textSha256"], "sameTextAsAnna": all(c["textSha256"] == source["textSha256"] for c in clips), "referenceAudioUsed": False, "postprocessing": config["postprocessing"], "protectedUpstreamFiles": len(baseline["protectedFiles"]), "upstreamFilesUnchanged": True, "environmentInventoryUnchanged": True, "modelId": lock["modelId"], "revision": lock["revision"], "humanQualityApproved": False, "annaQualityMatched": False, "clips": clips}
asr_path = HERE / "asr-results.json"
if asr_path.exists():
    asr = json.loads(asr_path.read_text())
    assert len(asr["results"]) == 2
    by_id = {r["clipId"]: r for r in asr["results"]}
    report["asr"] = []
    for clip in clips:
        result = by_id[clip["clipId"]]
        assert result["audioSha256"] == clip["audioSha256"]
        report["asr"].append({"clipId": clip["clipId"], "cer": result["comparison"]["characterErrorRate"], "asrRecognizedFullEnding": result["asrRecognizedFullEnding"], "repeatedPhraseCandidate": result["repeatedPhraseCandidate"]})
(HERE / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
cards = []
cards.append('<section><h2>현재 선호 · Anna</h2><audio controls preload="none" src="../../voice_audition/commercial/elevenlabs-anna-journey.mp3"></audio><p>공식 익명 공개 데모의 실제 다운로드 원음</p><p>정확한 API 모델·revision·설정은 미노출입니다. 아래 로컬 모델과 원문만 같습니다.</p></section>')
for condition in config["conditions"]:
    clip = next(c for c in clips if c["clipId"] == condition["id"] + "-journey")
    cards.append('<section><h2>' + html.escape(condition["label"]) + '</h2><audio controls preload="none" src="' + html.escape(clip["audioPath"]) + '"></audio><p>' + str(clip["durationSeconds"]) + '초 · Sohee 한국어 preset</p><p>' + html.escape(condition["instruct"] or "스타일 지시 없음") + '</p></section>')
(HERE / "listen.html").write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Nunti · 같은 여행 대사 비교</title><style>body{max-width:920px;margin:48px auto;padding:0 20px;background:#f6f1e8;color:#283a3c;font-family:system-ui,sans-serif}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}section{background:#fffefa;padding:26px;border:1px solid #ddd8c7;border-radius:24px}p{line-height:1.8}audio{width:100%}aside{line-height:1.8;color:#586765}</style><h1>Nunti · 같은 여행 대사</h1><p>기존 Qwen Sohee의 같은 설정으로 새 원문을 합성한 후보입니다. Anna 음원은 모델의 참조·학습 입력으로 사용하지 않았습니다.</p><p>''' + html.escape(source["text"]) + '</p><main>' + ''.join(cards) + '''</main><aside><p>피치·속도·음량 후처리 없이 원본 합성을 PCM16 WAV로 저장했습니다. 귀여움·자연스러움·Anna와의 품질 일치는 미검증입니다. 이전 VoiceDesign→Base 후보의 탈락 판단은 유지합니다.</p><p>ASR은 끝 구절과 원문 차이를 보는 보조 자료입니다. 이 검사는 실제 청취를 대체하지 않습니다.</p></aside></html>''')
print(json.dumps({"status": report["status"], "sameTextAsAnna": report["sameTextAsAnna"], "protectedFiles": report["protectedUpstreamFiles"], "clips": [{"id": c["clipId"], "seconds": c["durationSeconds"], "fullScaleSamples": c["pcm"]["fullScaleSamples"]} for c in clips]}, ensure_ascii=False), flush=True)
