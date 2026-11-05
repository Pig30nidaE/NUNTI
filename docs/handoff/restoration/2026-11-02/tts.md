# TTS 환경 복원 및 기준선 검증

2026-11-02, Asia/Seoul. 새 실행 결과를 과거 2026-11-01 검증과 구분한다.

## 기준과 소유권

- worktree: `/Users/pig30nidae/NUNTI/.worktrees/tts`
- branch: `codex/tts-next`
- HEAD: `ebde9027f97f56f80bf8262c1200dbbb92827483`, PM이 확인한 원격 main과 같다.
- 시작 시 tracked 변경은 없었다. 이번 작업은 TTS 역할 보고·증거 및 재생성 가능한 도구·산출물만 추가한다.
- 시작 프롬프트, 공통 RESTORE_CHECKLIST, README·STATUS·RELOCATION, TTS 직접 보고·협업 문서, TTS/voice README, Pleos 런타임 문서, v1 계약 README를 읽고 현재 파일과 대조했다.
- `android/feature/tts`, `android/feature/voice`의 기존 구현을 유지했다. 공통 Gradle·host·계약·다른 담당 코드는 수정하지 않았다.

## 복원 완료

| 항목 | 새 로컬 결과 | 증거 |
| --- | --- | --- |
| JDK | 공식 Temurin 21.0.8+9, macOS ARM. 공식 SHA-256 대조와 `java -version` 성공 | [JDK checksum](tts-evidence/jdk-checksum.log), [버전](tts-evidence/java-version.log) |
| 과거 증거 무결성 | 최초 148개, 역할 보고 추가 후 165개 통과, 실패 0. 과거 문서·로그·WAV 보존 검사다 | [handoff 결과](tts-evidence/handoff-result.json) |
| 고정 TTS 도구 | Kotlin compiler 2.2.20, Android35 r02, android.car, Pleos TextToSpeech3.3.1. lock의 9개 파일 SHA-256 대조 성공 | [환경·산출물](tts-evidence/environment-and-artifacts.json) |
| JVM 정책·큐·Provider | 62개 통과, 실패 0 | [테스트](tts-evidence/tests.txt) |
| 실제 SERVER/AVATAR fixture | 8개 통과. 저장소 fixture 호환성이며 실제 Android HTTP E2E가 아니다 | [fixture](tts-evidence/integration.txt) |
| A~D Mock | 4개 시연 성공. 오디오 생성 없음 | [Mock 로그](tts-evidence/demo.txt) |
| Android/Pleos adapter | Android35/android.car/Pleos3.3.1 실제 바이너리 컴파일 성공 | [컴파일](tts-evidence/android-compile.txt) |
| JVM target | 생성된 AndroidVoiceSession class major version 61, target17 | [javap](tts-evidence/bytecode-target.log) |
| 통합 debug APK | assembleDebug 종료 코드 0. 역할별 debug signing 사용 | [빌드](tts-evidence/gradle-debug-retry.json) |
| 통합 lint·release | lintDebug·assembleRelease 종료 코드 0. lint Fatal0·Error0·Warning7 | [빌드](tts-evidence/gradle-lint-release.json), [Lint XML](tts-evidence/lint-results-debug.xml) |
| release 진단 화면 제외 | aapt2로 실제 APK manifest 해석·DEX 검사. RuntimeProbeActivity는 debug에만 존재하며 release에는 둘 다 없다 | [APK 검사](tts-evidence/apk-result.json) |

TTS 독립 검사는 18:05:52~18:06:02 KST에 실행했고 종료 코드는 0이다. [실행 기록](tts-evidence/tts-bootstrap.json)에 명령·cwd·환경변수·시각·종료 코드가 있다.

공유 JDK의 `JAVA_HOME`은 `/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home`이다. PM과 AVATAR에게 설치 완료와 읽기 전용 사용을 알렸다. JDK archive SHA-256은 `59422c2292ae4e76b87e00d8808dbe49cffa39af731e08bb0292ddb0af4e0261`이다.

도구·캐시는 `/Users/pig30nidae/NUNTI/.local/tts-tools`와 이 worktree의 `.local`에 분리했다. 전체 Android 빌드는 PM이 복원한 `/Users/pig30nidae/NUNTI/.local/pm-tools/sdk`를 읽기만 사용한다. Gradle user·Android user·debug signing home·tmp는 TTS worktree `.local`을 사용한다.

새 debug APK는 `/Users/pig30nidae/NUNTI/.worktrees/tts/android/build/app/outputs/apk/debug/app-debug.apk`이며 SHA-256은 `e8642b8543268d70efc78a82a2fe8f9c5d5fe449a35322302a0c43a128aecef7`이다. 생성 직후 PM에게 경로와 해시를 전달했다. 새 unsigned release APK는 같은 출력 폴더의 `release/app-release-unsigned.apk`이며 SHA-256은 `ad8380e12e1bf9bb52a2f4c020ce5c121dc75c0af2bfaf23ea7ff256f7349f2b`다. 두 APK에 AndroidVoiceSession과 실제 Pleos TextToSpeech 클래스가 포함됐다.

## 환경 차이와 실패 이력

- 시작 Python은 시스템 3.9.6이다. TTS 독립 검사의 Python>=3.9 요구는 충족하지만 SERVER용 >=3.12 요구를 충족했다고 주장하지 않는다.
- 시작 당시 JDK·전체 Android SDK·Pleos AVD가 없었다. TTS의 Android JAR 복원은 SDK·에뮬레이터 설치가 아니다.
- sandbox의 공식 다운로드는 DNS 제한으로 실패했다. TTS bootstrap의 종료 코드 1과 원시 traceback을 [실패 기록](tts-evidence/tts-bootstrap-sandbox.json), [실패 로그](tts-evidence/tts-bootstrap-sandbox.log)에 남겼다. 허용된 escalated 실행에서 동일 lock의 공식 다운로드와 검사를 완료했다.
- 첫 Gradle 시도는 제가 역할 tmp 경로의 생성 위치를 잘못 지정해 종료 코드 1이었다. 디렉터리 생성 후 재시도했다. [시작 실패](tts-evidence/gradle-debug.log)를 보존하며 `run_gradle.py`가 이후 실행 전에 역할별 디렉터리를 생성한다.
- 통합 빌드는 JDK21·Gradle8.11.1·AGP8.10.1·Kotlin2.2.21을 유지했다. SDK XML v4와 구 AGP parser v3의 호환 경고가 있었으나 빌드는 성공했다.
- `./gradlew --version`의 Kotlin2.0.20은 Gradle 자체 내장 Kotlin이다. 앱 plugin의 Kotlin2.2.21, 독립 TTS compiler2.2.20과 구분한다.
- 새 온라인 lint 경고 7개 중 버전·의존성 알림 4개, DataExtractionRules·MissingApplicationIcon·UseKtx 각 1개다. 과거 오프라인 경고 3개를 이번 결과로 복사하지 않는다. 자동 버전 업그레이드와 제품 기능 변경은 하지 않았다.
- JDK 최초 다운로드는 curl 명령과 종료 코드가 tool 실행 기록에 있고 정확한 시작 시각은 별도 파일에 수집하지 않았다. checksum 재검사부터는 시각과 종료 코드를 파일로 보존한다.

## 미구현

- production host의 실제 차량·통화·내비·안전음 상태 feed와 실제 주행/리포트의 사용자 요청 발화 연결.
- 감정의 실제 음색·속도·pitch 제어, 외부 TTS provider, 감정 클립 재생기, Pleos PCM 선행 묵음 삽입.
- TTS 재생 상태의 서버 업로드. MVP 필수 연결로 확정된 요구는 아니다.
- 새 WAV 수집용 인증된 gRPC speaker capture client 복원. 과거 WAV와 해시는 보존되어 있다.

## 미검증

이 담당의 새 실행에는 Pleos 앱 설치·주차 ON_DEVICE 재생·사용자 중지·BACKGROUND·복귀 후 반복 억제가 아직 포함되지 않는다. PM이 SDK/AVD 복원과 통제된 런타임 조건을 확인하고 있으며, 과거 통과를 이번 통과로 재사용하지 않는다.

실제 P→D/속도→P 전환, 통화·내비·안전음과의 경합, HYBRID/SERVER 등록·네트워크 단절, 인간 청취 품질·첫 음절·선행 묵음·가청 지연, 취소→실제 무음 지연, 실차·장시간 누수는 남아 있다. 과거 Virtual Console `emulator_inactive`·DDS 미준비·503은 과거 차단사항이며 새 로컬에서 같은 오류가 발생했다고 가정하지 않는다. 41ms/73ms SDK callback은 가청 지연 측정값이 아니다.

## 다음 첫 작업과 완료 기준

PM이 복원한 공식 Pleos2.1.0/API34 AVD에서 실제 P·속도0·UX 상태, 현재 Android user, 경쟁 오디오가 없는 시험 조건을 확인하고 새 debug APK로 ON_DEVICE lifecycle 기준선을 실행한다. PM이 런타임 단일 실행을 소유하고 TTS는 이벤트·승인·큐·취소 결과를 검토한다.

완료 기준은 새 APK 해시, 장치 fingerprint·user·실제 차량 상태, SDK initialize/locale, QUEUED→STARTED→COMPLETED, USER_CANCELLED, BACKGROUND, 복귀 후 REPEATED_TEXT와 자동 재생 없음의 새 로그다. 새 오디오를 수집한다면 인증된 공식 speaker stream의 PCM과 포맷·해시도 남긴다. 인간 청취 평가는 별도 결과로 적는다.

주행 전환은 활성 차량 제어 경로를 확보한 뒤 별도 시나리오로 진행한다. 실제 신호가 없으면 UNKNOWN을 유지하고, 공유 CarUx listener 한 개를 사용하며, 중단·복귀 후 이전 요청을 자동 재생하지 않는 규칙을 유지한다.

## 재현

저장소 루트에서 실행한다. 첫 명령은 기존 cache의 SHA-256도 다시 검사한다.

```sh
export JAVA_HOME=/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home
export NUNTI_JAVA="$JAVA_HOME/bin/java"
python3 android/feature/tts/scripts/verify.py --bootstrap --android \
  --tools-dir /Users/pig30nidae/NUNTI/.local/tts-tools/artifacts
python3 docs/handoff/restoration/2026-11-02/tts-evidence/capture.py gradle-recheck -- \
  python3 docs/handoff/restoration/2026-11-02/tts-evidence/run_gradle.py \
  :app:assembleDebug :app:lintDebug :app:assembleRelease
```
