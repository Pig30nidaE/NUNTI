# 새 SERVER 세션 시작 프롬프트

2026-11-04 최신: 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../../product/2026-hmg-app-challenge.md)을 유지한다. 결과 표시와 보관함 갱신 사이에서 사진 업로드가 유실되는 버그를 [재현·수정](../../design/avatar-quality-v5/PHOTO-UPLOAD-FIX.md)했다. 전체 7단계 직접 실행 완료: 경계15·Chrome15·Android15·저장AI14·실제Canvas7개35자세 통과. 추가AI추론·유료호출·녹화0. 이전 승인 검토 장애는 화면 검사에 대해 해소됐으며 아래 미실행 설명은 당시 기록이다. 정원 추가AI와 미적 최종승인은 별도다.

최신은 [v5](../../design/avatar-quality-v5/README.md)다. 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../../product/2026-hmg-app-challenge.md)을 유지한다. 모델 참조는 내부축선없는구조+스타일2장, 원본경로이미지는전송하지않고데이터로보존한다. local-clean-silhouette-3·route-silhouette-3, 선택style-clean-master. 실제coast새AI44.56초/paid0, garden은승인검토capacity실패로0건. 전체246+하위10통과. scripts/verify_avatar_clean_image.py·verify_avatar_quality_v5.py의실제/미실행기록을따른다.

최신은 [v4 구현·검증](../../design/avatar-quality-v4/README.md)다. 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../../product/2026-hmg-app-challenge.md)을 유지한다. LOCAL_MODEL은 선택한 로컬 MLX 모델만 offline 실행하며 원본 RGB·참조·seed·commit·실제 RGBA를 보존한다. 단일 추론·timeout·멱등 결과·소유권을 유지한다. 전체 backend 241개+하위7 통과, 실제 Android 생성 45.01초와 복원 확인. 유료 API는 원화 선택 후 결정으로 보류·0회이며 기본 실행에서 승인 환경을 false로 강제한다. 아래 v3·v2 설명은 과거 기록이다.

최신은 [생성기 v3](../../design/avatar-generator/README.md)다. 운전습관 개선을 돕는 눈티 중 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../../product/2026-hmg-app-challenge.md)을 유지한다. 독립 FastAPI 앱 nunti.avatar_studio.api:app·port8768·즉시 소장·입력/미디어 SHA·멱등 결과를 구현했다. 선택 이미지 API는 별도 한 키, 기본은 새 로컬 RGBA다. v1·v2 소스·소장품은 보존했다. 아래 보고는 이전 기록이다.

제품 목표는 운전습관 개선을 도와주는 아바타 눈티다. 사용자 담당인 목적지·경로 기반 생성 기능과 전체 제품을 구분하는 [제품 기준](../../product/2026-hmg-app-challenge.md)을 우선한다. 생성한 ID·설정·외형·음색을 감정·음성 피드백 모듈에서 이어서 사용하도록 경계를 보존한다. 운전 점수·검증 이벤트·최종 코멘트 산정은 해당 모듈의 책임이며 생성 경로의 모양으로 대신 산정하지 않는다.

2026-11-03 최신 기준은 [생성 동반자 v2](../../design/generative-mvp/README.md), [검증 보고](../../design/generative-mvp/test-report.md), [현황](../STATUS.md)이다. SERVER는 별도 v2 계약·작업자·소장품/미디어 저장·공급자 어댑터·비용/음성 슬롯 경계·후속 대사·비용 확정/음성 유지 CLI를 구현했다. 서버 132개 검사와 로컬 인증 HTTP·재시작을 확인했다. API 모드의 키·가격 누락은 외부 호출 전에 실패한다. 실제 계정·요금·음성 TTL 연장은 미검증이다. 아래 로컬 Sohee와 v1 전용 범위 설명은 과거 기록이다.

최신 생성 흐름은 [목적지·경로에서 동반자가 태어나는 시험본](../../design/route-birth/test-report.md)을 따른다. 앱에서 목적지·특성·목적과 직접 그린 경로를 입력하면, 기존16윤곽 선택 없이 새72점 외형과 로컬 Sohee 음성을 생성한다. 경로 trace→몸체 morph→얼굴 등장, 런타임 음원 수신, 도착·보관·복원을 연결했다. 새5여정·15새WAV는 검증 표본이며 선택지나 생성 상한이 아니다. PC 모델/로컬 bridge가 필요하고 외부 API·계정은 사용하지 않는다. Anna 선호는 유지한다. 지도·내비 입력·폭넓은 자유 서술 해석·Android 추론·실차·사람의 품질 평가는 남았다. 아래8개 목록 방식은 이전 검증본이다.

이전 v2 기준선은 [TTS 실제 구현·시험 결과](../../design/journey-characters/tts-result.md)에 보존한다. 최신 상태는 위 생성 연동 보고를 따른다. v2 PC 합성·Android Debug 파일 재생과 실제 emulator 정책 이벤트까지 완료했다. 사용자 음성 피드백은 "전체적으로 더 작고 귀여운 느낌"이다. 새 2.5D 시각·매 여행 자동 모델 호출·제품 host 연결은 남았다. 아래 과거 기준선과 완료된 복원은 반복하지 않는다.

최신 요구는 [여정 캐릭터 브리프](../../product/journey-character-brief.md)와 [C 방향 통합 설계](../../design/journey-characters/README.md)다. [복원 결과](../restoration/2026-11-02/PM.md)와 [새 생성·컬렉션 제안](../../design/journey-characters/server-proposal.md)을 먼저 읽고 완료된 복원을 반복하지 않는다. 생성·선택·수집은 별도 상태이며 현재 v1은 새 job·자산·컬렉션 계약이 아니다. 외부 payload·담당 조율은 사용자 지시로 보류한다.

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
