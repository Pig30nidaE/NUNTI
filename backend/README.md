# Nunti 서버 MVP

FastAPI / Pydantic v2 / SQLite. 차량 앱의 실시간 동작과 독립적인 비동기 저장 서버다.
점수·감정 계산, 최종 코멘트 생성, 차량 SDK 호출, 음성 재생은 각 담당 모듈의 책임이다.
공통 계약은 **1.0 초안**이며 실제 차량 연동을 완료했다는 의미가 아니다.

## 로컬 실행

Python 3.12 이상과 uv가 필요하다. 명령은 저장소의 `backend/`에서 실행한다.

```sh
uv sync --frozen
export NUNTI_DEMO_TOKEN="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export NUNTI_AUTH_TOKENS="$(.venv/bin/python -c 'import json,os; print(json.dumps({os.environ["NUNTI_DEMO_TOKEN"]: "local-demo"}))')"
export NUNTI_SYNC_ENABLED=true
export NUNTI_ENABLE_MOCKS=true
export NUNTI_REQUIRE_HTTPS=false
.venv/bin/uvicorn nunti.api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

위 토큰은 출력하거나 커밋하지 않는다. 환경변수는 서버 터미널에만 존재한다.
`.env.example`은 설정 참고용이며 `.env`를 자동으로 읽지는 않는다.
기본 DB는 `backend/data/nunti.sqlite3`. `NUNTI_DB_PATH`로 변경한다.

- [Swagger UI](http://127.0.0.1:8000/docs): Authorize에 `NUNTI_DEMO_TOKEN` 값을 입력한다.
- [OpenAPI JSON](http://127.0.0.1:8000/openapi.json)
- [ReDoc](http://127.0.0.1:8000/redoc)
- 정적 OpenAPI: `../contracts/v1/openapi.json`
- Mock 목록: 인증 후 `GET /v1/mock/scenarios`

같은 환경변수의 별도 터미널에서 실행하거나 서버를 백그라운드로 띄운 셸에서 다음을 실행한다.

```sh
.venv/bin/python -m nunti.demo --scenario 09-reconnect --consent
```

이 명령은 **합성 데이터**를 전송하고 연결 실패·응답 유실·동일 요청 재전송을 재현한다.
`data/demo-outbox.sqlite3`에 미확인 요청을 보존한다. `--consent`가 없으면 전송하지 않는다.
가상 재시도 시계를 사용하는 시연용 도구이며 Android 백그라운드 동기화 구현은 아니다.

## 검증과 계약 재생성

```sh
.venv/bin/pytest tests -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/build_fixtures.py
.venv/bin/python scripts/export_contracts.py
.venv/bin/python scripts/smoke_server.py
```

커밋된 `uv.lock`이 실제 검증 버전을 고정한다. 배포 패키지는 `uv build`로 만든다.
운영 설치는 `uv sync --frozen --no-dev`를 사용하며 Mock 시연 도구는 개발 의존성 httpx가 필요하다.
외부 키·클라우드·메시지 브로커가 필요하지 않다.

## API

| 메서드 / 경로 | 역할 |
| --- | --- |
| GET /health | 민감 데이터 없이 DB 연결 상태 확인 |
| GET /v1/capabilities | 인증 후 계약 버전, 동기화/Mock 상태와 한도 조회 |
| POST /v1/trips | 앱이 만든 tripId와 명시적 syncConsent로 생성 |
| GET /v1/trips/{tripId} | 현재 경로/아바타 및 기록 수 요약 |
| PUT /v1/trips/{tripId}/route | 단조 증가하는 경로 버전 저장 |
| PUT /v1/trips/{tripId}/avatar | 현재 경로의 외형 버전 저장 |
| POST /v1/trips/{tripId}/events | 최대 100개 이벤트 원자적 저장 |
| POST /v1/trips/{tripId}/emotions | 최대 100개 감정 기록 원자적 저장 |
| GET /v1/trips/{tripId}/events | 발생 시각 순 조회, offset/limit |
| GET /v1/trips/{tripId}/emotions | 발생 시각 순 조회, offset/limit |
| PUT /v1/trips/{tripId}/report | 외부 최종 점수·코멘트 원문 저장 |
| GET /v1/trips/{tripId}/report | 리포트 및 아직 도착하지 않은 근거 ID 조회 |
| DELETE /v1/trips/{tripId} | 소유 주행과 하위 기록 삭제, 반복 가능 |
| GET /v1/mock/scenarios[/{scenarioId}] | opt-in 고정 Fixture 조회 |

배치 본문은 `{"schemaVersion":"1.0","events":[...]}` 또는 `emotions`다.
최대 요청 본문은 256 KiB, 조회 페이지는 최대 100개다.
쓰기 성공은 최초 저장/재전송 모두 HTTP 200이며 `data.status`로 `stored`/`duplicate`를 구분한다.
서버 수신 시각 `receivedAt`은 최초 저장값을 유지하며, `meta.serverTime`은 응답 생성 시각이다.

```json
{"data":{"id":"event-1","status":"duplicate","receivedAt":"2026-11-01T03:01:00Z"},"meta":{"requestId":"server-generated-uuid","serverTime":"2026-11-01T03:02:00Z"}}
```

```json
{"error":{"code":"id_conflict","message":"The identifier already has different content","details":[]},"meta":{"requestId":"server-generated-uuid","serverTime":"2026-11-01T03:02:00Z"}}
```

401은 인증 실패, 403은 HTTPS/동기화 정책 거부, 404는 해당 소유자의 리소스 없음,
409는 버전/ID/선행 데이터 충돌, 413은 크기 초과, 415는 Content-Type 오류,
422는 계약 위반, 503은 일시적 저장소 오류다. 입력값은 오류 본문에 반사하지 않는다.

## 운영 설정

| 환경변수 | 기본 / 의미 |
| --- | --- |
| NUNTI_AUTH_TOKENS | 필수 JSON `token → principal`; 32자 이상 무작위 토큰 |
| NUNTI_SYNC_ENABLED | false; 관리자의 동기화 사용 설정 |
| NUNTI_ENABLE_MOCKS | false; 고정 Mock 조회 API 활성화 |
| NUNTI_REQUIRE_HTTPS | true; /v1에서 HTTPS 요구 |
| NUNTI_DB_PATH | data/nunti.sqlite3 |
| NUNTI_RETENTION_DAYS | 30; 서버 생성 시각 기준 1..365일 |

같은 principal의 토큰은 같은 데이터를 볼 수 있다. 앱 설치별 principal과 토큰을 발급하고
공유 APK에 서버 관리자 키를 넣지 않는다. 실제 사용자 로그인/토큰 발급·갱신은 MVP 범위 밖이다.
외부 공개 시 TLS 프록시를 사용하고 내부 uvicorn 포트는 외부에서 접근할 수 없게 한다.
Uvicorn의 proxy header 신뢰 주소는 실제 프록시 주소만 지정하며 `*`로 두지 않는다.
공개 배포 전 프록시에서 요청 속도 제한과 body/read timeout을 설정한다.
이 세션에서는 공개 서버를 배포하지 않았다.

주행별 동의는 TripCreate.syncConsent=true로 명시해야 한다. 동의를 철회하면 앱 outbox를
비우고 서버 DELETE를 호출한다. 동기화 설정이 꺼져도 인증된 DELETE는 계속 가능하다.
로컬 반응 경로는 동의 및 서버 연결과 무관하게 동작해야 한다.

정확한 좌표/주소 필드는 계약에서 거부한다. 자유 텍스트(finalText 등)에 원본 위치를 넣지 않는
책임은 생산 모듈에도 있다. 서버는 코멘트를 마스킹해서 재작성하지 않고 그대로 보존한다.
요청 본문/헤더/토큰을 로깅하지 않으며 실행 예제는 접근 로그도 비활성화한다.
SQLite 파일은 0600, 새 데이터 디렉터리는 0700이다. 저장 데이터는 암호화되어 있지 않으므로
운영 호스트의 디스크 암호화와 접근 권한을 별도로 관리한다.

보존기간이 지나면 즉시 조회를 차단하고 시작 시 및 매시간 실제 행을 삭제한다.
SQLite secure_delete와 WAL checkpoint를 사용한다. 운영 백업을 추가한다면 동일한 만료·삭제
정책을 백업에도 적용해야 한다. 삭제된 주행을 앱이 자동 재생성하거나 동의 철회 후 재전송하지 않는다.

설계와 미확정 사항은 `../docs/architecture/server.md`, 연동 예제는
`../docs/architecture/integration.md`, 계약 설명은 `../contracts/v1/README.md`에 있다.
