"""Verify the two additional Base transcripts and preservation of the first ASR run."""
import hashlib
import json
from pathlib import Path
from transcribe import compare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
report = json.loads((HERE / "identity-results.json").read_text())
manifest = json.loads((HERE / "identity-input-manifest.json").read_text())
raw = [json.loads(line) for line in (HERE / "identity-results.jsonl").read_text().splitlines()]
assert len(raw) == len(manifest) == len(report["results"]) == 2
assert raw == report["results"]
assert {r["id"] for r in raw} == {"qwen-base/arrival", "qwen-base/comfort"}
baseline = json.loads((HERE / "identity-baseline-hashes.json").read_text())
for name, digest in baseline.items():
    assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
rows = []
for source, result in zip(manifest, raw):
    assert result["comparison"] == compare(source["referenceText"], result["recognizedText"])
    wav = ROOT / source["path"]
    assert hashlib.sha256(wav.read_bytes()).hexdigest() == source["sha256"] == result["sha256"]
    assert hashlib.sha256(wav.with_suffix(".json").read_bytes()).hexdigest() == source["referenceMetadataSha256"]
    c = result["comparison"]
    rows.append(f'| `{result["id"]}` | {result["recognizedText"].strip()} | {c["characterErrorRate"]:.2%} | {"일치" if not c["needsHumanListening"] else "재청취 필요"} |')
check = {"verifiedNewWavFiles": 2, "newWavBytesUnchanged": True, "newMetadataBytesUnchanged": True, "preservedPriorAsrResultFiles": len(baseline), "priorAsrResultBytesUnchanged": True, "newComparisonsRecomputed": True, "humanQualityVerified": False}
(HERE / "identity-verification.json").write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n")
(HERE / "identity-summary.md").write_text("""# Qwen Base 추가 두 문장 ASR

이전 10개 결과를 보존하고 같은 Whisper-small 모델·고정 greedy 설정으로 새 WAV 두 개만 각각 한 번 전사했다. 추가 모델 다운로드와 원문 프롬프트는 사용하지 않았다.

| 실제 파일 | ASR 전사 | 정규화 문자오류율 | 보조 플래그 |
|---|---|---:|---|
""" + "\n".join(rows) + """

도착 문장은 공백과 구두점을 제외한 원문과 일치했다. 동반자 문장은 이전 10개 비교와 같이 `네`를 `내`로 인식했다. 이 인식 차이는 ASR 자체의 혼동일 수도 있으므로 TTS 발음 오류로 확정하지 않는다. 문자 누락 후보는 없다.

원본 WAV와 메타데이터 4개, 기존 ASR 결과 파일 6개의 해시가 전후 일치한다. 상세 해시·전사·편집 정렬은 `identity-results.json`, 재검증은 `identity-verification.json`에 있다. 실행 로그는 `identity-transcription.log`에 보존한다.

자동 전사는 정확한 발음·자연스러움·귀여움·문장 간 화자 동일성을 증명하지 않는다. 사람의 청취 평가가 필요하다.
""")
print(json.dumps(check, ensure_ascii=False))
