# SERVER 환경 복원·검증 보고

2026-11-02, Asia/Seoul. 이번 실행의 기준은 원격 main과 같은 `ebde9027f97f56f80bf8262c1200dbbb92827483`이다. worktree는 `/Users/pig30nidae/NUNTI/.worktrees/server`, branch는 `codex/server-next`다. 제품 코드·wire 계약·공통 Gradle·host와 기존 보고 원문을 변경하지 않았다. 커밋과 index 변경도 하지 않았다.

SERVER 시작 프롬프트, handoff README·STATUS·RELOCATION·기존 SERVER 보고, backend·계약 README, 서버 설계·통합·초기 검증·후속 Pleos 런타임 기록, SERVER 협업 기록, PM의 RESTORE_CHECKLIST를 읽었다. 초기 빌드 기록의 미검증 문구와 후속 Pleos 주차·ON_DEVICE 출력 기록을 구분했다.

## 이번에 완료한 복원·검증

| 항목 | 실제 결과 | 증거 |
| --- | --- | --- |
| 문서·과거 증거 무결성 | 18:05 KST, 148 passed / 0 failed, exit 0. 새 앱 실행 결과는 아님 | [handoff.json](server-evidence/handoff.json) |
| Python·고정 의존성 | Python 3.12.14, uv 0.9.7. `uv sync --frozen --python <3.12.14 절대경로>` exit 0, 40 packages audited | [환경·버전·해시](server-evidence/environment.json), [sync 로그](server-evidence/uv-sync.log) |
| 서버 기준선 | pytest 91 passed, dependency warning 1개, exit 0 | [pytest 로그](server-evidence/pytest.log) |
| Ruff | `check .` 통과, `format --check .` 21 files already formatted, 각각 exit 0 | [check](server-evidence/ruff-check.log), [format](server-evidence/ruff-format.log) |
| 실제 HTTP·프로세스 재시작 | loopback HTTP, 합성 단절·응답 유실·동일 ID 재전송, 재시작 후 영속 기록 확인, exit 0 | [HTTP smoke](server-evidence/http-smoke.log) |
| 배포 패키징 | 기존 lock으로 offline wheel·sdist 빌드, exit 0 | [build 로그](server-evidence/package-build.log), [산출물 해시](server-evidence/environment.json) |
| wheel 직접 실행 검사 | 소스 경로 대신 wheel 추출본 import 확인, health·인증된 Mock 10개·OpenAPI 확인, exit 0 | [wheel 검사](server-evidence/package-runtime-resolved-path.log), [재실행 스크립트](server-evidence/verify_package.py) |
| 새 AVATAR 출력 연동 | AVATAR가 18:06:50~18:06:57 KST에 생성한 JSON 10개를 JSON Schema·Pydantic으로 검증하고 route/avatar API 저장·조회 4쌍 확인, exit 0 | [직접 입력 검사](server-evidence/kotlin-api.log), [입력 해시·시각](server-evidence/avatar-inputs.json) |
| 입력 보존 후 재현 | 위 새 JSON 10개를 SERVER 증거 폴더에 복사해 같은 검사 재실행, JSON 10개·API 4쌍 통과, exit 0 | [보존 입력 재검사](server-evidence/kotlin-api-preserved-inputs.log), [입력 사본](server-evidence/avatar-generated) |

새 Kotlin 입력 원본은 `/Users/pig30nidae/NUNTI/.worktrees/avatar/.local/avatar-build/reports`를 읽기만 했다. 기존 `backend/tests/fixtures/avatar-generated` 사본을 새 생성 결과로 사용하지 않았다. API 4쌍 검사는 FastAPI TestClient와 실제 SQLite 저장소를 사용하며, 실제 소켓 HTTP 검사는 별도 smoke 결과다.

패키징 산출물은 이 worktree의 `.local/dist/nunti_backend-0.1.0-py3-none-any.whl`과 `.local/dist/nunti_backend-0.1.0.tar.gz`에 있다. wheel SHA-256은 `32040fbc90a47959a3a51d2aaae835d23dfd2e3c8f3fd215ad83428533714f9b`, sdist는 `8177c48e0585ff9cef45d76a7ef76dc39119c475d617fe6028a6a57caf15626e`다.

전체 실행 명령·cwd·시각·종료 코드는 [commands.jsonl](server-evidence/commands.jsonl)에 있다. [run_command.py](server-evidence/run_command.py)가 stdout·stderr와 함께 기록했고 환경변수 전체나 실제 인증 토큰은 수집하지 않았다.

## 환경 차이와 실패 후 재시도

- PATH의 `/usr/bin/python3`는 3.9.6이므로 서버에 사용하지 않았다. Homebrew Python 3.12.14를 명시했다. 과거 검증 Python은 3.12.8이었다.
- `.local/uv-bootstrap/bin/uv`는 담당 배정 후 첫 확인 때 이미 존재했다. 실제 버전 0.9.7, pip 설치 메타데이터, 바이너리 SHA-256을 기록했다. 이번 실행이 최초 다운로드였다고 주장하지 않는다. uv cache와 Python 설치 경로는 이 worktree `.local`에 한정했고 서버 venv는 `backend/.venv`다.
- `backend/uv.lock`은 HEAD와 byte 단위로 같고 SHA-256은 `447cea0a1faf6507fe5d34b942ca618eaf5dee90cd4191a190f899311d748dc2`다. FastAPI 0.162.0, Pydantic 2.14.2, Uvicorn 0.54.0, pytest 9.2.0, Ruff 0.17.3 등 실제 설치 버전은 environment.json에 보존했다.
- sandbox 내부의 uv sync·build는 macOS system-configuration panic으로 exit 101이었다. 같은 명령을 sandbox 밖에서 재실행해 exit 0을 확인했다. [sync 첫 실패](server-evidence/uv-sync-sandbox.log), [build 첫 실패](server-evidence/package-build-sandbox.log)를 보존했다.
- sandbox 내부 HTTP smoke는 loopback bind의 `PermissionError`로 exit 1이었다. sandbox 밖에서 같은 smoke를 실행해 통과했다. [첫 실패](server-evidence/http-smoke-sandbox.log)를 보존했다.
- 새 증거 스크립트의 첫 wheel 검사는 macOS `/var`와 `/private/var` 경로 표기를 정규화하지 않은 관찰 오류로 실패했다. 실제 경로를 resolve한 뒤 통과했다. 입력 사본 수집도 처음에는 단독 파일명 `EmotionSnapshot.json`·`VoiceProfile.json`을 누락해 실패했고 필터를 고쳐 10개를 보존했다. 제품 코드 실패와 구분하며 첫 실패 로그도 지우지 않았다.
- Starlette TestClient가 httpx 사용 중단 예정 warning을 출력했다. 고정 의존성 유지 범위여서 이번에 버전을 바꾸지 않았다.

## 미구현

- Android HTTP client, Room·WorkManager 영속 outbox와 앱 재시작 후 동기화. Python outbox는 실행 참조 예제다.
- 실제 차량·NaviHelper 입력, production Automotive host, 앱 영속 event inbox, 외부 점수·최종 코멘트 모듈 연결.
- 실제 사용자 로그인·토큰 발급·갱신·회전, 운영 TLS·속도 제한·백업 복원·부하 시험 체계.
- 리포트 정정 버전, 동의 이력·철회 전용 API, 변경 피드 cursor, schema v1 이후 DB migration.

## 이번 세션에서 미검증

- Pleos 새 AVD 설치·앱 빌드·설치·주차 아바타·ON_DEVICE 발화·lifecycle 재현은 SERVER가 실행하지 않았다. Android SDK·공통 Gradle 빌드는 PM이 단독 담당한다.
- P→D·속도 변화→P와 실제 UX 차단·복귀, 실차 실행, 실제 차량·내비 입력에서 서버까지의 E2E는 SERVER가 검증하지 않았다. 18:15 KST 추가 읽기 조사에서는 PM의 공식 브라우저 접속 전후 원본 JSON을 비교해 inactive→DDS·gear bridge 준비 및 Park 실제값을 확인했다. [별도 조사](server-evidence/console-investigation.md)에 정적 heartbeat 구현과 새 관찰, 과거 원인 해석의 범위를 구분했다.
- TTS JVM 62개·fixture 8개·Android/Pleos 바이너리 컴파일은 SERVER가 이번에 실행하지 않았다. TTS 담당의 새 결과를 PM이 따로 취합해야 한다.
- 한국어 청취·첫 음절·선행 묵음·가청 지연·감정 음향 제어·실제 오디오 경합·장기 주행, 운영 인증·배포·백업 복원·부하 검증은 수행하지 않았다.

## 다음 작업과 완료 기준

1. PM이 차량 상태 제어 환경 복구를 통합 첫 작업으로 배정한다. SERVER가 Virtual Console 상태·bridge/DDS 준비와 실제 Car API 관찰을 진단하고 AVATAR/TTS가 실제 정책 반응을 확인한다. 완료 기준은 실제 P→D·속도→P 값, UX 변화, 표시·음성 차단과 복귀 로그다. HTTP 요청 수락이나 합성 상태만으로 완료 처리하지 않는다.
2. PM이 production host·차량/통화/내비 feed·영속 inbox·HTTP outbox의 Android 구현 소유자를 확정한다. SERVER는 기존 저장·ACK·충돌·동의 철회 계약을 제공한다. 완료 기준은 실제 앱 재시작·단절·ACK 유실·동일 ID 재전송·동의 철회 시나리오의 서버 저장 결과와 중복 감정·음성 미발생 증거다.
3. PM이 이은룡 담당의 실제 event·verification/confidence·correlation/recovery·TripReport payload와 승인 일정을 확보한다. SERVER는 합의된 payload를 계약·테스트로 고정한다. `overallScore=null`과 finalText 원문 보존을 수용 기준에 포함하며 합의 전 wire 변경을 하지 않는다.

SERVER 기본 환경·계약 호환·패키징 복원에는 남은 차단이 없다. 차량 런타임과 제품 E2E를 포함한 전체 복원 완료는 PM·각 담당의 별도 결과를 확인한 뒤 판단해야 한다.
