# 눈티 스킨 V2 구현과 검증

작업 브랜치: `codex/nunti-skin-v2`. 원래 작업 트리와 승인 원화를 보존했으며 main 병합은 없다. [디자인 계약과 원인 분석](SKIN_SYSTEM_V2.md) · [참고 자료 적용표](REFERENCE_TO_IMPLEMENTATION_MAP.md) · [편집 가능한 Figma 스킨 보드](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=42-5)

V1 매퍼는 공통 몸통·머리·새싹·스카프·가방·배지를 고정하고 표정, 포켓, 길 무늬만 선택했다. V1 Canvas도 그 위의 장식만 애니메이션했다. 이번 스킨은 얼굴 외곽·눈 위치·체형·새싹의 정체성을 유지하면서 의상, 머리·귀 주변, 눈매, 액세서리를 각자 교체한다.

| 로컬 스킨 | 외형 |
|---|---|
| Sea / Calm | 줄무늬 세일러 재킷, 모래색 신발, 물결 모자와 조개 귀, 타원 눈, 조개 파우치 |
| City / Curious | 반사 트림 봄버와 하이톱, 옆으로 넘긴 머리, 헤드폰, 눈매·눈썹, 테크 사첼 |
| Mountain / Excited | 바람막이·등산 바지·부츠, 니트 모자와 귀 덮개, 선 눈매, 등산 배낭 |

[컬러 비교](../../prototypes/avatar_generator/skin-v2/comparison-color.png) · [라벨 없는 흑백·64px 비교](../../prototypes/avatar_generator/skin-v2/comparison-grayscale.png) · [20개 PNG와 편집 소스 명세](../../prototypes/avatar_generator/skin-v2/manifest.json). 기본형 최종 PNG는 기존 승인본과 바이트 단위로 같다. 세 스킨은 `ART_DIRECTION_NOT_FINAL`이다. 신규 의상과 머리 장식은 로컬 SVG로 제작했고 공통 얼굴·손은 승인 래스터 일부를 재사용했다.

출발 전 기존 만들기 버튼에서 `DEFAULT_IDLE → ROUTE_ENERGY → OUTFIT_SWAP → HEAD_AND_EYES_TRANSFORM → SKIN_REVEAL → FINAL_IDLE`로 4초간 실행한다. 옷과 신발, 머리와 눈, 소품은 각자의 마스크로 바뀐다. 최종 화면과 다시 연 화면은 같은 번들 PNG를 사용한다. 새 기록은 기존 서버 기록과 분리해 기기에 저장한다. 새 스킨도 기존 Journey 서비스에 번들 그림을 전달한다.

## 변경 파일

| 경로 | 변경 |
|---|---|
| `prototypes/avatar_generator/nunti-skins.js` | SkinSpec, 모의 경로, 결정적 ID와 로컬 저장, 요청 가드 |
| `prototypes/avatar_generator/nunti-skin-motion.js` | Canvas 레이어 교체, 상태, Skip·축소·중단·fallback |
| `prototypes/avatar_generator/{index.html,studio.js,studio.css,navigation.js}` | 기존 폼·보관함과 모션 연결, 데모 선택, 캡션 공간 |
| `prototypes/avatar_generator/skin-v2/` | 새 로컬 SVG·투명 PNG·원본 비교와 제작 근거 |
| `android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt` | 생성 요청의 기기 차단, 차량 중단 사유, 오프라인 음성 선택, 기존 여정 연결 |
| `android/app/src/main/kotlin/ai/nunti/app/journey/JourneyRuntime.kt` | 허용한 스킨 ID의 번들 최종 PNG를 기존 여정 입력으로 준비 |
| `scripts/build_nunti_skin_v2_assets.py`, `scripts/test_nunti_skin_v2.mjs`, `scripts/verify_nunti_skin_v2_runtime.mjs` | 로컬 제작, 단위·실기 검증 |
| `scripts/test_avatar_{generation,collection,layers,voice}_ui_state.mjs` | 기존 UI 회귀의 테스트 환경을 새 Studio 변수와 일치 |
| `AGENTS.md`, `docs/NUNTI_DESIGN_CONTRACT.md`, `docs/redesign/SKIN_SYSTEM_V2.md`, `docs/redesign/REFERENCE_TO_IMPLEMENTATION_MAP.md` | V2 우선 범위, 참고 자료, 롤백 |

기존 서버 코드와 API schema는 이번 작업에서 수정하지 않았다. `.agents`의 기존 스킬 파일은 쓰기 보호 상태라 AGENTS와 V2 계약에서 충돌하는 규칙의 범위를 정했다. [시작 시 앱 소스](../../artifacts/skin-v2/pre-v2-source.tar.gz) · [시작 시 테스트·내비 소스](../../artifacts/skin-v2/pre-v2-test-sources.tar.gz)

## 빌드와 회귀

- Android `android/gradlew -p android :app:testDebugUnitTest :app:assembleDebug --offline --no-daemon` 성공. [빌드 로그](../../artifacts/skin-v2/build-final.log) · [APK SHA 및 번들 28개 바이트 일치](../../artifacts/skin-v2/apk-provenance.json)
- 앱 JVM 10개, 점수·여정·gate JVM 18개 통과. [점수 회귀 로그](../../artifacts/skin-v2/regression-score-final/score.log)
- 기존 JS 회귀 7개 suite 통과. [JS 회귀 보고서](../../artifacts/skin-v2/regression-js-final/report.json)
- `node --test scripts/test_nunti_skin_v2.mjs` 6/6. 결정성, 저장과 fallback, 가드, 20개 실제 PNG 조회, 6개 상태와 중단을 확인했다. Canvas 픽셀은 실기 검사에서 확인한다. [단위 테스트 로그](../../artifacts/skin-v2/skin-unit-final.log)
- 백엔드 395개와 subtest 104개 통과. 실기 생성과 별개의 mock 경계 회귀다. [백엔드 로그](../../artifacts/skin-v2/regression-backend/backend.log)
- 최초 JS 회귀는 VM harness에서 새 변수를 주입하지 않아 실패했다. 실제 코드를 읽는 harness를 맞추고 다시 실행했다. 최초 점수 회귀의 로컬 소켓 권한 오류는 동일 명령의 승인된 로컬 실행에서 해결했다.

## 실제 Pleos 화면과 오프라인 증거

Pleos Emulator `Nunti_Restore_2_1`에서 실제 앱 창 1682×1210, 전체 디스플레이 2560×1440으로 확인했다. [앱 이전/이후 비교](../../artifacts/nunti-skin-v2/previous-vs-skin-v2.png)는 각 캡처의 같은 앱 영역을 50%로 줄였다. [기본 단계](../../artifacts/nunti-skin-v2/runtime-caption-final/02-sea-default-idle.png) · [의상 교체 중](../../artifacts/nunti-skin-v2/runtime-caption-final/03-sea-outfit-swap.png) · [최종](../../artifacts/nunti-skin-v2/runtime-caption-final/04-sea-final.png).

[실제 만들기 버튼에서 시작한 MP4](../../artifacts/nunti-skin-transform-demo.mp4)는 8.02초이며 앞뒤 정지 화면과 4초의 변신을 담았다. 실제 녹화를 AVFoundation으로 디코딩해 [0–5초 프레임](../../artifacts/nunti-skin-v2/runtime-caption-final/video-frames/contact-sheet.png)을 확인했다. 기본 눈티, 리본, 옷, 머리·눈, 소품, 최종 모습이 순서대로 보인다. 첫 검증에서 보인 신발과 캡션의 겹침을 수정하고 이 APK에서 다시 캡처했다.

앱 시작 전에 호스트 Studio로 가는 ADB reverse를 제거했다. CDP는 비로컬 요청과 생성에 해당하는 POST를 차단하도록 설정했다. 허용한 단일 검증 요청은 실제 호스트로 전달될 수 없는 상태에서 앱의 네이티브 가드가 `403 MOCK_SKIN_MODE`로 막는지 확인하기 위한 빈 요청이다. 모델 사용 가능으로 응답하는 가짜 capabilities에서도 모의 스킨 모드만 선택 가능했다. **외부 생성 API 호출 0회**이며 실제 키는 필요하지 않았다.

실기에서 여섯 단계 순서, 동일 입력·빠른 재탭, 기본→바다·도시·산, 실입력 폼·경로 파일, 각 번들 그림과 최종 Canvas 픽셀 일치, 오프라인 저장·다시 열기, Skip·재생, 사용자·OS 모션 축소, 백그라운드에서 중단과 복귀, Virtual Console D/30에서 중단 후 P 정적 복귀를 확인했다. 디코더 오류를 통제해서 최종 자산을 읽지 못하게 했을 때 실제 앱이 승인 기본형을 표시하고 그 결과를 저장했다. 첫 실기 검증에서 CDP 네트워크 차단으로 번들 이미지를 누락시키려던 시도는 WebView의 로컬 자산 처리 때문에 동작하지 않았다. 최종 검증은 이미지 디코더 오류를 명시적으로 주입했다. 주행 중에는 Pleos가 앱을 가리며 숨겨진 동반자 UI를 검증한 것으로 보지 않는다.

최종 APK에서 중복을 제외한 **실기 검사 30개**가 통과했다. [합산 검증 결과](../../artifacts/nunti-skin-v2/runtime-verification.json). [최종 실기 기록](../../artifacts/nunti-skin-v2/runtime-caption-final/report.json)에서 27개가 통과한 뒤 UI Automator가 화면에 보이는 여정 종료 버튼을 XML에 포함하지 않아 자동 조작이 중단됐다. [동일 APK 후속 검사](../../artifacts/nunti-skin-v2/runtime-journey-continuation/report.json)는 실제 화면의 버튼 위치로 조작했고 8개가 통과했다(5개 중복). 오프라인으로 시작한 DEMO 여정은 같은 번들 PNG를 바이트 단위로 사용했고 정적 모드로 종료됐다. 두 실행 모두 원래 여정 기록의 바이트, 차량·공조, WebView 시험 저장소, 시스템 모션 설정, ADB reverse를 복원했다.

## 제한

외형은 기능 프로토타입이며 승인된 최종 아트는 기본형뿐이다. 세 목적지별 외형은 고정 제작했고, 길 유형·명시 기분은 리본과 전환 방향에 반영한다. 실기 한 차례 측정한 `gfxinfo` 지연 프레임은 68.70%, p95는 38ms이며 PSS는 약 149.8MiB였다. 기능 재생을 확인했지만 부드러움 검증 통과로 해석하지 않는다. 실차 성능, TalkBack 실제 음성 탐색, 글자 크기 확대, V2의 야간·좁은 창은 미검증이다.
