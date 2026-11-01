# 알고리즘 및 빌드 검증 보고서 · 2026-11-01

## 실제 결과

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| JVM 시나리오 테스트 | 58 통과 | 특징/생성/감정/표시 정책/복원/wire |
| 동일 입력 재현 | 1,000/1,000 | 고정 seed73의 합성 경로, full AvatarSpec equality |
| 파츠 규칙 충돌 | 0/1,000 | slot/배타/테마/얼굴/anchor/envelope/contrast |
| 근거 있는 출력 | 1,000/1,000 | base 또는 selected evidence 전부 verified |
| 근거 제거 fallback | 1,000/1,000 | featureEvidence 삭제 후 BASE |
| 대표 경로 차별성 | 4개 테마 구별 | CITY/JOURNEY/COASTAL/MOUNTAIN 고정 fixture |
| identity 보존 | 통과 | 4경로×11seed, 6표정의 body/face/signature 동일 |
| 생성 시간 중앙값 | 78.542 μs | 로컬 JVM, extractor/audit/hash 포함 |
| 생성 시간 p95 | 388.042 μs | 별도 AAOS 장치 측정 아님 |
| Android Compose/AAOS 직접 컴파일 | 통과 | 공식 Android35/android.car + Compose1.8.3 |
| 통합 Debug APK | 통과 | Gradle8.11.1/AGP8.10.1/Kotlin2.2.21/JDK21 |
| Android Lint | 오류 0, 경고 7 | 버전 권고4, backup 규칙1, 임시 앱 icon1, KTX 스타일1 |
| SERVER 계약 검사 | JSON10개 통과 | SERVER가 Schema/Pydantic 및 4경로 API 저장/조회 확인 |
| TTS 계약 검사 | 8개 통과 회신 | TTS가 실제 AVATAR voice/emotion fixture 검사 |

최종 통합 빌드: `BUILD SUCCESSFUL in 31s`, 130 tasks.
APK: `android/build/app/outputs/apk/debug/app-debug.apk`, 39,289,362 bytes.
SHA-256: `bdef0dd81b28f91dfaad570b7c0a9b8a801aad87a3a557148efe8f962174b547`.
APK는 생성물로 Git에 넣지 않는다. 소스와 Gradle Wrapper 및 재현 명령을 제공한다.

## 정량 검사 해석

검사기는 실패 시 nonzero로 종료한다. 테스트 목록은 `tests.txt`, 측정 원본은 `metrics.json`에 있다.
대량 fixture는 도로/거리/시간/지형 조합을 고정 난수 seed로 만든 합성 표본이다.
재현율/충돌율이 실제 경로의 분류 정확도나 사용자 만족도를 의미하지 않는다.
시간 측정은 JVM warmup, 동시에 실행한 Gradle, 장치 부하의 영향을 받는다. 실차 latency 보장값이 아니다.

경로 삭제·잘못된 숫자·NaN·근거 confidence·revision 변경·지형 tag별 증거·정렬 순서·동일 점수 tie를 검사했다.
중복/역순/미래/만료/불확실한 이벤트, debounce/cooldown/dwell/hysteresis, 무수신·회복·주행 종료·새 trip을 검사했다.
종료 이벤트가 마지막 위험 이벤트와 같은 시각이어도 trip을 종료한다.
설정 Properties를 외부에서 수정해도 이미 생성된 engine의 rule digest/행동이 바뀌지 않는 회귀 검사를 포함했다.

## 시각 검사

`demo/nunti-contact-sheet.png`를 직접 열어 4개 여정 및 6개 표정을 확인했다.
동일 몸체/얼굴/표식/눈·입 위치 유지, 가방/티켓/물병의 구분, 얼굴 가림 없음, 해안/능선 장식을 확인했다.
Compose, SVG, PNG는 같은 CharacterScene 명령을 쓴다. PNG backend는 JVM 검증 전용이다.
서로 다른 크기의 viewBox/normalized scene은 자동 검사했으나 실제 Compose 터치·회전·접근성 instrumentation은 수행하지 않았다.
`demo/index.html`의 출발 전/주행 차단/종료 후 보기 및 감정 replay는 실제 Kotlin 결과의 정적 뷰어다.
`demo/emotion-timeline.json`은 실제 reducer로 만든 0/3/6/9/12초 상태이며 임의 점수 매핑이 아니다.

## 초기 빌드 시점의 미검증 항목

- Pleos/AAOS 에뮬레이터 설치 및 앱 실행, 실차 화면 허가, 실제 주행 데이터 수신은 미검증.
- Debug APK는 일반 Android Mock 뷰어이며 Automotive에서는 실제 정책 host 연결 전 표시 중지.
- 실제 음향, 첫 음절, 통화/내비 focus, TTS runtime은 TTS와 차량 환경에서 후속 검증 필요.
- 실도로 GIS 정확도, 경로 분류/가중치 최적화, 사용자 평가, 최종 디자인 제작은 미완료.
- 본 모듈의 서버/TTS 연결은 v1 mapper 및 공유 DTO 경계다. 실시간 HTTP 동기화 서비스는 SERVER/host 책임.
- Lint의 7개 권고는 남아 있다. 의존성은 검증 조합에 고정했고 임시 Mock 앱은 출시용 패키지가 아니다.

## Pleos 실제 화면 후속 확인 · 2026-11-01

초기 빌드 이후 SERVER의 debug 진단 Activity로 Pleos 2.1 에뮬레이터 실행이 이루어졌다.
AVATAR는 2560×1440 캡처 6개와 실제 task 크기를 줄인 캡처 1개를 직접 열어 다음 항목을 확인했다.
이 절은 위 초기 미검증 범위 중 실제 화면 표시 항목을 갱신한다.

| 확인 항목 | 결과 |
| --- | --- |
| 넓은 창의 제목·본문 겹침 | 초기 실패 발견, 높이 320dp 지정 후 해소 |
| 도심/장거리/해안/산악 Mock 경로 | 실제 Compose 화면에서 의상·소품·장식 구분 확인 |
| 동일 캐릭터 정체성 | 얼굴·몸체·핵심 색·표식 유지 확인 |
| 놀람/기쁨 표정 | 실제 화면의 눈·입 변화 확인 |
| 작은 창/실제 task resize | 847×910px CITY 화면 관찰 통과; 중앙 배치 및 제목·본문 겹침 없음 |
| 실제 D 전환 및 UX 제한 변화 | 미검증; 차량 상태 변경 도구가 동작하지 않았다고 SERVER 보고 |

수정 커밋은 `01bf3be`, 루트 통합 커밋은 `3cef188`이다.
수정 모듈 `:feature:avatar:compileDebugKotlin`은 14초에 성공했고 SERVER는 debug 앱 재빌드·Lint·재설치 후 캡처했다.
이 레이아웃 수정은 생성/감정 규칙을 바꾸지 않는다.

작은 창은 SERVER가 `am task resize`로 `mBounds=Rect(853,90-1700,1000)`을 확인한 상태의 캡처다.
기본 창 `Rect(853,90-2535,1300)`(1682×1210px)으로 복원했다고 보고했다.
`wm size`로 화면만 잘린 이전 결과는 검증에서 제외했다. 이 관찰은 모든 창 크기·경로·표정 조합을 포괄하지 않는다.

증거: [도심](../../../../docs/architecture/validation-evidence/pleos-runtime/city.png),
[장거리](../../../../docs/architecture/validation-evidence/pleos-runtime/journey.png),
[해안](../../../../docs/architecture/validation-evidence/pleos-runtime/coast.png),
[산악](../../../../docs/architecture/validation-evidence/pleos-runtime/mountain.png),
[놀람](../../../../docs/architecture/validation-evidence/pleos-runtime/emotion-startled.png),
[기쁨](../../../../docs/architecture/validation-evidence/pleos-runtime/emotion-joyful.png),
[작은 창](../../../../docs/architecture/validation-evidence/pleos-runtime/narrow-task.png).
스크린샷의 P/속도0/UX0 표시는 에뮬레이터 상태이며 경로·감정은 여전히 합성 입력이다.
실차 허가, 지리정보 정확도, 실제 주행 중 표시 제한 검증으로 확대 해석하지 않는다.

## 재현

핵심: 저장소 루트에서 `KOTLINC=/path/to/kotlinc bash android/feature/avatar/scripts/test.sh`.
앱: Android SDK35/build-tools35와 JDK21을 설정하고 `cd android` 후 `./gradlew :app:assembleDebug :app:lintDebug`.
TTS 모듈이 동일 checkout에 있으면 자동 포함한다. 별도 worktree이면 `-PnuntiTtsCheckout=/path/to/tts-checkout/android`.
빌드 중 dependency download 외 서비스 API 호출이나 음성 재생은 하지 않는다.
