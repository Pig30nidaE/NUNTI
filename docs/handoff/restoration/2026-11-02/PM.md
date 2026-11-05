# 새 로컬 복원·검증 취합과 다음 작업

2026-11-02, Asia/Seoul. PM 시작 지침과 연결된 현황·담당 보고·복원 절차·계약·통합·Pleos 런타임·세 담당 협업 기록을 확인하고 실제 검사를 수행했다. 과거 담당 보고 원문과 2026-11-01 증거는 보존했다. 이번 변경은 복원 도구와 문서·검증 증거이며 제품 기능은 바꾸지 않았다.

## 원격 기준과 독립 작업 폴더

GitHub connector로 원격 `main=ebde9027f97f56f80bf8262c1200dbbb92827483`를 조회했고, 로컬 `main`·`origin/main`·세 담당의 시작 HEAD와 일치했다. [원격 확인 기록](remote-main.json)과 [worktree 실제 조회](worktrees.json)에 근거를 남겼다. 기존 구현 기준은 `bc0a948`이고 과거 브랜치를 다시 병합하지 않았다.

`git fetch origin`은 sandbox의 `.git/FETCH_HEAD` 쓰기 제한 뒤 허용된 재실행에서도 GitHub HTTPS 인증 부재로 실패했다. 원격 조회와 SHA 일치로 이번 기준선은 확인했지만 Git CLI 인증 복원은 남아 있다. 원격 push·배포는 수행하지 않았다.

| 역할 | 독립 worktree | branch | 다음 작업의 소유 범위 |
| --- | --- | --- | --- |
| PM | `/Users/pig30nidae/NUNTI` | `main` | 기준선·통합·공통 파일 승인·외부 입력 계약·수용 판정 |
| TTS | `/Users/pig30nidae/NUNTI/.worktrees/tts` | `codex/tts-next` | tts·voice 정책·큐·SDK·오디오 검증 |
| AVATAR | `/Users/pig30nidae/NUNTI/.worktrees/avatar` | `codex/avatar-next` | avatar·navigation·emotion·실제 경로 adapter·replay/journal 경계 |
| SERVER | `/Users/pig30nidae/NUNTI/.worktrees/server` | `codex/server-next` | backend·contracts·저장·통합. Android 공통 host·동기화는 후속 작업 후보 |

Git dir와 index가 각각 `.git/worktrees/tts`, `avatar`, `server`로 분리됐다. SDK는 PM, 공유 JDK는 TTS가 단독 설치했다. 나머지 도구·cache·빌드·debug signing은 역할별 경로로 분리했다. `.worktrees/`와 `.local/`은 루트에서 Git 제외했다. [공통 복원 절차](../../RESTORE_CHECKLIST.md)와 [worktree 재실행 도구](../../../../scripts/setup_role_worktrees.py)를 남겼다. 새 사용자 소유 채팅을 만들거나 기존 채팅·외부 담당에게 메시지를 보내지는 않았다.

## 이번에 실제 통과한 검사

| 영역 | 새 실행 결과 | 증거 |
| --- | --- | --- |
| 이관 무결성 | 시작 시 148 passed / 0 failed. 문서·과거 증거 보존 검사 | [초기 결과](handoff-verification.json) |
| SERVER | Python3.12.14·uv0.9.7·기존 lock, pytest91, Ruff check·format, 실제 loopback HTTP·응답 유실·재전송·프로세스 재시작 영속성, wheel·sdist와 wheel 직접 실행 통과 | [SERVER 보고](server.md) |
| AVATAR | JDK21.0.8+9·Kotlin2.2.21, JVM58, 합성1,000 재현·근거·fallback 모두1,000, 충돌0 | [AVATAR 보고](avatar.md) |
| 새 Kotlin→API | 방금 생성한 JSON10개를 Schema·Pydantic으로 검증, route/avatar4쌍 API 저장·조회 통과. TestClient와 SQLite 검사이며 실제 소켓 HTTP smoke와 구분 | [API 로그](server-evidence/kotlin-api.log), [새 입력 사본](server-evidence/avatar-generated) |
| TTS | lock의 Kotlin2.2.20, JVM62·실제 SERVER/AVATAR fixture8·Mock A~D, Android35/android.car/Pleos3.3.1 실제 바이너리 컴파일 통과 | [TTS 보고](tts.md) |
| Android 앱 | Gradle8.11.1·AGP8.10.1·앱 Kotlin2.2.21, debug·lint·release 성공. 온라인 lint 오류0·경고7 | [APK·lint 검사](tts-evidence/apk-result.json) |
| release 경계 | 실제 APK manifest·DEX에서 RuntimeProbeActivity 제외, debug에는 포함. 양쪽의 AndroidVoiceSession·Pleos TTS class 확인 | [APK 검사](tts-evidence/apk-result.json) |
| Pleos SDK 실행 | 공식2.1.0 ARM/API34·Emulator37.2.13 cold boot·RAM4GB, user10. 새 APK 설치·P/speed0·아바타 표시, ON_DEVICE 초기화·NOTIFICATION·ko_KR 및 완료 이벤트 | [앱 SDK 로그](pm-evidence/runtime-app-logcat.txt), [완료 이벤트](pm-evidence/events-completed.jsonl) |
| lifecycle | USER_CANCELLED, BACKGROUND, 각각 복귀 후 REPEATED_TEXT 통과 | [lifecycle 결과](pm-evidence/lifecycle-results.json) |
| 실제 에뮬레이터 주행 전환 | P→D→속도 변화→P 성공. Car API 최대15m/s=54km/h, 30km/h 구간 포함. 주행 중 requiresDO=true·avatarVisible=false, P 복귀 후 표시 | [최종 이벤트](pm-evidence/events-final.jsonl), [주행 화면](pm-evidence/moving.png), [복귀 화면](pm-evidence/final-parked.png) |
| D 전환과 TTS 정책 | D·속도0에서 새 요청 REJECTED/SPEECH_NOT_ALLOWED. 별도 주차 발화 STARTED 중 D·속도0 전환에서 CANCELLED/SPEECH_NOT_ALLOWED. P 복귀 후 자동 재발화 없음 | [D 취소 이벤트](pm-evidence/events-cancel-on-drive.jsonl), [최종 이벤트](pm-evidence/events-final.jsonl) |

새 debug APK SHA-256은 `e8642b8543268d70efc78a82a2fe8f9c5d5fe449a35322302a0c43a128aecef7`, unsigned release는 `ad8380e12e1bf9bb52a2f4c020ce5c121dc75c0af2bfaf23ea7ff256f7349f2b`다. 과거 APK 해시와 다르며 새 로컬 서명·빌드 결과를 기록한 것이다. APK는 TTS worktree의 `android/build/app/outputs/apk/`에 있고 Git에는 포함하지 않는다.

## 새 환경 차이와 해소한 차단

1. 시스템 Python은3.9.6이어서 SERVER는 설치된 Homebrew3.12.14를 명시했다. 과거3.12.8과 다르다. JDK21.0.8+9·Kotlin·SDK는 공식 배포물과 해시로 새로 복원했다.
2. sandbox DNS, uv의 macOS system-configuration panic, loopback bind 제한은 허용된 동일 명령 재실행에서 해소됐다. 담당별 최초 실패 로그를 보존했고 기능 실패와 구분했다.
3. SDK commandline23의 sdkmanager는 Android CLI로 위임한다. platform35 r02·build-tools35.0.0·platform-tools37.0.1·emulator37.2.13을 설치했다. 구 AGP parser와 SDK XML 버전 경고가 있었으나 빌드는 통과했다. 온라인 lint7개는 버전 권고4개와 기존 제품 정리3개이며 과거 오프라인3개와 조건이 다르다.
4. Pleos ZIP은 공식 feed와 동일 SHA-1 `24d28eb2f18eba5e87c861a7eb2bdccebb049419`, 4,669,762,816bytes, ZIP 전체 CRC 통과다. feed 경로의 `pleos_car_emulator`와 ZIP source.properties의 `android-automotive` tag가 달라 CLI 등록에 한 번 실패했다. image 내용은 바꾸지 않고 source tag의 표준 SDK 디렉터리에 등록해 AVD를 만들었다. 초기 생성 실패와 최종 config를 보존했다. 공식 devices.xml의2560×1440·160dpi·RAM4GB를 적용했다.
5. ADB native USB backend가 macOS IOServiceOpen에서 대기해 daemon이 시작되지 않았다. [스택 샘플](pm-evidence/adb-start-sample.txt)을 확인한 뒤 공식 지원 `ADB_LIBUSB=1`로 비교 실행해 연결을 복원했다. [실제 server-status](pm-evidence/adb-server-status.txt)는 LIBUSB를 확인한다. 사용법은 [공식 ADB 매뉴얼](https://android.googlesource.com/platform/packages/modules/adb/+/HEAD/docs/user/adb.1.md)을 따른다.
6. Virtual Console은 PC 브라우저 세션을 유지해야 활성화된다. 접속 전 browser.clients0·emulator_active/bridge/DDS=false에서 접속 후 clients1·모두true·actual Park로 변했다. [접속 전](pm-evidence/vehicle-state-before-browser.json), [접속 후](pm-evidence/vehicle-state-browser-open.json), [SERVER 조사](server-evidence/console-investigation.md)에 근거를 남겼다. 공식 프런트엔드의1초 heartbeat·3초 timeout과 맞는다. 직접 VHAL 쓰기나 user-build 보호 우회 없이 공식 UI에서 D·ACCEL·P를 조작했다. [공식 Console 절차](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/use-vehicle-emulator)를 따른다. 종료 때 이전 ADB 명령이 늦게 재개돼 출력 경로를 재사용한 문제는 SERVER가 미리 보존한 최초 사본으로 원본을 복구하고, 뒤늦은 응답을 별도 보존했다. [사본 출처·해시](pm-evidence/snapshot-provenance.json)에 구분을 기록했다.

과거 Virtual Console503·inactive 기록은 삭제하지 않는다. 이번 환경에서는 공식 브라우저 세션 유지로 활성화와 주행 전환을 확인했다. 모든 버전·호스트의503 원인이 동일하다고 일반화하지 않는다.

## 미구현

- 실제 NaviHelper adapter·GIS 근거 공급자·정식 DrivingEvent producer·production Automotive host 및 차량·통화·내비·안전음 feed.
- Android HTTP client·영속 outbox와 앱의 원자적 event inbox·AvatarReplay/EmotionJournal 저장 연결. Python outbox와 라이브러리 파일 왕복 검사를 Android 구현으로 확대하지 않는다.
- 이은룡 담당의 실제 점수·최종 코멘트 생성 모듈 연결과 payload 최종 합의. `overallScore=null`, `finalText` 원문 보존을 유지한다.
- 실제 감정 음향 제어·Pleos PCM 선행 묵음·새 인증 gRPC 오디오 캡처 도구, 최종 캐릭터 자산·rig·사용자 평가.
- 운영 로그인·토큰 발급/회전·TLS 배포·백업 복원·부하 시험 체계.

## 미검증과 적용 한계

이번 에뮬레이터는 `-no-window -no-audio`와 마이크 입력 비활성으로 실행했다. SDK 완료·정책 취소를 검증했지만 새 WAV·실제 PCM 출력·한국어 청취·첫 음절·선행 묵음·가청 지연·취소부터 실제 무음까지의 시간은 검증하지 않았다. 과거 WAV의 보존·해시 검사는 새 오디오 검사가 아니다.

D·속도0에서 요청 거부·진행 중 취소를 관찰했다. 속도>0 구간에서 별도의 새 TTS 요청을 제출하지 않았다. 주행 허용 기능의 정상 발화, 통화·내비·안전음 경합, Suspend/Resume·장기 누수, HYBRID/SERVER·네트워크 fallback, 실차는 여전히 미검증이다. SDK callback231ms·57ms는 개별 관찰이며 가청 지연·통계 benchmark가 아니다.

주행 화면은 플랫폼 차단 overlay다. 내부 renderer·접근성 subtree의 비노출을 독립 instrumentation으로 검증한 것은 아니다. 경로·감정·텍스트는 계속 Mock이며 실제 내비→점수→Android HTTP→서버의 제품 E2E는 없다. 이 결과는 production host의 출시 승인이 아니다.

## 다음 작업 배정과 완료 기준

현재 복원·검증 범위는 마쳤다. 사용자는 아직 외부 payload·저장소·담당 정보가 없으며 초기 단계이므로 외부 조율은 나중에 진행한다고 답했다. 외부 계약·담당자·일정 확정은 보류한다. 실제 입력 미제공을 이번 환경 복원의 차단으로 두지 않는다. 아래는 내부 다음 작업 후보이며 기능 구현에 새로 착수하지 않았다.

| 우선순위 | 다음 첫 작업·담당 | 선행 입력·완료 기준 |
| --- | --- | --- |
| 내부1 | PM이 공통 Android host·저장 경계를 정리. SERVER는 기존 저장 계약·HTTP/outbox 관점, AVATAR는 replay/journal 관점, TTS는 session/lifecycle 관점을 검토 | 현재 Mock producer로 app host와 영속 inbox/outbox 소유 경계를 먼저 정한다. CarUx listener1개, UNKNOWN 유지, 중복·재시작·ACK유실·동의 철회·삭제·자동 재발화 금지의 수용 시나리오를 작성. production 연결 완료로 부르지 않음 |
| 내부2 | SERVER의 Android HTTP/outbox와 AVATAR의 journal 영속 연결을 후속 구현 후보로 둠 | Mock 입력으로 로컬 반응이 네트워크·동의와 독립적으로 유지됨을 확인. 원자성·중단/재부팅·시계 원점·digest/손상·한도·trip전환을 검증. 공통 app·Gradle 소유권은 착수 시 PM이 확정 |
| 내부 병렬 | TTS는 녹음 도구 복원·청취 검증, AVATAR는 시각 자산·Mock 사용성 점검 후보를 정리 | 새 PCM·한국어 청취·첫 음절·가청 지연은 별도 증거로 판정. 지원하지 않는 음향 제어·묵음을 구현했다고 주장하지 않음. 고정 캐릭터·음성·원문 보존 유지 |
| 외부 조율 보류 | 사용자 지시에 따라 실제 NaviHelper/GIS·이은룡 이벤트/점수/코멘트·차량/오디오 feed 담당 협의는 추후 재개 | 향후 실물 표본이 생기면 전체/잔여 거리·단위·reroute, evidence 귀속, eventType·verification/confidence·correlation/recovery, 점수null·finalText 원문 보존을 확인. 지금 임의로 계약·담당·일정을 확정하지 않음 |
| 실연동 이후 | 실제 경로·이벤트·리포트 E2E와 실차·운영 준비 | 단절·재시작·철회 포함 실제 입력→로컬 반응→동의한 서버 저장을 검증. 초기 Mock 작업과 별도로 관리 |

이은룡의 점수·코멘트 소유권과 기존 세 담당의 모듈 소유권은 유지한다. 이번에는 외부 연락·추가 구현·운영 배포를 실행하지 않았다. 담당별 보고 끝의 실제 입력 협의 제안은 사용자 답변 전 제안이며 위 보류 결정이 현재 우선순위다.

## 재실행과 증거 보존

역할별 실제 명령·종료코드·도구 해시는 위 세 보고서에 연결돼 있다. 원본 기록 판정은 다음으로 다시 검사한다. 두 번째 명령은 보존된 이번 에뮬레이터 JSON을 검사하며 장치를 새로 실행하지 않는다.

[런타임 기록 검증](pm-evidence/runtime-verification.json)은9개 조건을 통과했다. [검증 도구의 실패 사례 검사](pm-evidence/verifier-audit.json)는 중복 lifecycle·삭제된 D 거부 증거·미생성/누락 worktree의 실패와 생성·재실행의 성공을 임시 사본에서 확인했다. [최종 문서·과거 증거 검사](final-handoff-verification.json)는 새 앱 실행 검사와 구분한다. TTS와 AVATAR도 PM 원시 기록을 읽고 [TTS 추가 검토](tts-evidence/runtime-review.md), [AVATAR 추가 검토](avatar-evidence/runtime-review.md)를 남겼다.

```sh
python3 scripts/setup_role_worktrees.py --expected-sha ebde9027f97f56f80bf8262c1200dbbb92827483
python3 scripts/verify_restored_runtime.py
python3 scripts/verify_handoff.py
```

새 장치 실행은 현재 로컬의 `.local/pm-tools/env.sh`를 읽어 JDK·SDK·AVD 경로와 `ADB_LIBUSB=1`을 설정한다. cold boot·RAM4GB로 실행한 뒤 `adb devices`·fingerprint·user10을 확인한다. Console 포트8088을 forward하고 브라우저 전체 페이지를 열어 유지한 상태에서 emulator_active·DDS·gear bridge를 확인한다. 새 APK 설치 후 `android/scripts/verify_runtime_probe.py`를 실행한다. 이 도구는 user10을 가정하고 직접 상태와 SDK 이벤트를 새로 확인해야 한다. 다른 user·device를 임의로 대체하지 않는다.

이번 실행의 최종 상태는 P·속도0으로 복원했다. 테스트 AVD·임시 ADB daemon은 증거 수집 후 종료하고 도구·AVD 디스크·worktree·소스는 다음 작업용으로 남긴다. 문서·기록 검증 결과와 산출물 해시는 이 폴더의 최종 검증 파일·manifest에 보존한다.
