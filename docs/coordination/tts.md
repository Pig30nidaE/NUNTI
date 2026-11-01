# TTS 구현 및 검증 기록

검증일: 2026-11-01 (Asia/Seoul). 소유: `android/feature/tts/`, `android/feature/voice/`, 이 문서.
작업 브랜치 `codex/tts-system`, worktree `/private/tmp/nunti-tts-worktree`, 기준 `da3e322`.
공통 계약, 서버, 아바타, 루트 Gradle 및 앱 shell은 변경하지 않았다.

## 현재 상태

- JVM 정책·큐·프로필·감정 매핑·Mock·Pleos 연결 수명 코드를 구현했다.
- 자동 테스트 62개 + 실제 JSON fixture 통합 검사 8개 통과, A~D Mock 시연 통과.
- 공식 Pleos AAR 3.3.1 + Google Android 35 및 android.car JAR로 실제 adapter 컴파일 통과.
- 설치된 JDK: Temurin 21.0.8, Oracle 20.0.2. 검증은 JDK21/Kotlin compiler 2.2.20, JVM target17.
- 개발 시작 시 Android Studio/adb/Gradle/Kotlin CLI/Pleos 에뮬레이터는 확인되지 않았다.
  SDK 바이너리와 컴파일러만 임시 캐시에 다운로드했고 설치된 차량 SDK/실기기로 오인하지 않는다.
- AVATAR 통합 Gradle `assembleDebug` 성공(AGP8.10.1/Kotlin2.2.21/Gradle8.11.1/JDK21).
  `app-debug.apk`에 TTS/voice 및 실제 Pleos TextToSpeech class가 포함된 것을 DEX로 확인했다.
  APK 위치: `/private/tmp/nunti-avatar/android/build/app/outputs/apk/debug/app-debug.apk`.
  초기 통합 검증 당시 AVATAR 기준 `f6ad9ac`, 해당 APK SHA-256
  `bdef0dd81b28f91dfaad570b7c0a9b8a801aad87a3a557148efe8f962174b547`.
  해당 Lint XML은 오류 0개/경고 7개였으며 APK 내 TTS/Pleos 클래스도 재확인했다.
  이후 루트 런타임 검증 APK와 최종 결과는 [SERVER 런타임 보고서](../architecture/pleos-runtime.md)를 기준으로 한다.
  이전 `2159214e...`는 첫 성공 빌드의 해시이고 현재 APK와 구분한다.
  포장 검증 기록: `build/verification/apk-packaging.json`.
- 후속 Pleos Connect 2.1.0 ARM/API34 에뮬레이터에서 ON_DEVICE 초기화·재생·사용자 중지·백그라운드 취소·반복 억제를 검증했다.
  SERVER가 실행했으며 TTS 세션은 저장된 원시 이벤트, lifecycle 결과와 WAV 통계를 다시 검사했다(아래 후속 검증).
- 인간 청취에 의한 한국어 내용/음질, 첫 음절, mode별 fallback, 실차 오디오 지연은 **미검증**.
- `demo/reference-ko.wav`는 macOS Yuna 참고 음성이다. `tts-first.wav`/`tts-final.wav`는 에뮬레이터 출력 캡처로 별개다.

재현:

```sh
python3 android/feature/tts/scripts/verify.py --bootstrap --android
```

다운로드는 공식 배포 URL만 사용하고 `scripts/toolchain-lock.json`의 SHA-256을 검사한다.
SDK/JAR은 Git에 포함하지 않는다. 테스트·시연·컴파일 증거는 `android/feature/tts/build/verification/`에 생성.
전체 앱 Gradle도 AVATAR 환경에서 통과했다. 첫 빌드에서 드러난 Java21/Kotlin17 타깃 불일치를
TTS 모듈의 Java source/target17 명시로 수정했다. APK 패키징 성공은 차량에서의 실행 성공을 의미하지 않는다.

## 실제 SDK 지원과 불확실한 기능

| 항목 | 근거 및 구현 | 실행 검증 |
|---|---|---|
| initialize / release | OnInitializeListener success/failure와 새 객체 재초기화 사용 | JVM fake 테스트 + 에뮬레이터 초기화 관찰; 실차 미검증 |
| setLocale | `Locale.forLanguageTag`, 기본 ko-KR. 공식 locale 목록만 노출 | 실제 바이너리 컴파일 |
| speak / stop | `speak(text, true)`, 중단/오류 시 취소, 원문 재전송 안 함 | Pleos 에뮬레이터 재생 완료·사용자 취소·BACKGROUND 이벤트 검증 |
| listener | Ready/Start/Done/Stop/Error/RMS, 동일 인스턴스 제거, 중복 등록 억제 | JVM fake 테스트 |
| ON_DEVICE | 기본 선택, 앱 등록 생략 | Pleos 에뮬레이터 초기 발화 관찰 + PCM 캡처; 네트워크 차단 시험은 별도 |
| HYBRID | 앱 등록/연결 후 요청. 등록 이후 fallback은 SDK 담당 | 전환 음색/지연/실기기 동작 미검증 |
| SERVER | 연결 성공 대기, 실패 반환, 자동 재발화 없음 | Mock 네트워크 오류 및 fake 등록 실패 검증 |
| setSpeakerType(String) | 메서드 존재를 AAR `javap`로 확인. 허용 문자열/목록 미확인 | 호출하지 않음 |
| setAudioAttributes | 존재/시그니처 확인; focus와 동일 속성 전달 | 실제 바이너리 컴파일 |
| setAudioZoneId(Int) | 존재 확인; 지정할 zone 정책 미확인 | 호출하지 않음 |
| rate/pitch/prosody/emotion | 확인한 public SDK에 조절 메서드 없음 | 적용하지 않음 |
| 볼륨 제어 | RMS는 출력 신호 관찰이지 볼륨 설정 API가 아님 | Duck 요청 시 취소 |
| 선행 묵음/PCM export | 확인한 SDK surface에 패딩·PCM 결과 API 없음 | SDK 내부 처리/OEM 확인 필요 |

문서의 `EventListener.onReady`는 발화 요청 준비 이벤트이며 SDK 초기화 성공으로 사용하지 않는다.
SDK event에 requestId가 없으므로 terminal마다 listener 해제/release 후 새 connection을 사용한다.
이전 generation의 콜백은 모두 무시한다. 안정성을 위한 선택이며 재연결 지연은 반드시 실측한다.

공식 근거:

- [SDK 소개와 mode](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/intro)
- [Maven/버전](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/importing-sdk)
- [초기화와 해제](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/initialization-and-release)
- [한국어와 locale](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/set-locale)
- [앱 등록](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/app-registration)
- [이벤트](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/event-listeners)
- [시작/중지](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/start-and-stop)
- [API 목록](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/text-to-speech/ai.pleos.playground.tts/text-to-speech/entry)
- [오류](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/TextToSpeech/error-code)

## 구조와 데이터 제안

`WireSpeechRequest + SpeechEvidence + AvatarVoiceInput + EmotionSnapshot`
→ `SpeechContractBridge` → `SpeechRequestBuilder` → `VoiceProfileManager / EmotionVoiceMapper`
→ `SpeechPlaybackPolicy` → `SpeechQueueManager` → `TtsProvider` → `AndroidPleosConnection`.
`AndroidVoiceSession`이 main looper, clock, scheduler, focus 및 lifecycle을 결합한다.

VoiceProfile은 id/locale/preferredVoiceId/baseSpeakingStyle/supportedControls/fallbackMode를 가진다.
기본 id `nunti-default-v1`, ko-KR, 화자 미지정(플랫폼 기본), ON_DEVICE.
실제 적용된 locale/speaker/control, 무시된 control, 논리적 감정 스타일, fallback 여부를 이벤트에 기록한다.
`fallbackMode`는 프로필 메타데이터이며 재생 중 임의 engine 전환 명령이 아니다. 세션 mode는 생성 시 고정한다.
지원하지 않는 preferredVoiceId는 플랫폼 기본값으로 유지한다. 지원하지 않는 locale은 거부한다.
프로필 id 누락/미등록은 기본 프로필을 적용한다. 지원 목록은 서버 선언이 아닌 provider capability를 기준으로 한다.

SpeechRequest는 requestId/tripId/avatarId/text/emotion/voiceProfileId/tripPhase/priority/requestedAt/expiresAt 및
발화 목적, emotionId/sourceEventId를 갖는 **로컬** 모델이다. 로컬 contentSource enum은 목적 의미이며,
wire에서는 아래 합의에 따라 speechPurpose로 매핑한다. JSON 계약을 로컬 data class 이름으로 재정의하지 않는다.

SERVER와 2026-11-01 메시지로 합의:

- wire `contentSource`: MOCK / TEMPLATE / EXTERNAL_REPORT 그대로 유지(텍스트 provenance).
- `speechPurpose`: PRE_DRIVE_GREETING / VERIFIED_EVENT_RESPONSE / USER_INITIATED / POST_DRIVE_REPORT 추가.
- sourceEventId / emotionId 추가. 공통 계약 편집은 SERVER가 수행한다.
- AvatarSpec의 persona/style 중복 필드 요청은 철회. VoiceProfile.persona/speakingStyle 참조로 충분하다.
- 재생 상태 서버 업로드는 MVP 필수 경로가 아니다. 로컬 observer 이벤트로 제공한다.

`SpeechEvidence`는 신뢰된 앱 경계의 승인, 확인된 이벤트 ID, 사용자 동작, Mock 허용 여부다.
외부 `contentSource` 이름 자체를 승인 증거로 삼지 않는다. MOCK은 기본 거부.
구형 TEMPLATE는 PRE_TRIP 첫인사, EXTERNAL_REPORT는 POST_TRIP 리포트만 좁게 추론하고
그 외 목적 누락은 거부한다. 알 수 없는 enum/schema는 거부한다.
`tryFromWire`와 `AndroidVoiceSession.submitWire`는 이를 REJECTED 결과로 반환하여 앱으로 예외를 전파하지 않는다.
실제 SERVER의 SpeechRequest/VoiceProfile/EmotionSnapshot JSON을 매핑·builder까지 통과시켰다.
AVATAR 생성 프로필/감정 JSON도 검사했다. 서로 다른 avatarId를 가진 AVATAR 예제의 잘못된 조합은 거부한다.
fixture와 출처는 `android/feature/tts/src/test/fixtures/`, 결과는 `build/verification/integration.txt`.
최종 코멘트는 공백/줄바꿈을 포함해 원문 그대로 전달한다. 점수 계산/위험 판정/문장 생성은 수행하지 않는다.

감정 매핑:

| 감정 | 논리적 스타일 | 실제 음향 제어 |
|---|---|---|
| NEUTRAL | natural | 기본 화자 유지 |
| RELAXED | calm | 기본 화자 유지 |
| CONCERNED | brief-concern | 기본 화자 유지 |
| STARTLED | brief-surprise | 기본 화자 유지 |
| RELIEVED | relief | 기본 화자 유지 |
| JOYFUL | warm-joy | 기본 화자 유지 |

감정 텍스트는 AVATAR/승인된 템플릿/리포트 담당이 제공한다. TTS가 사실이나 감탄사를 추가하지 않는다.
경로별 persona/styleHint는 메타데이터로 수용하지만 미검증 acoustic control로 변환하지 않는다.
HYBRID의 서버/온디바이스 간 음색 일치도는 보장할 수 없으며 실측 항목이다.

## 출력 정책과 큐

- trip id/phase가 현재 로컬 상태와 일치하고 설정·foreground·비Suspend 상태여야 한다.
- 실제 motion과 CarUxRestrictions가 알려져 있어야 한다. PRE_TRIP/POST_TRIP 문자열만으로 주차를 믿지 않는다.
- ALLOWED speech permission을 호스트가 제공해야 한다. 주행/일시정차/DO 필요 상태는 앱 주행 허가도 요구한다.
- CarUxRestrictions bit만으로 모든 TTS를 허용하거나 금지하지 않는다. 검토된 기능별 권한과 조합한다.
- 통화/내비/중요 차량 오디오 BUSY 또는 UNKNOWN이면 억제한다. focus를 얻더라도 이 정책을 우회하지 않는다.
- 주행 시 검증 이벤트/사용자 요청만, LOW 제외, 최대 80 codepoint, 시작 간격 15초.
- 문구 반복 60초, 큐 최대 8, trip당 seen ID 4096. 한도 이후 새 요청은 거부하고 과거 dedup ID를 버리지 않는다.
- 높은 우선순위는 더 낮은 pending을 제거하거나 진행 중인 낮은 요청을 취소할 수 있다. 차량 정책은 우회하지 않는다.
- TTL 최대 120초. 초기화 5초/음성 시작 3초/재생 30초 watchdog.
- 수신 시/큐 출고 시/시작 callback/주기적 watchdog에서 다시 검사한다. 만료는 monotonic deadline도 사용한다.
- 플랫폼 상태 5초 초과 시 중단. 호스트는 실제 조회로 신선도를 갱신해야 한다.
- 취소·거부 요청을 큐에 계속 보관하거나 자동 재생하지 않는다. POST_TRIP 리포트는 원본 저장소에서 새 사용자 요청으로 읽는다.
- 새 trip/취소/포커스 상실/백그라운드/종료 시 큐를 정리한다. Suspend는 session dispose, Resume는 새 session.
- 재시작 시 큐 복원 없음. session 시작 이전 요청은 거부한다. 지연 서버 재전송을 새 발화로 취급하지 않는다.

숫자는 프로젝트의 보수적인 초기 제품 정책이며 OEM이 정한 수치라고 주장하지 않는다.
100ms watchdog 및 callback 시점은 실제 스피커 첫 샘플 시점과 다를 수 있다. 차량에서 만료 경계 지연을 실측한다.

오디오 focus: NOTIFICATION + CONTENT_TYPE_SPEECH + TRANSIENT_MAY_DUCK,
delayed focus 불허. SDK와 같은 AudioAttributes 사용. LOSS/TRANSIENT/CAN_DUCK 시 중단/반납,
focus gain만으로 재개하지 않는다. 실제 시스템 matrix 판단을 따른다.
음량 API를 임의로 만들어 duck을 흉내내지 않으며 spoken content는 중단하는 정책이다.

근거: [Pleos Audio Focus](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/audio-focus-development-guide/audio-focus-development),
[CarUxRestrictions](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/driving-restriction-development-guide),
[Suspend](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/audio-focus-development-guide/suspend-mode-audio-focus).

## AVATAR 통합 요청

직접 메시지 전달 완료. 대기 중에도 Mock으로 독립 구현했다.

1. 루트 plugin kotlin jvm/android 및 com.android.library 버전, 두 모듈 include, Pleos Maven 등록.
2. 앱에서 feature:voice 및 feature:tts 의존성, android.car 환경 및 TTS 권한 합성 확인.
3. applicationContext로 main thread에서 AndroidVoiceSession 생성; lifecycle 연결.
4. 현재 trip/phase, 실제 motion, CarUxRestrictions, 검토된 기능 허가, 설정,
   통화·내비·중요 오디오, foreground/suspend의 신선한 상태 공급. 모르면 UNKNOWN.
5. AvatarSpec.voiceProfileId → VoiceProfile 참조, EmotionSnapshot id/trip/avatar/emotion 일치 전달.
6. Suspend 이후 새 session 생성. SDK가 없는 일반 host는 Mock으로 분기.
7. 사용자 발화 요청 및 인증된 서버/이은룡 리포트 경계에서만 content evidence 승인.

로컬 SpeechEvent: QUEUED/STARTED/COMPLETED/CANCELLED/REJECTED/FAILED,
requestId/tripId/reason/appliedVoice/mode/startLatencyMs. startLatency는 monotonic submit→SDK onStart이며
실제 첫 가청 샘플 지연으로 단정하지 않는다. 원문/비밀키는 event/log에 포함하지 않는다.

## 선행 묵음과 실차 검증

[Pleos 가이드](https://document.pleos.ai/docs/pleos-only/vehicle-app-developer-guide/voice-guidance-preroll-silence-guide)는
150~200ms를 권장하며 오디오 데이터 앞단 삽입을 우선한다.
직접 출력하는 SDK에 결과 PCM 접근이 없어 구현했다고 표시하지 않는다.
문장 앞 공백/SSML/Thread.sleep/단순 delayed speak로 padding을 가장하지 않는다.
SDK/OEM이 기본 padding을 제공하는지 확인하고, 미제공이면 공식 지원 방식 또는 합법적 클립 경로를 협의한다.

차량/에뮬레이터 후속 체크리스트(주차 ON_DEVICE 재생·중지·background·반복 억제 외 항목은 별도 검증 필요):

- TTS_SERVICE 권한, ON_DEVICE 초기화/ko-KR/Ready→Start→Done, stop→onStop, 반복 listener 누수.
- 실제 허용 화자 값과 default voice 확인, mode별 같은 화자 정체성 청취.
- HYBRID 앱 등록/연결 후 네트워크 단절 fallback, 최초 오프라인 진입, SERVER 단절 오류, ON_DEVICE 무네트워크.
- 내비·음악·통화·Gleo·안전/긴급음 및 다중 holder 조합의 grant/reject/duck/stop.
- CarUxRestrictions 변경, signal 단절, STOPPED/MOVING, background/Suspend/Resume.
- 요청 만료/초기화 지연/합성 지연 도중 차량 상태 변경 후 늦은 오디오가 나오지 않는지.
- 각 문장 첫 음절 손실, 앞 묵음, RMS/onStart와 실제 microphone loopback 시간 차이.
- 장시간(1시간 이상) 반복 시 listener/service 연결/메모리/focus 누수.

음질·성능 평가 프로토콜: 제공된 A~D 문장과 날짜/숫자/도로명 포함 승인 문장 30개,
ON_DEVICE/HYBRID/SERVER별 cold/warm 및 offline 각 최소 30회. 첫 가청 샘플 지연 p50/p95,
SDK onStart 지연 p50/p95, 취소→무음 시간, 첫 음절 누락률, 발음 정확도, 화자 일관성,
5점 자연스러움/감정 전달 평가를 기록한다. 반복 실험/p50/p95 측정값은 **없음**.
아래의 개별 73ms/41ms SDK callback 관찰이나 Mock 0ms를 가청 지연/품질 benchmark로 사용하지 않는다.

## 후속 에뮬레이터 런타임 검증

2026-11-01 SERVER 세션의 공식 Pleos Connect 2.1.0 ARM/API34 에뮬레이터 검증이다.
초기 Android35 컴파일 검증 및 실제 차량 검증과 구분한다. 진단 Activity는 debug/emulator 전용이며,
경로·감정 입력은 Mock, 주차/UX 관측은 실제 에뮬레이터 Car 상태다.

- SERVER 관찰: 앱 PID12010에서 ON_DEVICE initialize → NOTIFICATION AudioAttributes → listener → ko_KR.
- SERVER 관찰: QUEUED → STARTED(submit부터 73ms) → COMPLETED(발화 약5.05초).
  이 수치는 첫 가청 샘플 측정이 아니며 한 번의 callback 관찰이다.
- root `initial-logcat.txt`에서 실제 gear4(P)/speed0/UX known/DO=false 및 debug Mock 표시를 확인했다.
- TTS_SERVICE/CAR_POWERTRAIN/CAR_SPEED 권한 grant, focus-empty/in-call=false는 SERVER 관찰이다.
  경쟁 오디오는 운영자가 통제한 테스트 조건이며 일반 앱의 자동 상태 탐지 검증으로 확대하지 않는다.
- gRPC speaker 출력 캡처 `tts-first.wav`: 48,000Hz, 16bit, stereo, 407,117 frames, 8.4816초.
  TTS 세션이 파일을 다시 읽어 nonzero samples300,794, peak1,408, RMS207.3769를 확인했다.
  캡처 길이에는 발화 전후 구간이 포함되므로 발화 시간5.05초와 다르다.
- WAV SHA-256: `417cefdc4d3b8229efa058d8605949c5445be2c6c81cbfff3b2f1b9f39b49ada`.
- 캡처는 호스트 마이크가 아닌 에뮬레이터 speaker 경로다. 인간 청취/한국어 내용 정확도/첫 음절 품질은 미검증.
- 발화·SDK 초기화 원시 로그와 권한 자료가 최종 보존되었다: `tts-initial-app-log.txt`,
  `final-logcat.txt`, `events.jsonl`, `package-permissions.txt`. 초기 로그만 있던 시점의 증거 누락은 해소됐다.
- 최종 요청 `probe-490bbbf0-93c5-40bd-b3bc-3fd3655ee1ad`의 원시 이벤트 순서를 TTS 세션에서도 검사했다:
  13:08:08.185912Z QUEUED → 13:08:08.226394Z STARTED(41ms) → 13:08:11.958046Z COMPLETED.
  초기73ms와 최종41ms는 각각 한 요청의 callback 지연이다. 가청 시점 또는 통계 benchmark가 아니다.
- `lifecycle-results.json`의 4가지 관찰을 확인했다: USER_CANCELLED, BACKGROUND,
  stop 이후 동일 문구 REPEATED_TEXT, background 복귀 후 동일 문구 REPEATED_TEXT.
  취소 이벤트 시점 이후 실제 speaker가 무음이 되는 시간은 별도 측정 대상이다.
- 최종 `tts-final.wav`를 다시 읽어 48kHz/16bit/stereo, 7.166875초, nonzero293,067,
  peak1,409, RMS225.5789가 JSON과 일치함을 확인했다. 초기 WAV와 최종 WAV를 구분한다.
- 재생 중 D/속도 전환 및 P 복귀는 **미검증**이다. Virtual Console은 HTTP503
  `emulator_inactive` 및 `dds_ready=false`, `hmg_car_service`는 미존재,
  `car_service`는 user build 제한으로 상태 변경 경로를 사용할 수 없었다.
  주행 정책의 JVM 테스트 통과를 실제 D 전환 성공으로 확대하지 않는다.
- HYBRID/SERVER, 인간 청취 음질·첫 음절·선행 묵음, 최초 가청 샘플 지연, 실제 차량 및 장시간 누수 검증은 남아 있다.

최종 실행 범위·재현 방법·플랫폼 제한·APK 출처는
[SERVER Pleos 런타임 보고서](../architecture/pleos-runtime.md)를 기준으로 한다.
주요 증거는 `docs/architecture/validation-evidence/pleos-runtime/`의
`events.jsonl`, `lifecycle-results.json`, `tts-final.json`, `tts-final.wav`다.

## 외부 감정형 TTS 비교

판단: MVP는 A 유지. 음질 측정에서 구체적인 결함이 확인될 때 B 또는 C를 작은 범위로 검증한다.
D는 모델/권리/운영 체계가 별도로 확보되기 전 필수 의존성으로 삼지 않는다.
아래 비용·난이도는 구조에 따른 정성 판단이며 견적/벤치마크가 아니다.

| 평가 | A Pleos | B 사전 클립 + Pleos | C 외부 API | D 자체 호스팅 |
|---|---|---|---|---|
| 한국어 음질 | 실제 ko-KR 청취 필요 | 녹음/제작 품질 직접 확인 | 후보별 같은 문장 청취 | 모델/체크포인트별 청취 |
| 화자 일관성 | 플랫폼 기본, mode 차이 확인 | 클립과 TTS 음색 매칭 어려움 | 화자 고정 가능 여부 검증 | 학습/화자 조건 및 권리 검증 |
| 감정 제어 | acoustic API 미확인 | 고정 문구별 제작 가능 | 해당 한국어 화자의 지원 스타일 확인 | 모델별 conditioning 지원 확인 |
| 첫 음성/연속 발화 | 실차 실측 필요 | 로컬 시작 빠를 가능성; 연결감 측정 | 네트워크/서버 queue/streaming 실측 | GPU cold start/queue/streaming 실측 |
| 비용/서버 부담 | OEM 이용 조건 확인 | 제작비·배포/저장 부담 | 사용량 비용·인증 proxy/관측 | GPU·배포·모델 관리 부담 |
| 네트워크 | ON_DEVICE 독립 | 클립 독립, 나머지는 mode | 기본 의존; cache 허용 확인 | 원격 호스팅이면 의존 |
| Android 연동 | 현재 adapter | player 추가, 같은 focus 정책 | HTTP/stream decoder/player 추가 | 서버 API+player 추가 |
| 약관/상업 권한 | Pleos 앱 배포 조건 확인 | 성우/제작 음원 권리 확보 | 선택 서비스/voice 계약별 확인 | 코드·가중치·데이터 권리 각각 확인 |
| 저장/재사용 | SDK가 PCM 파일을 제공하지 않음 | 권리 범위 내 로컬 파일 | 생성물 저장/재사용 조건 확인 전 미확정 | 체크포인트/음성 원천 조건별 미확정 |

후보 조사 근거: [Azure 언어·화자 지원](https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support?tabs=tts)
및 [SSML voice/style](https://learn.microsoft.com/en-us/azure/cognitive-services/speech-service/speech-synthesis-markup-voice)는
한국어 지원과 화자별 스타일 범위가 별개임을 보여준다. 전체 감정 6종을 임의로 지원한다고 가정하지 않는다.
[Coqui XTTS 공식 저장소](https://github.com/coqui-ai/TTS/blob/dev/docs/source/models/xtts.md)는
한국어와 CPML 모델 라이선스를 명시한다. 공개 코드가 상업적 가중치 이용/캐시 권한을 자동 부여하지 않는다.
어느 후보도 실제 음질/비용/권리 검토를 완료하거나 가장 적합하다고 판정하지 않았다.
외부 전송/API 추가는 SERVER와 인증·TTL·취소·저장 조건 계약을 먼저 확정한다.
