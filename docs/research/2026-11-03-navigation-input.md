# 실제 내비 경로를 아바타 입력으로 받는 방법

2026-11-04 후속: [실제 에뮬레이터·배포 SDK·사진 추출 검토](2026-11-04-navigation-review/README.md)를 우선한다. routePoints는 경유·목적지 요약점임을 SDK 소스로 확인했다. 실제 내비 탐색은 가능했고 현 사진 추출은 보강이 필요하다. 아래는 11월3일 조사 당시의 기록이다.

조사일: 2026-11-03. 공식 문서와 현재 저장소를 읽었다. 계정 등록, 키 발급, 유료 API 호출, 경로 계산 요청, 지도 데이터 다운로드, 앱·서버 코드 수정은 하지 않았다.

## 이번 결정

Nunti의 경로는 출발지에서 목적지까지 내비게이션이 계산한 실제 자동차 경로다. 손그림은 기존 렌더러의 동작 시험용 입력이었다. 제품에서 사용자가 경로를 그리는 것으로 요구를 바꾸지 않는다. 이번 범위는 해당 경로를 받아 아바타를 생성하는 경험이며, 지도 검색·위치 추적·턴바이턴 안내 앱을 새로 만드는 일이 아니다.

현대 제공 NaviHelper를 우선 조사하고 연결한다. 공모전은 Pleos SDK·API를 핵심 기능과 경험에 활용하는지 평가한다. 따라서 외부 내비 API 키를 지금 구매하는 것보다, 현대 내비에서 목적지와 실제 경로를 어느 범위까지 받을 수 있는지 확정하는 일이 먼저다. [공모전 심사 기준](https://appdevchallenge.auto-hmg.io/guide/judging-awards)

전체 polyline의 공개 계약을 확정하기 전에는 **실제 경로가 표시된 스크린샷과 그 경로의 검증된 좌표 JSON을 한 쌍으로 보존해 시험**하는 방법을 권한다. 스크린샷만으로 시험할 때는 화면 속 경로를 추출하고 사람이 원본과 비교한 화면 좌표임을 표시한다. 이 경우 GPS 좌표, 실제 거리, 시간, 도로 종류를 복원했다고 주장하지 않는다. 아래 fixture 절차는 권고안이며 이번 조사에서 구현하지 않았다.

## 현대 NaviHelper에서 확인한 범위

공식 안내는 NaviHelper v3.0.5를 기준으로 한다. Pleos Connect의 내장 Navigation 앱에 요청을 전달하며 결과와 상태 변화는 리스너 콜백으로 받는다. 목적지 설정·조회·취소, 경유지, 경로 옵션·재탐색, 내비 정보와 화면 요청을 제공한다. 실제 이벤트는 Navigation 앱 구현과 상태에 따라 달라질 수 있다. [공식 소개](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/intro)

| 필요한 입력 | 공식 근거 | 판정 |
|---|---|---|
| 목적지 이름·위경도 | `requestRoute(RouteInfo(latitude, longitude, poiName, ...))`, `getDestinationInfo()`와 `onDestinationInfo(DestinationInfo)` | API의 존재와 목적지 설정 좌표 확인. 실제 장치 payload는 미수집 |
| 탐색 완료·재탐색 시점 | `onRoutingCompleted()`, `onReRouteEnded()`, 목적지·옵션 변경 콜백 | 공개 이벤트 확인. Nunti에서 실제 수신은 미검증 |
| 목적지까지의 전체 경로 polyline | API 목차의 `RoutePointInfo`, `RouteStateInfo`, `getRouteStateInfo()`, `requestTrip()` | **미확정.** 타입 이름과 함수 목차는 보이나 읽을 수 있는 공개 본문에는 좌표 배열·인코딩·전체/잔여 구간의 의미가 제시되지 않음 |
| 해안·산악·도로 비율 | 위 공개 소개와 조회 문서 | Nunti가 필요한 수준의 GIS 근거 제공은 미확정 |

목적지·좌표의 근거는 [Destinations](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/destinations), 탐색 이벤트의 근거는 [Event listeners](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/event-listeners)다. `requestRoute()`가 정상 호출되어도 탐색 성공을 뜻하지 않으며, 최종 콜백을 확인해야 한다.

전체 선형 좌표의 반환 여부를 확인하기 위해 [NaviHelper 함수 목차](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/navi-helper/ai.pleos.playground.navi.helper/navi-helper/entry), [RoutePointInfo](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/navi-helper/ai.pleos.playground.navi.data/route-point-info/entry), [RouteStateInfo](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/navi-helper/ai.pleos.playground.navi.data/route-state-info/entry)를 열었다. 공개 페이지에서 필드가 읽히지 않았으므로 이를 '미지원' 또는 '전체 경로 지원'으로 단정하지 않는다. 현재 위치나 지난 주행 기록을 얻는 기능도 목적지까지의 계획 경로와 구분해야 한다.

SDK는 공식 Maven 저장소의 `ai.pleos.playground:NaviHelper:3.0.5`로 안내된다. 별도 내비 REST API 키를 구매하는 절차는 이 안내에 없다. 프로젝트 안내는 NaviHelper를 신청 없이 사용 가능한 SDK로 분류한다. SDK 설치·장치 호환·실제 권한 승인은 아직 시험하지 않았다. [SDK 가져오기](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/importing-sdk), [프로젝트·SDK 사용 안내](https://document.pleos.ai/docs/pleos-only/create-my-project)

공식 권한은 조회·`requestTrip()`에 `pleos.car.permission.NAVI_ROUTE`, 경로 탐색·변경에 `pleos.car.permission.NAVI_ROUTE_SEARCH`, Navigation 화면 요청에 `pleos.car.permission.NAVI_CUSTOM_MAP`이다. 실제 adapter를 설계할 때 해당 API의 정확한 요구 권한을 다시 대조한다. [권한 선언](https://document.pleos.ai/docs/pleos-only/connect-sdk-pleos/NaviHelper/declaring-permissions)

다음 확인에서는 실제 SDK 클래스·공식 샘플의 필드와 문서를 대조하고, 에뮬레이터에서 목적지 설정 → 탐색 완료 → 조회 → 재탐색의 원시 payload를 받는다. 좌표계·좌표 순서·정밀도·전체 경로 여부·경로 revision·전체/잔여 거리·시간을 확인해야 polyline adapter를 완료로 판정할 수 있다. 이번에는 SDK나 샘플을 내려받지 않았다.

## 지도 표시와 경로 계산은 별도다

MapLibre Native는 Android/Kotlin을 포함한 지도 렌더링 엔진이다. SDK 자체는 BSD-2-Clause 라이선스이며, 쓸 지도 타일·스타일·폰트의 공급과 조건은 별도로 정해야 한다. 목적지까지의 자동차 경로를 계산하려면 경로 엔진이나 경로 API가 추가로 필요하다. [MapLibre Native](https://maplibre.org/projects/native/), [코드 라이선스](https://github.com/maplibre/maplibre-native/blob/main/LICENSE.md)

현재 아바타 시험에서는 기존 Canvas에 polyline을 표시할 수 있으므로 MapLibre를 추가하는 것조차 필수는 아니다. 실제 지도를 배경에 보여 줄 필요가 생길 때 표시 계층으로 검토한다.

| 경로 엔진 | 얻는 기하 | 키·호스팅 | 한국 자동차 경로 시험에 대한 판단 |
|---|---|---|---|
| OSRM, BSD-2-Clause | Route API의 `geometries=geojson&overview=full`로 전체 경로 선. 입력은 경도·위도 순서 | 자체 호스팅에는 공급자 API 키 불필요. OSM 원자료 전처리·그래프·서버 운영 필요 | 선형 좌표만 필요한 별도 시험 공급자로 가장 단순한 후보. 한국 정확도·실시간 교통은 별도 검증 |
| Valhalla, MIT | `costing=auto`, leg의 `shape`는 기본 polyline6. 다중 leg를 순서대로 합쳐야 함 | 자체 서버·경로 타일 구축 필요. 공개 데모도 있음 | 모드·시간별 비용과 부가 정보를 다룰 때 후보. 이번 polyline 입력만을 위해 먼저 도입할 이유는 적음 |
| GraphHopper, Apache-2.0 | 자체 Web API `/route`, `points_encoded=false`로 경로의 GeoJSON 좌표 | Java 라이브러리 또는 서버를 직접 운영할 수 있음. 상용 hosted Directions API는 별도 상품·키 | Java 운영을 선택할 때 유효한 대안. 상용 API와 오픈소스 자체 서버를 같은 것으로 취급하지 않음 |

위 판단은 구현 범위를 고려한 권고다. 한국의 실제 자동차 경로를 계산해 비교한 성능·정확도 결과가 아니다. 공식 근거는 [OSRM HTTP API](https://project-osrm.org/docs/v26.6.1/http.html), [OSRM 저장소·전처리 안내](https://github.com/Project-OSRM/osrm-backend), [Valhalla 경로 API](https://valhalla.github.io/valhalla/api/route/api-reference/), [polyline6 정밀도](https://valhalla.github.io/valhalla/api/decoding/), [Valhalla 저장소](https://github.com/valhalla/valhalla), [GraphHopper 저장소](https://github.com/graphhopper/graphhopper), [자체 서버 Web API](https://github.com/graphhopper/graphhopper/blob/master/docs/web/api-doc.md)다.

한국 OSM 지역 추출본은 [Geofabrik South Korea](https://download.geofabrik.de/asia/south-korea.html)에서 제공된다. 따라서 한국 그래프를 만들 원자료를 구할 수는 있다. 이 사실은 국내 도로의 일방통행·진입 제한·고가/지하 연결·주차장 입구·새 도로의 완전성이나 상용 내비와 동일한 경로를 보장하지 않는다. 실제 시험에는 해당 지역을 아는 사람의 도로 대조가 필요하다. 이번에는 원자료를 다운로드하거나 그래프를 구축하지 않았다.

### 공개 데모와 라이선스

OSRM의 FOSSGIS 공개 서버는 car 전 세계 범위를 안내하지만, 최대 초당 1요청, 대량 사용·스크래핑 금지, 출처 표기와 유효한 User-Agent/Referrer를 요구한다. 요청 위치는 서버 로그에 남는다. 소량의 수동 시험용 후보이며 제품의 상시 백엔드로 확정하지 않는다. [운영자 정책](https://routing.openstreetmap.de/about.html)

Valhalla 공식 문서도 공개 데모에 fair-use와 rate limit이 있다고 안내한다. 최종 사용자 앱이 데모를 호출한다면 운영자에게 알리고 식별 가능한 `X-Client-Id`를 보내도록 요청한다. 데모 호출량과 장기 운영 조건을 확인하지 않은 채 자동 시험이나 앱에 고정하지 않는다. [공식 Demo Server 안내](https://valhalla.github.io/valhalla/#demo-server)

코드의 BSD/MIT/Apache 라이선스와 OSM 데이터의 ODbL은 별개다. OSM에서 나온 지도·경로 자료는 출처와 라이선스를 보존해야 한다. 데이터베이스 배포·파생 데이터의 의무와 공개 지도 이미지의 표기 방법도 구분한다. 생성 아바타·보관 자료에 적용할 구체적 조건은 실제 데이터 흐름을 정한 뒤 확인한다. 무료 데이터라는 이유로 OSM 공용 타일 서버를 무제한으로 사용할 수는 없다. [OSM 저작권·라이선스](https://www.openstreetmap.org/copyright), [OSMF 출처 표기](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines), [타일 서버 사용 정책](https://operations.osmfoundation.org/policies/tiles/)

## 국내 경로 API는 필요할 때 선택한다

현대 경로를 직접 받을 수 없거나 독립적인 한국 경로 데이터가 필요한 경우의 비교다. 지금 키 구매를 요청하지 않는다. 실제 계정 권한·요금·호출 성공·응답 품질·생성 모델로의 데이터 전달 허용은 전부 미검증이다.

| 공급자 | 경로 입력과 최소 인증 | 경로 기하 | 주의점 |
|---|---|---|---|
| 카카오모빌리티 자동차 길찾기 | 출발·목적지 경도/위도. 카카오 Developers 앱의 REST API 키 1개, `Authorization: KakaoAK ...` | `summary=false`의 `routes[].sections[].roads[].vertexes`를 도로·구간 순서로 연결. 평탄 배열은 경도,위도 쌍 | 장소명만 있으면 별도 장소 검색/좌표 변환 필요. 상용 데이터 보관·변형·외부 모델 전달 조건은 채택 전에 확인 |
| TMAP 자동차 경로안내 | `POST /tmap/routes?version=1`, 출발·목적지 X/Y. SK Open API의 `appKey` 1개 | 전체 응답과 `resCoordType`을 요청. 실제 응답 기하·정렬은 payload 대조 후 연결 | 공개 약관은 API 데이터를 저장 후 24시간 이상 사용하지 못하도록 함. 별도 허용 없이 장기 재현 fixture로 채택하지 않음 |
| NAVER Maps Directions 5 | 출발·목적지 경도/위도. Application의 Client ID와 Client Secret, Directions 5 사용 선택 | `route.{option}[].path` 배열. 거리 m, 시간 ms | 현행 Maps 기본 주소는 `maps.apigw.ntruss.com`. 구형 `naveropenapi.apigw.ntruss.com` 예제와 혼동하지 않음. 교통 상황 때문에 같은 입력도 경로가 달라질 수 있음 |

카카오 공식 [시작하기](https://developers.kakaomobility.com/guide/navi-api/start.html)와 [자동차 길찾기 규격](https://developers.kakaomobility.com/guide/navi-api/directions), TMAP 공식 [자동차 경로안내 규격](https://tmap-skopenapi.readme.io/reference/%EC%9E%90%EB%8F%99%EC%B0%A8-%EA%B2%BD%EB%A1%9C%EC%95%88%EB%82%B4)와 [데이터 사용 제약](https://tmapapi.tmapmobility.com/terms.html), NAVER 공식 [Maps 공통 URL·인증](https://api.ncloud-docs.com/docs/application-maps-overview)과 [Directions 5](https://api.ncloud-docs.com/docs/application-maps-directions5)를 확인했다. 이 조사에서는 API 테스트 버튼을 누르거나 키를 읽지 않았다.

## 현재 저장소와 연결 경계

현재 v2 생성 입력의 `route.points`는 위경도 배열이 아니다. 0–1 범위의 정규화된 화면 좌표이고 2–512점, 유한 숫자, 길이가 0이 아닌 경로를 요구한다. `destination`도 이름·특성 텍스트를 받으며 목적지 위경도 필드는 없다. extra 필드를 금지하므로 현재 요청에 원본 GeoJSON·provider·스크린샷을 임의로 끼워 넣을 수 없다. [현재 입력 검증](../../backend/nunti/characters/models.py)

기존 `RouteSnapshot`은 거리·시간·도로 비율·지형 태그와 근거를 위한 내부 모델이다. 전체 polyline 필드는 없고 SDK에 직접 의존하지 않는다. `DataSource.NAVI_HELPER` enum이 있다는 사실은 실제 연결 완료를 뜻하지 않는다. [RouteFeatures.kt](../../android/feature/navigation/src/main/kotlin/ai/nunti/navigation/RouteFeatures.kt)

인수인계 역시 실제 NaviHelper binary·payload, 전체/잔여 값의 의미, GIS 근거, 실제 adapter를 남은 작업으로 기록한다. [AVATAR 복원 보고](../handoff/restoration/2026-11-02/avatar.md)

후속 설계에서는 실제 내비 공급자 adapter가 원본 기하를 읽고 검증한 다음, 원본의 방향·비율을 유지해 v2 화면 좌표로 변환한다. 원본 경로와 출처 정보는 별도 원본 기록으로 보관하고 해당 기록 해시를 생성 입력에 연결하는 계약을 검토한다. 이번에는 wire나 저장 구조를 변경하지 않았다.

## 스크린샷으로 지금 시험하는 현실적인 방법

아래는 다음 구현에 사용할 시험 절차다. 내비게이션 기능 없이도 입력 경로와 아바타 탄생의 연결을 확인할 수 있다.

1. 저장·시험 권한이 있는 실제 자동차 경로를 고른다. 출발지·목적지, 공급자, 탐색 옵션, 조회 시각, 경로 선택 번호를 기록한다. 다른 시각에 재조회한 유사 경로와 섞지 않는다.
2. 지도에 선택 경로가 표시된 스크린샷과 **그 동일 응답의 원본 좌표 JSON/GeoJSON**을 한 묶음으로 보존한다. screenshot, raw response, 선택한 LineString 각각의 SHA-256과 출처·보관 조건을 기록한다. 장기 fixture는 OSM 기반 또는 별도 재사용 허용 자료를 우선한다.
3. 좌표를 얻을 수 없는 스크린샷만 있다면, 보이는 선택 경로를 화면 좌표로 추출하고 출발→도착 순서로 정렬한다. 원본 위에 추출 선을 겹쳐 사용자가 확인한 뒤 `SCREENSHOT_TRACE`로 기록한다. 분기·중첩·가려진 구간을 확정할 수 없으면 추측해 연결하지 않는다. 사람이 확인한 화면 선도 실제 도로 주행 가능성이 검증된 GPS polyline은 아니다.
4. 원본 위경도가 있으면 경도·위도 순서, 좌표계, 정상 범위, 시작·끝점, leg 연결, 역순 여부, 경로 끊김을 확인한다. Valhalla polyline6을 polyline5로 잘못 읽지 않는다. 거리·시간은 원본 단위와 전체/잔여 의미를 보존한다.
5. 위경도는 투영 좌표로 바꾼 뒤 하나의 배율로 fit한다. 가로·세로를 각각 늘려 경로 모양을 찌그러뜨리지 않는다. 위쪽이 작은 화면 Y가 되도록 변환하고 시작→도착 순서는 유지한다. 스크린샷 좌표는 crop·회전·원근 정보를 보존하며 GPS 경로와 구분한다.
6. 512점을 넘으면 시작·끝과 중요한 굴곡을 유지하는 단순화를 적용한다. 원본은 그대로 두고 변환 알고리즘·버전·오차·최종 점 수·변환 결과 해시를 기록한다. 화면 좌표가 전부 같은 점이 되거나 유효 길이가 사라진 입력은 거절한다.
7. 시험 화면은 실제 경로와 변환된 선을 먼저 보여 준다. 동일 선의 시작점·곡선·목적지 방향이 탄생 첫 프레임과 맞는지 확인한 뒤 생성한다. 원본 스크린샷과 JSON은 아바타 원본 이미지·음성 정체성과 별도로 추적한다.

fixture에 권하는 정보는 `sourceKind`, `provider`, `capturedAt`, `coordinateSystem`, `origin`, `destination`, `routeOption`, `routeRevision`, `rawResponseSha256`, `screenshotSha256`, `rawGeometrySha256`, `normalizedGeometrySha256`, `normalizationVersion`, `reviewStatus`, `license`, `attribution`, `retentionRule`다. 이는 새 wire 필드가 아니라 다음 설계를 위한 제안이다. 원본 스크린샷은 지도 맥락과 대조용으로 사용하고 아바타 이미지 생성 모델에는 검증한 경로 guide를 전달하는 편이 입력을 명확히 한다.

## 완료·미구현·미검증

| 구분 | 현재 상태 |
|---|---|
| 완료 | 공모전 기준에 맞춘 현대 우선순위 확인, 공식 NaviHelper 목적지·이벤트·권한 조사, 오픈소스 역할·한국 데이터 존재·공개 데모 제한 조사, 국내 API 최소 인증 비교, 현재 v2 계약과의 차이 확인 |
| 미구현 | NaviHelper adapter, 실제 polyline 획득·변환, 스크린샷 입력·검토 화면, 원본 fixture 묶음 저장·출처 연결, 대체 경로 엔진·지도 SDK 도입 |
| 미검증 | NaviHelper 전체 계획 polyline의 실제 필드·정밀도·권한·에뮬레이터 수신, 한국 실도로 경로 정확도, 국내 API 계정·요금·응답·장기 보관·생성 모델 전달 조건, 실제 스크린샷 추출 품질 |

우선순위는 현대 내비의 실제 반환 범위 확정 → 출처가 있는 경로 fixture로 탄생 경험 시험 → 필요한 경우에만 대체 경로 공급자 선택이다. 외부 내비 API 키 구매와 턴바이턴 개발은 이번 조사 결과로 요구하지 않는다.
