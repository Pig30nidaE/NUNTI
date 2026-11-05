"""Build a local listening comparison from the real immutable audition files."""
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import wave

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIGS = [
    ("A", "Qwen · 둥근 미소", "journey_voice_v3", "round-smile", True),
    ("C", "Qwen · 반짝 조약돌", "journey_voice_v3", "bright-pebble", False),
    ("D", "Qwen · 포근 이끼", "journey_voice_v3", "soft-moss", False),
    ("B", "Chatterbox · A의 합성 음색 참조", "chatterbox_audition", "qwen-reference", False),
    ("E", "Chatterbox · 기본 음색", "chatterbox_audition", "builtin", False),
]
TEXTS = {
    "hello": "안녕하세요. 오늘의 여행도 함께할게요.",
    "comfort": "천천히 가도 괜찮아. 나는 네 옆에 있을게.",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    feedback = json.loads((HERE / "user-feedback.json").read_text())
    followup_rejected = feedback.get("fixedReferenceFollowup", {}).get("status", "").startswith("REJECTED")
    candidates, cards = [], []
    for label, title, directory, prefix, selected in CONFIGS:
        clips, players = [], []
        for sentence, expected in TEXTS.items():
            base = ROOT / "prototypes" / directory / "samples" / (prefix + "-" + sentence)
            meta = json.loads(base.with_suffix(".json").read_text())
            audio = base.with_suffix(".wav")
            assert meta["text"] == expected and meta["textSha256"] == digest(expected.encode())
            assert digest(audio.read_bytes()) == meta["audioSha256"]
            with wave.open(str(audio), "rb") as wav:
                assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (24000, 1, 2)
                assert wav.getnframes() > 0
                duration = wav.getnframes() / wav.getframerate()
            relative = "../" + directory + "/samples/" + audio.name
            clips.append({"utterance": sentence, "text": expected, "audioPath": str(audio.relative_to(ROOT)),
                          "audioSha256": meta["audioSha256"], "metadataPath": str(base.with_suffix(".json").relative_to(ROOT)),
                          "durationSeconds": duration})
            players.append('<p>' + html.escape(expected) + '</p><audio controls preload="none" src="' + relative + '"></audio>')
        candidates.append({"label": label, "title": title, "userPreferredForNaturalness": selected, "clips": clips})
        verdict = ''
        if selected:
            message = 'A>B의 상대 선호 기록. 후속 Qwen Base 대사는 부자연스럽다는 평가로 탈락했습니다.' if followup_rejected else '사용자가 B보다 자연스럽다고 선택한 기준 음성'
            verdict = '<p class="choice">' + message + '</p>'
        cards.append('<article><h2>' + label + ' · ' + html.escape(title) + '</h2>' + verdict + ''.join(players) + '</article>')
    result = {"schemaVersion": 1, "status": "REAL_AUDIO_AUDITION_NOT_GLOBAL_MODEL_RANKING",
              "candidates": candidates, "humanFeedback": "user-feedback.json", "commercialAccountAvailable": False,
              "finalVoiceSelected": False, "qwenFollowupRejectedByUser": followup_rejected,
              "notVerified": ["Commercial API head-to-head quality", "cuteness acceptance", "cross-text speaker identity", "Android integration of new models"]}
    (HERE / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    page = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nunti 새로운 목소리 비교</title><style>
body{font-family:system-ui,sans-serif;background:#f4f4f0;color:#25302d;margin:0;padding:32px;line-height:1.7}
main{max-width:980px;margin:auto}h1{font-size:30px}h2{font-size:20px}article{background:white;padding:24px;border:1px solid #dedfd8;border-radius:16px;margin:20px 0}
audio{width:100%;max-width:680px}.choice{color:#27704b;font-weight:600}a{color:#285978}small{color:#57615a}
</style><main><h1>작은 동반자의 새로운 목소리</h1>
<p>같은 두 대사, 실제 두 엔진. 모든 파일은 피치·속도 후처리 없는 원음입니다. Chatterbox에는 공식 모델의 워터마크가 포함됩니다.</p>
<p>이 페이지는 이전 실험 기록입니다. Qwen Base 후속 대사는 사용자 청취에서 탈락했고 최종 음색은 미확정입니다.</p>
<p>먼저 자연스러운 말의 흐름과 한국어를 듣고, 그다음 귀여움과 캐릭터의 느낌을 비교해 주세요. 원음의 음량은 서로 다릅니다. 재생 크기를 비슷하게 조절해서 비교하세요.</p>
<p>A의 선택은 이번 두 후보 간 자연스러움에 대한 사용자 응답입니다. 모든 상용 모델보다 좋거나 귀여움이 확정됐다는 뜻은 아닙니다. 같은 스타일로 독립 합성한 두 문장의 화자가 같은지도 별도로 확인해야 합니다.</p>
<p><a href="../journey_voice_v3/identity/listen.html">선택한 A의 합성 참조를 고정해 만든 새 대사 듣기</a></p>
''' + ''.join(cards) + '''<details><summary>이전 v2 기준 음성</summary><p>사용자가 기계적으로 느낀다고 평가한 Supertonic3 F3 +3반음 후보입니다.</p><audio controls preload="none" src="../journey_voice/samples-v2/coast-common.wav"></audio></details>
<p><a href="../../docs/design/journey-characters/tts-research-commercial.md">상용 조사</a> · <a href="../../docs/design/journey-characters/tts-research-opensource.md">공개 모델 조사</a> · <a href="comparison.json">파일·출처</a></p>
<small>로컬 파일만 사용합니다. 자동 재생·업로드·계정 연결은 없습니다. 이 페이지는 앱의 주행 안내 화면이 아닙니다.</small></main></html>'''
    class LocalReferences(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in ("src", "href"):
                    assert (HERE / value).resolve().is_file(), value
    LocalReferences().feed(page)
    (HERE / "listen.html").write_text(page)
    print(json.dumps({"status": "PASS", "candidates": len(candidates), "actualAudioFiles": 10,
                      "htmlReferencesExist": True, "listeningQualityJudgedByScript": False}))


if __name__ == "__main__":
    main()
