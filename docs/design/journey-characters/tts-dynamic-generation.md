# 캐릭터 생성에 따른 음성 연결 결과

2026-11-02 사용자 요청은 "이 정도면, 가능합니다. 이제, 생성에 따라 바뀌면 되겠습니다."다. 현재 시제품 수준에서 생성 연동을 진행하라는 뜻으로 적용했다. 후속 선택은 "Anna가 여전히 가장 가까움"이므로 Anna 선호를 유지한다. 계정 연결은 앞선 결정대로 보류했다. 로컬 자동 생성에는 기존 Qwen CustomVoice Sohee를 사용한다. Sohee를 최종 선호 화자로 바꿨다는 기록은 아니다.

## 생성 흐름

`voice_cli.py`가 의미 태그와 목적이 있는 여행 입력을 받아 기존 `recipe_cli.py`로 최초 캐릭터 레시피를 저장한다. `settings.py`는 레시피의 목적·몸체 계열·이름 어근·seed에서 별도의 음성 plan을 정한다. `engine.py`는 실제 direction·seed·원문을 고정된 한국어 Sohee 모델에 전달한다.

휴식은 차분하고 느긋한 표현, 캠핑은 따뜻한 호기심, 전시는 작고 명료한 즐거움을 요청한다. 몸체 계열은 부드럽거나 둥근 표현의 보조 지시를 더한다. 목적지 태그는 대사 주제를 정한다. 같은 문장 비교용 대사도 각 캐릭터의 지시로 합성했다. 이 지시는 실제 모델 입력이며, 희망한 음향 특성이 모두 지각적으로 구현됐다는 측정 결과는 아니다.

원래 레시피 ledger와 과거 v1·v2 음원은 보존한다. 새 plan은 `voiceBinding`과 `character.json`의 소유자다. 생성한 표시 이름도 여기서 별도로 확정한다. 기존 C 이미지나 새로운 2.5D 외형을 자동 생성한 결과로 표기하지 않는다.

## 정체성과 실패 경계

| 상황 | 동작 |
| --- | --- |
| 새 여행 ID | 새 캐릭터·seed와 레시피에 맞는 음성 plan 생성 |
| 같은 여행의 재시도·reroute | 최초 레시피·plan·대사·완료 WAV 유지 |
| 같은 캐릭터의 새 문구 | 같은 voice binding에서 문구별 자산 추가 |
| 같은 문구 재요청 | 원문·설정·metadata·실제 WAV를 확인하고 캐시 반환 |
| 다른 여행에 request ID 재사용 | 기존 데이터 변경 전 거절 |
| 완료 자산 누락·변조 | 자동 재합성·기본 화자 전환 없이 오류 |
| 모델·runtime 변경 | 동결한 fingerprint와 다르면 기존 캐릭터 생성 거절 |
| 중단·동시 실행 | 한 state의 전체 명령을 잠금으로 직렬화하고, WAV·metadata를 한 디렉터리로 게시 |

확정 전에 중단된 합성은 다시 수행할 수 있다. 별도 state들의 GPU 실행까지 조정하지 않으므로 같은 컴퓨터에서 여러 state의 모델 작업을 동시에 실행하지 않는다. 원시 journey ID를 경로에 사용하지 않는다. 도로 사실과 이동 거리는 검증된 운전 이벤트나 희귀 보상을 생성하지 않는다.

## 실제 검증

- 합성 여정 4개에서 WAV 12개를 생성했다. 같은 해안 경로의 다음 여행은 다른 캐릭터·seed·몸체와 다른 연기 지시를 받았다.
- 새 프로세스 재실행은 12개 캐시 적중, 모델 로드 없음, 원래 12개 WAV 해시 일치였다.
- 기존 해안 캐릭터로 새 문장 "오늘의 기억은 내가 간직할게."를 실제 합성했다. 같은 binding과 direction을 유지했다.
- 독립 파일 검사는 실제 4개 plan·12개 WAV의 원문·해시·PCM·설정·모델 pin을 읽었다. [검사 결과](../../../prototypes/journey_voice_dynamic/verification.json)를 따른다.
- ASR 13개 중 12개는 정규화 원문과 일치했다. 산 도착 대사의 `산빛을`이 `삼비칠`로 인식돼 발음 청취 확인이 남았다. ASR 오류인지 TTS 발음 문제인지는 단정하지 않았다. [실제 전사](../../../prototypes/journey_voice_dynamic/asr/summary.md)에 보존했다.

현재 모델은 고정된 `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit`, revision `41d3337e8b7f2843a75841595fc14e4b9a7a4b96`다. 기존 MLX 환경·모델 파일을 재사용했다. Anna 음원·실인물 녹음을 참조하지 않았고 외부 API·새 모델 다운로드·피치나 속도 후처리는 없다.

## Android 전달

기존 `LegacyCatalog`와 새 `DirectedSohee`를 sealed source identity로 구분했다. 기존 fingerprint 계산과 저장 ledger를 유지하고, 새 형식은 실제 모델 revision·engine fingerprint·direction hash·seed를 고정한다. Qwen에 없는 Supertonic speed·steps 값을 꾸며 넣지 않는다.

별도 `journey-dynamic` Debug 자산으로 원본 WAV 12개와 v2 manifest·라이선스를 내보냈다. 기존 서명의 Debug APK를 데이터 삭제 없이 업데이트했다. 실제 Pleos user10에서 JSON parser를 거쳐 설치한 12개 파일의 해시가 원본과 일치했다. 캐릭터 4개의 QUEUED→STARTED→COMPLETED, 반복 차단, 중지·백그라운드 취소를 포함한 10개 사례를 통과했다. [런타임 결과](../../../prototypes/journey_voice_dynamic/android-runtime/verification.json)를 따른다.

인증된 에뮬레이터 스피커 PCM도 한 번 수집했다. 같은 문장의 다른 3개 캐릭터 출력을 대조군으로 함께 측정했다. [대조 결과](../../../prototypes/journey_voice_dynamic/android-runtime/source-capture-comparison.json)는 출력 대응의 보조 자료이며 음질·화자 고유성·취소 후 무음 지연 판정은 아니다.

Debug·Release 빌드와 Debug lint를 통과했다. Debug APK의 새 자산은 원본과 바이트가 같고 release APK의 `journey-dynamic` 자산은 0개였다. 기존 정책과 취소 후 무음 측정의 한계를 이번 결과로 확대하지 않는다.

## 완료와 남은 범위

완료한 것은 로컬 여행 입력→캐릭터 레시피→캐릭터별 연기·대사→실제 음원→Android Debug 큐 재생이다. [실행 가이드](../../../prototypes/journey_voice_dynamic/README.md)에서 직접 시험한다.

현재 변화는 Sohee 한 화자 안의 표현 변화다. 무한히 고유한 새 화자, Anna API 재현, 새 2.5D renderer·rig, 제품의 여행 시작 트리거·서버 생성 job·컬렉션 연결, 실차·장기 청취·운전습관 개선은 완료하지 않았다. 추가 방향별 사람 청취 평가도 별도다.
