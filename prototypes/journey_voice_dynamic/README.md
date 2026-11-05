# 여행에서 생성된 캐릭터의 목소리 테스트

기존 한국어 Sohee 모델을 사용해 여정 입력에서 캐릭터 레시피·말투·대사·실제 WAV까지 생성한다. 계정이나 외부 API를 사용하지 않는다. 사용자 선호 기준은 Anna로 유지하며, Sohee는 계정 없이 생성 흐름을 실행하는 로컬 엔진이다.

## 만들어 둔 결과 듣기

다음 페이지를 열어 캐릭터별 인사·도착용 대사와 같은 문장 비교를 재생한다.

```sh
open /Users/pig30nidae/NUNTI/prototypes/journey_voice_dynamic/demo/listen.html
```

합성 여정 네 개에서 만든 WAV 12개가 있다. 해안 휴식, 산악 캠핑, 도심 전시, 같은 해안경로의 다음 여행이다. 모델 설치 없이 저장된 파일을 들을 수 있다.

## 새 여행에서 음성 생성하기

저장소 루트에서 기존 가상환경을 사용한다. 새 패키지·모델을 설치하지 않는다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_dynamic/voice_cli.py \
  --state-dir .local/journey-voice-dynamic/my-trips generate \
  --input prototypes/journey_characters/examples/coastal_rest.json
open /Users/pig30nidae/NUNTI/.local/journey-voice-dynamic/my-trips/listen.html
```

자신의 입력을 만들려면 예제 JSON을 복사하고 의미 태그·목적을 바꾼다. 새 출발에는 새 `journeyId`와 `requestId`를 준다. 같은 여행의 reroute에는 `journeyId`를 유지하고 새 `requestId`를 준다. 처음 정한 캐릭터와 목소리를 그대로 반환한다. 입력 필드와 지원 태그는 [레시피 입력 가이드](../journey_characters/README.md#입력과-설계축)를 따른다. GPS와 정밀 주소는 받지 않는다.

`--input` 뒤에 JSON 여러 개를 주면 한 프로세스에서 모델을 한 번 로드해 순서대로 만든다. `--plan-only`를 추가하면 레시피와 음성 설정만 저장하고 모델을 로드하지 않는다.

## 같은 캐릭터에 새 대사 추가하기

앞선 출력의 `characterId`를 사용한다. 다음은 보존한 데모의 첫 해안 캐릭터다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_dynamic/voice_cli.py \
  --state-dir prototypes/journey_voice_dynamic/demo speak \
  --character-id nunti-9a3f63d68e67292a3a33fc5e \
  --text '오늘의 기억은 내가 간직할게.'
```

이 경로도 실제 합성했다. 기존 binding·연기 지시를 유지하며 새 문구만 별도로 저장한다. 같은 문구를 다시 요청하면 WAV를 재사용한다. 긴 원문은 `--text-file`로 전달할 수 있으며 최대 100자다.

## 파일과 재시도 확인하기

```sh
python3.12 prototypes/journey_voice_dynamic/test_pipeline.py
python3.12 prototypes/journey_voice_dynamic/test_export.py
python3.12 prototypes/journey_voice_dynamic/verify.py
.local/voice-audition-asr/venv/bin/python prototypes/journey_voice_dynamic/asr.py --verify-only
```

`test_pipeline.py`는 가짜 오디오 엔진으로 상태 전이·충돌·강제 종료·동시 프로세스를 확인한다. 실제 음질 검사가 아니다. `verify.py`는 보존한 데모의 실제 파일을 읽는다. ASR 재검사는 이미 저장한 전사와 원음의 일치를 확인하며 새 모델 추론을 하지 않는다.

설정·완료된 음원·메타데이터가 손상됐으면 자동 교체하지 않고 오류를 낸다. 모델이나 런타임이 달라져도 기존 캐릭터를 조용히 새 화자로 바꾸지 않는다. 확정된 clip은 중단 후 재사용한다. 게시 전 중단된 합성은 다시 실행될 수 있고, 미게시 임시 폴더가 남을 수 있다.

## Android Debug 자산으로 전달하기

```sh
python3.12 prototypes/journey_voice_dynamic/export_android.py \
  --state-dir prototypes/journey_voice_dynamic/demo \
  --output-dir android/app/src/debug/assets/journey-dynamic
```

이 명령은 실제 12개 WAV를 변환 없이 내보냈다. 같은 출력에는 새 캐릭터를 추가할 수 있다. 출력 경로별 잠금으로 동시 추가를 직렬화하고 WAV 게시 뒤 manifest를 교체한다. 기존 clip을 바꾸거나 삭제하는 출력은 거절한다. 기존 캐릭터를 포함한 원래 state를 유지한다.

새 Debug APK를 설치한 뒤 probe를 종료하고 `voice_catalog=dynamic`으로 새로 실행한다. `local_install`로 파일을 복사하고 `local_greeting` 또는 `local_speak`에 캐릭터 ID를 전달한다. 실제 실행 검사는 [검사 도구](verify_android_runtime.py)와 [보존 결과](android-runtime/verification.json)를 따른다. release APK에는 이 데모 자산이 없다.

Android가 Python 모델을 실행하는 기능은 아니다. 현재는 PC 생성 결과를 Debug 자산으로 가져와 기존 단일 TTS 큐에서 재생한다. 제품의 여행 시작 이벤트·서버 job·실시간 내비 입력과 새 외형 렌더러는 연결하지 않았다.

## 결과 범위 읽기

[연결·검증 보고](../../docs/design/journey-characters/tts-dynamic-generation.md)에 설정 변화·저장 규칙·실행 결과를 기록했다. Sohee 한 화자 안의 연기 변화이며 무한히 고유한 화자를 생성하지 않는다. 새 지시의 귀여움과 자연스러움은 개별 청취 평가를 거치지 않았다. 산 도착 대사의 ASR 차이는 [전사 요약](asr/summary.md)에 남겼다.
