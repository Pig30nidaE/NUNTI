# Android / Pleos adapter

2026-11-02 `AndroidLocalAudioPlayer`와 `LocalVoiceManifest`를 추가했다. `AndroidVoiceSession`의 기본 provider는 Pleos로 유지하고 Debug 시험에서는 catalog 파일 재생을 주입한다. 실제 v2 WAV·emulator PCM·D 취소/P 복귀 결과와 남은 무음·청취 검증은 [최신 PM TTS 보고](../../../docs/design/journey-characters/tts-result.md)를 먼저 읽는다. 아래는 기존 ON_DEVICE 경로의 기록이다.

실제 Pleos TTS 3.3.1 및 Android 35/android.car 바이너리로 컴파일 검증한 Android library 소스다.
공식 Pleos Connect2.1.0 ARM/API34 에뮬레이터에서 ON_DEVICE 재생 완료, 사용자 중지,
백그라운드 취소, 복귀 후 반복 억제와 출력 PCM을 확인했다. 최종 범위·재현은
`docs/architecture/pleos-runtime.md` 참조. 경로/감정은 debug Mock 입력이며
인간 청취 품질·D 전환·실차 검증은 별도다. 일반 JVM에서 실행하지 않는다.

AVATAR 앱 shell 통합:

```kotlin
// root settings.gradle.kts
include(":feature:tts", ":feature:voice")
// dependencyResolutionManagement.repositories
maven("https://nexus-playground.pleos.ai/repository/maven-releases/")
// app dependencies
implementation(project(":feature:voice"))
implementation(project(":feature:tts"))
```

루트는 Kotlin JVM/Android 및 `com.android.library` 플러그인 버전을 관리한다.
모듈 설정은 JVM target 17, compileSdk 35, minSdk 28, `useLibrary("android.car")`.
호스트도 적절한 `android.car` uses-library 환경과 TTS 권한을 제공해야 한다.
TTS library manifest는 `pleos.car.permission.TTS_SERVICE` 선언만 포함한다.
Distraction Optimization 선언은 차량 정책 승인이 아니므로 이 모듈이 임의 추가하지 않는다.

메인 스레드에서 `AndroidVoiceSession(applicationContext)`를 만들고 `beginTrip` 후
실제로 관찰한 `PlaybackContext`를 공급한다. 기본 상태는 모두 발화 불가다.
`CarUxRestrictionFeed`는 앱이 이미 연결한 `CarUxRestrictionsManager`를 받아
초기 조회, 변경 listener, 명시적 refresh, 해제를 제공한다. Car 연결/재연결은 앱 소유다.

`speechPermission`과 `appAllowedWhileDriving`는 앱 카테고리/기능/플랫폼 정책을 검토한
호스트가 결정한다. `activeRestrictions == 0`이나 STOPPED만으로 ALLOWED를 설정하지 않는다.
통화/내비/안전음 상태를 알 수 없으면 UNKNOWN을 유지한다. 포커스 성공이 이 검사를 대체하지 않는다.
UX callback이 없는 동안도 상태가 유효함을 실제 조회로 확인하여 5초 이내 heartbeat를 공급한다.

`submit(ApprovedSpeech)`는 큐에 들어가며 이벤트는 `onEvent`로 전달된다. 모든 호출/SDK callback은
메인 looper로 직렬화한다. 앱의 onStop에서 onBackground, suspend 신호에서 onSuspend,
수명 종료에서 close를 호출한다. Suspend 이후에는 이전 session을 재사용하지 말고 새 객체를 만든다.

포커스는 NOTIFICATION / CONTENT_TYPE_SPEECH / TRANSIENT_MAY_DUCK.
SDK와 포커스가 동일 AudioAttributes를 사용한다. LOSS, TRANSIENT, CAN_DUCK 모두 중단/반납한다.
통화·내비·공식 경고를 대체하지 않으며 NAVIGATION/EMERGENCY/SAFETY usage를 사용하지 않는다.
차량 시스템의 focus matrix 결정을 따른다. 다른 holder 목록을 일반 앱이 완전히 읽을 수 있다고 가정하지 않는다.

선행 묵음: SDK에 PCM 출력/패딩 API가 확인되지 않았다. 단순 delay를 묵음으로 가장하지 않는다.
차량 SDK 내부 패딩 및 첫 음절 손실 검증은 출시 전에 필요하다.

## 생성 음색 manifest의 실제 JSON 파서 검사

`LocalVoiceManifest`는 기존 schema 1/2를 보존하고 schema 3의 `designed-voice-v1` source를 지원한다.
source의 provider/model/mediaOrigin 조합과 최상위 provider, speaker ID, 불변 binding 및 정규화 WAV를
검증한다. `rawAudioSha256`은 선택적인 공급사 원본 hash metadata이며, 여기서 원본 파일을 읽는 것은 아니다.
실제 상용 생성 음성과 오프라인 녹음 fixture는 provider와 origin으로 구분한다.
이 검사는 계약·파일 무결성 검사이며, JSON의 출처 표기만으로 공급사가 실제 합성한 음성임을 입증하지 않는다.
원본 수신·공급사 응답·정규화 과정의 provenance는 신뢰된 생성 worker가 검증하고 보관해야 한다.

다음 검사는 프로덕션 `LocalVoiceManifest.kt`를 캐시된 실제 `org.json` JVM 구현과 함께 컴파일하여 실행한다.
기존 18개 WAV와 schema 3 정상·위조·새 대사 추가·재시작을 검사한다. 다운로드나 공급사 API 요청은 없다.

```sh
NUNTI_JAVA="$PWD/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home/bin/java" \
  python3.12 android/feature/voice/scripts/verify_manifest.py
```

`--voice-manifest PATH [--audio-directory PATH]`로 생성한 schema 3 번들을 추가 검사할 수 있다.
compiler는 `.local/tts-tools/artifacts`, org.json은 기존 TTS worktree의 Gradle cache를 사용하고
SHA-256이 다르거나 없으면 중단한다. `--tools-dir`, `--json-jar`로 같은 pinned artifact 위치를 지정한다.
결과는 `build/manifest-verification/tests.txt`에 저장한다. Android의 실제 JSON 구현·기기 재생·음질 검증은 별도다.
