# AVATAR 환경 복원 결과

2026-11-02, Asia/Seoul 기준. AVATAR의 순수 JVM 환경과 새 Kotlin 출력의 서버 호환성 검증을 완료했다. 기능 소스와 공통 설정은 변경하지 않았다.

## 기준선과 소유 범위

| 항목 | 실제 확인값 |
| --- | --- |
| worktree | `/Users/pig30nidae/NUNTI/.worktrees/avatar` |
| branch | `codex/avatar-next` |
| HEAD | `ebde9027f97f56f80bf8262c1200dbbb92827483` |
| 시작 시 tracked 변경 | 없음 |
| 원격 기준 확인 | PM이 GitHub connector에서 확인한 `main`과 HEAD 일치 |
| 소유 범위 | `android/feature/avatar`, `android/feature/navigation`, `android/feature/emotion`, AVATAR 협업 문서 |
| 이번 변경 | 이 복원 보고서와 `avatar-evidence` 증거. 도구와 빌드 출력은 전용 `.local`에 저장 |

`docs/handoff/README.md`, `STATUS.md`, `RELOCATION.md`, `reports/avatar.md`, `prompts/avatar.md`와 PM의 `RESTORE_CHECKLIST.md`를 읽었다. AVATAR README, 검증·기술 보고서, metrics, tests, 해시 manifest, 협업 문서, Pleos 런타임 보고서, v1 계약을 확인했다. 실제 extractor, wire adapter, 감정 reducer, journal, 검사 스크립트도 대조했다. 과거 담당 브랜치는 다시 병합하지 않았다.

## 새 검증 완료 항목

| 검사 | 새 실행 결과 | 실제 실행과 증거 |
| --- | --- | --- |
| 문서와 과거 증거 무결성 | 148 passed, 0 failed, exit 0 | [handoff-verification.json](avatar-evidence/handoff-verification.json). 앱 실행 검사가 아니다 |
| JDK | Temurin 21.0.8+9, exit 0 | [java-version.log](avatar-evidence/java-version.log). TTS가 설치한 경로를 읽기 전용으로 사용 |
| Kotlin | kotlinc-jvm 2.2.21, exit 0 | [kotlin-version.log](avatar-evidence/kotlin-version.log) |
| AVATAR JVM | 58개 통과, exit 0 | 18:06:50.277~18:06:57.160 KST. [avatar-tests.log](avatar-evidence/avatar-tests.log), [tests.txt](avatar-evidence/reports/tests.txt) |
| 합성 경로 | 동일 결과 1,000, 충돌 0, 근거 있는 출력 1,000, 근거 제거 fallback 1,000 | [metrics.json](avatar-evidence/reports/metrics.json) |
| 새 계약 JSON | 실제 Kotlin 실행으로 10개 생성. 기존 결정적 SHA-256과 10개 모두 일치 | [wire-determinism.json](avatar-evidence/wire-determinism.json), [생성물 해시](avatar-evidence/generated-sha256.json) |
| 새 Kotlin 출력의 API 연결 | JSON Schema와 Pydantic 10개, API 저장·조회 4쌍 통과, exit 0 | SERVER가 18:07:31.740~18:07:32.054 KST 실행. 실제 [로그 사본](avatar-evidence/server-kotlin-api.log), [명령·출처](avatar-evidence/server-kotlin-api-command.json)를 AVATAR가 직접 읽어 확인 |
| JVM 렌더링 출력 | 새 contact sheet를 직접 열어 네 경로의 의상·소품·장식, 같은 몸체·얼굴·표식, 여섯 표정과 제목 겹침 없음을 관찰 | [새 contact sheet](avatar-evidence/reports/nunti-contact-sheet.png). Compose 화면 또는 차량 런타임 검증과 별개 |

새 로컬의 합성 JVM 생성 시간은 중앙값 33.917μs, p95 133.875μs다. 로컬 프로세스에서 audit와 hash를 포함한 수치이며, 과거 수치와 실행 부하가 다르다. 실차 성능이나 개선율을 뜻하지 않는다.

API 검사는 `FastAPI TestClient`를 사용한 실제 서버 모듈·임시 SQLite 경로다. Android HTTP client, production outbox, 실제 네트워크 전체 경로를 검증한 결과로 확대하지 않는다. 고정 의존성에서 Starlette의 httpx 사용 중단 권고가 출력됐으며 검사는 성공했다. 의존성은 변경하지 않았다.

## 복원 도구와 환경 차이

| 설정 | 이번 경로·버전 |
| --- | --- |
| `JAVA_HOME` | `/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home` |
| `KOTLINC` | `/Users/pig30nidae/NUNTI/.worktrees/avatar/.local/avatar-tools/kotlinc/bin/kotlinc` |
| `JSON_JAR` | `/Users/pig30nidae/NUNTI/.worktrees/avatar/.local/avatar-tools/json-20250517.jar` |
| `AVATAR_BUILD_DIR` | `/Users/pig30nidae/NUNTI/.worktrees/avatar/.local/avatar-build` |
| `CONTRACT_ROOT` | `/Users/pig30nidae/NUNTI/.worktrees/avatar/contracts/v1` |

공식 [Kotlin 2.2.21 release](https://github.com/JetBrains/kotlin/releases/tag/v2.2.21)의 ZIP을 복원했다. GitHub 공식 release API가 제공한 SHA-256 `a623871f1cd9c938946948b70ef9170879f0758043885bbd30c32f024e511714`와 ZIP CRC를 확인했다. `org.json:json:20250517`은 Maven Central SHA-1 `d67181bbd819ccceb929b580a4e2fcb0c8b17cd8`과 대조하고 SHA-256 `3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796`을 보존했다. Maven의 `.sha256` URL은 HTTP 404였고 `.sha1`은 성공했다. [도구 출처와 해시](avatar-evidence/tool-provenance.json)에 기록했다.

샌드박스 안에서 GitHub API DNS 조회가 실패했다. 승인된 네트워크 실행으로 공식 Kotlin과 Maven Central 다운로드를 완료했다. 남은 네트워크 차단은 없다. 과거 `/private/tmp/nunti-*` 도구 경로는 사용하지 않았다.

검사 재실행 명령은 다음과 같다. [run_restore.py](avatar-evidence/run_restore.py)는 고정 도구의 해시를 검사하고, 버전·명령·시각·종료 코드·로그를 보존한다. 도구 다운로드 자체를 수행하지 않으며 이미 복원된 파일이 필요하다.

```sh
JAVA_HOME=/Users/pig30nidae/NUNTI/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home \
python3 docs/handoff/restoration/2026-11-02/avatar-evidence/run_restore.py
```

[commands.json](avatar-evidence/commands.json)은 이번 새 실행의 원본이다. `avatar-evidence/reports`는 그 실행에서 생성한 산출물을 복사한 것이다. 기존 `android/feature/avatar/reports`는 과거 기록으로 보존했다.

## 미구현 항목

- 실제 NaviHelper 응답을 `RouteSnapshot`으로 바꾸는 adapter와 실제 GIS 근거 공급자.
- 실제 DrivingEvent 생산자와 외부 점수 담당의 정식 이벤트 의미 합의.
- production trip host, 차량 상태·정책·lifecycle 공급, Android 영속 inbox와 서버 HTTP outbox 연결.
- 앱 저장소에 `AvatarReplay`와 `EmotionJournal`을 원자적으로 기록하고 재시작·재부팅 후 복원하는 host. 이번 파일 왕복 검사는 라이브러리 기능만 검증했다.
- 실제 경로 복잡도 산출. 현재 `routeComplexity`는 `UNKNOWN`이다.
- 최종 시각 자산, rig, 다양한 포즈와 사용자 평가. 현재 자산은 placeholder다.

## 미검증 항목과 차단사항

AVATAR의 새 순수 JVM 기준선과 새 Kotlin→API 경로에는 현재 차단사항이 없다. 통합 APK·lint·release는 PM 조율에 따라 TTS가 별도 cache로 검사한다. AVATAR에서 중복 빌드하지 않았으며 그 결과를 이 보고의 완료 항목에 포함하지 않았다.

이번 AVATAR 세션에서 Pleos 설치·기동, 실제 Compose 화면, 주차 상태 표시, lifecycle, TTS 출력은 실행하지 않았다. 과거 2026-11-01의 화면·음성 결과는 과거 증거로만 유지한다. 실제 P→D·속도→P와 UX 제한 변화는 여전히 미검증이다. 당시 Virtual Console 503은 과거 원인이며, 현재 환경에서도 같은 오류가 발생한다고 단정하지 않는다.

실제 NaviHelper binary·payload, GIS 원자료·검증 방식, 외부 이벤트 생산자의 계약은 아직 제공되지 않았다. 이 정보가 실제 입력 연결의 선행 조건이다. 인간 청취, 실도로 정확도, 실차·장기 시험과 모든 화면 크기·회전·접근성 instrumentation도 미검증이다.

## 다음 작업 제안과 완료 기준

다음 구현의 첫 작업은 PM이 실제 입력 소유자에게 payload와 의미를 확보하는 일이다. 아래 항목은 제안이며 이번 복원에서 구현하지 않았다. 확정 전에는 featureEvidence나 `verified=true`를 임의로 만들지 않는다.

| 순서·작업 | 선행 의존성과 담당 제안 | 완료 기준 |
| --- | --- | --- |
| 1. NaviHelper 입력 의미 확정 | PM·내비 host 담당이 실제 SDK 버전, binary의 필드·단위, 최초 계획 전체값과 진행 중 잔여값, reroute 콜백·순서·시각의 의미를 제공. AVATAR가 채택 규칙 검토, SERVER가 wire 영향 검토 | 실제 수집 payload에 source·시각을 남기고 최초 경로→진행→reroute 표본 확보. `distanceMeters`와 `estimatedDurationSeconds`가 전체 경로인지 확정. 잔여값을 전체값으로 사용하지 않음. trip 내 revision 단조 증가, routeId 변경 시 규칙, 누락 시 UNKNOWN 동작을 공동 승인 |
| 2. GIS 근거 규격 확정 | GIS 공급자가 경로 geometry와 도로·지형 자료의 버전, 교차 알고리즘, 거리 가중 분모, 알려지지 않은 구간, confidence 산출 근거 제공. PM이 신뢰 provider 승인 | roadTypeRatios 합 ≤1, 잔여 UNKNOWN. COASTAL·MOUNTAIN 각각의 근거 키, routeId·revision·특징값 귀속, observedAt·validUntil을 확인. reroute·값 변경 시 producer 재검증, stale·다른 태그·미승인 provider의 UNKNOWN 처리를 실제 표본으로 입증 |
| 3. 이벤트 의미 확정 | PM이 이은룡 담당과 producer의 eventType 목록·단위·verificationStatus·confidence의 근거와 범위·시각 기준 확보. AVATAR가 reducer mapping, SERVER가 저장·재전송 검토 | 동일 사건은 안정된 eventId로 재전송. correlationId의 사건 범위와 새 event ID를 가진 recoveryOfEventId의 연결 규칙 확정. 정상 위험→일치 회복, 불일치 회복, 중복, 역순, 미래·만료, 미검증·낮은 confidence 표본으로 같은 disposition과 감정 결과 확인. 현재 0.80 기준은 실데이터 승인 전 실험 설정으로 유지 |
| 4. AvatarReplay·EmotionJournal 영속 host 설계·구현 | PM이 공통 app host 소유자 지정. AVATAR가 라이브러리 경계, SERVER가 inbox·outbox의 원자성 경계 협의. trip 보존·삭제·암호화 정책, 부팅 식별자와 시간 변환 규칙을 먼저 확정 | app-private 원자적 기록, 원래 평가 시각·route·seed·rule/asset digest와 journal의 원래 수신 시각·tick 보존. 프로세스 중단 전후 동일 AvatarSpec·감정 상태·pending·dedup 복원. reboot 후 과거 monotonic 원점을 그대로 사용하지 않음. digest 변경·손상·20,000 entry 또는 10,000,000자 제한 초과는 명시적으로 거부하거나 승인된 migration·compaction 수행. 서버 조회·journal 복원으로 TTS가 자동 재생되지 않음 |
| 5. production 연결·차량 검증 | 실제 정책 host와 차량 시뮬레이터 복구가 선행. CarUx listener 하나를 AVATAR·TTS에 공유. PM이 화면 허가 기준과 통제된 실행 조건 확인 | 실제 P→D·속도→P의 차량값과 정책 freshness 로그, 차단·누락·노후 시 화면 및 접근성 숨김, 재주차 복귀 관찰. 합성 policy 단위 테스트와 구분한 화면·로그 증거 확보 |

영속 host의 추가 수용 시나리오는 기록 직전·직후의 강제 종료, 반복 복원, 지연·중복 이벤트, trip 전환·종료, 동의 철회·삭제다. 감정 엔진에는 서버에서 조회한 과거 감정을 다시 입력하지 않는다. 로컬 기능은 네트워크와 동의 여부에 독립적이어야 한다. 저장 원자성과 TTS 재생의 경계를 먼저 정하고, 검증되지 않은 exactly-once 보장을 제품 설명에 넣지 않는다.
