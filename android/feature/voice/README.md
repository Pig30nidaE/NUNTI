# Android / Pleos adapter

실제 Pleos TTS 3.3.1 및 Android 35/android.car 바이너리로 컴파일 검증한 Android library 소스다.
공식 Pleos Connect2.1.0 ARM/API34 에뮬레이터의 ON_DEVICE 초기 발화 및 출력 PCM을 확인했다.
경로/감정은 debug Mock 입력이며 인간 청취 품질·주행 전환·실차 검증은 별도다. 일반 JVM에서 실행하지 않는다.

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
