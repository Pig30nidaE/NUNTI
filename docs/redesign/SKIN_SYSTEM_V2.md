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
