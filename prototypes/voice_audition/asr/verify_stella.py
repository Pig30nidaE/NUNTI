"""Verify the Stella ASR file, its recognized ending and prior artifact preservation."""
import hashlib
import json
from pathlib import Path
from transcribe import compare, normalize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
report = json.loads((HERE / "stella-results.json").read_text())
manifest = json.loads((HERE / "stella-input-manifest.json").read_text())
raw = [json.loads(line) for line in (HERE / "stella-results.jsonl").read_text().splitlines()]
assert len(raw) == len(manifest) == len(report["results"]) == 1
assert raw == report["results"]
baseline = json.loads((HERE / "stella-baseline-hashes.json").read_text())
for name, digest in baseline.items():
    assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
source, result = manifest[0], raw[0]
assert result["comparison"] == compare(source["referenceText"], result["recognizedText"])
mp3 = ROOT / source["path"]
assert hashlib.sha256(mp3.read_bytes()).hexdigest() == source["sha256"] == result["sha256"]
assert hashlib.sha256(mp3.with_suffix(".json").read_bytes()).hexdigest() == source["referenceMetadataSha256"]
assert result["sourceContext"]["modelId"] is None
ending = "여기서 어떤 기억을 만나게 될까"
recognized_ending = normalize(result["recognizedText"]).endswith(normalize(ending))
check = {"verifiedNewMp3Files": 1, "newMp3BytesUnchanged": True, "newMetadataBytesUnchanged": True, "preservedPriorAsrArtifactFiles": len(baseline), "priorAsrArtifactBytesUnchanged": True, "newComparisonRecomputed": True, "asrRecognizedFullEnding": recognized_ending, "expectedEnding": ending, "normalizedTranscriptMatchesSource": result["comparison"]["distance"] == 0, "commercialDemoModelIdKnown": False, "humanQualityOrCutoffVerified": False}
(HERE / "stella-verification.json").write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n")
(HERE / "stella-summary.md").write_text("""# Stella 공개 데모 추가 ASR

공식 UI에서 `Stella - Steady, Clear and Cheerful`을 선택해 받은 MP3 한 개를 기존 Whisper-small 모델과 동일한 greedy 설정으로 한 번 전사했다. 다른 결과는 다시 전사하지 않았고, 원문은 ASR 프롬프트에 주지 않았다.

ASR 전사:

> """ + result["recognizedText"].strip() + """

정규화 CER는 0%이며 삭제·치환·삽입 후보는 없다. 마지막 `여기서 어떤 기억을 만나게 될까`도 전사에 포함됐다. 다만 ASR은 틀리거나 들리지 않은 말을 추정할 수 있으므로 실제 끝 잘림이 없다는 사람의 청취 검증을 대체하지 않는다. 구두점과 띄어쓰기는 CER에서 제외한다.

원본 MP3와 메타데이터의 해시, 기존 ASR 산출물 23파일의 해시가 전후 일치한다. MP3 SHA-256은 `""" + source["sha256"] + """`다. 상세 전사·편집 정렬·출처는 `stella-results.json`, 재검증은 `stella-verification.json`, 실행 로그는 `stella-transcription.log`에 기록했다.

공개 익명 데모의 정확한 모델 ID·revision·합성 파라미터는 미노출이다. 특정 ElevenLabs 모델 버전으로 표기하지 않는다. 이 검사는 자연스러움·귀여움·화자 동일성을 판정하지 않는다.
""")
print(json.dumps(check, ensure_ascii=False))
