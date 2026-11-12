# Nunti 서버 MVP

FastAPI / Pydantic v2 / SQLite. 차량 앱의 실시간 동작과 독립적인 비동기 저장 서버다.
현재 이미지 생성·대화는 `nunti.avatar_studio.api:app`의 v3 Studio에서 제공한다.
실행은 [루트 안내](../README.md#현재-실행--리팩토링-이후)를 따른다.
기존 [v2 계약](../contracts/v2/README.md)은 과거 기록이며, 해당 작업자와 CharacterStore 구현은 리팩토링에서 제거됐다.
점수·감정 계산, 최종 코멘트 생성, 차량 SDK 호출, 음성 재생은 각 담당 모듈의 책임이다. 서버는 앱이 계산한 점수와 Pleos 샘플을 저장한다 ([telemetry-sync](../docs/architecture/telemetry-sync.md)).
공통 계약은 **1.0 초안**이며 실제 차량 연동을 완료했다는 의미가 아니다.

Studio의 이미지 API 응답은 해석 전에 소유자별 불변 미디어와 `provider_responses`에 보존한다.
이미지·응답 원문·프롬프트·키는 로그에 출력하지 않고, 형식 오류는 `json`/`image_payload`/`image`/`usage`
단계명만 남긴다. 이미지 크기·투명도 오류는 각각 `WARDROBE_IMAGE_SIZE`와
`WARDROBE_ALPHA_MISSING`으로 구분한다. 같은 입력의 실패 기록과 비용 예약은 유지하며
자동 유료 재시도를 하지 않는다. 보존 기능 적용 전 실패의 원본 응답을 소급 복원할 수는 없다.

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

## 캐릭터 생성 v2

> 아래는 리팩토링 전 기록이다. `nunti.characters`와 관련 스크립트·테스트는 현재 checkout에 없으므로 아래 명령은 실행할 수 없다. 현재 생성은 위 v3 Studio 실행 안내를 따른다.

[별도 v2 계약](../contracts/v2/README.md)은 기존 v1 여행 동기화·30일 만료 정책과 분리된다. 생성 작업, 소장 캐릭터, 오디오/이미지 자산, 비용 예약, 공급자 영수증은 별도 SQLite와 미디어 디렉터리에 기록한다. FastAPI는 인증·입력·조회만 처리하고 모델 호출을 시작하지 않는다.

작업자는 같은 서버 환경으로 별도 실행한다.

```sh
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m nunti.characters.worker
```

`--once`는 최대 한 작업을 처리하고 종료한다. SIGTERM/SIGINT는 실행 중 작업이 끝나면 종료하고 자신의 lease를 해제한다. 강제 종료 후 CALLING 상태의 공급자 요청은 RESULT_UNKNOWN으로 남기며 유료 요청을 자동 반복하지 않는다.

기본 모드는 DISABLED다. OFFLINE_FIXTURE에서 NUNTI_FIXTURE_PNG와 NUNTI_FIXTURE_MANIFEST의 기존 미디어를 사용한다. 본문과 원래 Sohee 출처를 보존하고, 임의의 새 대사를 생성한 것처럼 표시하지 않는다. `GET /v2/generation-capabilities`는 시험 가능한 초기 3문장과 다른 후속 1문장을 안내한다.

API 모드는 자격증명과 계정에서 확인한 단계별 비용 상한이 모두 있어야 첫 외부 요청을 허용한다. 필요한 상한 키는 planning/image_candidates/voice_candidates/selection/save_voice/speech이며 Google 비교에는 remove_background도 필요하다. speech는 초기 3회분으로 계산해 생성 전 합계가 여정당 상한을 넘으면 거절한다. 초기 총 20개·여정당 $0.30·전체 $6이 상한이며 구독료는 제외한다. reservedMicros는 보수적인 예약액이고 actualMicros는 미확정일 때 null이다. fixture의 실비만 0이다.

주 공급자 어댑터는 Sol 기획, Flare 1024 medium RGBA 이미지 2후보, Eleven Voice Design 3preview에서 1화자 저장, v4 후속 합성, Gemini 이미지/음성 상대 평가다. Google 비교는 1K 이미지 2후보와 저장 화자 1개를 만들고 선정 이미지 1장에 Recraft 배경 제거를 적용한다. Google의 미선정 음성 2개를 불필요하게 저장하지 않는다. 이 후보 수 차이는 비교 조건에 남긴다. 평가는 상대적인 휴리스틱이며 자연스러움·귀여움에 대한 사람의 승인이 아니다.

선택 PNG·원본 Google 이미지, 정규화 WAV와 원본 오디오/모델 응답·usage·공급자 request ID를 소장품 출처에 연결한다. 공급자 임시 URL에 보관을 의존하지 않는다. 원래 voiceId와 모델·설정·specHash 바인딩을 후속 대사에 유지한다. 기본 공급자 설정을 바꿔도 기존 동반자는 저장한 공급자를 사용하고, 해당 키가 없으면 실패한다. 동일 캐릭터·동일 본문은 원래 WAV를 재사용한다.

실제 공급자 요청·계정 접근·유료 호출은 이번 키 없는 구현에서 실행하지 않았다. 어댑터 테스트는 공식 요청 형태에 대한 주입 응답 검사다. 실제 품질·계정별 가격·모델 접근·지연은 API 연결 후 검증해야 한다. 현재 모델과 가격 근거는 PM이 관리하는 설계 문서를 따른다.

```sh
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/pytest backend/tests/test_characters_v2.py -q
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python backend/scripts/export_character_contracts.py
```

### 실제 비용 영수증 반영

계정의 사용량/청구 영수증으로 확인한 실제 비용을 다음 JSON으로 기록한다. `actualMicros`는 USD의 백만분의 1 단위이며, 아래 숫자는 입력 형식을 보여주는 예시다. 예약액을 복사하거나 추정치를 확정 청구액으로 적지 않는다.

```json
{"owner":"installation-owner","requestId":"11111111-1111-4111-8111-111111111111","steps":[{"name":"planning","actualMicros":12345,"providerRequestId":"provider-request-id","evidenceReference":"account-receipt-reference"}]}
```

저장소 루트에서 실행한다.

```sh
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m nunti.characters.reconcile --input /absolute/path/account-charges.json --output /absolute/path/reconciliation-result.json
```

이 CLI는 네트워크를 사용하지 않는다. 해당 owner/requestId의 DONE 단계만 일괄 반영하며 확정한 금액·증거를 나중에 덮어쓰지 못한다. 실제 0은 명시적으로 기록할 수 있고, 미확정 단계는 null로 남는다. 한 단계라도 미확정이면 작업의 actualMicros도 null이다. 예약을 넘은 실비는 숨기지 않고 `overReservation`, 전체 상한 초과는 `overBudget`으로 알린다. 다음 호출의 한도 계산에는 예약과 확인 실비 중 큰 값을 사용한다. 실패한 생성에서도 이미 완료된 유료 단계의 실제 비용은 기록할 수 있다.

### 저장 Google 음성 만료 점검

Google voice 생성 응답의 expire_time은 immutable artifact의 음색 source와 별개인 binding.providerOperations에 마지막 관측값으로 보존한다.

```sh
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m nunti.characters.maintenance --dry-run
```

이 명령은 90일 안에 만료되는 저장 Google 음성을 나열한다. 외부 요청·새 작업 제출·WAV 교체는 0회이며 키가 없어도 작동한다. 만료일은 마지막으로 관측한 공급자 값이다. 인수 없이 실행해도 dry-run이다.

```sh
PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m nunti.characters.maintenance --enqueue-due
```

이 옵션은 실제 API 모드로 만든 Google 캐릭터의 월별 UUID5 작업을 준비한다. 본문은 연·월을 포함해 매월 달라지며, 같은 달에 다시 실행해도 같은 작업 한 개다. CLI 자체의 외부 요청은 0회다. 작업자는 명시적인 API 설정·원래 공급자의 키·speech 비용 상한·전체 예산을 통과한 뒤 저장 voiceId로 합성한다. 이어서 무료 GET /voices/{id}의 같은 id와 갱신된 expire_time을 확인하고 voice_operations만 갱신한다. 기존 artifact, source, 보관 WAV는 바뀌지 않으며 앱의 자동 재생 경로도 없다.

만료/404·키 누락·예산 부족은 실패로 남기며 새 화자를 만들어 대체하지 않는다. 합성은 완료됐지만 만료 조회가 실패한 경우에도 검증한 대사 파일은 캐시에 고정해 다른 요청에서 유료 재합성하지 않는다. 예약과 실청구 기록은 일반 후속 대사와 같은 경로를 사용한다. 이 실행 경로는 가짜 transport로 검증했으며 실제 Google 갱신 호출·청구·TTL 연장은 검증하지 않았다. 실제 자동 스케줄은 등록하지 않았다.
