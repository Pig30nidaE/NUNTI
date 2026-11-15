# 눈티 · Nunti

눈티는 길마다 다른 아바타와 함께 떠나고 주행 이벤트와 도착 후 리포트로 운전 습관을 돌아보는 Pleos Connect 차량용 앱입니다.

## 릴리스 APK 실행

[릴리스 APK 다운로드](apk/NUNTI_release.apk)

Pleos Connect 2.1.0 ARM64 시스템 이미지(Android Automotive 14, API 34)와 Android Emulator 37.2.13.0을 사용합니다. 기준 디스플레이는 2560 × 1440 px, 160 dpi입니다. Android SDK Platform-Tools의 `adb`, Python 3.12 이상, `uv`를 준비하세요.

1. 저장소 루트에서 아래 명령으로 Python 의존성을 설치하고 PC의 로컬 생성 서버를 시작합니다.

   ```sh
   uv sync --frozen --project backend --no-dev
   NUNTI_STUDIO_PAID_API_APPROVED=false NUNTI_STUDIO_CHAT_API_ENABLED=false NUNTI_STUDIO_ROUTE_API_ENABLED=false \
     backend/.venv/bin/python -m uvicorn nunti.avatar_studio.api:app --host 127.0.0.1 --port 8768 --no-access-log
   ```

   검토용 새 체크아웃에서 실행합니다. 이미 다른 눈티 서버가 PC의 8768 포트를 사용 중이면 해당 서버와 연결 코드를 사용하거나, 사용 중인 환경을 확인한 뒤 빈 테스트 환경에서 실행하세요.

2. Pleos 에뮬레이터를 주차(P) 상태로 두고 APK를 설치합니다. 아래에서 `emulator-5554`를 `adb devices`로 확인한 Pleos 장치 번호로 바꾸세요.

   ```sh
   adb devices
   SERIAL=emulator-5554
   USER_ID="$(adb -s "$SERIAL" shell am get-current-user | tr -d '\r')"
   adb -s "$SERIAL" reverse tcp:8768 tcp:8768
   adb -s "$SERIAL" install --user "$USER_ID" -g apk/NUNTI_release.apk
   adb -s "$SERIAL" shell am start --user "$USER_ID" -n ai.nunti.avatar.demo/ai.nunti.app.MainActivity
   ```

   기존 개발 APK와 서명 인증서가 다르면 같은 앱 ID로 설치할 수 없습니다. 개발 중인 앱 데이터가 필요하면 새 Pleos AVD를 사용하세요.

3. PC에서 `python3 scripts/run_avatar_generator.py --show-code`로 로컬 연결 코드를 확인하고, 차량 화면의 연결 창에 입력합니다. 이 코드는 로컬 서버에만 사용합니다.

4. API 키 없이 체험하려면 목적지에 **아직 미정**을 입력합니다. **어떤 일로 가나요?**와 **분위기 더하기 → 그곳의 느낌**은 비우고, 풍경은 **아직 모르겠어요**로 둡니다. **눈티 만들기**를 누릅니다. 결과 화면의 **여행 기록**에서 **함께할 여정 → 운전 습관 연습**을 선택합니다. **닫기**를 누른 뒤 **함께 출발**을 선택합니다. 주차 상태에서 연습 데이터로 주행 이벤트와 점수 변화를 볼 수 있습니다. 약 30초 뒤 여정을 마치면 리포트를 확인할 수 있습니다.

### 목적지에 맞춘 새 외형을 생성할 때

이미지 생성 권한이 있는 본인의 `OPENAI_API_KEY`를 PC의 환경변수 또는 Git에서 제외된 `.env.local`에 설정합니다. 8768 포트가 비어 있는 상태에서 `python3 scripts/run_avatar_generator.py --server-only`를 실행합니다. 이미지 생성과 대화 API 호출에는 비용이 발생할 수 있습니다. APK에는 공유 키가 포함되지 않습니다. 화면에서 요구하는 로컬 연결 코드와 OpenAI API 키는 서로 다른 값입니다.

NaviHelper로 Pleos 내비가 제공하는 목적지와 상태를 가져옵니다. 도로 형상이 필요할 때는 별도 경로 서비스가 계산한 경로를 사용합니다. 연습 모드는 합성 데이터를 재생합니다. 실시간 모드는 Vehicle SDK와 차량 콜백으로 들어온 신호를 사용합니다. 애니메이션과 입력 UI는 차량의 `CarUxRestrictions` 및 주차 상태에 따라 제한됩니다. 대화는 텍스트 입력과 음성 응답을 지원합니다. 음성 입력(STT)과 실차 환경 검증은 개발 범위에 남아 있습니다.

## 소스 빌드

JDK 21, Android SDK Platform 36, SDK Build-Tools 35.0.0 이상을 준비합니다. `ANDROID_HOME`과 `JAVA_HOME`을 설정한 뒤 실행합니다. Gradle Wrapper 8.11.1을 사용하며 첫 빌드에는 Google Maven, Maven Central, Pleos Playground Maven 접근이 필요합니다.

```sh
cd android
./gradlew :app:assembleRelease :app:testReleaseUnitTest :feature:score:testReleaseUnitTest
```

Gradle 출력은 `android/build/app/outputs/apk/release/app-release-unsigned.apk`입니다. 새 APK를 배포할 때는 먼저 `zipalign`을 적용하고 배포용 키로 `apksigner sign`을 실행합니다. 서명 파일과 암호는 Git에서 제외합니다.

## 저장소 구조

| 경로 | 역할 |
| --- | --- |
| [android/app](android/app) | Kotlin 기반 차량 앱, 아바타 Studio와 여정 화면 |
| [android/feature/score](android/feature/score) | 주행 신호, 연습 시나리오, 점수와 리포트 |
| [android/feature/voice](android/feature/voice) | Pleos TextToSpeech 연동 및 음성 자산 |
| [prototypes/avatar_generator](prototypes/avatar_generator) | Android Studio WebView 화면과 로컬 캐릭터 자산 |
| [backend](backend) | FastAPI 기반 아바타·경로·대화 API와 SQLite 저장 |
| [contracts](contracts) | 모듈과 백엔드 데이터 계약 |

- [여정 통합 구조와 검증 이력](docs/architecture/integrated-journey.md)
- [Pleos 에뮬레이터 검증 이력](docs/architecture/pleos-runtime.md)
- [아바타 시각 효과 출처와 라이선스](docs/NUNTI_VFX_ASSET_CREDITS.md)
