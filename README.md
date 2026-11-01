# 눈티 · Nunti

경로 특징에 따라 외형이 달라지고 주행 이벤트에 반응하는 가상 동승자 MVP다.
차량의 실시간 반응은 앱 내부에서 처리하고 서버는 동의받은 기록을 비동기로 저장한다.

| 영역 | 코드와 실행 가이드 |
| --- | --- |
| 서버 API · SQLite · 동기화 Mock | [backend/README.md](backend/README.md) |
| 공통 JSON Schema · OpenAPI | [contracts/v1/README.md](contracts/v1/README.md) |
| 경로 · 아바타 · 감정 · Compose | [android/feature/avatar/README.md](android/feature/avatar/README.md) |
| 음성 정책 · 큐 · 프로필 | [android/feature/tts/README.md](android/feature/tts/README.md) |
| Pleos 음성 adapter | [android/feature/voice/README.md](android/feature/voice/README.md) |
| 모듈 연결 · 장애 처리 | [docs/architecture/integration.md](docs/architecture/integration.md) |
| 실제 검증 범위 | [docs/architecture/validation.md](docs/architecture/validation.md) |

서버는 Python 3.12 이상에서 `cd backend && uv sync --frozen`으로 준비한다.
토큰·동의 설정 및 실행 명령은 서버 가이드에 있다. 기본 동기화는 비활성화되어 있다.

Android 앱은 합성 경로로 동작하는 Mock 뷰어다. 실제 차량 정책 연결 전 AAOS 표시를 차단하며
기본 앱에서 실제 음성을 재생하지 않는다. Android 모듈 빌드와 실제 차량에서의 동작 검증은 구분한다.
실차 신호 수신, 이은룡 담당 점수·최종 코멘트 모듈, 실제 TTS 음질은 별도 검증이 필요하다.

통합 Debug APK 빌드와 Lint는 루트 저장소에서 통과했다. 로컬 산출물은
`android/build/app/outputs/apk/debug/app-debug.apk`이며 Git에는 포함하지 않는다.
합성 시연은 [아바타 데모](android/feature/avatar/demo/index.html)에서 확인할 수 있다.

공통 v1.0 계약은 조율 중인 초안이다. 운전 점수 가중치·임계값 및 SDK 데이터 가용성을
확정하지 않았으며 원본 `눈티-주행습관-정리.html`의 논의 초안은 그대로 보존했다.

AVATAR의 JVM 테스트를 실행한 후, 새 Kotlin 출력과 서버의 연결을 다음으로 검증할 수 있다.

```sh
backend/.venv/bin/python backend/scripts/verify_android_outputs.py
```

이 검사는 JSON Schema/Pydantic 형식 검사와 실제 서버 API 저장·조회까지 수행한다.
실제 차량 SDK 호출이나 음성 재생은 수행하지 않는다.
