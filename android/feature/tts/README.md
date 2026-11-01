# Nunti TTS core

순수 Kotlin/JVM 음성 요청 검증, 프로필/감정 메타데이터, 정책, 큐 및 Provider 수명 관리.
`../voice`는 실제 Android/Pleos SDK 경계다. 공통 계약과 앱 shell은 수정하지 않는다.

## 실행

JDK 17 이상 및 Python 3.9 이상에서:

```sh
python3 android/feature/tts/scripts/verify.py --bootstrap --android
```

첫 실행만 공식 Maven/Google/Pleos 저장소에서 SHA-256으로 고정한 도구를 다운로드한다.
그다음에는 `--bootstrap` 없이 오프라인 실행 가능. `--tools-dir`로 캐시 위치를 지정한다.
62개 자동 테스트와 8개 실제 SERVER/AVATAR fixture 검사 로그, A~D Mock 시연 로그, 실제 Android/Pleos 바이너리 컴파일 결과는
`build/verification/`에 생성된다. SDK 실행/에뮬레이터 검증을 대신하지 않는다.

앱 shell에 모듈이 포함되면 `:feature:tts:verifySpeech`, `:feature:tts:demo`,
`:feature:voice:assembleDebug`를 사용할 수 있다. AVATAR 통합 `assembleDebug`도 통과했다. 차량에서의 실제 재생은 별도 검증해야 한다.

## 경계와 기본값

- `SpeechContractBridge`: SERVER v1 projection. provenance/contentSource와 speechPurpose 분리.
  `SpeechEvidence`는 신뢰된 호스트가 공급한다. 외부 JSON의 `verified: true` 같은 값을 그대로 신뢰하지 않는다.
- `SpeechRequestBuilder`: 원문 보존, ID/길이/TTL/출처/아바타·감정 정합성 검사.
- `VoiceProfileManager`, `EmotionVoiceMapper`: 논리적 스타일만 선택. SDK 미지원 rate/pitch/emotion 전송 안 함.
- `SpeechQueueManager`: 단일 실행 스레드. 최대 8 pending, trip당 4,096 ID, 최대 TTL 120초.
  음성 시작 timeout 3초, 초기화 5초, 재생 최대 30초. 로그 sink에는 텍스트와 인증 정보가 없다.
- 주행 중 80 codepoint, 최소 간격 15초, 같은 문구 60초 제한. 제품 초깃값이며 차량 법규의 숫자가 아니다.
- 플랫폼 상태 freshness 5초. 호스트는 실제 조회 결과로 heartbeat를 제공해야 한다. 캐시의 시간만 갱신하면 안 된다.
- 요청은 거부/취소 시 자동 재시도하지 않는다. 서버 보고서는 별도 저장된 상태를 사용자 요청으로 다시 읽을 수 있다.
- 앱 재시작은 빈 큐. 새 세션 시작 이전 `requestedAt`은 거부한다. 자동 offline replay를 만들지 않는다.
- Suspend는 session close. Resume 시 새 `AndroidVoiceSession`을 생성하고 최신 차량 상태로 다시 평가한다.

## Provider

`MockTtsProvider`는 소리를 만들지 않는 결정적 시뮬레이터다.
`PleosTtsProvider`는 실제 SDK wrapper인 `AndroidPleosConnection`을 주입받는다.
테스트에서만 fake connection을 사용한다. 실제 SDK에는 요청 ID가 없어서,
terminal 이후 연결을 폐기하고 새 연결 및 generation으로 오래된 콜백을 격리한다.
첫 요청 이후 재초기화 지연은 차량에서 측정해야 한다.

`ON_DEVICE` 기본. `HYBRID`/`SERVER`는 호스트가 `PleosCredentials`를 메모리로 공급한다.
키를 소스/로그에 넣지 않는다. SDK의 앱 등록 방식과 앱 자격 증명 배포 요구사항은 Pleos와 확인한다.
HYBRID 등록 실패를 성공으로 처리하지 않으며 재생 중 SDK fallback은 SDK 책임이다.
오류 후 원문을 재전송하여 중복 발화시키지 않는다.

## 한국어 참고 오디오

`demo/reference-ko.wav`는 **macOS Yuna**로 생성한 발음·문장 길이 확인용 파일이다.
Pleos 음질, 캐릭터 최종 음색, 감정 표현, 차량 지연 또는 상업적 음원 재사용 권한을 검증한 파일이 아니다.
각 문장 앞에 실제 PCM 묵음 180ms를 넣었다. Pleos SDK 선행 묵음 구현 증거로 사용하지 않는다.
재생성은 macOS에서 `python3 android/feature/tts/scripts/reference_audio.py`로 한다.
시연 입력은 `demo/approved-ko.txt`; Mock A~D는 `SpeechDemo.kt`.

세부 지원 범위/협업/실차 체크리스트: `docs/coordination/tts.md`.
