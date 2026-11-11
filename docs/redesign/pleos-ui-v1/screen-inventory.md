# 눈티 Pleos 화면 목록과 현재 구현

조사 기준: 2026-11-10 현재 작업 트리. 이 문서에서 `production 경로`는 `android/app/src/main`의 런처가 연결하는 경로를 뜻한다. 출시 승인이나 공식 Pleos 적합성 인증을 뜻하지 않는다. 이번 문서 작업은 소스 조사이며 앱, 차량 상태, Figma를 변경하지 않았다.

적용 기준은 [AGENTS.md](/Users/pig30nidae/NUNTI/AGENTS.md), [디자인 계약](/Users/pig30nidae/NUNTI/docs/NUNTI_DESIGN_CONTRACT.md), [nunti-pleos-ui](/Users/pig30nidae/NUNTI/.agents/skills/nunti-pleos-ui/SKILL.md)다. 공식 Pleos 가이드와 디자인 키트의 최신 확인, 새 Figma 화면과 실제 화면 비교는 상위 디자인 작업에서 별도로 수행한다. 이 소스 목록만으로 그 검증이 완료됐다고 판단하지 않는다.

## 1. 실제 진입 구조

[MainActivity.onCreate](/Users/pig30nidae/NUNTI/android/app/src/main/kotlin/ai/nunti/app/MainActivity.kt:22)는 시작 화면을 직접 그리지 않는다. `JourneyRuntime.isRunning`이 참이면 `JourneyActivity`, 아니면 `AvatarStudioActivity`를 열고 종료한다.

| 디자인 상태 | 현재 화면과 구현 | 구현 범위 |
|---|---|---|
| `PRE_TRIP` 출발 전 | `AvatarStudioActivity` 안의 WebView, `input-view` | production 경로. 실제 차량 gate, 로컬 생성 서버, 내비 bridge와 연결됨 |
| `REVEAL_PARKED` 주차 중 결과 | 같은 WebView의 `result-view` | production 경로. 생성 결과·목소리·출발 동작이 있음. 승인 A `LOCAL_LAYERS` 결과는 정적 표시 |
| `REVEAL_PARKED` 4초 변신 | `TransformationPreviewActivity`와 전용 Canvas | debug APK 전용. 두 모션 시안과 9개 로컬 샘플을 비교하는 별도 진입점. Studio의 생성 완료나 출발 버튼에는 아직 연결되지 않음 |
| `DRIVING_RESTRICTED` 주행 중 | `JourneyActivity` + `JourneyCompanionView` | production 경로. `JourneyService`의 차량 신호·점수·음성 상태를 표시 |
| `POST_TRIP` 도착 후 | 같은 `JourneyActivity`의 종료·중단 상태 | production 경로. 정차 시 항목별 점수와 이벤트 상세를 보여줌. 도착 감지로 자동 전환하는 기능은 없음 |
| 보관함 | Studio `collection-view`, 화면 이름 `내 눈티` | production 경로의 캐릭터 목록. 여러 주행 기록을 고르는 목록은 아님 |

현재 앱은 WebView와 네이티브 View를 함께 사용한다. 네 상태가 모두 하나의 Compose 화면이나 navigation graph에 구현되어 있다고 가정하면 안 된다. 기존 `LegacyMockActivity`, `JourneyMvpActivity`, `RouteBirthActivity`, `GeneratedCompanionActivity`는 현재 런처의 네 상태를 설명하는 기준 화면이 아니다.

## 2. PRE_TRIP: 출발 전 입력

화면 소스는 [index.html](/Users/pig30nidae/NUNTI/prototypes/avatar_generator/index.html:19), [studio.js](/Users/pig30nidae/NUNTI/prototypes/avatar_generator/studio.js:53), [navigation.js](/Users/pig30nidae/NUNTI/prototypes/avatar_generator/navigation.js:1)다. Kotlin 호스트가 차량 상태와 파일 선택, 내비·음성·여정 bridge를 담당한다.

| 보이는 항목 또는 동작 | 실제 역할과 보존할 조건 |
|---|---|
| `내 눈티`와 개수 | `GET /v3/avatars`로 서버의 보관 캐릭터 목록을 엶 |
| `내비 목적지 불러오기` | 실제 NaviHelper의 현재 위치·목적지·경로 상태 응답을 기다림. 도로 전체 polyline을 가져오는 동작은 아님 |
| `현대 내비 열기` | native `navigationCommand('foreground')` |
| `이 목적지를 현대 내비에 설정` | 입력 위경도와 이름을 `requestRoute` 명령으로 전송. 요청 수락과 내비 경로 계산 완료를 구분함 |
| `현대 경로 전체 보기` | native `overview` 명령. 앱 자체 지도 렌더러로 전환하는 기능은 아님 |
| 좌표 입력과 시험 경로 선택 | 출발·목적지 위경도, 판교/서울/바다 시험 입력. 시험 입력과 실제 내비 입력을 구분해야 함 |
| `경로 API로 길 불러오기` | `POST /v3/route-plans`. OSRM이 계산한 길이며 현대 내비의 선택 경로와 일치 미검증 |
| `저장 경로 다시 보기` | 마지막 `planId`로 `GET /v3/route-plans/{planId}`. 주행 기록 조회 기능은 아님 |
| `경로 사진 불러오기`, `좌표 파일` | 사진 선 추출 또는 정규화 좌표 파일 입력. 경로 API 기능이 활성화되면 기존 도구 영역을 숨김 |
| 경로선과 확인 체크 | `표시된 선이 이번에 갈 경로가 맞아요`. 기존 경로가 있을 때 명시 확인이 필요함. 내비 설정이나 좌표가 바뀌면 확인을 해제함 |
| `목적지` | 필수 이름, 최대 60 UTF-16 단위. `destination.name` |
| `그곳의 느낌` | 선택 텍스트, 최대 240. `destination.traits` |
| `이번에 가는 이유` | 선택 텍스트, 최대 120. `purpose`. 기존 생성·목소리 계획에서 사용됨 |
| 이미지 생성 방식 | `LOCAL_RENDER`, `LOCAL_LAYERS`, `LOCAL_MODEL`, `IMAGE_API`. 서버 capability에 따라 옵션 노출. 계약 기본값은 `LOCAL_RENDER`; UI는 local model이 가용하면 그 모드를 선택함 |
| 목적지 유형·도로 유형·직접 고르는 기분 | `LOCAL_LAYERS`를 선택했을 때만 표시. 목적지 이름/방문 이유와 별도 입력임 |
| `이 길에서 눈티 만나기` | `POST /v3/avatars`. 생성 성공과 동시에 서버에 저장됨 |
| 입력 예시 카드 | 경로와 목적지 입력을 채움. 완성 캐릭터 선택 카드가 아님 |

생성 버튼은 busy/planning, 차량 gate 불허, 필수 목적지 누락, 경로 확인 누락에 따라 비활성화된다. `LOCAL_LAYERS`만 경로 없이 기본 눈티를 만들 수 있다. 기존 세 모드에서는 경로가 필수다. A 모드에서도 목적지 이름은 현재 요청 계약상 필수다.

승인 A의 목적지 유형은 `unknown/city/coast/mountain`, 도로 유형은 `unknown/urban/highway/rural/mixed`, 직접 고르는 기분은 `unset/calm/curious/adventurous`다. 이 선택값은 SDK가 알아낸 풍경이나 운전자의 감정으로 표시하면 안 된다. UI가 출처를 `user-selected` 또는 누락 시 `fallback`으로 보낸다. 경로 ID는 앱이 기존 API plan ID 또는 좌표의 SHA256으로 만든다.

`목적지 이름`, `그곳의 느낌`, `이번에 가는 이유`를 승인 A의 외형 변경 근거로 설명하지 않는다. A 외형은 별도 `variantContext`의 유형·기분과 경로를 사용한다. 기존 카피 중 "방문 이유에 따라 옷, 소품, 행동이 달라진다"는 설명은 기존 생성 모드에 맞춘 문구이므로 새 디자인에서는 모드별로 구분해야 한다.

## 3. REVEAL_PARKED: 결과와 출발

[showArtifact/birthAnimation](/Users/pig30nidae/NUNTI/prototypes/avatar_generator/studio.js:143)이 결과 화면을 그린다. `LOCAL_LAYERS` 또는 `design.staticOnly=true`이면 최종 PNG를 정적으로 표시하고 진행 바와 `탄생 다시 보기`를 숨긴다. 새 4초 Android 변신은 이 함수에서 호출되지 않는다.

| 영역 | 현재 표시·동작 |
|---|---|
| 캐릭터 stage | 저장된 `visual.path` 이미지. 모드에 따라 기존 formation 또는 정적 표시 |
| 캐릭터 정보 | `displayName`, `design.personality`, 목적지 이름, 방문 이유 |
| 만들어진 이야기 | 기존 character plan 또는 motifs 상세. A 모드는 목적지 장식, 경로 무늬, 명시적으로 선택한 표정 설명 |
| 생성 출처 | A 모드는 `기본 눈티 A · 로컬 모습 조합 · 외부 API 없음` |
| 목소리 듣기 | 음원이 없으면 사용자가 누를 때 목소리 생성 요청. 이미 있으면 보관 음원 재생. 이미지 저장을 막지 않음 |
| 주행 음성 준비 | 인사와 `NEUTRAL/WORRY/RELIEF/JOY` 피드백 음원을 주차 중 명시 요청으로 준비 |
| 함께할 여정 | 현재 `LIVE` 실시간과 `DEMO` 회복 시나리오 선택이 존재함. 시연 데이터가 실제 운전 기록처럼 보이지 않아야 함 |
| `눈티와 함께하기` | native `startJourney(characterId, source)` 후 그림·기존 음원을 기기에 캐시하고 네이티브 여정 화면을 엶 |
| `진행 중인 여정 · 마지막 리포트` | native `openJourney()`. 현재 또는 마지막 기기 내 snapshot을 엶 |
| `새 여정 만들기` | 입력 화면으로 돌아감. 현재 입력값·기존 캐릭터를 지우지 않으며 HTTP 생성이나 trip 생성 요청도 하지 않음 |
| 저장 상태 | `내 눈티에 저장됐어요. 다시 열어도 같은 모습이에요.` 별도 저장 버튼 없음 |
| 원래 경로 | 생성에 사용한 정규화 좌표를 receipt canvas로 표시. 경로 없는 A는 선을 숨기고 기본 외형 이유를 안내 |

생성 중에는 결과 정보와 replay를 숨긴다. A 모드는 움직이는 loading 연출을 실행하지 않는다. 생성 실패 시 입력 화면으로 돌아가고 재시도 안내를 표시한다. 동일 입력의 실패·재시도는 `state.pending`의 request ID를 유지한다. 정상 생성 이후 새 요청을 만들면 다른 캐릭터 기록이 생기지만, A 모드의 동일한 시각 입력은 같은 외형을 재현한다.

### debug 변신 화면과 연결할 때의 범위

[TransformationPreviewActivity](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/transformation/TransformationPreviewActivity.kt)는 승인 A를 고정하고 `빛의 길/고요한 색`, 9개 샘플, 4초 timeline, skip, reduced motion, 주야간을 제공한다. 실제 차량 gate를 사용하고 제한 시 중단한다. 프로토타입은 APK 자산을 읽으며 Studio의 저장된 character ID를 받는 production adapter는 아직 없다.

Figma의 변신 화면에는 이 모션을 재사용하는 설계를 넣을 수 있다. 다만 저장된 `AvatarSpec`·최종 PNG를 native 모션에 연결하고 완료·skip 이후 기존 결과/출발 동작으로 복귀하는 작업은 구현 예정으로 남겨야 한다.

## 4. DRIVING_RESTRICTED: 주행 동반자

[JourneyActivity.buildView/refresh](/Users/pig30nidae/NUNTI/android/app/src/main/kotlin/ai/nunti/app/journey/JourneyActivity.kt:72)는 가로 `LinearLayout`과 `JourneyCompanionView` Canvas를 사용한다. 전경에서 500ms마다 runtime snapshot을 읽는다. 현재 live 값 갱신은 [JourneyService](/Users/pig30nidae/NUNTI/android/app/src/main/kotlin/ai/nunti/app/journey/JourneyService.kt:44)의 1초 간격이며, DEMO는 별도 시험 속도로 진행된다.

| 화면 요소 | 데이터와 현재 표시 |
|---|---|
| 데이터 출처 | `실시간 차량 신호 · 여정 동반자` 또는 `시연 데이터 · 여정 동반자` |
| 눈티 | 선택한 캐릭터의 기기 캐시 PNG. 새 얼굴을 생성하거나 사용자 기분을 다시 추론하지 않음 |
| 이름·목적지 | `displayName`, `destination`, `purpose` |
| 진행 시간 | `함께한 시간 N분 N초`, `elapsedMs` |
| 점수 | `현재까지 주행 점수`, `total`; null이면 `평가 대기` |
| 평가 범위 | `coverage` 백분율과 `미수신 항목 제외`; 신호 부족은 별도 문구 |
| 한 줄 피드백 | snapshot `line`, 예: `함께 살펴보고 있어요.` |
| 음성 상태 | `voiceStatus`, `muted` |
| `음성 끄기/켜기` | 활성 여정에서 표시. 서비스 `ACTION_MUTE` |
| `내비 열기` | `ai.pleos.playground.intent.action.NAVI_START`로 외부 내비 실행. 여정 서비스는 계속 동작 |
| `여정 마치기` | 활성 여정이며 실제 정차 gate와 `canFinish`가 참일 때만 표시 |
| `눈티로 돌아가기` | 정차 시 표시, Activity 종료. 여정 자체를 종료하지 않음 |
| 상세 점수·이벤트 스크롤 | 주행 중 숨김 |

주행 피드백 `emotion`은 `NEUTRAL/WORRY/RELIEF/JOY`이며 점수 엔진이 결정한다. 출발 전 사용자가 선택한 `calm/curious/adventurous`와 다른 데이터다. `LOCAL_LAYERS` 아바타는 `staticOnly=true`가 기기 metadata에 이어져 pose animation을 실행하지 않는다. 점수·피드백 문구·색·배지의 상태 갱신은 현재 코드에 남아 있다.

현재 manifest는 `JourneyActivity`에 `distractionOptimized=true`를 선언한다. 이 선언 자체가 공식 승인 증거는 아니다. 실제 주행 화면의 허용 정보량·버튼·상태 갱신은 공식 가이드와 emulator에서 다시 검토해야 한다. Studio는 제한 시 전체 WebView를 숨기는 반면 Journey는 본문을 유지하고 일부 조작을 숨긴다. 두 화면을 같은 차단 로직으로 설명하면 안 된다.

## 5. POST_TRIP: 종료와 마지막 기록

실제 종료 trigger는 정차 상태의 `여정 마치기`다. NaviHelper의 도착 또는 `onRouteEnded` callback에서 이 화면으로 자동 이동하는 연결은 없다. `JourneyService.finishJourney()`가 `JourneySession.finish()`를 호출하고 report를 저장한다.

| 상태 | 현재 화면 |
|---|---|
| `FINISHED`, 정차 | `여정 완료 · N분 N초`, `이번 여정의 점수`, 평가 범위, 마지막 피드백. `여정 돌아보기`에 항목 점수·basis, `기억할 순간`에 최대 30개 이벤트 |
| `INTERRUPTED`, 정차 | `중단된 여정`, 마지막 저장 데이터. `중단 전까지 받은 신호만 남겼어요. 중단 구간은 평가하지 않았어요.` |
| usable signal 없음 | `평가 대기` 또는 `평가 불가`, 신호 부족 안내. 임의의 0점이나 좋은 운전 점수를 만들지 않음 |
| snapshot 없음 | `아바타를 먼저 선택해 주세요`, `보관한 눈티를 열어 여정을 시작할 수 있어요.` |
| 종료 기록을 제한 상태에서 열음 | 상세 스크롤과 돌아가기 버튼을 숨김. 본문은 남음 |

마지막 report는 `filesDir/journeys/latest.json`, 개별 report는 `{sessionId}-report.json`에 저장된다. 생성 캐릭터 목록과 별도다. 현재 화면은 current 또는 latest 한 건을 읽으며 날짜별 주행 기록 목록, 여러 기록 선택, 공유, 삭제, 저장 버튼은 없다. Figma에 이런 기능을 넣으면 기존 기능 보존 범위를 넘는 신규 동작으로 표시해야 한다.

## 6. 공통 제한·실패·테마

| 조건 | 현재 구현 |
|---|---|
| Studio 제한 또는 차량 상태 미수신 | foreground + 실제 P + 속도 절댓값 0.01m/s 미만 + known UX + `requiresDO=false` + restrictions 0일 때만 허용. 불허 시 전체 WebView 차단, 음성·frame loop 중지 |
| Studio 복귀 | 저장 결과를 `animate=false`로 다시 표시. 장식 모션을 자동 재시작하지 않음 |
| 로컬 서버 연결 실패 | Kotlin shield에 재연결 안내. 앱 standalone 오프라인 생성으로 대체하지 않음 |
| 진행 중 여정의 인터넷 단절 | 준비한 그림·음원과 점수 처리는 기기 로컬 사용. 새로운 여정 준비는 여전히 서버의 artifact 조회가 필요함 |
| Journey 이미지 loading/실패 | 현재 Canvas는 `눈티 그림을 불러오는 중` 또는 `그림을 불러오지 못했어요` 텍스트. 승인 A base PNG fallback은 production Journey에 아직 연결되지 않음 |
| 앱 종료·프로세스 중단 | 서비스는 `START_NOT_STICKY`; 남은 ACTIVE 기록을 복원할 때 `INTERRUPTED`로 표시하고 음성을 자동 재생하지 않음 |
| 주야간 | production WebView는 light color scheme, Journey는 고정 밝은 색. debug 모션만 주야간 토글 구현. 새 Figma의 night mode는 production 적용 예정 |
| 크기 변경 | WebView responsive CSS와 native Journey의 가로 weight layout이 존재. 새 디자인의 작은 창·큰 글씨 적합성은 별도 검증 필요 |

기존 검증 자료는 2560×1440, 160dpi Pleos emulator 전체 화면을 기록했다. 실제 앱은 차량 정보·상태바·내비게이션·공조 영역을 제외한 창에 표시된다. 전체 2560×1440을 앱 소유 캔버스로 사용하지 않는다. 이번 Figma 작업의 실제 창 bounds와 현재 모드는 [baseline](/Users/pig30nidae/NUNTI/docs/redesign/pleos-ui-v1/baseline)에서 새로 측정한 자료를 기준으로 한다.

## 7. 디자인에서 분리해서 표시할 항목

- 현재 기능: 자동 저장, 캐릭터 보관함, 정차 중 수동 종료, 마지막 기기 리포트, 내비 열기, 음성 mute, 데이터 부족 안내.
- 통합 예정: 저장된 A 결과를 4초 native 변신으로 연결, production night theme, Journey 이미지 실패의 승인 base fallback.
- 추가 기획 없이는 만들지 않을 동작: 자동 도착 종료, 주행 기록 목록/공유/삭제, 캐릭터 이름 편집, 차량 신호로 사용자의 선택 기분 변경, 현대 내비와 일치한다고 보장하는 경로선.
- 검증 필요: 주행 화면의 공식 허용 범위와 실제 제한 전환, 새 디자인의 글자·대비·터치 영역·작은 창·접근성, Figma와 emulator의 화면 비교.

세부 함수·데이터·API 연결은 [kotlin-mapping.md](/Users/pig30nidae/NUNTI/docs/redesign/pleos-ui-v1/kotlin-mapping.md)에 정리했다.
