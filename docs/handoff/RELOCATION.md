# 새 로컬에서 Nunti 작업 재개

이 절차는 [현재 상태](STATUS.md)의 코드·문서·검증 증거를 새 로컬에서 복원한다. SDK·AVD·가상환경과 Codex 채팅 설정은 별도로 준비한다.

명령 예시는 macOS/Linux의 POSIX 셸 기준이다. Windows에서는 WSL 등 Bash 환경을 사용하거나 가상환경 실행 경로와 `gradlew.bat` 명령을 맞춘다. 기존 직접 검증 호스트는 macOS ARM이다.

## 저장소 복원

새 로컬 터미널에서 실행한다.

```sh
git clone https://github.com/Pig30nidaE/NUNTI.git Nunti
cd Nunti
git switch main
git log -1 --oneline
git status --short --branch
python3 scripts/verify_handoff.py
```

인증을 요구하는 저장소라면 해당 GitHub 계정의 Git 접근 권한을 먼저 설정한다. 토큰을 URL이나 프롬프트에 넣지 않는다.

원격 이관 대상은 통합 코드와 문서를 담은 `main` 하나다. `server/integration-v1`은 이전 로컬의 통합 브랜치 이름이고, `avatar/route-emotion-v1`, `codex/tts-system`은 이전 로컬의 담당 브랜치다. 과거 브랜치 ref는 새 원격으로 전송하지 않으며 담당 보고에 이력을 보존했다. 기능은 이미 cherry-pick으로 통합돼 있으므로 새 로컬에서 과거 담당 브랜치를 다시 병합할 필요가 없다.

## 도구 설치

| 도구 | 재현 기준 | 확인 방법 |
| --- | --- | --- |
| Python | >=3.12,<3.15. 기존 검증은 3.12.8 | `python3 --version` |
| uv | `backend/uv.lock` 지원 버전. 이전 로컬 0.9.7 | `uv --version` |
| JDK | 21. 이전 Temurin 21.0.8, JVM target 17 | `java -version` |
| Android SDK | platform 35, platform-tools, build-tools 35.0.0 | SDK Manager, `adb version` |
| android.car | platform 35의 `optional/android.car.jar` | 파일 존재 확인 |
| Gradle | 저장소 Wrapper 8.11.1 | `cd android && ./gradlew --version` |
| Kotlin standalone | kotlinc 2.2.21 이상 | `kotlinc -version` |
| Pleos TTS | Maven artifact 3.3.1, Gradle에 고정 | 최초 빌드 의존성 다운로드 |

AGP 8.10.1·Gradle Kotlin 2.2.21·Compose 1.8.3·compile/targetSdk35·minSdk28은 저장소 설정을 유지한다. TTS 독립 검사는 별도 lock의 Kotlin 2.2.20을 사용하므로 standalone kotlinc 설치와 구분한다.

Android Studio의 SDK Manager로 Android SDK Platform 35, Platform-Tools, Build-Tools 35.0.0을 설치한다. `JAVA_HOME`과 `ANDROID_HOME`을 실제 설치 경로로 설정하고 `platform-tools`를 PATH에 추가한다. `android/local.properties`를 쓸 경우 sdk.dir은 새 로컬 경로를 사용하며 커밋하지 않는다.

첫 실행에는 Google Maven·Maven Central·Gradle 배포 저장소·Pleos Nexus 접근이 필요하다. 임의로 라이브러리를 최신 버전으로 올리기 전에 고정된 조합을 재현한다.

## 서버 검사 및 실행

`backend/`에서 의존성과 기본 검사를 실행한다.

```sh
cd backend
uv sync --frozen --python 3.12
.venv/bin/pytest tests -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/smoke_server.py
cd ..
```

기존 기준은 pytest 91개 통과다. smoke는 loopback 포트를 연다. 네트워크 실행이 제한된 환경에서는 제한을 별도 기록하고 통과로 처리하지 않는다.

서버의 토큰 생성·로컬 실행·Mock 전송은 [backend/README.md](../../backend/README.md)의 명령을 사용한다. `.env.example`은 설정 참고이며 `.env`를 자동 로드하지 않는다. 개발 HTTP는 loopback 전용으로 설정한다.

필요한 설정 이름은 `NUNTI_AUTH_TOKENS`, `NUNTI_DEMO_TOKEN`, `NUNTI_DB_PATH`, `NUNTI_SYNC_ENABLED`, `NUNTI_ENABLE_MOCKS`, `NUNTI_REQUIRE_HTTPS`, `NUNTI_RETENTION_DAYS`다. 로컬 데모 토큰은 새로 생성한다. 서버 MVP에 외부 클라우드 키·메시지 브로커는 필요하지 않다.

기존 `backend/.venv`는 절대경로 symlink가 있어 복사하지 않는다. 조사 시점에는 별도 보존해야 할 `backend/data`나 실제 `.env`가 없었다. 이후 데이터가 생겼다면 그 소유자·동의·백업 조건을 별도로 확인한다.

## 아바타와 계약 연결 검사

루트에서 새로 설치한 kotlinc를 지정한다.

```sh
KOTLINC=/실제/설치경로/kotlinc/bin/kotlinc \
bash android/feature/avatar/scripts/test.sh
backend/.venv/bin/python backend/scripts/verify_android_outputs.py
```

`kotlinc`가 PATH에 있으면 절대경로 지정 없이 실행할 수 있다. 첫 검사는 `org.json:json:20250517`을 내려받고 JVM 58개 및 합성 경로 1,000개를 검사한다. 두 번째 검사는 방금 생성된 JSON 10개와 route/avatar API round trip 4쌍을 검사한다. 기존 fixture 사본만 검사한 결과와 구분한다.

아바타 화면 시연은 [정적 데모](../../android/feature/avatar/demo/index.html)에서 볼 수 있다. 실제 Compose·AAOS 런타임 검증은 이 HTML 시연과 별개다.

## TTS 검사

루트에서 실행한다.

```sh
python3 android/feature/tts/scripts/verify.py --bootstrap --android
```

공식 저장소에서 SHA-256 lock으로 도구를 받아 JVM 62개, 실제 fixture 연동 8개, Android35/android.car/Pleos3.3.1 대상 컴파일을 실행한다. 다운로드 뒤에는 `--bootstrap` 없이 재실행할 수 있다. 지속 캐시는 `--tools-dir /실제/캐시경로`로 지정한다.

이 명령은 소리를 재생하지 않는다. ON_DEVICE 런타임은 Pleos 이미지에서 별도 검사한다. HYBRID/SERVER는 `PleosCredentials`를 호스트 메모리로 제공하는 구조지만, 실제 자격 증명·등록 및 실행 검증은 아직 없다.

## Android 빌드

`android/`에서 실행한다.

```sh
cd android
./gradlew :app:assembleDebug :app:lintDebug :app:assembleRelease
cd ..
```

Debug APK는 `android/build/app/outputs/apk/debug/app-debug.apk`에 생긴다. release는 배포 서명이 없는 검사 산출물이다. release에 `RuntimeProbeActivity`가 포함되지 않는지 패키지 검사도 수행한다. 과거 기준은 lint 오류 0개, 오프라인 경고 3개였다. 새 실행의 경고 수와 조건은 그대로 기록한다.

모듈 소스는 모두 통합되어 있으므로 기본 빌드에 `-PnuntiTtsCheckout`은 필요하지 않다. 독립 checkout 간 통합이 필요할 때만 실제 상대 worktree의 `android` 경로로 지정한다.

## Pleos 에뮬레이터 복원

공식 [설치 가이드](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/setup-connect-sdk-emulator)를 따라 Pleos Connect 2.1.0/API34 이미지를 설치한다. 2026-11-02 확인한 가이드는 cold boot·RAM 4GB를 안내한다. Mac은 ARM feed, Windows/Linux는 해당 x86 feed를 사용한다. 기존 직접 검증은 macOS ARM에서 수행했으므로 다른 호스트에서의 재현을 보장한 기록은 없다.

1. Android Studio의 SDK Manager → SDK Update Sites에 공식 Pleos feed를 등록한다.
2. SDK Platforms에서 API34의 Pleos 이미지를 설치한다.
3. Device Manager에서 Automotive → Pleos Connect v2.1.0으로 AVD를 만든다.
4. cold boot·RAM 4GB를 설정하고 AVD를 실행한다.
5. `adb devices`와 현재 Android user를 확인한다. 기존 검사 스크립트는 user 10을 가정하므로 새 이미지가 다르면 경로를 점검한다.

설치 가이드의 feed는 Mac `https://nexus-playground.pleos.ai/repository/raw-releases/connect-avd/2.x/crp-arm64-sys-img.xml`, Windows/Linux `https://nexus-playground.pleos.ai/repository/raw-releases/connect-avd/2.x/crp-sys-img.xml`이다. 과거 다운로드 버전·해시는 [tool-provenance.json](../architecture/validation-evidence/pleos-runtime/tool-provenance.json)에 있다. URL의 이미지 내용이 갱신되면 버전과 해시를 새로 기록한다. 과거 ARM ZIP만 약 4.67GB였으므로 다운로드·압축 해제·AVD 데이터 공간을 확보한다.

아래 명령에서 serial은 실제 `adb devices` 결과로 바꾼다. 경쟁 오디오가 없는 통제된 시험 환경을 직접 확인한 뒤 quiet-test 입력을 사용한다.

```sh
adb -s emulator-5554 install -g -r android/build/app/outputs/apk/debug/app-debug.apk
adb -s emulator-5554 shell am start -W -f 0x14000000 \
  -n ai.nunti.avatar.demo/ai.nunti.app.RuntimeProbeActivity --ez confirm_quiet_test true
adb -s emulator-5554 shell am start -f 0x14000000 \
  -n ai.nunti.avatar.demo/ai.nunti.app.RuntimeProbeActivity \
  --es probe_action speak --ez confirm_quiet_test true
python3 android/scripts/verify_runtime_probe.py \
  --adb "$ANDROID_HOME/platform-tools/adb" --serial emulator-5554 \
  --output /tmp/nunti-runtime-lifecycle.json
```

기존 [런타임 보고서](../architecture/pleos-runtime.md)의 `/private/tmp/nunti-*` SDK·AVD 경로는 이미 사라진 과거 실행 환경이다. 명령을 그대로 복사하지 않는다. 현재 설치 경로를 사용한다.

위 lifecycle 도구는 발화 이벤트를 검사하며 스피커 WAV를 새로 수집하지 않는다. 당시 gRPC 오디오 캡처 클라이언트는 보존되지 않았다. 새 녹음이 필요하면 공식 emulator speaker stream과 새 세션 인증을 사용하는 캡처 도구를 복원한다. 기존 WAV와 그 형식·해시는 Git에 남아 있다.

2026-11-02 새 로컬에서 확인한 환경 차이는 [PM 복원 보고](restoration/2026-11-02/PM.md)에 있다. macOS의 ADB native USB 초기화가 대기하면 해당 daemon의 스택을 확인하고 공식 지원 `ADB_LIBUSB=1`을 지정한 새 daemon으로 비교한다. 이번 실행에서는 이 설정으로 연결됐다. 모든 ADB 실패에 같은 원인을 가정하지 않는다.

실제 주행 전환을 재검사하려면 [Virtual Console 가이드](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/use-vehicle-emulator)에 따라 `adb forward tcp:8088 tcp:8088`을 설정하고 `http://127.0.0.1:8088/`에 접속한다. 기존 환경의 `emulator_inactive`/bridge/DDS 미준비가 해결됐는지 먼저 확인한다. P→D/속도→P와 실제 UX 변화가 관찰되기 전에는 주행 차단 검증을 통과로 기록하지 않는다.

브라우저 전체 Console 페이지를 열고 시험 동안 유지한다. 이번 공식 프런트엔드는1초 간격 heartbeat와3초 세션 timeout을 사용한다. 단순 GET 조회만으로 세션이 활성화되지 않는다. 새 실행에서 browser.clients0→1과 emulator_active·DDS all·gear bridge=false→true를 관찰한 뒤 실제 P→D·속도→P에 성공했다. 브라우저가 닫히면 inactive가 될 수 있으므로 새 환경에서 상태를 다시 확인한다.

## 네 세션의 작업 폴더 구성

PM은 처음 clone한 통합 폴더에서 조율한다. 역할별 새 브랜치·worktree를 같은 기준에서 만든다. 다음 명령은 PM이 한 번 실행한다.

```sh
git fetch origin
git worktree add ../Nunti-tts -b codex/tts-next origin/main
git worktree add ../Nunti-avatar -b codex/avatar-next origin/main
git worktree add ../Nunti-server -b codex/server-next origin/main
```

같은 이름이 있으면 기존 작업 상태를 먼저 확인하고 새 이름을 고른다. 과거 prunable worktree 메타데이터를 옮기거나 기존 브랜치를 다시 병합하지 않는다. 각 폴더를 Codex에서 열어 [해당 프롬프트](README.md)를 붙여넣는다. 사용자별 skills·플러그인·모델 설정은 Git에 없으며 필수 구현 지침은 저장소 문서에서 복원한다.

이번 로컬은 저장소 안의 Git 제외 경로 `.worktrees/{tts,avatar,server}`를 사용했다. [setup_role_worktrees.py](../../scripts/setup_role_worktrees.py)는 독립적으로 확인한 원격 SHA와 `origin/main`을 비교하고 기존 branch·path를 덮어쓰지 않는다. `--create`로 생성하고 옵션 없이 실제 HEAD·Git dir·변경 파일을 조회한다. 다른 환경에서는 먼저 원격 main의 최신 SHA를 확인한다.

PM이 통합 브랜치 반영을 맡고 담당은 자신의 branch/index에서만 작업한다. 공통 파일 변경과 모듈 간 입력 계약을 먼저 공유한다. 다른 세션 메시지를 보낼 권한은 새 환경에서 사용자가 허용한 범위에 맞춘다.

## 복원 완료 확인

- 문서와 보존된 증거의 무결성 검사가 통과했다.
- SERVER 91, AVATAR 58+1,000, TTS 62+8 및 새 Kotlin→API 검사를 각 담당이 다시 실행했다.
- Debug 빌드·lint·release 구성을 확인하고 새 결과와 환경 차이를 기록했다.
- Pleos 주차 상태의 아바타·TTS와 lifecycle을 재검사했다. 실행하지 못한 항목은 사유와 필요한 환경을 적었다.
- 네 세션이 자신의 소유 범위·현재 차단사항·첫 작업을 PM에게 보고했다.

SDK 설치 실패나 실제 주행 전환 실패를 숨긴 채 완전 복원으로 기록하지 않는다. 코드·문서 복원과 하드웨어 실행 검증의 완료 상태를 따로 보고한다.
