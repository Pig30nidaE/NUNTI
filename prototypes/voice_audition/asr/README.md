# 독립 한국어 ASR

합성 음성에 빠진 말이 있는지 보조 점검한다. Qwen VoiceDesign 6개와 Chatterbox 4개의 원본 WAV를 수정하지 않고, 원문을 ASR 프롬프트에 주지 않은 채 각각 한 번씩 전사했다. 사람이 음성을 듣는 일을 대체하지 않는다.

실제 결과는 [summary.md](summary.md), 원문·전사·문자 편집 정렬은 [results.json](results.json), WAV 해시는 [input-manifest.json](input-manifest.json)에 있다. `summarize.py`는 모델을 실행하지 않고 현재 WAV 해시와 CER 계산을 다시 확인한다.

## 사용한 구현과 모델

[공식 MLX Examples Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)의 `mlx-whisper==0.4.3`과 [MLX-community Whisper-small](https://huggingface.co/mlx-community/whisper-small-mlx)을 사용했다. 실제 가중치는 고정 revision `45f3915923c7a79a5a5b5a7d909d39aeb0e5630e`, 총 다운로드 481,309,720바이트다. 한 모델만 다운로드했다. [원본 OpenAI Whisper](https://github.com/openai/whisper)의 코드와 모델은 MIT다. 변환 모델 카드에는 별도 라이선스 필드가 없어 이 점을 기록한다. 공식 라이선스 파일을 함께 보존했다.

공식 API는 인메모리 파형을 받을 수 있다. WAV를 읽은 뒤 ASR 입력만 16kHz로 변환하며 원본은 그대로 둔다. ASR 언어는 `ko`, temperature는 0, 디코더는 greedy다. 원문 프롬프트와 이전 문장 조건은 사용하지 않는다. 최초 beam 옵션 시도는 디코더 미구현 오류로 결과를 내기 전에 종료됐다. 실패 로그는 [beam-unsupported.log](beam-unsupported.log)에 보존했고, 지원되는 greedy 설정으로 10개 전사를 완료했다. 실패 결과를 버리고 품질이 나은 전사만 고르는 재시도는 하지 않았다.

## 실행

Apple Silicon GPU가 필요하다. 저장소 루트에서 실행한다. 기본 uv와 Python 경로는 기존에 설치된 실행 파일을 읽어 쓰며, 새 환경·패키지·모델은 `.local/voice-audition-asr/`에만 저장한다.

```sh
bash prototypes/voice_audition/asr/setup.sh
.local/voice-audition-asr/venv/bin/python prototypes/voice_audition/asr/transcribe.py
.local/voice-audition-asr/venv/bin/python prototypes/voice_audition/asr/summarize.py
```

이미 결과가 있으면 `transcribe.py`는 덮어쓰거나 모델을 다시 실행하지 않는다. 완료된 현재 결과의 재검증에는 마지막 명령만 실행한다. 원본 WAV·합성 메타데이터, 상위 비교 보드와 `corpus.json`은 수정하지 않았다.

Qwen Base의 추가 `comfort`, `arrival` 두 문장은 같은 모델과 설정으로 `transcribe.py --identity`를 한 번 실행해 [별도 결과](identity-summary.md)에 기록했다. 기존 10개 전사는 다시 실행하지 않았다. 추가 결과와 기존 파일 보존을 모델 실행 없이 확인하려면 아래 명령을 사용한다.

```sh
.local/voice-audition-asr/venv/bin/python prototypes/voice_audition/asr/verify_identity.py
```

두 번째 비교의 Sohee WAV 4개와 ElevenLabs 익명 공개 데모 MP3 1개는 `transcribe.py --round2`로 같은 모델을 재사용해 별도 전사했다. [두 번째 결과](round2-summary.md)는 `round2-*` 파일에만 저장했다. 상용 데모는 정확한 모델 ID가 노출되지 않아 특정 모델 버전으로 분류하지 않는다. 원음과 이전 결과 보존 재검증에는 다음 명령을 사용한다.

```sh
.local/voice-audition-asr/venv/bin/python prototypes/voice_audition/asr/verify_round2.py
```

마지막으로 추가된 공식 공개 데모 Stella MP3 한 개는 `transcribe.py --stella`로 별도 전사했다. [Stella 결과](stella-summary.md)는 `stella-*` 파일에 저장했으며 기존 결과를 덮어쓰지 않았다. 원음·기존 결과 해시와 마지막 문장 전사 포함 여부를 다시 확인하려면 다음 명령을 사용한다.

```sh
.local/voice-audition-asr/venv/bin/python prototypes/voice_audition/asr/verify_stella.py
```

## 해석

CER는 NFC로 조합하고 공백·구두점을 제거한 뒤 Unicode 문자 단위 Levenshtein 거리를 원문 문자 수로 나눈 값이다. 띄어쓰기와 문장 부호는 제외하지만 `네`와 `내` 같은 표기는 그대로 다르게 센다. 삭제·치환·삽입은 ASR 문자열의 차이에 대한 플래그일 뿐 실제로 사람이 들은 누락·오발음 판정이 아니다.

ASR은 틀릴 수 있다. 문자가 일치해도 발음·자연스러움·귀여움·화자 정체성을 보증하지 않는다. 원문과 다를 때에는 원본을 다시 듣는다. 모델의 품질이나 상용 서비스에 대한 제삼자 성능 주장은 이 결과에 사용하지 않았다.
