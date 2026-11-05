# 더 작은 캐릭터 목소리 후보 v2

사용자 청취 피드백인 "전체적으로 더 작고 귀여운 느낌"에 맞춰 실제 음성을 다시 만들었다. 기존 F1/M3/F2의 v1 바인딩·카탈로그·모델 lock·WAV·청취 페이지를 보존하고, 별도 v2 실험으로 분리했다. [listen-v2.html](listen-v2.html)을 열면 새 시안을 들을 수 있다.

후속 Android Debug 파일 재생과 실제 emulator 검증까지 완료했다. [PM 결과·시험 가이드](../../docs/design/journey-characters/tts-result.md)에 실제 앱 이벤트·PCM과 남은 청취·무음 검증을 구분해 기록했다. 아래 합성 파일 검사는 그 자체로 Android 출력 검증을 대신하지 않는다.

| 여정 | 새 원화자 | 프로필 | 합성 속도 | 후처리 |
| --- | --- | --- | --- | --- |
| 바다·휴식 | F3 | `nunti-keepsake-calm-v2` | 1.04 | 길이 보존, +3 반음 |
| 숲·캠핑 | F4 | `nunti-keepsake-curious-v2` | 1.08 | 길이 보존, +3 반음 |
| 도시·전시 | F5 | `nunti-keepsake-clear-v2` | 1.06 | 길이 보존, +3 반음 |

새 원화자를 골라 보는 **A안**과 동일한 실제 원본 파형을 약하게 높인 **B안**을 함께 보존했다. 기본 청취 후보는 B안이다. 사용자가 "높이를 올리기 전 목소리와 비교"를 열면 A안을 같은 문장으로 비교할 수 있다. 단순 재생 속도 증가로 피치를 올리지 않는다. Librosa의 길이 보존 pitch shift를 사용하며 최대 피크가 0.95를 넘는 경우에만 감쇠한다. 새로운 어린이 화자를 학습하거나 특정인의 목소리를 복제한 결과가 아니다.

F3/F4/F5가 사람에게 더 귀엽거나 작은 존재처럼 들린다는 평가는 아직 없다. 피치 상승은 포먼트와 음질에 부자연스러운 인상을 줄 수 있다. 한국어 명료도·첫 음절 누락·치찰음·금속성 울림·장시간 피로는 원본과 새 음성을 사람이 비교해야 한다. 파형의 에너지 시작 시각이나 클리핑 0건으로 발음 정확성을 대신 판정하지 않는다. 말이 빨라져 알아듣기 어려워진 경우를 개선으로 세지 않는다.

## 실행과 보존

```bash
bash prototypes/journey_voice/setup-v2.sh
.local/journey-voice/venv-v2/bin/python prototypes/journey_voice/generate_samples_v2.py
open prototypes/journey_voice/listen-v2.html
```

v1은 `.local/journey-voice/venv`와 `requirements.lock.txt`의 9개 패키지, v2는 `.local/journey-voice/venv-v2`와 `requirements-v2.lock.txt`를 사용한다. 실제 설치 후 v1을 기존 9개 정확 버전으로 복원했고, 같은 버전임을 검사했다. v2가 추가하는 화자 JSON은 동일한 고정 Supertonic 3 revision에서 약 900KB만 추가로 받는다. 큰 ONNX는 바꾸지 않는다. 원래 `model-lock.json` 대신 별도 `model-lock-v2.json`이 추가 화자 파일까지 검증한다.

```bash
.local/journey-voice/venv-v2/bin/python prototypes/journey_voice/voice_v2.py \
  --recipe prototypes/journey_characters/sample-output.json \
  --text '안녕하세요. 오늘의 여행도 함께할게요.' \
  --output .local/journey-voice/my-character-v2.wav
```

v2 바인딩과 캐시는 `.local/journey-voice/state-v2/`에 둔다. v1 기본 state 디렉터리를 지정하거나 기존 v1 바인딩이 들어 있는 ledger를 넘기면 오류로 거부한다. 이는 사용자 캐릭터의 기존 목소리를 자동으로 바꾼 제품 마이그레이션이 아니다. 같은 합성 여정의 **새 실험 버전**이다.

바인딩 해시에 실제 원화자·모델·합성 속도·단계뿐 아니라 전체 DSP 설정과 카탈로그 digest를 포함했다. 새 버전 안에서도 reroute·재시작은 기존 설정을 보존한다. 미정 intent나 누락·변조 캐시는 기본 화자나 재합성으로 숨기지 않는다. CLI는 v1처럼 정확한 UTF-8 입력과 모델 내부 정규화 결과를 모두 기록한다.

## 실제 결과와 검사

`samples-v2/manifest.json`의 `clips`는 Android 연결용 B안 6개다. `schemaVersion: 1`, `providerId: supertonic3-local-catalog`를 유지하며 모든 `profileId`가 `-v2`로 끝난다. 모델 revision은 그대로이며 `candidateVersion: 2`로 구분한다. `comparisonClips`는 같은 문장의 A안 3개를 담는다. 여정별 인사의 원본 3개도 `sourceRawAudioPath`로 함께 보존해 전체 WAV는 12개다.

```bash
python3 prototypes/journey_voice/test_voice.py
python3 prototypes/journey_voice/test_voice_v2.py
python3 prototypes/journey_voice/verify_samples_v2.py
```

기존 19개 검사와 v2 추가 7개 검사, 실제 v2 WAV 12개 검사에 통과했다. 실제 6개 후처리 파일의 프레임 길이는 원본과 같고 full-scale 클리핑은 0개다. 다른 세 화자의 동일 문장을 비교할 수 있다. v1 비교 기준 9개 파일의 SHA-256도 그대로다. v2 생성기를 재실행했을 때 6개가 모두 캐시에 적중해 실제 WAV와 manifest가 바뀌지 않았다.

`sample-verification-v2.json`, `unit-verification-v2.txt`, `v2-environment-verification.json`에 결과를 기록했다. 귀여움·명료도·첫 음절·DSP 왜곡의 사람 청취 평가는 미완료이며, 차량 스피커 출력이나 Pleos 음성 생성의 검증 결과로 쓰지 않는다.

## 출처

모델과 검토한 helper의 출처·고정 버전·MIT/Open RAIL-M 전문은 [v1 가이드](README.md#출처와-사용-조건)와 동일하다. 지원이 끝난 모델의 로컬 청취 시안이라는 범위도 같다.

DSP는 [Librosa 0.11.0 공식 pitch_shift 문서](https://librosa.org/doc/0.11.0/generated/librosa.effects.pitch_shift.html)의 API를 사용했다. 실제 패키지의 [ISC 라이선스](licenses/librosa-0.11.0-ISC.txt), soxr 패키지와 포함된 libsoxr·PFFFT의 고지·라이선스를 `licenses/`에 보존했다. 사용자 데이터나 원문을 원격 합성 서비스로 전송하지 않는다.
