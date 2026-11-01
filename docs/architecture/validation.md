# SERVER 검증 기록

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
- Android APK 전체 빌드·설치 및 차량 UX 제한의 실시간 동작
- 실제 Pleos 음성 합성/오디오 포커스/한국어 화자 품질
- 점수 담당 모듈의 실제 이벤트·최종 점수·코멘트 연결
- 운영 TLS 프록시, 사용자 토큰 발급/회전, 부하·장애 복구 및 백업 복원

AVATAR의 알고리즘/렌더러 자체 테스트 등 이 문서에서 직접 재실행하지 않은 결과는
해당 세션의 보고로 구분한다. TTS 컴파일 성공도 차량 실행 성공으로 표시하지 않는다.
