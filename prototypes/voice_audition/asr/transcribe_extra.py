"""Inspect one immutable extra audio file and transcribe once using the existing ASR model."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import time
from transcribe import compare, normalize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ROOT / ".local/voice-audition-asr"
os.environ["HF_HOME"] = str(TOOLS / "hf")
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True, help="Input JSON filename inside this ASR folder")
parser.add_argument("--prefix", required=True, help="New output prefix; existing files are never overwritten")
args = parser.parse_args()
if Path(args.input).name != args.input or not args.prefix or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.prefix):
    raise SystemExit("Input must be a filename and prefix must use lowercase letters, digits or hyphens")
result_path = HERE / f"{args.prefix}-results.json"
summary_path = HERE / f"{args.prefix}-summary.md"
if result_path.exists() or summary_path.exists():
    raise SystemExit("Existing result is immutable; inspect it rather than rerunning inference")
config_path = HERE / args.input
config = json.loads(config_path.read_text())
audio_path = (ROOT / config["audioPath"]).resolve()
if not audio_path.is_relative_to(ROOT):
    raise SystemExit("Audio must be inside the repository")
before_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
assert before_hash == config["audioSha256"]
prior_files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file() and p.suffix in [".json", ".jsonl", ".md", ".log"] and not p.name.startswith(args.prefix + "-")}
lock = json.loads((HERE / "model-lock.json").read_text())

import mlx.core as mx
import mlx_whisper
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

started = time.monotonic()
values, rate = sf.read(audio_path, dtype="float32", always_2d=True)
assert values.size and np.isfinite(values).all()
mono = values.mean(axis=1)
divisor = math.gcd(rate, 16000)
asr_audio = resample_poly(mono, 16000 // divisor, rate // divisor).astype(np.float32)
settings = {"language": "ko", "task": "transcribe", "temperature": 0.0, "condition_on_previous_text": False, "initial_prompt": None, "word_timestamps": False}
print(json.dumps({"event": "transcribing", "audioPath": config["audioPath"], "sourceDurationSeconds": len(values) / rate}), flush=True)
asr_started = time.monotonic()
asr = mlx_whisper.transcribe(asr_audio, path_or_hf_repo=lock["localPath"], verbose=None, **settings)
asr_seconds = time.monotonic() - asr_started
comparison = compare(config["referenceText"], asr["text"])
preserved = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest for name, digest in prior_files.items()}
assert all(preserved.values())
after_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
assert after_hash == before_hash
ending_recognized = normalize(asr["text"]).endswith(normalize(config["expectedEnding"]))
record = {"schemaVersion": 1, "createdAt": datetime.now(timezone.utc).isoformat(), "input": config, "inputConfigSha256": hashlib.sha256(config_path.read_bytes()).hexdigest(), "sourceAudio": {"sha256Before": before_hash, "sha256After": after_hash, "bytes": audio_path.stat().st_size, "sampleRateHz": rate, "channels": values.shape[1], "frames": len(values), "durationSeconds": len(values) / rate, "decodedFloatPeak": float(np.max(np.abs(values))), "decodedFloatRms": float(np.sqrt(np.mean(values.astype(np.float64) ** 2))), "samplesAtOrAboveFullScale": int(np.count_nonzero(np.abs(values) >= 1.0)), "allSamplesFinite": True, "modified": False}, "asr": {"modelId": lock["modelId"], "revision": lock["revision"], "settings": settings, "decoder": "greedy", "sampleRateHz": 16000, "transcript": asr["text"], "language": asr["language"], "seconds": asr_seconds, "segments": asr["segments"], "comparison": comparison, "asrRecognizedExpectedEnding": ending_recognized}, "priorArtifacts": {"files": len(prior_files), "allBytesPreserved": True, "sha256": prior_files}, "runtime": {"peakMlxMemoryBytes": mx.get_peak_memory(), "totalSeconds": time.monotonic() - started, "packages": {p: importlib.metadata.version(p) for p in ["mlx-whisper", "mlx", "numpy", "scipy", "soundfile"]}}, "limitations": ["Only one ASR pass with the existing Whisper-small checkpoint. No new model download, synthesis, or environment changes.", "Reference text is only used after transcription, never as an ASR prompt.", "Only the ASR input is resampled in memory; the original MP3 remains unchanged.", "ASR is fallible and can infer missing words; recognizing the expected ending does not prove the recording has no audible cutoff.", "CER measures NFC letters/numbers after removing punctuation and whitespace; it does not prove correct phonetic pronunciation.", "This check does not establish naturalness, cuteness, stable speaker identity or product quality."]}
record["sourceAudio"]["decodedPcmFloat32LeSha256"] = hashlib.sha256(values.astype("<f4", copy=False).tobytes()).hexdigest()
result_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
summary_path.write_text("# Anna 여행 대사 추가 점검\n\n실제 MP3를 기존 Whisper-small로 한 번 전사했다. 원문 프롬프트는 사용하지 않았다.\n\n> " + asr["text"].strip() + f'\n\n정규화 CER {comparison["characterErrorRate"]:.2%}, 편집 거리 {comparison["distance"]}. 마지막 요청 구절의 ASR 포함 여부는 {ending_recognized}다. 삭제·치환·삽입의 상세 정렬은 `{result_path.name}`에 있다.\n\n원음은 {rate}Hz, {values.shape[1]}채널, {len(values) / rate:.6f}초, {audio_path.stat().st_size:,}바이트다. MP3 SHA-256은 `{before_hash}`이며 전후 동일하다. 기존 ASR 산출물 {len(prior_files)}파일도 해시가 일치한다.\n\n공개 익명 데모의 정확한 모델 ID·revision·합성 설정은 미노출이다. 특정 ElevenLabs 모델 버전으로 표기하지 않는다. ASR은 잘못 인식하거나 들리지 않은 말을 추정할 수 있다. 실제 끝 잘림·발음·자연스러움·귀여움·화자 동일성은 청취 판단이 필요하다.\n')
print(json.dumps({"event": "complete", "transcript": asr["text"], "cer": comparison["characterErrorRate"], "asrRecognizedExpectedEnding": ending_recognized, "sourceHashPreserved": True, "priorFilesPreserved": len(prior_files)}, ensure_ascii=False), flush=True)
