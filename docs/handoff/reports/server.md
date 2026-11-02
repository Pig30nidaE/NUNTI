# SERVER 담당 직접 보고

수신일: 2026-11-02, Asia/Seoul. 기존 채팅: Nunti 서버 시스템 통합 구현 (`01a196f8-81b9-7ac1-85ad-15b5ed127fcd`). PM의 요청에 대한 담당 세션 최종 답변이다. 아래 보고의 문구는 보존하고 로컬 파일 링크만 저장소 상대경로로 바꿨다. Git 미포함 APK 링크는 경로 표기로 바꿨다.

보고 시점의 “remote 없음”은 이후 사용자가 `https://github.com/Pig30nidaE/NUNTI.git`를 지정하면서 해소됐다. PM이 origin을 연결했으며, 최종 이관 상태는 [전체 현황](../STATUS.md)과 [복원 절차](../RELOCATION.md)를 따른다. 이 보고의 `/private/tmp` 경로와 과거 로컬 절대경로는 새 로컬 설정값이 아니다.

2026-11-02 KST 기준으로 점검했습니다. **서버 MVP와 계약·Mock 통합은 구현됐고, Pleos에서 아바타와 실제 ON_DEVICE TTS 출력까지 검증했습니다.** 운영 배포, 실제 차량 데이터 연결, Android의 서버 동기화 구현은 남아 있습니다.

이번 보고에서는 파일·Git·서비스 상태를 변경하지 않았습니다. 테스트 결과는 11월 1일 실제 실행 기록이며, 오늘은 현재 소스·Git 상태·파일 존재 여부·APK 해시를 확인했습니다.

1. **확정된 요구사항과 설계 결정**

   SERVER는 서버 API, 공통 데이터 계약, 저장, 시스템 통합을 담당합니다. 아바타 생성·감정 계산·TTS 내부 구현·운전 점수·최종 코멘트 생성은 SERVER 소유가 아닙니다. 점수와 최종 코멘트 생성은 이은룡 담당입니다.

   주요 결정은 다음과 같습니다.

   - FastAPI, Pydantic v2, SQLite를 사용합니다. 마이크로서비스·메시지 브로커·WebSocket·SSE는 도입하지 않았습니다.
   - 실시간 반응은 Android 안에서 처리합니다. `차량 이벤트 → 로컬 이벤트 어댑터 → 감정 엔진 → TTS 정책` 경로가 서버 연결에 의존하면 안 됩니다.
   - 서버는 동의된 데이터를 HTTP 배치로 저장하고 조회합니다. 서버 재전송이 감정 계산이나 음성을 다시 실행시키면 안 됩니다.
   - 동기화와 Mock API는 기본 비활성화입니다. 서버 설정과 주행별 명시적 동의가 모두 있어야 업로드할 수 있습니다.
   - 정확한 GPS·주소·목적지 원본은 서버 계약에서 제외했습니다.
   - 점수 계산 불가는 `null`로 보존합니다. `0`으로 바꾸지 않습니다. `TripReport.finalText`를 재작성하지 않습니다.
   - 기획 HTML의 배점·시간 구간·평가 임계값·SDK 데이터 가용성은 초안입니다. 서버가 이를 확정하거나 평가 알고리즘으로 구현하지 않았습니다.
   - 원본 HTML의 STT-only 문구보다 최신 사용자 지침인 “허용된 상황의 짧은 TTS”를 우선했습니다.
   - 사용자가 추가로 실제 Pleos APK 검증을 요청했습니다. 기존 Automotive 기본 화면이 차단 상태여서, 담당자 협의 후 debug 전용 `RuntimeProbeActivity`를 추가했습니다. production 기본 화면의 차단은 유지했습니다.

   설계 근거는 [서버 아키텍처](../../../docs/architecture/server.md)에 있습니다.

2. **구현 상태와 주요 파일**

   | 범위 | 현재 상태 | 주요 파일 |
   |---|---|---|
   | API·인증·응답 규격 | 구현 완료 | [api.py](../../../backend/nunti/api.py), [config.py](../../../backend/nunti/config.py) |
   | 공통 계약 | 7개 공유 모델과 3개 전송 모델, 스키마 10개·샘플 30개 | [models.py](../../../backend/nunti/models.py), [계약 설명](../../../contracts/v1/README.md) |
   | SQLite 저장 | 소유자 분리, 멱등성, revision 충돌, 원자적 배치, 역순 도착, 삭제·만료 구현 | [store.py](../../../backend/nunti/store.py) |
   | Mock | 고정 시나리오 10개와 인증된 opt-in 조회 API | [fixtures.py](../../../backend/nunti/fixtures.py) |
   | 재전송 예제 | Python 영속 outbox와 장애 시연 구현 | [demo_outbox.py](../../../backend/nunti/demo_outbox.py), [demo.py](../../../backend/nunti/demo.py) |
   | 계약·Fixture 생성 | 재생성 및 drift 검사 가능 | [export_contracts.py](../../../backend/scripts/export_contracts.py), [build_fixtures.py](../../../backend/scripts/build_fixtures.py) |
   | 실제 Kotlin 출력 연동 | AVATAR 출력 검증·서버 저장 검사 구현 | [verify_android_outputs.py](../../../backend/scripts/verify_android_outputs.py) |
   | Pleos 진단 통합 | debug 전용 실행 화면과 lifecycle 검사 구현 | [RuntimeProbeActivity.kt](../../../android/app/src/debug/kotlin/ai/nunti/app/RuntimeProbeActivity.kt), [verify_runtime_probe.py](../../../android/scripts/verify_runtime_probe.py) |

   API는 `/health`, 인증된 `/v1/capabilities`, 주행 생성·조회·삭제, 경로·아바타 저장, 이벤트·감정 배치 저장 및 조회, 종료 리포트 저장·조회, Mock 조회를 제공합니다. 배치와 조회 페이지는 최대 100개, 요청 본문은 최대 256 KiB입니다.

   SQLite는 WAL, `BEGIN IMMEDIATE`, 외래키, `user_version=1`을 사용합니다. 동일 ID와 동일 내용의 재전송은 `duplicate`, 같은 ID의 다른 내용은 충돌입니다. 리포트는 주행당 하나의 불변 산출물입니다.

   다음은 미구현 또는 후속 범위입니다.

   - Android Room·WorkManager 기반 영속 outbox와 실제 서버 동기화
   - 실제 NaviHelper·차량 SDK 입력을 연결한 전체 제품 흐름
   - 이은룡 모듈의 실제 이벤트·점수·최종 코멘트 연결
   - production Automotive 앱 화면과 차량 상태 관리의 완성
   - 로그인·토큰 발급·갱신·회전
   - 운영 TLS·속도 제한·백업·복원·부하 검증
   - 리포트 정정 버전, 동의 이력·철회 전용 API, 변경 피드 cursor
   - schema version 1 이후 DB migration

   Python outbox는 실행 가능한 동작 예제입니다. Android 동기화가 구현됐다는 의미로 넘기면 안 됩니다.

3. **실제 검증 결과와 한계**

   아래 명령은 저장소 루트 또는 표기한 작업 디렉터리에서 실행했던 검증입니다.

   | 검증 | 실행 명령 또는 경로 | 결과 |
   |---|---|---|
   | 서버 테스트 | `backend/.venv/bin/pytest backend/tests -q` | 91 passed |
   | 서버 정적 검사 | `backend/.venv/bin/ruff check backend`, `ruff format --check backend` | 통과 |
   | 실제 HTTP·재시작 | backend에서 `.venv/bin/python scripts/smoke_server.py` | loopback HTTP, 재전송, 프로세스 재시작 후 영속성 통과 |
   | 배포 패키징 | `uv build backend --offline --out-dir /private/tmp/nunti-dist` | wheel·sdist 생성, 패키지 import·Mock 포함 확인 |
   | AVATAR JVM | `KOTLINC=… JSON_JAR=… bash android/feature/avatar/scripts/test.sh` | 58개 테스트와 합성 경로 1,000개 통과 |
   | 실제 AVATAR JSON | `backend/.venv/bin/python backend/scripts/verify_android_outputs.py` | JSON 10개 검증, 경로·아바타 4쌍 API 저장·조회 |
   | TTS | `python3 android/feature/tts/scripts/verify.py --android --tools-dir …` | JVM 62개, 실제 계약 Fixture 8개, Android·Pleos 바이너리 컴파일 통과 |
   | Android | Android 디렉터리에서 Gradle `:app:assembleDebug :app:lintDebug`, `:app:assembleRelease` | 빌드 성공, debug Lint 오류 0개·경고 3개 |
   | 런타임 lifecycle | `android/scripts/verify_runtime_probe.py`와 동일한 검증 절차 | 사용자 중지·BACKGROUND 취소·각 복귀 후 REPEATED_TEXT 확인 |

   서버 테스트에는 인증·소유자 분리·동의·HTTPS·자료형·스키마 drift·동시 재전송·원자적 rollback·revision 충돌·역순 이벤트·삭제·보존기간·Mock E2E가 포함됩니다. 의존성 관련 deprecation warning 한 건이 있었고 실패는 없었습니다.

   Pleos 실제 검증 환경은 공식 Connect 2.1.0 ARM 이미지, API 34, Android Emulator 37.2.13, RAM 4GB, cold boot였습니다. 장치는 `emulator-5554`, Android 사용자는 10이었습니다.

   실제 확인 사항은 다음과 같습니다.

   - 기어 P, 속도 0, UX 제한 0, `requiresDO=false`를 Car API에서 읽었습니다.
   - 도심·장거리·해안·산악 외형과 NEUTRAL·STARTLED·JOYFUL 표정 변화가 화면에 나타났습니다.
   - 넓은 화면에서 발견한 Canvas 넘침은 AVATAR 담당자가 수정했고 통합했습니다.
   - 실제 앱 창 1682×1210과 847×910에서 겹침 해소를 확인했습니다.
   - 실제 Pleos SDK의 ON_DEVICE 초기화, NOTIFICATION audio attributes, listener, `ko_KR` 설정을 확인했습니다.
   - 최종 발화는 `QUEUED → STARTED → COMPLETED`였습니다. 해당 요청의 submit→SDK onStart는 41ms였습니다.
   - 인증된 localhost gRPC로 에뮬레이터 스피커 출력을 녹음했습니다. 최종 WAV는 48kHz·16bit·stereo, 7.166875초, peak 1,409, RMS 225.58입니다.

   검증 범위에는 다음 제한이 있습니다.

   - 경로·감정·발화 문장은 MOCK입니다. 실제 내비게이션 경로와 서버 HTTP를 연결한 차량 E2E는 아닙니다.
   - 경쟁 오디오 없음은 통제된 테스트 조건입니다. 실제 차량의 모든 오디오 상태를 검증하지 않았습니다.
   - Virtual Console은 `emulator_active=false`, `bridge_ready=false`, `dds_ready.all=false`였습니다. D 전환 요청은 HTTP 503 `emulator_inactive`로 실패했습니다.
   - `hmg_car_service`는 이미지에 없었고, 일반 `car_service` 명령은 user build 제한으로 거부됐습니다. 실제 주행 UX 차단과 재주차 복귀는 미검증입니다.
   - 인간 청취에 의한 발음·음질·첫 음절·선행 묵음 평가는 하지 않았습니다. 41ms는 가청 지연 benchmark가 아닙니다.
   - 감정별 실제 음색·속도·피치 제어를 검증하지 않았습니다.

   기준 증거는 [서버·빌드 검증 기록](../../../docs/architecture/validation.md)과 후속 [Pleos 런타임 기록](../../../docs/architecture/pleos-runtime.md)입니다. 후속 기록에는 화면, WAV, 원시 SDK 로그, 구조화 이벤트, 권한, lifecycle 결과, APK 출처가 연결돼 있습니다.

4. **Git 상태와 이관할 파일**

   현재 확인한 상태입니다.

   | 항목 | 값 |
   |---|---|
   | 통합 브랜치 | `server/integration-v1` |
   | HEAD | `bc0a9483d4baaefee397635dd3dc01fe2b7f4b3e` |
   | 마지막 커밋 | `test(integration): verify avatar and TTS on Pleos emulator` |
   | 미커밋·미추적 파일 | 없음 |
   | Git remote | 설정 없음 |
   | AVATAR 브랜치 ref | `avatar/route-emotion-v1`, `e1183b6` |
   | TTS 브랜치 ref | `codex/tts-system`, `e640908` |

   AVATAR와 TTS 구현·후속 수정은 통합 브랜치에 cherry-pick돼 있습니다. 브랜치별 커밋 해시가 달라도 미통합으로 판단하면 안 됩니다. 새 개발 기준은 통합 HEAD입니다.

   **두 담당 worktree 디렉터리는 현재 없어졌습니다.** Git 등록만 남아 `prunable`로 표시됩니다. 이번 점검에서는 정리하지 않았습니다.

   소스 재개에 필요한 항목은 추적 파일 전체와 Git 이력·브랜치입니다. remote가 없으므로 현재 저장소를 보존하거나 PM이 별도 bundle 또는 원격 이관을 준비해야 합니다. 이번 보고에서는 export·push를 하지 않았습니다.

   ignored 파일 중 기존 검증 바이너리를 보존하려면 다음 두 파일을 별도로 이관해야 합니다.

   - `android/build/app/outputs/apk/debug/app-debug.apk`
     SHA-256 `87f207f35418d1979133c903117327eb46cc4fc0a3aa6a40847a5a24ff74cc58`
   - `android/build/app/outputs/apk/release/app-release-unsigned.apk`
     SHA-256 `e09c1735d9ca0e204965dfabdcbd9a5bd7dba89e50d49615e4fb16dbee21a7a3`

   오늘 두 파일의 존재와 해시 일치를 확인했습니다. 소스 재개만 필요하면 재빌드할 수 있지만, 새 로컬의 서명·빌드 환경에서 동일 APK 해시를 보장하지는 않습니다. release APK는 unsigned이며 검증용 Activity가 포함되지 않습니다.

   `.venv`, `.gradle`, 일반 build 출력, pytest·ruff·Python 캐시는 재생성 대상입니다. 추적된 스크린샷·WAV·JSON·로그는 이미 Git에 포함돼 있습니다. 현재 backend에서 실제 `.env`나 SQLite DB 파일은 발견되지 않았습니다.

5. **새 로컬 의존성·설정·외부 경로**

   서버는 Python `>=3.12,<3.15`를 요구하며 실제 검증은 3.12.8에서 했습니다. `uv sync --frozen`으로 [uv.lock](../../../backend/uv.lock)을 적용합니다. 가상환경을 다른 로컬로 복사해 재사용하지 않습니다.

   잠금 파일의 주요 버전은 FastAPI 0.162.0, Pydantic 2.14.2, Uvicorn 0.54.0, pytest 9.2.0, httpx 0.28.1, jsonschema 4.26.0입니다. 서버 자체에는 외부 클라우드 키나 별도 DB 서버가 필요하지 않습니다.

   Android 재빌드 환경은 다음과 같습니다.

   - JDK 21, JVM target 17
   - 포함된 Gradle wrapper 8.11.1
   - AGP 8.10.1, Kotlin·Compose plugin 2.2.21
   - Android SDK Platform 35, Build Tools 35.0.0
   - compileSdk·targetSdk 35, minSdk 28
   - Pleos `TextToSpeech:3.3.1`
   - Google Maven·Maven Central·Pleos Maven 저장소 접근
   - 에뮬레이터 실행에는 별도로 Pleos API 34 이미지와 플랫폼 도구 필요

   TTS 독립 검사 도구는 `verify.py --bootstrap --android`로 고정된 도구를 다시 받을 수 있습니다. AVATAR 독립 검사는 Kotlin compiler 2.2.21 이상과 `org.json` JAR를 사용합니다.

   아래 임시 경로는 **오늘 모두 존재하지 않는 것으로 확인했습니다.** 이전 문서의 절대 경로를 그대로 실행하면 안 됩니다.

   ```text
   /private/tmp/nunti-android-build
   /private/tmp/nunti-pleos-runtime
   /private/tmp/nunti-tts-tools
   /private/tmp/nunti-kotlin
   /private/tmp/nunti-avatar
   /private/tmp/nunti-tts-worktree
   ```

   SDK·AVD·Gradle 캐시·독립 컴파일러를 복원해야 합니다. 임시 gRPC 녹음 보조 스크립트도 저장소에 포함하지 않았으므로 다시 준비해야 합니다. 녹음 결과와 PCM 형식 검증 자료는 Git에 남아 있습니다.

   공식 Pleos 이미지의 당시 다운로드 정보는 [tool-provenance.json](../../../docs/architecture/validation-evidence/pleos-runtime/tool-provenance.json)에 있습니다. 당시 압축 파일은 약 4.67GB, 해제 이미지는 약 20GB였습니다. AVD·SDK·빌드 캐시 공간도 필요합니다.

   설정과 비밀정보는 다음 이름으로 관리합니다. 실제 값은 인수인계 문서에 넣지 않습니다.

   | 이름 | 복원 방식 |
   |---|---|
   | `NUNTI_AUTH_TOKENS` | 새 무작위 토큰과 principal 매핑을 생성해 환경변수로 주입 |
   | `NUNTI_DEMO_TOKEN` | 합성 시연 클라이언트가 사용할 토큰을 같은 환경에 주입 |
   | `NUNTI_SYNC_ENABLED` | 필요한 개발 환경에서 명시적으로 활성화 |
   | `NUNTI_ENABLE_MOCKS` | Mock 검증 시 명시적으로 활성화 |
   | `NUNTI_REQUIRE_HTTPS` | 기본 true. localhost 개발 시에만 문서에 따라 조정 |
   | `NUNTI_DB_PATH` | 저장 위치 지정. 기본은 backend 작업 디렉터리 기준 `data/nunti.sqlite3` |
   | `NUNTI_RETENTION_DAYS` | 기본 30일 |
   | `ANDROID_HOME`, `ANDROID_USER_HOME`, `ANDROID_AVD_HOME`, `GRADLE_USER_HOME` | 새 로컬의 실제 설치 경로로 설정 |
   | `KOTLINC`, `JSON_JAR`, `NUNTI_JAVA` | 독립 모듈 검증 도구 경로가 필요할 때 설정 |
   | `PleosCredentials.clientId`, `clientSecret` | HYBRID·SERVER 모드 도입 시 TTS 호스트가 안전하게 공급. 이번 ON_DEVICE 검증에는 사용하지 않음 |

   `.env.example`은 참고 파일이며 서버가 `.env`를 자동으로 읽지는 않습니다. 재실행 절차는 [backend README](../../../backend/README.md)를 기준으로 삼으면 됩니다.

6. **알려진 문제와 다음 우선순위**

   재개 순서는 다음이 적절합니다.

   1. 통합 HEAD와 증거·필요한 APK를 먼저 이관하고 새 로컬 환경을 복원합니다.
   2. 서버 91개 테스트, Android 빌드, 모듈 검사를 다시 실행해 새 환경의 기준선을 만듭니다.
   3. 활성 차량 시뮬레이터 또는 검증 장치에서 D 전환·주행 UX 제한·재주차 복귀를 확인합니다.
   4. 실제 Android host에 차량 상태·UX·오디오 상태와 SDK adapter를 연결합니다.
   5. Android 영속 outbox를 구현하고 실제 서버 저장·재전송까지 연결합니다.
   6. 이은룡 담당의 실제 이벤트·점수·리포트 정의를 승인받고 계약을 확정합니다.
   7. 공개 배포 전 인증 발급 체계·TLS·속도 제한·백업·복원을 검증합니다.

   문서의 시점 차이도 정리 대상입니다. [SERVER 협업 기록](../../../docs/coordination/server.md)은 아직 에뮬레이터 실행을 미검증으로 적고 있습니다. 이전 `root-integration.json`의 `vehicleRuntimeTested=false`와 APK 해시 `49a664…`도 초기 빌드 기록입니다. 최신 상태는 `pleos-runtime.md`와 그 증거 디렉터리의 `apk-provenance.json`을 우선해야 합니다. 이번에는 읽기 전용 요청에 따라 문서를 수정하지 않았습니다.

   `verify_runtime_probe.py`는 현재 패키지명과 Android 사용자 10을 전제로 합니다. 다른 AVD에서 사용자가 다르면 조정해야 합니다. 기본 launcher 화면은 여전히 Automotive에서 차단됩니다. 진단 Activity를 명시적으로 실행해야 합니다.

7. **계약·소유권·통합 주의사항**

   공통 계약은 `schemaVersion: "1.0"`, camelCase, **JSON Schema Draft 2020-12**입니다. AVATAR·TTS와 핵심 필드는 조율하고 실제 연동도 확인했지만, 외부 점수 담당의 최종 승인이 남아 있어 여전히 협의 중인 초안으로 표시합니다.

   재개할 담당자가 유지해야 할 계약 규칙은 다음과 같습니다.

   - `EmotionSnapshot.emotionId`는 재전송 식별자입니다.
   - `generationSeed`는 문자열입니다.
   - 같은 `avatarId`를 revision 사이에 유지할 수 있습니다. 서버 외형 저장 키에는 `routeRevision`이 포함됩니다.
   - `routeRevision`은 같은 trip 안에서 증가합니다. `routeId`가 바뀌어도 증가 규칙을 유지합니다.
   - 경로 특징의 근거는 해당 snapshot의 route·revision·값에 귀속됩니다. 값이나 revision 변경 시 재검증해야 합니다.
   - `routeOption`은 실제 도로 비율의 근거가 아닙니다.
   - `SpeechRequest.contentSource`는 출처입니다. `speechPurpose`는 목적이며 재생 허가가 아닙니다.
   - `sourceEventId`·`emotionId`와 신뢰된 로컬 근거를 TTS 정책이 검증해야 합니다.
   - 서버는 `VoiceProfile`·`SpeechRequest`를 원격 재생 명령으로 저장하거나 실행하지 않습니다.
   - 서버 조회 결과를 로컬 감정 엔진 입력으로 다시 넣지 않습니다.
   - 알려지지 않은 필드·버전은 거부합니다. 합의 없이 필드·타입·enum을 바꾸면 안 됩니다.

   SERVER 소유 범위는 `backend`, `contracts/v1`, 아키텍처 문서, SERVER 협업 문서와 공통 계약 요청입니다. AVATAR 생성·감정·렌더러와 TTS adapter·큐·재생 정책은 담당자에게 변경 요청을 먼저 전달해야 합니다.

   이번 Canvas 수정도 AVATAR 담당자가 구현했고 SERVER가 검토·cherry-pick·런타임 재검증했습니다. debug 진단 Activity는 두 담당과 협의한 SERVER 통합 범위입니다.

   새 로컬에서는 최신 통합 HEAD를 기준으로 담당별 branch·worktree를 다시 만드는 편이 안전합니다. 기존 `/private/tmp` worktree 경로와 분리 개발용 `nuntiTtsCheckout` 설정을 그대로 재사용하지 않습니다. 통합 저장소에는 TTS 모듈이 이미 포함돼 있습니다.

   실제 연결 순서와 장애 처리 규칙은 [통합 문서](../../../docs/architecture/integration.md)에 있습니다. 문서 속 adapter 호출 예시는 앱이 구현할 인터페이스 의사코드이며, 확인된 Pleos SDK 메서드명으로 취급하면 안 됩니다.
