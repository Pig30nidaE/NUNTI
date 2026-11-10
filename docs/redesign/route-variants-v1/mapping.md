# 입력과 외형 매핑

## 버전과 정체성

| 필드 | v1 값 |
| --- | --- |
| `schemaVersion` | `nunti.avatar.layers/1` |
| `mappingVersion` | `nunti-layers-v1` |
| `assetVersion` | `nunti-a-layers-v1` |
| `characterId` | `nunti-a-v1` |
| 기본 `seed` | 문자열 `0` |
| 출력 | 768 × 768 투명 PNG, `motion=none` |

매핑과 타입의 단일 기준은 [variant_spec.py](../../../backend/nunti/avatar_studio/variant_spec.py)다. JSON 스키마는 이 타입에서 [내보낸 파일](AvatarSpec.schema.json)이다. 임의의 파일 경로를 요청에 받지 않는다.

## 목적지와 기분

| 명시 입력 | 변경 요소 | 유지 요소 |
| --- | --- | --- |
| `coast` | 스카프 푸른 포인트 `#5595B0`, 포켓 물결 | 몸·얼굴 외곽·새싹·브랜드 배지 |
| `mountain` | 스카프 이끼색 포인트 `#709260`, 포켓 능선 | 동일 |
| `city` | 스카프 라일락 포인트 `#9780B1`, 포켓 창문 | 동일 |
| `calm` | 감은 눈, 작은 미소 | 얼굴 앵커·볼·앞머리·후드 |
| `curious` | 한쪽 올라간 눈썹, 작은 미소 | 원래 눈 픽셀·얼굴 앵커 |
| `adventurous` | 또렷한 눈썹, 원래 열린 미소 | 원래 눈과 입 픽셀·얼굴 앵커 |

기분은 `userSelectedMood`만 읽는다. 방문 목적 문자열, 속도, 급가속, 점수, 운전 이벤트로 사용자 감정을 추정하지 않는다. 사용자 선택 외의 출처를 선언한 기분은 `unset`으로 낮춘다. 검토용 `mock`은 허용하지만 결과에도 그대로 표시한다.

## 경로

| `roadType` | 스카프에 적용하는 한 가지 무늬 |
| --- | --- |
| `urban` | 작은 각진 선 |
| `highway` | 길게 이어지는 선 |
| `rural` | 완만한 곡선 |
| `mixed` | 각과 곡선을 함께 가진 선 |
| `unknown` | 경로 무늬 없음 |

경로는 기존 `Route.points`의 정규화된 2D 좌표를 사용한다. `routeId`가 없으면 좌표의 정규 JSON 해시에서 안정적인 ID를 만든다. `routeId + 좌표 해시 + mappingVersion + seed`가 도로별 세 가지 무늬 중 하나를 선택한다. 경로의 모든 굴곡을 몸통에 그리지 않는다.

전체 `variantId`는 정규 입력, 경로 좌표 해시, 입력 출처, 캐릭터·에셋 버전으로 만든다. 요청 UUID, 생성 시간, 목적지 이름, 방문 목적은 외형을 바꾸지 않는다. 경로 수정은 `routeFingerprint`에 기록된다. 무늬가 세 가지뿐이므로 서로 다른 경로가 같은 무늬를 고르는 것은 정상이다.

`displayMode=day|night`는 배경 메타데이터를 바꾼다. 캐릭터 PNG는 동일하다. 현재 Studio 전체 UI 테마를 변경하는 필드는 아니다.

## 데이터 출처

| 데이터 | 확인된 출처와 처리 |
| --- | --- |
| 목적지 이름·좌표, 현재 위치, 경로 상태, trip/TBT | 기존 [PleosNavigationAdapter](../../../android/app/src/main/kotlin/ai/nunti/app/navigation/PleosNavigationAdapter.kt)의 NaviHelper 콜백. 이 작업에서 실제 주행 수신을 새로 검증하지는 않았다. |
| 도로 전체 폴리라인 | 어댑터는 public SDK 경로에서 미제공이라고 명시한다. trip의 지점은 경유지·목적지 요약이며 도로 전체 형상으로 간주하지 않는다. |
| 개발용 경로 형상·거리·시간 | 기존 [route_api.py](../../../backend/nunti/avatar_studio/route_api.py)의 별도 OSRM 경로. 현대 내비 선택 경로와의 일치는 미검증이다. 기존 표시를 바꾸지 않았다. |
| `routeId`, `routeRevision` | 앱에서 파생하거나 명시 전달한다. UI는 기존 plan ID 또는 좌표 해시를 사용한다. `direct-sdk` 주장은 검증된 SDK ID로 인정하지 않고 app-derived와 사유로 기록한다. |
| `destinationCategory`, `roadType` | 새 UI의 사용자 선택 또는 앱 분류. SDK 필드라고 주장하면 unknown으로 처리한다. 목적지 이름에서 바다·산·고속도로를 추측하지 않는다. |
| `userSelectedMood` | 사용자 선택. `direct-sdk`·`app-derived`로 선언한 값은 사용하지 않는다. |
| 비교 보드 입력 | 합성 화면 경로와 분류. 모든 관련 필드를 `mock`으로 기록한다. |

`Route.inputOrigin`에서 실제 경로 출처를 정한다. `TEST_ROUTE`는 mock, `ROUTE_FILE`은 user-selected, `NAVIGATION_SCREENSHOT`과 `API_ROUTE`는 app-derived다. 요청자가 별도로 쓴 `routeGeometry` provenance가 이 판정을 덮어쓰지 못한다. 요청 출처 표시는 암호학적으로 증명된 SDK 데이터가 아니다.

## 누락·오류 처리

| 상황 | 외형과 계약 |
| --- | --- |
| 경로 없음 | 목적지·기분이 있어도 완전한 기본 눈티. `MISSING_ROUTE` 기록. 새 모드만 허용. |
| 목적지 분류 누락·unknown·general | 목적지 포인트 없음. 알려진 표정·경로는 유지. |
| `nature` | 아직 전용 에셋이 없으므로 목적지 포인트 없음. `UNSUPPORTED_DESTINATION`. |
| 기분 누락·unset | 원래 기본 표정. 다른 장식은 유지. |
| `bright` | 아직 전용 표정이 없으므로 기본 표정. `UNSUPPORTED_MOOD`. |
| 기분 출처가 사용자 선택이 아님 | unset. `MOOD_NOT_USER_SELECTED`. |
| 도로 종류 누락·unknown | 경로 무늬 없음. |
| 알 수 없는 enum, 잘못된 좌표·버전·식별자 | 기존 API 경계에서 422. 무효 요청을 정상 경로로 꾸미지 않는다. |
| 활성 레이어·manifest 누락 또는 해시·형식 불일치 | 별도 manifest로 보호한 `fallback/base.png` 전체 사용. 부분 얼굴을 출력하지 않는다. `BASE_FALLBACK`. |
| 활성 에셋과 별도 기본형 모두 손상 | `LayerAssetError`로 실패. 새로운 캐릭터를 임의로 만들지 않는다. |
| 인터넷 연결 없음 | 로컬 Python 합성은 가능. 외부 이미지·지도·음성 호출 없이 검증했다. 로컬 서버 연결 자체가 없는 첫 생성은 이 보장에 포함하지 않는다. |

명세에는 정규 입력과 실패 사유, 실제 적용 레이어, 접근성 라벨을 함께 저장한다. 사용한 PNG의 SHA256은 `design.layerAssets`와 샘플의 `render-metadata.json`에 있다. 에셋 변경 시 파일만 바꾸지 말고 `assetVersion`과 해당 매핑 버전을 올려 이전 명세의 의미를 보존해야 한다.
