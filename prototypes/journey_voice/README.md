# 여정 캐릭터의 한국어 목소리

이 문서는 첫 목소리 v1의 실행·비교 기록이다. 사용자 청취 피드백을 반영한 더 작은 목소리 후보는 [v2 가이드](README-v2.md)와 [v2 청취 페이지](listen-v2.html)에 별도로 보존했다. 기존 캐릭터의 v1 바인딩을 자동 변경하지 않는다.

캐릭터 생성 레시피의 `voiceIntent`를 **실제 화자 벡터와 합성 속도**에 연결한 로컬 실행 프로토타입이다. 기존 Android/Pleos 발화 경로와 독립돼 있다. 원격 TTS API, 자격증명, 유료 호출, 음성 복제를 사용하지 않는다.

`listen.html`을 브라우저로 열면 세 화자의 같은 문장과 여정별 인사 총 6개 WAV를 비교할 수 있다. HTTP 서버가 필요하지 않다. 실제 생성 파일은 `samples/manifest.json`과 각 WAV 옆 JSON에 원문·화자·모델·설정·파일 해시를 기록했다. 캐릭터 이름과 인사는 합성 여정의 시연용 문장이다. 인사 문구를 자동 생성하는 기능은 없다.

| 창작 방향 | 캐릭터 시안 | 청취 후보 | 실제 적용 |
| --- | --- | --- | --- |
| `calm_warmth` | 바다·휴식, 파도빛 | `nunti-keepsake-calm-v1` | Supertonic 3 F1, 속도 0.95 |
| `gentle_curiosity` | 숲·캠핑, 이끼별 | `nunti-keepsake-curious-v1` | Supertonic 3 M3, 속도 1.03 |
| `quiet_delight` | 도시·전시, 조각빛 | `nunti-keepsake-clear-v1` | Supertonic 3 F2, 속도 1.00 |

이는 유한한 청취 후보 카탈로그다. 감정·귀여움·실제 화자 구별을 사람이 평가한 결과가 아니며, 감정 이름은 캐스팅 의도다. 별도 감정 모델·피치 변환은 적용하지 않는다. 새 캐릭터의 목소리는 후보 안에서 선택하므로 서로 다른 모든 캐릭터가 무한히 고유한 음색을 갖지는 않는다.

## 실행

저장소 루트에서 실행한다. 설치는 약 400MB의 공개 모델과 격리 Python 패키지를 내려받는다. 모든 도구·가상환경·가중치·캐시는 무시된 `.local/journey-voice/`에 저장한다. macOS ARM64/Python 3.12.12에서 검증했다. 다른 플랫폼 실행·성능은 미검증이다.

```bash
bash prototypes/journey_voice/setup.sh
.local/journey-voice/venv/bin/python prototypes/journey_voice/generate_samples.py
open prototypes/journey_voice/listen.html
```

새 레시피 JSON 또는 기존 샘플 배열을 입력할 수 있다. `--recipe-index`는 배열의 0부터 시작하는 위치다.

```bash
.local/journey-voice/venv/bin/python prototypes/journey_voice/voice_cli.py \
  --recipe prototypes/journey_characters/sample-output.json \
  --recipe-index 1 \
  --text '안녕하세요. 오늘의 여행도 함께할게요.' \
  --output .local/journey-voice/my-character.wav
```

`--text` 대신 `--text-file`로 UTF-8 파일을 전달한다. 원문 바이트의 공백과 줄바꿈을 보존해 저장·해시한다. 모델 내부 토큰화는 upstream의 NFKD·공백·문장부호 정규화와 `ko` 태그를 사용하며, 정규화 결과도 `upstreamNormalizedModelText`에 공개한다. 정규화가 발음 정확성을 보장하지 않는다. 지원하지 않는 기호나 이모지는 조용히 지우지 않고 입력 오류로 거부한다. 시연은 문장 길이 100자·예측 음성 30초 이내로 제한한다. 생성 문구의 운전 점수나 사실을 추론하지 않는다.

음성 모델 설치 없이 바인딩만 확인하려면 다음처럼 실행한다.

```bash
python3 prototypes/journey_voice/voice_cli.py \
  --recipe prototypes/journey_characters/sample-output.json --bind-only
```

## 보존과 실패

첫 요청에서 `characterId`에 `profileId`, 실제 `speakerId`, locale, 속도, 추론 단계, 카탈로그 해시, 모델·소스 버전을 묶어 `.local/journey-voice/state/bindings.json`에 원자적으로 보존한다. 같은 캐릭터의 재시도·경로 변경·재시작은 재선택하지 않는다. 다른 여정이 같은 캐릭터 ID를 재사용하면 거부한다. 미정·미지원 intent는 `UNBOUND_INTENT`이며 기본 화자를 대신 쓰지 않는다. 기존 바인딩이 있으면 새 intent가 미정이어도 기존 것을 보존한다.

합성 캐시 키는 정확한 원문 UTF-8 해시, 전체 바인딩, 실제 모델 파일·소스·런타임 설정의 해시로 만든다. 같은 요청은 저장한 WAV 바이트를 재사용한다. 캐시의 누락·변조·불완전 쓰기는 오류로 알리고 자동 재합성으로 숨기지 않는다. 멀티 프로세스의 바인딩·캐시 쓰기는 로컬 파일 잠금으로 직렬화한다. 로컬 POSIX 파일시스템을 전제로 하며 네트워크 파일시스템은 검증하지 않았다.

seed는 실제 생성 때 기록한다. 다른 하드웨어·라이브러리의 새 합성이 같은 바이트가 된다고 보장하지 않는다. 수집 캐릭터의 복원에는 seed만이 아니라 WAV·바인딩·manifest를 함께 보존해야 한다. `.local`을 지우면 바인딩·개인 생성 캐시도 사라진다. 샘플 6개는 `samples/`에 별도 보존했다.

## 검증

```bash
python3 prototypes/journey_voice/test_voice.py
python3 prototypes/journey_voice/verify_samples.py
.local/journey-voice/venv/bin/python prototypes/journey_voice/verify_runtime.py
```

19개 정책·저장 경계 검사는 재시작·reroute 보존, 서로 다른 여정, 미정 intent, 원문 바이트·공백·줄바꿈 보존, 캐시 재사용, 모델 런타임 분리, 변조와 불완전 쓰기 거부를 다룬다. 합성 자체를 대신 입증하지 않는 테스트 대역을 사용한다. `unit-verification.txt`에 결과를 보존했다.

별도 실제 ONNX 실행으로 3화자 × 같은 문장 1개와 여정별 인사 1개, 총 6개를 생성했다. `verify_samples.py`는 각 WAV의 SHA-256, PCM16·단일 채널·44.1kHz, 실제 프레임 길이, 비무음 파형, 공통 문장의 동일 텍스트·서로 다른 3화자/파일을 검사한다. 결과는 `sample-verification.json`에 있다. 소리가 사람에게 귀엽게 들리는지, 한국어 발음이 정확한지, 장시간 듣기에 편한지, 운전습관에 영향을 주는지는 미검증이다.

`verify_runtime.py`는 테스트 대역 없이 실제 CLI 3개 프로세스를 실행한다. UTF-8 파일의 줄바꿈·이중 공백 보존, 첫 실제 ONNX 합성, 프로세스 재시작 시 캐시 적중, 목적지·음성 intent가 바뀐 reroute에서도 같은 바인딩과 WAV 바이트 재사용을 확인한다. 결과는 `runtime-verification.json`에 보존했다.

후속 Android 연결은 별도 담당이 진행한다. 이 디렉터리의 합성 성공과 개발 PC의 계산 시간은 Pleos SDK 발화 성공·차량 스피커 출력·가청 시작 지연을 입증하지 않는다.

## 출처와 사용 조건

- [Supertonic 소스 보관소](https://github.com/supertone-oss-archive/supertonic/tree/1e9799e964ea4c0dad7cde993b65c3c813a7b373), 고정 commit `1e9799e964ea4c0dad7cde993b65c3c813a7b373`. 검토한 `py/helper.py`만 `vendor/supertonic_helper.py`에 원본 그대로 포함했다. [MIT 라이선스](licenses/supertonic-code-MIT.txt)를 함께 보존했다.
- [Supertonic 3 공개 모델](https://huggingface.co/supertone-oss-archive/supertonic-3/tree/aafc6e32416a594460b32413efc49d7fe4ce6d46), 고정 revision `aafc6e32416a594460b32413efc49d7fe4ce6d46`. [모델 Open RAIL-M 라이선스 전문](licenses/supertonic-3-model-license.txt)을 보존했다. 코드와 모델의 라이선스가 다르다. 가중치는 저장소에 포함하지 않는다.
- upstream은 2026-09-09 보관 안내에서 개발·지원 종료를 명시했다. 이번에는 재현 가능한 로컬 청취 프로토타입으로 채택했다. 운영 공급자나 장기 지원 모델을 확정한 결정은 아니다.
- `model-lock.json`의 큰 ONNX는 게시된 LFS SHA-256, 작은 JSON은 고정 Git blob SHA-1과 크기로 검증하며 실제 SHA-256도 각 합성 manifest에 기록한다. 임의 원격 Python이나 `trust_remote_code`를 실행하지 않는다. 설치 패키지 버전은 `requirements.lock.txt`에 고정했다.
