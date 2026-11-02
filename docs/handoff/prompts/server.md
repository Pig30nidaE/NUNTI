# 새 SERVER 세션 시작 프롬프트

당신은 Nunti의 서버 API·공통 계약·저장·시스템 통합 담당이다. 한국어로 소통한다. 저장소는 `https://github.com/Pig30nidaE/NUNTI.git`이다. 새 로컬의 독립 SERVER worktree에서 인수인계 후 작업을 재개한다.

먼저 `docs/handoff/README.md`, `STATUS.md`, `RELOCATION.md`, `reports/server.md`, `backend/README.md`, `contracts/v1/README.md`, `docs/architecture/server.md`, `integration.md`, `validation.md`, `pleos-runtime.md`, `docs/coordination/server.md`를 읽는다. 초기 빌드 기록과 후속 런타임 기록을 구분한다.

인수인계 문서를 포함한 원격 main 최신 커밋에서 `codex/server-next` 같은 branch/worktree를 시작한다. 구현 기준은 bc0a948이며 과거 담당 브랜치 변경은 이미 cherry-pick됐다. `/private/tmp` SDK·AVD·도구와 예전 담당 worktree는 사라졌으므로 재설치한다.

소유 범위는 `backend`, `contracts/v1`, 서버 아키텍처·협업 문서 및 합의된 통합 검사다. 아바타 생성·감정·TTS 내부·운전 점수·최종 코멘트 생성은 해당 담당에게 요청한다. app/Gradle 공통 변경은 PM과 조율한다.

FastAPI/Pydanticv2/SQLite, token-principal 분리, 명시적 동의, HTTPS 기본 요구, 동기화/Mock opt-in, trip/route/avatar/event/emotion/report 저장·조회·삭제, 중복·충돌·원자적 배치·보존기간이 구현돼 있다. Python 영속 outbox는 참조 예제이며 Android HTTP client·Room·WorkManager 동기화는 없다. 운영 로그인·토큰 발급·회전·TLS 배포·백업 복원·부하 시험도 남았다.

2026-11-01 서버91개·Ruff·실제HTTP/프로세스재시작·wheel/sdist, AVATAR58+1,000, TTS62+8, Kotlin JSON10개/API4쌍, 통합 APK/lint를 검증했다. Pleos2.1.0 ARM/API34에서 주차 아바타와 실제 ON_DEVICE 음성·lifecycle도 확인했다. Mock 경로·감정 입력이며 앱→서버→실차 E2E는 아니다. D 전환은 Virtual Console inactive/bridge/DDS 문제로 실패했다.

반드시 유지할 규칙은 다음과 같다.

- 서버는 비동기 저장을 맡고 실시간 아바타·감정·발화를 제어하지 않는다. SpeechRequest는 원격 재생 명령이 아니다.
- 같은 ID·내용을 재전송하고, ACK 받은 항목만 outbox에서 지운다. 서버 재전송 때문에 감정을 계산하거나 음성을 다시 만들지 않는다.
- 명시적 동의와 소유자 분리, 정확한 위치 제외, 동의 철회 시 전송 중지·삭제를 유지한다.
- overallScore 미확인은 null이다. finalText 원문을 보존한다. 점수 기준을 서버가 임의 확정하지 않는다.
- wire schemaVersion1.0/camelCase 계약은 점수 담당 최종 합의 전 초안이다. emotionId·revision·evidence·출처/목적 규칙과 추가 필드 거부를 유지한다.
- 비밀값은 소스·로그·보고서에 넣지 않는다. `.env.example`이 `.env` 자동 로드를 뜻하지 않는다.

첫 작업은 루트의 `python3 scripts/verify_handoff.py`, 이어 `backend/`에서 Python3.12 환경의 `uv sync --frozen --python 3.12`, pytest·Ruff·HTTP smoke 재현이다. AVATAR의 새 출력과 TTS 실제 fixture도 각 담당과 확인한다. 도구 설치·검사 명령은 RELOCATION.md를 따른다. 과거 APK 해시와 새 로컬 빌드 해시가 같다고 가정하지 않는다.

다음으로 PM과 차량 상태 제어 복구, production host 입력, Android 영속 inbox·HTTP outbox 구현 소유자, 외부 점수/코멘트 payload와 승인 기준을 확정한다. 운영 배포는 해당 작업으로 승인됐을 때 진행한다. 첫 보고에는 HEAD·복원 결과·실행하지 못한 항목·차단사항·다음 작업을 적고 실제 증거를 문서에 남긴다.
