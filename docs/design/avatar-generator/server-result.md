# 목적지·경로 기반 생성기 v3 서버 결과

2026-11-03. 전체 제품 목표는 운전습관 개선을 돕는 눈티다. 이번 서버는 사용자 담당인 목적지·경로 기반 아바타 생성 기능을 구현한다. 생성 이미지나 설명에서 운전 점수·검증 주행 이벤트·최종 코멘트를 산정하지 않는다. 실제 행동 개선 효과는 미검증이다.

[공통 계약](IMPLEMENTATION-CONTRACT.md)에 따라 별도 FastAPI 앱 `nunti.avatar_studio.api:app`과 SQLite·원본 미디어 저장을 추가했다. 기본 주소는 `http://127.0.0.1:8768`이고 저장 위치는 `.local/avatar-generator`다. 기존 v1·v2 코드와 소장품은 변경하지 않았다. `illustration.py`, `navigation.py`는 해당 담당이 구현했고 이 서버 작업에서 수정하지 않았다.

서버는 확인된 경로와 목적지·특성·목적·새 여정 UUID를 로컬 renderer에 전달해 새 RGBA를 받는다. 파일 형식·알파·크기를 검사한 뒤 원본 PNG·SHA·생성 입력·디자인 설명을 함께 확정한다. 초기 음원이나 음성 API 없이 이미지 결과가 완료된다. `LOCAL_RENDER`는 실제 새 그림을 그리는 로컬 렌더이며 AI 이미지 생성으로 표시하지 않는다.

브라우저는 `POST /session`에 JSON `{token}`을 보내 HttpOnly·SameSite=Strict 쿠키를 받는다. Android도 같은 응답의 Set-Cookie를 WebView로 옮겨 사용할 수 있다. API는 Bearer 인증도 받는다. 쿠키 이름은 `nunti_studio_session`이다. 루프백 IP·정확한 Host·Origin·Fetch-Site를 확인하며 JSON 외 상태 변경 요청과 교차 출처 요청을 거절한다. API 토큰을 URL이나 응답 본문에 넣지 않는다.

launcher가 `NUNTI_STUDIO_TOKEN`과 `NUNTI_STUDIO_WORKSPACE`를 서버에 전달한다. 토큰 해시별 owner를 구분하므로 재시작 복원에는 기존 launcher 연결 파일을 유지한다. 서버는 단일 uvicorn 프로세스로 실행한다. 모든 `/v3` 데이터와 원본 이미지에는 인증이 필요하다. 공개 UI는 `prototypes/avatar_generator`에서 제공하며 예시 원본은 인증 미디어 URL로 변환한다.

| 경계 | 구현한 동작 |
|---|---|
| 입력 | UUID·문자열 길이·정규화 경로 2~512점·유한 좌표·명시적 confirmed=true를 검증한다. 경로가 비었거나 화면 경로에 extractionId가 없으면 거절한다. |
| 이미지 추출 | PNG/JPEG 최대 8MiB·최대 변 4096px·최대 8,388,608픽셀을 받는다. 추출 점은 전체 화면 좌표이며 GPS나 도로 검증 근거로 취급하지 않는다. UI의 여섯 색상 힌트를 전달한다. |
| 원본과 확인 | 원본 바이트·SHA·추출 제안·경고·사용자가 확인한 점을 보관한다. 보정 시 원래 추출 점도 남긴다. EXIF 회전을 적용한 표시 치수와 원본 파일을 함께 유지한다. |
| 멱등성 | 같은 owner·requestId·같은 본문은 확정 결과를 재사용한다. 본문이 바뀌면 409다. 동시에 같은 요청이 오면 한 번만 생성하며 진행 중 중복은 409 `REQUEST_IN_PROGRESS`다. |
| 보관과 복원 | 완료 결과를 즉시 소장 목록에 넣는다. 재시작과 목록 재열기는 같은 PNG·설정·SHA를 사용한다. 미디어는 읽을 때도 SHA와 크기를 확인한다. |
| 실패 | 잘못된 이미지나 모호한 추출은 완료로 보이지 않는다. 중단된 작업과 유료 결과 불명확 상태는 자동 재생성하지 않는다. 성공 전 파일만 만들어졌더라도 별도 소장품으로 노출하지 않는다. |
| 음성 | capabilities와 artifact에 `DEVICE_SPEECH`, `newVoiceGenerated:false`, `automaticPlayback:false`를 표시한다. 저장한 description/rate/pitch로 기기의 기존 화자를 시험한다. 새 음색 설계나 자연스러움 승인을 뜻하지 않는다. |
| 설명 | 로컬 renderer의 label/source/target/detail과 전체 입력 해시를 저장한다. 실제 AI 이미지에는 로컬 디자인 모티브를 제안으로 표시하며 그림 반영이 자동 검증됐다고 단정하지 않는다. |

선택 이미지 API도 구현했다. 기본값은 꺼짐이며 요청의 `renderMode:'IMAGE_API'`와 다음 서버 설정이 모두 있어야 활성화한다. OpenAI 한 곳의 키로 이미지 한 장을 요청하며 로컬 디자인 기준 PNG와 확인한 경로 그림을 함께 전달한다. 음성 공급자나 별도 평가 공급자는 호출하지 않는다.

| 서버 환경변수 | 의미 |
|---|---|
| `NUNTI_STUDIO_IMAGE_API_ENABLED=true` | 외부 이미지 모드를 명시적으로 켠다. |
| `OPENAI_API_KEY` | 이미지 공급자 키. 서버에만 둔다. |
| `NUNTI_STUDIO_IMAGE_MODEL` | 코드 기본값은 `gpt-image-2.5-flare`다. 실제 계정 접근은 미확인이다. |
| `NUNTI_STUDIO_IMAGE_PRICES_VERIFIED=true` | 계정의 가격을 검토했다는 설정이다. 서버가 실제 가격을 검증해 주는 기능은 아니다. |
| `NUNTI_STUDIO_IMAGE_RESERVATION_MICROS` | 요청당 검토한 양의 예약 상한이다. 기본값 0에서는 외부 모드가 비활성화된다. |
| `NUNTI_STUDIO_IMAGE_JOB_CAP_MICROS` | 기본 300000, 요청당 최대 $0.30 예약 상한이다. |
| `NUNTI_STUDIO_IMAGE_TOTAL_CAP_MICROS` | 기본 6000000, 누적 예약 $6 상한이다. |
| `NUNTI_STUDIO_IMAGE_REQUEST_LIMIT` | 기본 20, 외부 요청 수 상한이다. 고정 아바타 수나 로컬 생성 상한이 아니다. |

capabilities는 `imageApiAvailable`, `imageApiModel`, 예약 제약을 반환한다. 비용은 실제 청구액과 구분한다. 실제 청구액은 null이며 HTTP 오류·timeout·응답 유실에 유료 POST를 자동 재시도하지 않는다. 실패해도 예약은 보수적으로 남긴다. 기존 결과는 API 설정을 꺼도 같은 요청과 GET으로 다시 읽을 수 있다. 외부 생성 실패를 로컬 생성 성공으로 조용히 대체하지 않는다.

검증 환경은 Python 3.12.14, 기존 `.worktrees/server/backend/.venv`와 Pillow 12.3.0이다. `backend/pyproject.toml`과 `backend/uv.lock`에 Pillow를 추가했고 기존 잠금 버전은 바꾸지 않았다.

| 직접 실행한 검사 | 결과와 범위 |
|---|---|
| `PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m pytest backend/tests/test_avatar_studio.py -q` | 22 passed. 실제 HTTP 경계인 TestClient·SQLite·실제 renderer와 세 예시 추출·복원·owner 격리·변조·EXIF·동시 중복·비용 예약·응답 불명확·실제 multipart 어댑터 형식을 검사했다. 공급자 응답은 테스트 대역이며 실제 생성 API 호출은 없다. |
| `PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m pytest backend/tests -q` | 전체 202 passed, 11 subtests passed. 이 실행 후 추가한 multipart 검사 1개는 위 22개 실행에 포함된다. |
| v3 패키지와 서버 테스트 Ruff | 통과. |
| pyproject·잠금 파일 `git diff --check` | 통과. |

FastAPI TestClient의 httpx 사용에 대한 Starlette 폐기 예정 경고 한 건이 있다. 실패는 없다. 초기에 수정 중이던 navigation의 색상 힌트 검사 여섯 건이 실패했으나 담당 수정 후 전체 202개 실행에서 통과했다.

이번 담당은 실제 브라우저·Android·Pleos 주차 gate를 재실행하지 않았다. 이 연결은 root의 실제 앱 검증 범위다. 상용 이미지 모델 접근·품질·가격·지연, 새 음색 생성, 사람의 귀여움·소장 의향, 실제 내비 SDK 입력과 운전습관 개선 효과는 미검증이다. 녹화와 녹음은 하지 않았다.
