"""Recheck the completed ASR against real files without rerunning any model."""
import hashlib
import json
from pathlib import Path
from transcribe import compare

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
report = json.loads((HERE / "results.json").read_text())
manifest = json.loads((HERE / "input-manifest.json").read_text())
raw = [json.loads(line) for line in (HERE / "results.jsonl").read_text().splitlines()]
assert len(raw) == len(manifest) == len(report["results"]) == 10
assert raw == report["results"]
assert len({r["id"] for r in raw}) == 10
rows = []
for source, result in zip(manifest, raw):
    assert result["comparison"] == compare(source["referenceText"], result["recognizedText"])
    wav = ROOT / source["path"]
    assert hashlib.sha256(wav.read_bytes()).hexdigest() == source["sha256"] == result["sha256"]
    assert hashlib.sha256(wav.with_suffix(".json").read_bytes()).hexdigest() == source["referenceMetadataSha256"]
    comparison = result["comparison"]
    rows.append(f'| `{result["id"]}` | {result["recognizedText"].strip()} | {comparison["characterErrorRate"]:.2%} | {"원문과 일치" if not comparison["needsHumanListening"] else "네 → 내, 재청취 필요"} |')
checks = {"verifiedWavFiles": 10, "allWavBytesUnchanged": True, "allMetadataBytesUnchanged": True, "allComparisonsRecomputed": True, "jsonlMatchesSummary": True, "humanQualityVerified": False}
(HERE / "verification.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
summary = """# 독립 한국어 ASR 보조 점검

실제 합성 WAV 10개를 동일한 Whisper-small 모델로 각각 한 번씩 전사했다. 모든 인사 문장은 원문과 일치했다. 모든 동반자 문장은 원문의 `네`를 `내`로 인식한 한 음절 차이가 있었다. 문자 누락은 검출되지 않았다.

Qwen과 Chatterbox가 같은 차이를 보이므로 ASR 자체의 인식 혼동일 수 있다. 이 차이를 TTS 발음 오류로 확정하지 않는다. `네 옆에` 구간은 사람의 재청취가 필요하다.

| 실제 파일 | ASR 전사 | 정규화 문자오류율 | 보조 플래그 |
|---|---|---:|---|
""" + "\n".join(rows) + """

전체 문자오류율은 3.125%다. 이는 이 짧은 두 문장의 표기 차이를 센 값이며 모델 품질 순위가 아니다. NFC 조합 후 공백과 구두점만 제거하고 글자를 치환하거나 발음대로 고치지 않았다. 모델은 원문을 프롬프트로 받지 않았다. 언어는 한국어, temperature 0, 기본 greedy decoder로 고정했다. 기존 전사와 문맥을 재사용하지 않았다.

ASR 결과의 일치만으로 정확한 발음·자연스러움·귀여움·문장 간 같은 화자임을 증명하지 못한다. CER가 있는 경우에도 ASR 오류일 수 있다. 실제 음성 청취 평가가 우선이다.

원본 WAV와 합성 메타데이터의 SHA-256은 `input-manifest.json`에 기록했고 전후 모두 일치한다. 인식 원문과 segment 정보, 정규화 문자열, 최소 편집 정렬은 `results.json`과 `results.jsonl`에 있다. 실제 파일 재검증은 `verification.json`에 기록한다.
"""
(HERE / "summary.md").write_text(summary)
print(json.dumps(checks, ensure_ascii=False))
