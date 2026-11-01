# 서버 아키텍처 결정

## 최초 환경과 기획 분석 (2026-11-01 KST)

루트에는 `눈티-주행습관-정리.html`만 있었고 Git, 기존 API/계약, 백엔드, Android 코드,
API 키 관리 파일은 없었다. 원문은 수정하지 않았다. Python 3.14/3.12, uv, Java 21,
Node가 있으며 최초 PATH에는 Kotlin/Gradle/adb/emulator/sdkmanager와 Android SDK가 없었다.
기능 브랜치 `server/integration-v1`를 만들고 Python 3.12의 전용 가상환경에서 검증한다.

기획에서 지킬 방향은 데이터 누락을 정상/0점으로 단정하지 않기, 같은 사건의 중복 처리 방지,
현재 감정의 회복과 과거 기록의 공존, 애니메이션 제한, 최종 코멘트의 근거 연결이다.
35/35/20/10 배점, 1분 평가 구간, 감점·반응 간격, 데이터 충분성, 각 SDK 속성 수신 여부는
논의 초안이다. 서버는 어떤 운전 평가 임계값도 구현하지 않는다.
HTML의 STT-only 문구보다 최신 사용자 지침의 제한된 짧은 TTS 허용을 우선한다.
구체적인 허용 조건은 TTS 모듈의 차량 상태/UX 제한 검증으로 결정한다.

## 기술 선택

| 선택지 | 판단 |
| --- | --- |
| FastAPI + Pydantic + pytest | 채택. Python 환경 활용, typed 입력/오류 검증과 OpenAPI, Mock 테스트 용이 |
| Kotlin Ktor | JVM 통합과 Kotlin 공유에 장점. 기존 JVM 서버가 없으므로 이번 서버 MVP의 초기 설정 이득이 작음 |
| 기존 프레임워크 유지 | 기존 프로젝트 없음 |

FastAPI의 모델 기반 입력 검증·OpenAPI 생성은 [공식 request-body 문서](https://fastapi.tiangolo.com/tutorial/body/),
Ktor의 OpenAPI 지원은 [공식 문서](https://ktor.io/docs/server-openapi.html)를 참고했다.
선택은 프로젝트 환경에 따른 판단이며 Ktor가 기능을 제공하지 않는다는 의미가 아니다.

## 경로 분리

실시간: Android SDK adapter → 로컬 이벤트 adapter → AVATAR 감정 엔진 → TTS 정책 엔진.
비동기: 동의된 최소 데이터 → 영속 outbox → HTTP 배치 API → SQLite → 종료 리포트 조회.
서버 없이도 아바타 생성·감정 반응·허용 음성 출력이 가능해야 한다.
서버 장애를 운전 이벤트로 변환하거나 앱의 UI 스레드를 대기시키지 않는다.

| 통신 방식 | 결정 |
| --- | --- |
| HTTP 배치 | 채택. 작은 요청, 명확한 ACK, 재전송과 멱등성 테스트 가능 |
| WebSocket | 왕복 반응이 필요하지 않으므로 미도입; 재접속·세션·순서 관리 부담 |
| SSE | 서버 push 요구가 없어 미도입 |
| 주기적 polling | 상시 사용 안 함; 사용자 요청/주행 종료 시 조회만 |

하나의 프로세스/SQLite 파일로 시작한다. 쓰기는 BEGIN IMMEDIATE로 직렬화하고 동일 ID 충돌과
경로 버전 검사를 같은 트랜잭션에서 수행한다. 읽기는 일관된 snapshot이다. WAL과 5초 busy timeout을 사용한다.
DB schema user_version=1이며 알 수 없는 버전으로 시작하면 실패한다. 다음 변경 때 명시적 migration을 추가한다.
단일 호스트의 작은 MVP용이며 여러 서버 간 공유 SQLite 파일이나 대규모 부하를 보장하지 않는다.

원본 route/각 avatar revision/event/emotion/report를 종류별 immutable JSON으로 보존하고
trip 소유자와 복합 외래키로 연결한다. 새로운 데이터베이스나 브로커는 도입하지 않는다.

## 위험 및 미확정

- 공통 v1은 AVATAR/TTS와 핵심 필드를 조율했지만 점수 담당자의 최종 승인을 받지 않았다.
- 실제 차량 신호, NaviHelper 풍경/도로 비율, 차량/에뮬레이터 UX 제한은 서버에서 검증하지 않았다.
- TTS 실제 화자 ID·음색 제어 지원은 TTS adapter의 검증 사항이다.
- 사용자 로그인/토큰 발급, 배포 TLS/속도 제한, 백업·디스크 암호화는 운영 환경 작업이다.
- report 정정, consent 이력/철회 전용 API, 장기 변경 피드 cursor, 대규모 부하는 후속 범위다.
- 로컬 outbox 예제는 FIFO 단일 worker이다. Android는 Room/WorkManager 등으로 영속화하고
  네트워크 제약, 지수 backoff+jitter, 429 Retry-After, 인증 갱신, 영구 오류 격리를 구현해야 한다.
  삭제·철회 후 지연된 생성 요청을 다시 보내지 않도록 queue와 주행 상태를 함께 관리한다.
