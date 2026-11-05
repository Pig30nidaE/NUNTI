# 사진 없는 내비 API 연결 계약

2026-11-04. 사용자 요청은 사진 추출을 제외하고 내비 API를 확인한 뒤 SDK 연결·선택 경로 확인·반복/GPS 시험을 완료하는 것이다. 전체 제품은 운전습관 개선을 돕는 눈티, 담당은 목적지·경로 기반 생성이다. 과금 외부 API·동영상·음성 녹음은0회다.

## 선택한 구조

공식 NaviHelper3.0.5의 공개 API와 getInternalApi를 확인했다. 확장은 updateOccupiedRegion(Rect)만 제공하며 도로 전체 polyline 반환 경로를 찾지 못했다. 요약 경유·목적지점을 도로로 이어서 사용하지 않는다.

현대 SDK는 실제 목적지·현재 위치·routeId·옵션·탐색 이벤트를 제공한다. 실제 전체 도로 형상은 opt-in OSRM/FOSSGIS 경로 API로 계산하고 출처·원본·좌표 변환·SHA를 보존한다. 이 선을 현대 내비와 동일한 선택 경로라고 표시하지 않는다. 출발·도착·경로선을 사용자가 확인한 뒤 기존 생성 API로 전달한다.

대안으로 사진 캡처는 사용자 요청과 충돌해 제외한다. 목적지 요약점을 shape로 쓰는 방법은 실제 도로 굴곡을 잃으므로 제외한다. 다른 API 계산 결과라는 구분 없이 현대 native path로 표시하는 방법도 제외한다.

## 모듈과 소유

- navi_adapter_impl: Android navigation/PleosNavigationAdapter.kt, app Gradle 의존성, Manifest NAVI권한·query. 실제 SDK DTO·연결·명령·이벤트와 private snapshot을 소유한다.
- route_api_impl: backend 신규 route_api.py·api.py·models.py·tests. 경로 API·위경도/정규화·snapshot 보존·캐시 재생·입력 검증을 소유한다.
- nav_test_replay: scripts/verify_navigation_integration.py·navigation_native_command.mjs 등 전용 검증 도구와 .local 재생 자료. 공식 emulator getGps/setGps와 SDK readback을 비교하고 원래 GPS를 복원한다.
- root: Android studio host·JS/HTML/CSS·실행기·문서·최종 빌드/실물 검증. 주차 gate와 기존 소장품·음성 설정은 보존한다.

## 안정된 인터페이스

Android: PleosNavigationAdapter(context,onChanged:(String)->Unit), start(), snapshot():String, dispatch(command,payloadJson="{}"):String, close(). snapshot.source=PLEOS_NAVI_HELPER_API, geometryStatus=NOT_PROVIDED_BY_PUBLIC_SDK. onChanged는mainthread. commands refresh/requestRoute/requestTrip/changeRouteOption/reroute/overview/foreground/cancelRoute. NativeBridge.getNavigationSnapshot()/navigationCommand()는실제P·정차·UX·foreground gate로접근한다. 공급자키는없다.

서버: POST /v3/route-plans {origin:{latitude,longitude,name?},destination:{latitude,longitude,name},nativeSnapshot?}. 반환route는points/inputOrigin=API_ROUTE/apiPlanId/confirmed=false다. 생성 시confirmed=true+apiPlanId를전달하고서버가소유권·좌표·목적지일치를확인한다. GET /v3/route-plans/{id}는저장된같은원본을재생한다. geometry.provider=OSRM_FOSSGIS, geometryMatchesHyundaiRoute=false. 명시`--navigation-api`로개발용공개경로API를활성화한다. 유료이미지승인과독립이며기본은외부경로호출없음.

## 반복과 정체성

SDK 재탐색·위치 콜백은 새 아바타 생성 트리거가 아니다. 이미 생성한 눈티·원본 입력·이미지/음성바인딩을 보존하고, 새 snapshot과 route revision은 별도 상태로 표시한다. 새 여정 생성만 사용자가 명시적으로 시작한다. API 재생은 저장 planId·rawSHA를 유지하고 live재계산과 구분한다.

## 검증

실제SDK initialize+목적지/상태/위치callback, API전체선형상+출발/도착검증, 확인전생성차단, 생성·보관복원, 저장plan반복동일SHA, native재탐색후기존눈티불변을시험한다. GPS는공식EmulatorController.getGps/setGps만사용하고원상복원한다. SDK가주입위치를소비하는지콜백으로확인하며실패시완료로표시하지않는다. 상용차량·실제운전습관개선·현대원형상API획득은검증범위가아니다.
