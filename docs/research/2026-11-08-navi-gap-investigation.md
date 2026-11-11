# 내비 연동 미해결 3건 조사 (2026-11-08)

대상: "네비 실제 연동 확인" 항목. `docs/design/navigation-integration/RESULT.ko.md`가 남긴 미검증 3건을 NaviHelper 3.0.5 실제 클래스로 따져 본 정적 조사다. 이 조사에서는 에뮬레이터를 실행하지 않았고, 아무것도 시작·중지·수정하지 않았다(Kotlin 코드 변경 없음, 네트워크 호출 없음).

표기: **[관측]** = 이번에 jar/AAR·소스·문서에서 직접 확인한 사실. **[추론]** = 관측으로부터 이끌어 낸 판단이며 에뮬레이터에서 확인 전까지 사실로 쓰지 않는다.

## 1. 요약

| 항목 | 결론 |
|---|---|
| (a) 주입 GPS가 SDK 위치에 안 들어감 | SDK(NaviHelper) 안에는 위치를 읽거나 넣는 코드가 아예 없다. 위치는 현대 내비 앱(서비스 반대편)이 가진 값을 콜백으로 전달받을 뿐이다. SDK 쪽에서 위치를 주입하는 방법은 없다. 내비 앱이 어떤 위치원을 쓰는지가 열쇠이고, 그건 에뮬레이터에서만 확인된다. |
| (b) 재탐색 완료 콜백 없음 | `requestReRoute()`는 서비스에 "RequestReRoute" 문자열 이벤트를 던지는 단방향 호출이다. `onReRouteEnded`는 내비 앱이 `NotifyReRouteEnd`를 보낼 때만 온다. SDK에는 조건·타임아웃·결과 코드가 없다. 조건은 내비 앱 내부 로직이라 jar만으로는 알 수 없다. |
| (c) 전체 도로 polyline 없음 | 재확인됨. 공개 API·데이터 타입·AIDL·이벤트 enum 어디에도 좌표 배열이 없다. |
| 부수 발견 | `NaviSignalSource.onRouteEnded()`가 "경로 종료"로 해석하는데, 기존 연구 문서는 이 콜백이 "경로 탐색 완료"라고 기록했다(아래 5절). |

## 2. 확인한 자료

- 문서: `RESULT.ko.md`, `TESTING.ko.md`, `docs/research/2026-11-04-navigation-review/README.md`, `docs/architecture/score-signals-api.md`.
- 코드: `android/app/src/main/kotlin/ai/nunti/app/navigation/PleosNavigationAdapter.kt`, `android/feature/score/src/main/kotlin/ai/nunti/score/live/NaviSignalSource.kt`.
- SDK(Gradle 캐시, 읽기 전용, 복사본을 스크래치에서만 풀어 javap): `NaviHelper-3.0.5.aar`, `navi-data-3.0.4.aar`, `navi-aidl-3.0.1.aar` (`~/.gradle/caches/modules-2/files-2.1/ai.pleos.playground/`). 소스 JAR는 캐시에 없다. 클래스 이름이 난독화돼 있어(`helper.manager.a/b/c`, `helper.callback.a` 등) 내부 동작은 바이트코드로만 봤다.
- 참고: 문서들이 가리키는 `.local/navigation-integration/...` 증거 파일과 `/Users/pig30nidae/NUNTI` 경로는 이 Mac(`/Users/eunryong/develop/NUNTI`)에는 없다(`.local` 디렉터리 부재). 즉 RESULT.ko.md의 수치(10.48km, 19.36km, 콜백 32개 등)는 이 머신에서 재확인하지 못했다.

## 3. SDK 구조 (관측)

- `NaviHelper`는 `ServiceConnection` 기반 클라이언트다(`helper.manager.a implements ServiceConnection`, `INaviService` 바인딩). AAR 매니페스트의 `queries`는 action `ai.pleos.playground.intent.action.NAVI_START`, 서비스 최소 버전 2.0.1/code 11, SDK 3.0.5/code 75.
- `INaviService`(navi-aidl 3.0.1)의 메서드: `registerCallback(V2)`, `requestToNavi`, `requestToNaviProvider`, `requestDefaultNaviSetting`, `showDefaultNaviDialog`, `setDefaultNaviPackage`, `getServiceVersion`. 요청은 모두 (패키지명, 이벤트명 문자열, 데이터 문자열) 형태다.
- `NaviEvent`(SDK→내비) 18종: RequestRoute, RequestRouteWithWaypoints, RequestRouteOptionChange, RequestRouteCancel, RequestWaypoint, RequestReRoute, RequestRemoveWaypoint, Get*(CurrentLocationInfo, RouteStateInfo, DestinationInfo, WaypointInfo, Bookmark, RecentDestination, TBTInfo, ChargerOperatorInfo), RequestNavigationScreen, RequestTrip, UpdateOccupiedRegion. **위치를 설정하는 이벤트는 없다.**
- `NaviProviderEvent`(내비→SDK) 27종: NotifyRouteStarted/Ended/RoutingCompleted/**ReRouteEnd**/RouteOptionChanged/RouteCancelled, WaypointChanged, DestinationArrived, WaypointArrived, DestinationChanged, Error, **CurrentLocationInfo**, RouteStateInfo, DestinationInfo, **CurrentRoadSpeedLimit**, CameraAlert, DrivingInfo, NavigationStatus, **TBTInfo**, ChargerOperatorInfo, CautionPointInfo, TripInfo 등. 즉 위치·제한속도·TBT·재탐색 종료는 전부 "내비 앱이 알려 주는 값"이다.
- `NaviHelper` 공개 메서드 중 `getInternalApi()`가 반환하는 `InternalApi`는 `updateOccupiedRegion(Rect)` 하나뿐. `PrivateApi`는 애너테이션 인터페이스일 뿐 기능 없음.

## 4. 항목별 상세

### (a) 현재 위치는 어디서 오는가, 주입 방법이 있는가

- [관측] `NaviHelper` AAR, `navi-data`, `navi-aidl` 클래스 전체에서 `LocationManager`, `android/location`, `setTestProvider`, MockLocation 문자열이 0건이다. SDK는 위치를 스스로 읽지 않는다.
- [관측] `getCurrentLocationInfo()`는 `NaviEvent.GetCurrentLocationInfo` 요청을 보내고, 값은 `onCurrentLocationInfo(CurrentLocationInfo)` 콜백(`latitude, longitude, heading, address, routeId, currentRouteIndex`)으로 비동기 도착한다. 이 값은 내비 앱이 `NotifyCurrentLocationInfo`로 보낸 것이다.
- [관측] 공개·내부 API에 위치를 SDK/내비로 밀어 넣는 함수가 없다. 어댑터(`PleosNavigationAdapter.kt`)도 위치 입력 명령이 없다(`connect/refresh/requestRoute/requestTrip/changeRouteOption/reroute/overview/foreground/cancelRoute`).
- [관측, 문서] `score-signals-api.md` 5절: `adb emu geo fix`는 Pleos FusedLocation만 바뀌고 내비 엔진 위치는 고정이었다. `RESULT.ko.md`: 에뮬레이터 gRPC `setGps`로 3점 주입 후 readback은 성공, SDK 위치는 판교에 머물렀다(내비를 앞에 두고 16초 유지해도 동일).
- [추론] 현대 내비 앱이 Android `LocationManager`/FusedLocation 대신 Pleos 차량 서비스의 자체 위치(차량 GNSS 속성 등)를 쓰고 있을 가능성이 높다. 근거는 "Android GPS와 Pleos FusedLocation은 움직였는데 내비 위치만 안 움직임"뿐이라 확정이 아니다. 대안 가설: 내비가 GPS 변화가 매우 느린 주기로만 반영한다, 또는 위치 점프(10km 이상)를 이상치로 버린다(맵매칭 실패). 이 셋은 지금 구분할 증거가 없다.
- 결론: **SDK 측에서 할 수 있는 일은 없다.** 가능한 길은 (1) 내비 앱이 소비하는 위치원을 찾아 그 위치원에 주입, (2) 내비 앱의 자체 모의주행, (3) Pleos 측 문의 중 하나다. 시험 계획 4~6단계 참고.
- 부가: `NaviMode.SIMULATION_GUIDING` enum이 있으나 이를 시작하는 SDK 함수는 없다(`NaviHelper` 공개 메서드 목록에 없음). 모의주행은 내비 앱 UI에 있는지만 확인할 수 있다[미확인].

### (b) onReRouteEnded가 발화하는 조건

- [관측] `NaviHelper.requestReRoute()` → 로그 후 `manager.c.y()` → 권한 `pleos.car.permission.NAVI_ROUTE_SEARCH` 확인 → `NaviEvent.RequestReRoute`를 `INaviService.requestToNaviProvider(패키지, "RequestReRoute", ...)`로 전송. 반환값·콜백 ID·타임아웃이 없다. 어댑터가 "COMMAND_DISPATCHED"를 남기는 것은 서비스 호출이 예외 없이 끝났다는 뜻일 뿐 내비가 받아들였다는 뜻이 아니다.
- [관측] `onReRouteEnded()`는 `NaviHelperEventListener`의 default 메서드이고, `NotifyReRouteEnd` 수신 시에만 호출된다(`helper.callback.a`/`listener`에 문자열 존재). SDK에서 발화 조건을 걸러 내는 코드는 보이지 않는다.
- [추론] 재탐색이 실제로 새 경로를 계산해 끝났을 때만 내비 앱이 `NotifyReRouteEnd`를 보낼 것이다. 재탐색이 "경로 안내 중이 아님", "위치 미갱신", "동일 경로라 변경 없음", 서버 오류(`NaviErrorCode.CAUSE_SEARCH_ROUTE*`) 등으로 무시·실패하면 아무 콜백이 없을 수 있다. 실패 시 `onError(NaviErrorCode)`가 올 수 있으나 실제로 오는지는 미확인(`NaviErrorCode`: CAUSE_LOW_BATTERY, CAUSE_SEARCH_ROUTE_OVER_DISTANCE, CAUSE_SEARCH_ROUTE, CAUSE_SEARCH_ROUTE_TOO_SHORT_DISTANCE, CAUSE_SEARCH_TRIP).
- [관측, 코드] `NaviSignalSource`는 `onReRouteEnded`, `onCurrentLocationInfo`, `onDestinationArrived`, `onCameraAlert`를 구독하지 않는다. 어댑터는 `onReRouteEnded`를 구독해 lifecycle을 `REROUTED`로 기록하니 완료 콜백이 오면 `navigation-api-events.jsonl`에 남는다.
- 결론: (a)와 (b)가 연결돼 있을 가능성이 크다(위치가 안 움직이면 재탐색할 이유가 없는 상황이거나, 재탐색은 현재 위치 기준일 것이다 = 추론). 재탐색 단독 시험보다 경로 옵션 변경(`changeRouteOption` → `onRouteOptionChanged`)이 같은 서비스 경로의 완료 이벤트를 받는지 먼저 보는 것이 구분에 유용하다.

### (c) 전체 도로 polyline

- [관측] `TripSummary`는 `trafficConditions: List<TrafficInfo>`(혼잡 종류와 `startRatio/endRatio`)와 `routePoints: List<RoutePointInfo>`(위경도, poiName, `ratioOnRoute`, ORIGIN/WAYPOINT/DESTINATION 등 타입)만 가진다. 도로 형상 좌표 배열은 없다.
- [관측] `RouteStateInfo`, `DestinationInfo`, `CurrentLocationInfo`, `TBTInfo`, `DrivingInfo/DrivingState`(충전 계획 중심), `RouteStartInfo`에도 좌표 배열이 없다. 전체 보기는 `NavigationScreenRequest.OverviewRoute`(화면 요청)뿐이고 이미지·좌표를 돌려주지 않는다.
- 결론: 기존 결론 유지(OSRM 별도 계산 + `geometryMatchesHyundaiRoute=false`). 대안 근사: `TripSummary.trafficConditions`의 비율 구간과 `routePoints.ratioOnRoute`로 OSRM 선 위에 진행률(%)을 매핑하는 것은 가능하나, 현대 경로와 OSRM이 같은지는 여전히 미검증이다[추론].

## 5. 점수 모듈에 쓸 수 있는 SDK 데이터

| 데이터 | 콜백/API | 점수 모듈 용도 | 주의 |
|---|---|---|---|
| 도로 제한속도 | `onCurrentRoadSpeedLimit(int)` | 제한속도 준수(현재 `NaviSignalSource.speedLimitKmh`) | 단위는 SDK에 명시 없음(추론: km/h). `0 이하`는 null 처리 중. 위치가 갱신돼야 올 것이므로 에뮬레이터에서 미수신(`score-signals-api.md`). |
| 카메라 경고 | `onCameraAlert(List<CameraAlert>)`: `type`(고정/이동/구간/신호/스쿨존 등), `speedLimit`, `remainDistance`, `sectionAvrSpeed`, `status` | 단속 구간 제한속도·구간 평균속도 비교, 스쿨존 가중 | 현재 미구독. 제한속도 보완 소스가 될 수 있음 |
| 주의 구간 | `onCautionPointInfo(List<CautionPoint>)`: SCHOOL_ZONE, SPEED_BUMP, RAILROAD_CROSSING 등 + `remainDistance` | 상황 맥락(스쿨존 과속 등) | 현재 미구독 |
| TBT | `onTBTInfo(List<TBTInfo>)`: `TurnType`(좌/우/유턴/IC/회전교차로 등), `distance`(m), `description` | 회전 이벤트 생성(현재), 회전 전 감속 평가 | 회전 "통과" 판정은 TBT 변화로 추정하는 방식이라 실제 회전 여부는 지시등·조향과 교차검증 필요 |
| 경로 요약 | `TripInfo`: `distance`, `eta`, `estimatedSocAtDest`, `energyConsumption`, `summary.trafficConditions` | 도착 ETA vs 실제, 전비 비교(효율 영역 평가 불가 해소 후보), 정체 구간 맥락 | `requestTrip`은 목적지·POI 필요. 단위(eta 초?)는 SDK에 명시 없음 |
| 도착·경유 | `onDestinationArrived(DestinationArrivedInfo: duration, distance, name, address)`, `onWayPointArrived` | 주행 종료 시점·총 시간/거리 확정 → 종료 후기 | 현재 미구독. 종료 신호로 유용 |
| 상태 | `onNavigationStatus`(INACTIVE/INITIALIZING/FREE_DRIVE/ROUTE_DRIVE), `RouteStateInfo.naviMode` | 주행 세션 시작/종료 판단 | `isRouting` 필드는 문서 설명과 실제 응답이 달랐다고 기록돼 있음(연구 문서) |

[관측, 코드] `NaviSignalSource.onRouteEnded()`는 TBT head를 지우고 `nextTurn = "경로 종료"`로 표시한다. 그러나 2026-11-04 연구 문서는 이 구형 콜백을 "경로 탐색 완료이며 안내 종료가 아니다"라고 기록했고, 같은 문서의 실제 SDK 로그에서 `onRouteStarted` 약 12ms 뒤에 `onRouteEnded`가 왔다. 어댑터(`PleosNavigationAdapter`)는 이 점을 반영해 READY로 처리하지만 `NaviSignalSource`는 그렇지 않다. 경로 시작 직후 TBT 추적이 초기화되고 "경로 종료"가 표시될 수 있다(추론: 코드와 문서의 대조 결과). 점수 모듈 쪽 수정은 이번 범위 밖이라 건드리지 않았고, 이은룡이 판단할 사항이다. 안내 종료는 `onRouteCancelled` 또는 `onDestinationArrived`로 구분하는 것이 문서와 맞는다.

## 6. 현재 환경 상태 (관측, 변경 없음)

- `adb devices`(PATH의 adb는 없고 `~/Library/Android/sdk/platform-tools/adb`): 연결된 기기 없음(목록 비어 있음).
- `~/Library/Android/sdk/emulator`: 실행 파일 `emulator`, `emulator-check`, `qemu` 계열 폴더 등 설치돼 있음.
- `~/.android/avd`: `Pleos_Connect_Nunti.avd`, `Medium_Phone.avd`. 시스템 이미지: `android-34/pleos_car_emulator/arm64-v8a`, `android-37.0/google_apis_playstore/arm64-v8a`.
- 에뮬레이터 프로세스: 실행 중인 `qemu`/`emulator` 프로세스는 보이지 않았다.
- 결론: **지금은 실행 중인 에뮬레이터가 없다.** `Pleos_Connect_Nunti` AVD는 있으므로 이은룡이 직접 띄우면 된다(`TESTING.ko.md`의 `run_avatar_generator.py`가 기동을 맡는지는 이번에 확인하지 않았다). 이 머신에는 `.local/...` 증거가 없어 Pleos 콘솔(127.0.0.1:8088) 접근 가능 여부도 확인할 수 없다.

## 7. 미검증으로 남는 것

1. 현대 내비 앱이 위치를 어디서 읽는지(Android GPS, Pleos FusedLocation, 차량 GNSS 속성, 자체 모의 위치).
2. 큰 위치 점프(10~19km)를 내비가 이상치로 버리는지, 천천히 연속 이동하면 따라오는지.
3. `NotifyReRouteEnd`의 발화 조건(경로 안내 중 + 위치 갱신 + 실제 재계산 여부)과 실패 시 `onError` 유무.
4. `onCurrentRoadSpeedLimit`의 단위·주기, 위치가 움직일 때 실제 오는지.
5. 내비 앱 UI에 모의주행(`SIMULATION_GUIDING`)이 있는지, 있다면 SDK 콜백(위치·TBT·제한속도)이 같이 오는지.
6. RESULT.ko.md의 수치 자체(이 Mac에는 증거 파일이 없어 재확인 불가).

## 8. 에뮬레이터 시험 계획 (이은룡용, 순서대로)

각 단계의 결과는 어댑터가 앱 내부 저장소(`filesDir`)에 남기는 `navigation-api-events.jsonl`과 `navigation-api-snapshot.json`으로 확인할 수 있다(디버그 빌드에서 `adb shell run-as <앱 패키지> cat files/navigation-api-events.jsonl`; 패키지명은 사용 빌드의 것을 쓰고, 이 조사에서는 확인하지 않았다). 단계마다 시각과 결과를 기록한다.

0. 준비: `Pleos_Connect_Nunti` 에뮬레이터를 띄우고 현대 내비 초기 대화상자(계속안내/안내종료)를 끝낸다. `adb devices`에 기기가 보이는지 확인. 눈티 앱에서 연결 후 콜백 수신(`receivedCallbackCount > 0`, `onCurrentLocationInfo`의 좌표 유효)을 확인한다. 기준 위치(판교)를 기록한다.
1. 위치원 파악(읽기 전용, 가장 먼저): 내비를 안내 중으로 둔 상태에서 `adb shell dumpsys location`을 저장해 현대 내비 앱 패키지(`ai.umos.maps.android.navigation.app`)가 어떤 provider(gps/fused/passive/network)를 구독하는지 본다. 내비 앱이 구독하는 provider가 없다면 위치는 차량 서비스에서 온다는 강한 단서다. 같은 시점에 `adb logcat -d`에서 내비 앱·`ai.pleos.playground.service.navi`의 위치 관련 로그를 grep으로 저장한다.
2. 가장 단순한 주입 재시험: 1단계에서 확인된 provider에 맞춰 `adb emu geo fix <lon> <lat>`를 **작은 이동**(수백 m)으로 5초 간격 5~10회, 내비를 앞에 둔 채 실행하고 `onCurrentLocationInfo`가 변하는지 본다. 지금까지는 판교→10km 이상 점프만 시험했으므로 "점프라서 버려졌는가"를 가른다. 끝나면 원래 위치로 되돌린다.
3. 연속 이동 재시험: 2단계가 실패하면 에뮬레이터 Extended controls > Location > Routes(GPX 재생)로 속도 있는 연속 이동(예: 시속 30~60km에 해당하는 간격)을 5분 이상 재생한다. 정지 위치 주입과 달리 속도·방향(bearing)이 같이 들어가는지 본다. 이 방법이 내비를 움직이면 (a)는 해결이다.
4. Pleos 콘솔(`adb forward tcp:8088 tcp:8088` → http://127.0.0.1:8088)에서 Motion/ADAS 외에 위치·GNSS·주행거리 관련 입력이 있는지 화면과 항목 이름만 기록한다. 주행거리·조향각이 내비 위치에 영향을 주는지(추측 항법) 작은 값으로 확인하되, 기어 P/속도 0 전제를 `TESTING.ko.md`대로 유지한다.
5. 내비 앱 자체 모의주행: 현대 내비 앱의 경로 안내 화면·설정에서 모의주행/데모 주행 메뉴가 있는지 확인한다. 있으면 실행 중 `onCurrentLocationInfo`, `onTBTInfo`, `onCurrentRoadSpeedLimit`, `onNavigationStatus`(SIMULATION_GUIDING 여부)가 오는지 기록한다. 오면 점수 모듈의 회전·제한속도 시험 수단이 된다.
6. 2~5단계에서 위치가 움직인 경우에만 재탐색 시험: 경로 안내 중에 `reroute`를 1회 보내고 30초 동안 `onReRouteEnded`/`onRouteStateInfo`/`onError`/`onRouteOptionChanged`를 기록한다. 이어서 경로 이탈(경로에서 벗어난 좌표 주입) 후 내비 앱이 스스로 재탐색하는지 본다(자동 재탐색 시 `onReRouteEnded`가 오는지가 SDK 쪽 콜백 배선 검증이다).
7. 위치가 끝내 안 움직이는 경우의 SDK 배선 분리 시험: 위치와 무관한 두 호출을 보내 콜백 배선이 정상인지 확인한다. `changeRouteOption`(추천 ↔ 다른 옵션)은 `onRouteOptionChanged`가, `requestRoute`로 다른 목적지를 주면 `onDestinationChanged`/`onRouteStarted`/`onRoutingCompleted`가 오는지 본다. 이 둘이 오는데 `onReRouteEnded`만 안 온다면 재탐색은 위치 갱신 없이는 완료되지 않는 내비 내부 조건일 가능성이 높다.
8. 실패 결론 기록: 위 어느 방법으로도 SDK 위치가 안 움직이면, 대회 측(Pleos)에 다음을 문의한다. "NaviHelper 3.0.5 에뮬레이터에서 내비 위치를 모의로 이동시키는 공식 방법이 있는가, 재탐색 완료(NotifyReRouteEnd)의 발화 조건은 무엇인가, 전체 도로 형상을 제공하는 API가 있는가." 점수 모듈은 그동안 차속(`PERF_VEHICLE_SPEED`) 기반으로 두고, 제한속도·회전은 "평가 불가(미수신)" 처리를 유지한다(현재 `score-signals-api.md`와 동일).
9. 점수 모듈 후속 확인(위치가 움직인 뒤): `onCurrentRoadSpeedLimit` 값과 단위, `onCameraAlert`/`onCautionPointInfo` 수신 여부, `onDestinationArrived` 수신(주행 종료 신호)을 기록한다. 그리고 5절의 `NaviSignalSource.onRouteEnded` 문제를 확인하기 위해 경로 시작 직후 `nextTurn` 표시가 "경로 종료"로 바뀌는지 본다.

## 9. 이은룡이 결정할 것

- `NaviSignalSource`의 `onRouteEnded` 처리(5절)를 어댑터처럼 "탐색 완료"로 바꿀지.
- `onDestinationArrived`, `onCameraAlert`, `onCautionPointInfo`를 점수 모듈에 연결할지(위치가 움직이는 것이 확인된 뒤).
- 8단계 문의를 보낼지, 그 전까지 내비 연동 항목을 "SDK 콜백 수신 확인 / 위치·재탐색 미검증"으로 유지할지.
