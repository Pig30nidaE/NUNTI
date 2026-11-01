# SERVER 검증 기록

후속 [Pleos 실제 런타임 검증](pleos-runtime.md): 아바타·ON_DEVICE TTS 출력·중지/백그라운드·중복 차단 확인. 실제 주행 상태 전환은 플랫폼 제어 서비스 문제로 미검증. 아래 빌드 단계의 미검증 범위는 이 후속 기록을 함께 참고한다.

검증일: 2026-11-01 (Asia/Seoul). Python 3.12.8, Java 21 환경.
서버 의존성은 backend/uv.lock에 고정했다.

## 직접 실행한 검증

| 검증 | 결과 |
| --- | --- |
| `backend/.venv/bin/pytest backend/tests -q` | **91 passed**, 1 dependency deprecation warning |
| `backend/.venv/bin/ruff check backend` | 통과 |
| `backend/.venv/bin/ruff format --check backend` | 통과 |
| `python backend/scripts/build_fixtures.py`, `export_contracts.py` | JSON Schema/예제/OpenAPI 생성 성공 |
| `python scripts/smoke_server.py` (backend cwd) | 실제 loopback HTTP, 장애 재전송, 서버 프로세스 재시작 후 영속성 통과 |
| `uv build backend --offline --out-dir /private/tmp/nunti-dist` | wheel + sdist 빌드 성공 |
| wheel 자체 압축 해제본 import/health/Mock API/OpenAPI | 통과, Mock JSON 10개 포함 |
| TTS `verify.py --android --tools-dir /private/tmp/nunti-tts-tools` | JVM 62개 + 실제 계약 Fixture 8개 통과, 실제 SDK 바이너리 대상 컴파일 통과 |
| 루트 AVATAR `scripts/test.sh` | JVM 58개 + 합성 경로 1,000개 통과 |
| 루트 `verify_android_outputs.py` | 새 Kotlin JSON 10개 검증, 경로/아바타 4쌍 API 저장·조회 통과 |
| 루트 Gradle `--offline :app:assembleDebug :app:lintDebug` | BUILD SUCCESSFUL, 36초, 130 tasks. Lint 오류 0개/경고 3개 |

## 최종 모듈 통합

`server/integration-v1`에 AVATAR `f6ad9ac`과 TTS `2a0ce2f`, 문서 후속 `3925eb8`/`9c3fbe5`를
cherry-pick했다. 각 담당 모듈 소스는 추가 변경하지 않았다.
루트에서 서버 91개, AVATAR 58개/1,000 fixtures, TTS 62개/실제 계약 8개를 실행했다.
AVATAR의 새 Kotlin 출력은 서버에서 JSON Schema/Pydantic 및 API round trip으로 재검증했다.

루트 APK: `android/build/app/outputs/apk/debug/app-debug.apk`

SHA-256: `49a664600e69e13d9e6769562cb227ad264c59a54aeb6b1f8cfeef213c61897a`

이 해시는 루트에서 다시 빌드한 산출물이다. AVATAR worktree에서 빌드한 `bdef0dd8...`와
구분한다. 루트의 **오프라인** Lint 경고 3개는 Mock 앱 아이콘, 백업 설정, KTX 권고다.
담당 세션의 이전 온라인 실행에서는 라이브러리 버전 권고를 포함해 7개였다.
서버가 해당 경고를 숨기거나 소유 모듈 구현을 변경하지 않았다.

실행에 사용한 임시 SDK/Gradle 경로와 재현 명령:

```sh
# 저장소 android/에서 실행
ANDROID_HOME=/private/tmp/nunti-android-build/sdk \
ANDROID_USER_HOME=/private/tmp/nunti-android-build/android-user \
GRADLE_USER_HOME=/private/tmp/nunti-android-build/gradle-home \
/private/tmp/nunti-android-build/extract/gradle-8.11.1-bin/gradle-8.11.1/bin/gradle \
  --offline --no-daemon --console=plain :app:assembleDebug :app:lintDebug
```

일반 개발 환경에서는 JDK21/Android SDK35를 준비하고 포함된 `android/gradlew`를 사용할 수 있다.
임시 캐시가 없는 환경의 최초 빌드에는 의존성 다운로드가 필요하다.

pytest 범위: 정상/오류 API, 계약별 정상·필수 누락·비정상 샘플, JSON Schema/Pydantic 일치,
스키마 drift, 잘못된 타입/시간/버전, 명시적 동의, 토큰/소유자 분리, HTTPS,
중복/동시 재전송/ID 충돌, 원자적 배치 rollback, 경로 버전 충돌/이전 버전 재전송,
역순 이벤트/타임존 정렬, 감정 중복/아바타 선행 조건, 리포트 원문·null 점수,
지연된 근거 참조, DB 재생성·삭제·cascade·보존기간, 10개 Mock E2E,
클라이언트 outbox 재시작/동의 철회/backoff/응답 유실, OpenAPI 예제 형식.

실제 Kotlin AVATAR mapper 출력 10개를 읽어 서버에서 직접 JSON Schema/Pydantic 검증했다.
그중 도심/장거리/해안/산악 4개 route/avatar 쌍은 API 저장·조회도 검증했다.
입력 스냅샷과 SHA256는 backend/tests/fixtures/avatar-generated/provenance.json에 보관한다.
이 검증은 Python으로 아바타 생성 알고리즘을 재구현한 것이 아니다.

TTS 세션이 제공한 검증 스크립트를 SERVER에서도 직접 실행했다.
공통 SpeechRequest/VoiceProfile/EmotionSnapshot JSON을 Kotlin wire mapper와 request builder에
입력해 원문/목적/감정 ID가 유지되는 것, 근거 누락·미지원 감정이 안전하게 거부되는 것,
AVATAR의 음성 프로필/감정 출력이 연결되는 것 등 8개 실제 Fixture 검증을 통과했다.
별도 TTS JVM 테스트 62개와 Mock A~D 시연도 통과했다.
Android 35 + android.car + Pleos TTS 3.3.1 바이너리에 대한 Kotlin 컴파일은 성공했지만
SDK 초기화나 실제 음성 출력은 실행하지 않았다. 로그 사본은 `validation-evidence/`에 보관한다.

Starlette가 TestClient의 httpx 사용에 대해 httpx2 전환 권고 warning을 한 번 출력했다.
테스트 실패는 없으며 현재 잠금 버전에서의 결과를 기록했다.
uv 설치/빌드는 sandbox 안에서 macOS system-configuration 접근 시 panic이 났으나,
권한 검토 후 동일 명령으로 성공했다. loopback 포트 검증도 sandbox 외 실행으로 완료했다.
공개 인터넷 서버는 생성하지 않았고 smoke 서버/임시 DB는 종료 시 정리했다.

## 실행하지 않은 검증

- 실차/Pleos 에뮬레이터에서 경로·차량 데이터 실제 수신
- Android 앱 설치·실차/에뮬레이터 실행 및 차량 UX 제한의 실시간 동작
- 실제 Pleos 음성 합성/오디오 포커스/한국어 화자 품질
- 점수 담당 모듈의 실제 이벤트·최종 점수·코멘트 연결
- 운영 TLS 프록시, 사용자 토큰 발급/회전, 부하·장애 복구 및 백업 복원

합성 입력의 JVM/패키징 검증은 실제 차량 실행·음성 재생·사용자 시각 평가와 구분한다.
