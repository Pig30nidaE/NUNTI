# 눈티 Skin System V2

이 문서는 기본 눈티를 출발점으로 하는 게임 스킨과 앱 내 변신에 적용한다. 기존 [디자인 계약](../NUNTI_DESIGN_CONTRACT.md)의 장식 중심 규칙보다 이 문서의 스킨 범위를 우선한다. 기존 캐릭터와 저장 기록, 서버 데이터 계약, 주행 안전 조건에는 기존 계약을 적용한다. 이번 단계는 `MOCK_SKIN_MODE=true`로 고정하고, 실제 생성 API 연결과 호출은 에뮬레이터 증거를 검토한 뒤 사용자 승인을 별도로 받는다.

## 기존 외형과 재생 범위

V1 외형이 비슷한 이유는 레이어 선택의 범위다. `build_avatar_spec`은 모든 유효 조합에 같은 몸체, 머리, 새싹, 스카프, 가방, 배지 6개를 먼저 넣는다. 그 위에 표정, 목적지 모티프와 길 무늬만 고른다. 경로 해시로 바뀌는 값은 길 무늬의 세 가지 인덱스다. 목적지와 기분이 바뀌어도 재킷이나 모자의 실루엣을 선택할 필드나 레이어가 없다. [V1 매핑](../../backend/nunti/avatar_studio/variant_spec.py#L234-L280)

`render_layered_avatar`는 매퍼가 선택한 순서대로 PNG를 검증하고 합성한다. 활성 레이어가 손상되거나 누락된 경우에는 별도 원본 사본으로 복귀한다. 유효한 입력에서 외형 차이가 작은 현상은 정상적인 V1 레이어 선택만으로 재현된다. 캐시나 오류 복귀가 원인이라는 증거는 발견하지 않았다. [V1 합성](../../backend/nunti/avatar_studio/layered_render.py#L69-L110)

이전 통합에는 4초 V1 Canvas 모션이 있었다. 검증된 `LOCAL_LAYERS` 결과의 동일한 몸체 위에서 스카프, 포켓, 길 무늬와 표정을 바꾸는 방식이다. 다른 모드, 버전/해시가 다른 결과 또는 변경 요소가 없는 기본형은 이 모션의 대상이 아니다. 화면 재진입은 정적 결과를 보여주고, 재생 중 차량 제한과 모션 축소가 우선한다. 기존 기록에서 장식 변신은 확인했으며, 복장과 머리가 교체되는 게임 스킨 변신은 V2의 작업 범위다. [V1 모션](../../prototypes/avatar_generator/nunti-transformation.js#L19-L42) · [이전 앱 캡처](integration-v1/comparison/character-runtime-matrix.png)

## 유지할 특징과 바꿀 외형

승인된 [A 정면 원화](identity-refine-v1/nunti-a-front-transparent-v1.png)와 [번들 기본 PNG](../../prototypes/avatar_generator/nunti-motion/base.png)를 기준으로 얼굴 외곽, 눈 중심과 상대 간격, 통통한 체형의 비율, 작은 새싹 모티프를 유지한다. 중심축과 발의 기준 위치는 모든 스킨에 동일하게 맞춘다. 눈매와 눈썹, 헤어, 잎 방향, 귀 주변 윤곽은 달라질 수 있다. 새싹의 작은 크기와 위치 관계만 알아볼 수 있게 남긴다.

스킨마다 아우터와 하의, 신발, 머리 액세서리, 휴대품의 형태를 교체한다. 주제별 무늬는 새 옷에 배치한다. 색을 제거하고 이름을 숨긴 비교판에서도 옷과 머리 윤곽으로 네 모습을 구분할 수 있어야 한다. 64px에서는 주인공의 얼굴 비율과 새싹이 남는지 확인한다.

| 스킨 | 필수 의상·신발 | 머리·눈·소품 |
|---|---|---|
| Coastal Explorer · SEA/CALM | 바다색 줄무늬 세일러 재킷과 모래색 스니커즈 | 새싹이 드러나는 해변 모자, 둥근 귀 윤곽과 편안한 타원 눈, 조개 소품 또는 여행 파우치, 물결·거품 디테일 |
| Night City Adventurer · CITY/CURIOUS | 짙은 남색·보라색 오버사이즈 보머, 반사 트림과 하이톱 | 옆으로 넘긴 헤어/잎과 헤드폰, 눈매·눈썹 변화, 테크 사첼과 절제된 도시 빛 디테일 |
| Mountain Trekker · MOUNTAIN/EXCITED | 등산용 바람막이, 등산 하의와 트레일 부츠 | 새싹이 드러나는 니트 헤드기어와 솟은 귀/잎, 활기찬 눈매, 등산 배낭과 등고선 디테일 |

## 스킨 데이터와 저장

`SkinSpec`은 `skinId`, `outfit`, `headStyle`, `earStyle`, `eyeStyle`, `accessories`, `palette`, `pattern`, `mood`, `animationPreset`을 갖는 앱 로컬 계약이다. 정규화한 같은 입력을 같은 버전, 스킨과 레이어 순서로 해석한다. 목적지 분류가 옷과 눈매, 의상에 그려진 무늬를 고른다. 길 유형은 리본 형태를, 사용자가 직접 고른 기분은 의상 교체 방향을 바꾼다. 차량 신호에서 기분을 추정하지 않는다. 데모의 Mountain/EXCITED는 기존 UI의 `adventurous`(씩씩하게)에 해당한다. 알 수 없는 목적지는 기본형으로, 알 수 없는 길 유형과 기분은 기본 연출값으로 처리한다. `default/sea/city/mountain` 데모 선택기는 정해진 모의 입력을 폼에 채운 뒤 기존 생성 버튼을 사용한다. [SkinSpec 매퍼와 fixture](../../prototypes/avatar_generator/nunti-skins.js)

원본 원화와 새 의상 자산은 별도로 둔다. 원본 PNG의 승인 범위와 새 레이어의 검수 상태를 구분한다. 각 스킨 폴더의 `outfit.png`, `head.png`, `eyes.png`, `accessory.png`는 공통 768×768 좌표계에서 합성하는 투명 레이어다. `final.png`는 같은 좌표계의 정적 결과다. 원본 PNG에서 추출한 영역은 이미 렌더링된 부분의 분리본이므로 관절이나 숨겨진 표면을 복원한 리깅으로 설명하지 않는다. 신규 로컬 아트는 `ART_DIRECTION_NOT_FINAL`로 표시한다. [스킨 자산](../../prototypes/avatar_generator/skin-v2/)

V2 기록은 기존 서버 보관함과 분리된 WebView 로컬 저장소에 둔다. 다시 열 때는 저장 당시의 버전과 스킨을 사용한다. 표시 중의 모션 프레임이나 데모 입력 변경이 기존 보관 기록을 바꾸지 않는다. 최종 스킨 파일이 없으면 승인 기본 PNG와 해당 상태를 보여준다. 최종 스킨은 있고 중간 레이어가 없으면 정적 스킨으로 끝낸다. [Studio 연결](../../prototypes/avatar_generator/studio.js) · [기기 여정의 번들 그림](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyRuntime.kt)

모의 모드의 생성은 앱 내부에서 처리하며, JS 전송 가드와 Android WebView 전송 경계에서 생성 요청을 차단한다. 모의 경로와 스킨 기록은 서버 요청에 담지 않는다. 기존 저장 결과의 열람이나 기기 음성처럼 범위 밖 기능의 연결은 기존 앱 경계를 따른다. 실제 검증은 새 스킨 생성·저장·재열기 전체에 대해 네트워크 호출을 관찰한다. [Android 모의 모드 경계](../../android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt)

## 변신 상태와 차량 안전

### 자연스러운 동행자 · 공통 리그 v1

2026-11-12 선택한 방향은 **A · 자연스러운 동행자 + 공통 2D 리그**다. 변신이 끝났다는 것은
장식 효과가 종료됐다는 뜻이며, 주차·전경·모션 허용 상태에서는 같은 눈티가 호흡, 깜빡임,
주변 살펴보기, 체중 이동, 기지개를 이어갈 수 있다. 머리 터치는 쓰다듬기 반응, 양손 터치는
해당 손의 인사, 몸 터치는 호기심 반응으로 연결한다. 포인터를 향하는 시선은 **입력 좌표**만
사용하며 카메라나 운전자 시선을 추정하지 않는다. 키보드·접근성 클릭은 손인사다.

[공통 행동](../../android/app/src/main/kotlin/ai/nunti/app/journey/NuntiCompanionMotion.kt),
[관절 메시](../../android/app/src/main/kotlin/ai/nunti/app/journey/NuntiCompanionMesh.kt),
[원본 텍스처 렌더러](../../android/app/src/main/kotlin/ai/nunti/app/journey/NuntiSharedRenderer.kt)는
기본 눈티와 새 `nunti-rig-1` 스킨에서 공유한다. 조용히 머무르는 구간과 행동의 준비·반응·정리를
구분하며, 연속 입력은 제한하고 새 반응은 관절 보간으로 연결한다. 매 프레임 에셋 생성·해독이나
네트워크 요청을 하지 않는다. 눈 깜빡임과 시선용 텍스처는 자산 작업자에서 미리 준비한다.

새 스킨은 서버가 `companionRigVersion`을 광고할 때 `animationRig: "nunti-rig-1"`로 요청한다.
실제 생성 1회 검증에서 포즈가 고정되지 않아 등록이 거절됐다. 따라서 기본값은 비활성화이며,
별도 검수·승인 후 `NUNTI_STUDIO_COMPANION_RIG_ENABLED=true`를 설정해야 새 리그 요청을 허용한다.
기본 설정에서는 리그 버전을 광고하지 않고 직접 리그 요청도 예약·모델 호출 전에 거절한다.
이 제한은 기존 스킨 생성이나 이미 저장한 스킨 열람의 승인 상태를 바꾸지 않는다.
기존 요청은 기존 생성·캐시 계약을 유지한다. 리그 요청은 별도 버전 seed를 사용하고 중립 정면의
얼굴·관절 위치를 유지하도록 생성한다. 같은 요청에서 모델 이미지를 한 번 받은 뒤 로컬에서
머리·몸통·팔·다리·눈·입의 원본 픽셀 영역과 JSON 리그를 묶어 소유자별 불변 자산으로 저장한다.
Android는 원본 해시와 리그 매니페스트 해시를 함께 전달받고, 매니페스트의 버전·원본 바인딩과
눈 텍스처 해시를 검사한 뒤 작업자에서 준비한다. 원본과 리그가 맞지 않거나 자산을 읽지 못하면
정적 원본을 보존하고 움직임 준비 실패를 알린다.
[리그 정의·출처·내보내기·fallback](../../prototypes/avatar_generator/companion-rig/manifest.json),
[등록 검사와 에셋 묶음](../../backend/nunti/avatar_studio/motion_rig.py)을 따른다.

이 방식은 **정면 텍스처 메시의 제한된 관절 변형**이다. 잘라 낸 영역이 가려진 신체를 복원하거나
3D 리깅·측면·후면·앉는 포즈를 제공한다는 의미는 아니다. 손 모양과 가방이 늘어나지 않도록
팔은 등록된 정면의 별도 컷아웃으로 회전한다. 팔이 움직이며 드러나는 어깨·옆구리는 보이는
옷감에서 만든 로컬 2D 측면 패널로 연결한다. 이는 새로 구성한 겹침 영역이며 가려진 신체의
정확한 복원이나 생성 모델의 결과가 아니다. 알파 경계와 관절 영역 검사는 기하 등록
검사이며 해부학적 대응이나 미적 품질의 자동 인증이 아니다. 맞지 않는 결과는
`COMPANION_RIG_ALIGNMENT`로 실패시키며 비용 예약을 유지하고 자동 유료 재시도를 하지 않는다.
기존 자유 포즈 스킨을 공통 리그로 허위 표시하지 않는다. 신규 에셋은 `humanQualityApproved=false`,
`MOCK_SKIN_MODE=true`를 유지하고 실제 생성 품질·Figma 대조·에뮬레이터 확인 후 별도 승인한다.
UI도 모의 모드에서 새 유료 리그 요청을 보내지 않는다. 서버 광고와 UI 승인 조건이 모두 충족돼야
새 리그를 생성하며, 승인 전 기존 생성 요청에는 `animationRig`를 추가하지 않는다.

연결부 회귀는 실제 Android의 `CompanionRigInstrumentation`으로 검사한다. 원본과 정적 프레임의
픽셀 일치, 손인사·기지개·쓰다듬기 중 옷의 불투명 연결, 가방 고정, 제한 상태 클릭 거부,
취소된 터치의 무반응을 확인한다. 앱 JVM 검사는 행동의 관절별 변위·복귀·경계값을 확인한다.
실행: `./gradlew :app:assembleDebug :app:assembleDebugAndroidTest :app:testDebugUnitTest :app:lintDebug` 후
해당 기기의 현재 사용자에 APK 두 개를 설치하고
`adb shell am instrument --user <user> -w ai.nunti.avatar.demo.test/ai.nunti.app.journey.CompanionRigInstrumentation`.
픽셀 검사는 예술적 품질이나 실제 AI 포즈 일치를 대신하지 않는다.

2026-11-12 확인 결과: backend 208개, JS runner 16개(내비 UI 내부 검사 10개 포함), 앱 JVM 5개,
Android 픽셀·터치 계측 검사, Debug/Release 빌드와 Debug Lint가 통과했다. Pleos 에뮬레이터의
2560×1440 분할 화면에서 기본형·로컬 리그 스킨, 모션 축소 시 정지, 다른 Activity로 전환할 때
실제 foreground gate의 해제·복귀를 확인했다. 기존 Figma 스킨 보드의 기본 캐릭터와 대조했으며
신규 모션의 Figma 편집·디자인 승인은 수행하지 않았다. 실제 주행 중으로의 차량 신호 전환은
이 기기에서 재현하지 못했으므로 정차 검증·모의 경계 테스트와 구분한다.

승인받은 유료 이미지 요청은 **1회**이며, 결과는 컵을 든 포즈와 기준을 벗어난 알파 경계 때문에
공통 리그 등록에서 거절됐다. 실패 출력은 원본 미디어로 보존했고 비용 예약 $0.25는 해제하지
않았다. 이는 실제 청구액이 아니다. 재요청은 하지 않았고, 이후 포즈와 상충하는 기획 지시를
분리한 프롬프트 수정은 모의 transport로만 검증했다. 따라서 실제 AI 생성 스킨의 자동 리깅이
완성됐다고 보지 않는다. 고정 관절에 맞는 별도 원화·분리 에셋 검증이 다음 승인 조건이다.

차량 제한, 백그라운드, 모션 축소 또는 입력 폼·대화상자 사용 중에는 이 행동 체계도 정지한다.
주행 중 팔·눈·호흡을 포함한 장식 모션을 재생하지 않는다. 기존 차량 정책을 완화하지 않는다.

현재 앱의 출발 전 생성 버튼에서 시작한다. Canvas의 4초 타임라인을 아래처럼 구분한다. 의상과 머리 트랙은 2.0–2.5초에 겹칠 수 있다. 마지막 프레임과 다시 연 화면에는 같은 스킨의 정적 PNG를 사용한다. [Canvas 합성](../../prototypes/avatar_generator/nunti-skin-motion.js)

| 상태 | 시간 | 화면 동작 |
|---|---|---|
| `DEFAULT_IDLE` | 0.0–0.5초 | 중앙에서 승인 기본 눈티를 유지한다. |
| `ROUTE_ENERGY` | 0.5–1.2초 | 눈티의 주변으로 짧은 경로 리본을 그린다. |
| `OUTFIT_SWAP` | 1.2–2.5초 | 마스크가 진행되며 기존 옷 영역에서 새 의상과 신발이 드러난다. |
| `HEAD_AND_EYES_TRANSFORM` | 2.0–3.3초 | 같은 얼굴 위치에서 모자, 헤어·귀 주변과 눈매가 바뀐다. |
| `SKIN_REVEAL` | 3.3–4.0초 | 소품이 자리 잡고 짧은 테마 빛이 가라앉는다. |
| `FINAL_IDLE` | 4.0초 이후 | 저장에 사용한 같은 합성으로 정지한다. |

차량의 주차·속도·`CarUxRestrictions`와 앱 전경 상태를 재생 조건으로 사용한다. 조건을 잃으면 모션을 취소하고 차량 정책이 허용하는 정적 화면으로 돌아간다. 다시 주차하거나 앱으로 돌아와도 자동 재생하지 않는다. Skip과 사용자·시스템 모션 축소는 가능한 경우 같은 최종 스킨을 정적으로 표시하고, 준비되지 않았다면 기본 눈티를 표시한다. Replay는 허용 조건을 다시 확인한다. 화면 진입을 연달아 누르거나 비동기 자산 응답이 늦어져도 이전 세션이 새 결과를 덮어쓰지 않아야 한다. [참고 자료와 적용 위치](REFERENCE_TO_IMPLEMENTATION_MAP.md)

## 비교와 되돌리기

이전 실제 화면은 [출발 전·변신·도착 비교](integration-v1/comparison/before-after-actual-day.png), 이전 스킨은 [V1 변형 표](integration-v1/comparison/character-runtime-matrix.png)에 있다. 새 기기 캡처에는 사용한 빌드와 화면 크기를 기록한다. 비교판, 실시간 모션 영상, 상태·픽셀 검증을 구분한다.

Figma의 `Skin V2 · Offline Wardrobe` 페이지는 승인 기본형 인스턴스, 새 스킨 3종과 6개 모션 상태를 비교하는 1384×912 프레임이다. 의상·헤드기어·눈·소품은 로컬 SVG를 불러온 편집 가능 벡터 그룹이다. 승인 얼굴과 손은 레이어 정렬을 유지한 리뷰용 래스터이며, 기본형은 기존 승인 컴포넌트를 사용한다. Nunti의 색상·간격·모서리 변수를 연결했다. [편집 가능한 Figma 비교판](https://www.figma.com/design/LHLHBra8ON3OdVW0qhBnbm?node-id=42-5) · [Figma 렌더 캡처](../../artifacts/skin-v2/figma-wardrobe.png)

작업 시작 시 V1 통합 소스와 자산 일부가 커밋되지 않은 상태였다. 소스를 되돌릴 때는 시작 시 사본을 먼저 별도 임시 디렉터리에 풀고 V2 변경 목록과 대조한다. V2 작업 이후 추가 수정이 없는 파일은 해당 사본으로 복원하고, 이후 수정이 있는 파일에서는 V2 변경 구간만 검토해 되돌린다. V2에서 추가한 파일은 변경 목록으로 식별하고 기존 추적되지 않는 자산은 보존한다. `AGENTS.md`와 기존 디자인 계약은 이 작업에서 추가한 V2 안내 문단만 되돌린다. 시작 시 테스트·내비게이션 코드 사본도 함께 확인한다. 복원한 V1 소스로 APK를 다시 빌드하거나 보유 중인 V1 APK를 사용해 `adb install -r <V1_APK>`로 설치하면 앱 데이터를 보존할 수 있다. V2 로컬 보관 자료와 기존 서버 보관함은 각각의 저장 경계에서 관리한다. [작업 시작 시 앱 소스 사본](../../artifacts/skin-v2/pre-v2-source.tar.gz) · [테스트·내비게이션 소스 사본](../../artifacts/skin-v2/pre-v2-test-sources.tar.gz)
