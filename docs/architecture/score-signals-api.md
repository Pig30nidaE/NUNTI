# 눈티(Nunti) 사용 API 정리 (협업 합치기용)

기준: 2026-11-05, 에뮬레이터 `Pleos_Connect_Nunti` (API 34)에서 확인한 결과.
상태 표기: ✅ 에뮬레이터에서 값 수신 확인 / ⚠️ 연결은 했으나 값 미확인 / ❌ 신호 없음 / 🔧 비공식 경로

## 1. 빌드 설정

| 항목 | 값 |
|---|---|
| Maven 저장소 | `https://nexus-playground.pleos.ai/repository/maven-releases/` (`settings.gradle.kts`) |
| Vehicle SDK | `ai.pleos.playground:Vehicle:2.3.2` |
| Vehicle AIDL | `ai.pleos.playground:vehicle-aidl:1.1.1` (🔧 직접 구독에 사용) |
| 내비 SDK | `ai.pleos.playground:NaviHelper:3.0.5` |
| AAOS Car API | `compileOnly(files(".../platforms/android-37.0/optional/android.car.jar"))` |
| SDK 버전 | compileSdk 37 / minSdk 28 / targetSdk 34 |
| 툴체인 | Gradle 9.6.0, AGP 9.4.1, Kotlin 2.2.10, Compose BOM |

## 2. 매니페스트

| 종류 | 값 | 이유 |
|---|---|---|
| 권한 | `android.car.permission.CAR_SPEED` | AAOS 속도 |
| 권한 | `pleos.car.permission.CAR_DRIVE` | 기어·브레이크·지시등 등 |
| 권한 | `pleos.car.permission.CAR_SAFETY` | 안전벨트 |
| 권한 | `pleos.car.permission.CAR_SEATS` | 좌석 탑승 |
| 권한 | `pleos.car.permission.CAR_DOORS` | 문 열림 |
| 권한 | `pleos.car.permission.CAR_LIGHTS` | 하향등 |
| 권한 | `pleos.car.permission.NAVI_ROUTE`, `NAVI_NOTIFY` | NaviHelper (없으면 `SecurityException`으로 앱 종료) |
| uses-library | `android.car` (required=false) | |
| meta-data | `distractionOptimized = true` (MainActivity) | 없으면 주행 중 "사용할 수 없습니다"로 차단됨 |

## 3. 신호별 API (점수 항목과 연결)

| 신호 | API | 상태 | 쓰이는 점수 항목 |
|---|---|---|---|
| 차속 | 🔧 `IVehicleService.registerPropertyCallback(pkg, "PERF_VEHICLE_SPEED", 0, IPropertyCallback)` (단위 m/s → ×3.6) | ✅ 계기판과 일치 | 급가속·급감속·급제동, 후진 속도, 제한속도, 문/벨트/전조등 "주행 중" 판정 |
| 브레이크 | `vehicle.getBrake()` → `registerBrakePedalStatus` / `getCurrentBrakePedalStatus` | ✅ | 급제동 구분 |
| 기어 | `vehicle.getGear()` → `registerGearSelection` | ✅ | 후진 속도 |
| 지시등 | `vehicle.getTurnSignal()` → `registerTurnSignalState` | ✅ | 차선 변경 지시등 (이벤트 쪽 신호 없음, 아래 ❌) |
| 하향등 | `vehicle.getLight()` → `registerLowBeamLightState` | ✅ | 야간 전조등 (밤 판단 신호 없음) |
| 안전벨트 | `vehicle.getSeat()` → `registerSeatBeltBuckledState(SeatArea(ROW_1_LEFT/RIGHT))` | ✅ | 안전벨트 |
| 좌석 탑승 | `getSeat()` → `registerSeatOccupancy` | ✅ | 안전벨트 (빈 좌석은 평가 제외) |
| 문 열림 | `vehicle.getDoor()` → `registerDoorPosition(DoorArea(ROW_1/2 L/R))` (0=닫힘, 0 초과=열림) | ✅ | 주행 중 문 열림 |
| 다음 회전 | `NaviHelper` `onTBTInfo` | ✅ 값 수신 (`LEFT 80m`) | 회전 이벤트 생성 |
| 회전 이벤트 | `onTBTInfo`의 회전 지점이 60 m 이내로 지나가면 `DrivingEvent(TURN, 방향)` | ⚠️ 차가 움직이지 않아 미검증 | 회전 전 감속 |
| 도로 제한속도 | `NaviHelper` `onCurrentRoadSpeedLimit` | ⚠️ 콜백 미수신 (위치 고정 때문으로 추정) | 제한속도 준수 |
| 핸들 각도 | `vehicle.getSteeringWheel()` → `registerSteeringWheelAngle` (도, 콘솔 부호는 반대) | ✅ 에뮬레이터 확인 | 커브 속도 조절 |
| 앞차 거리 | 🔧 Vehicle 서비스 직접 구독 `ADAPTIVE_CRUISE_CONTROL_LEAD_VEHICLE_MEASURED_DISTANCE` (INT32, mm) | ✅ 값 수신 (에뮬레이터 기본 100000 = 100 m). ⚠️ 실차에서는 크루즈가 앞차를 잴 때만 값이 올 것으로 추정(미확인) | 앞차 거리 |
| 차선 변경 | 없음 | ❌ | 차선 변경 지시등 → 평가 불가 처리 |
| 연비·전비 | 미연결 | ❌ | 효율적 운전 영역 → 평가 불가 |

## 4. 공개 SDK 한계 (중요)

- Vehicle SDK 2.3.2 공개 API에는 **차속이 없다**. 그래서 서비스에 직접 바인드하는 🔧 `RawSpeedProbe`를 쓴다.
  - 바인드: `ComponentName("ai.pleos.playground.service.vehicle", "ai.pleos.playground.service.vehicle.VehicleService")`, action `ai.pleos.playground.vehicle.VEHICLE_START`
  - 구독 콜백은 다른 속성 이벤트도 같이 받으므로 `prop == "PERF_VEHICLE_SPEED"`만 거른다.
  - **공모전 기획서에 비공식 경로 사용을 명시해야 한다** (SDK 사용이 심사 항목).
- AAOS `CarPropertyManager`는 앱에 속성 목록을 비워 줘서 `PERF_VEHICLE_SPEED`·앞차 거리 등록이 모두 실패한다 (표준 속성은 시스템 서명 권한이 필요하고 앱에는 부여되지 않음). 같은 이름의 속성을 Vehicle 서비스 직접 구독으로는 받을 수 있다.
- Pleos 플랫폼에는 `ai.pleos.playground.service.adas` 서비스와 `ADAS_TRACKED_OBJECT`·`ADAS_DRIVING_WARN` 권한이 있으나 공개 문서·SDK는 없다. 쓰려면 Pleos 확인이 필요하다.
- 에뮬레이터의 외부 카메라(`ai.umos.car.evs`, AAOS EVS)는 전방·후방·좌·우 화면 **미리보기만** 하는 시스템 앱이다. 녹화 기능은 없고, 앱이 카메라 프레임을 받으려면 시스템 서명 권한(`USE_CAR_EVS_CAMERA`)이 필요해 일반 앱은 쓸 수 없다.
- FusedLocation 1.1.3에는 속도 필드가 없다 (속도 용도로 쓰지 않음).

## 5. 에뮬레이터에서 값을 만들 수 있는 방법

- 가상 콘솔: `adb forward tcp:8088 tcp:8088` 후 http://127.0.0.1:8088
  - Motion: 기어, 브레이크, 주행거리, 조향각. 액셀은 `button.pedal`을 누르고 있는 동안 가속.
  - ADAS: 크루즈 상태·목표 속도만 있음. **앞차 거리 카드는 없어서 값을 바꿀 수 없다** (차량 속성에는 있으며 기본값만 나온다).
  - 속도·브레이크·조향각은 `PUT /vehicle/controls?speed_kph=..&brake_pct=..&steering_deg=..` (정수만). 값을 한 번 넣으면 콘솔이 관성으로 줄이므로 유지하려면 계속 다시 넣는다. 콘솔은 웹 화면의 세션(`POST /browser/session`)이 끊기면 `web-deactivation`으로 꺼져 503을 준다. 웹 화면을 열어 둔 채로는 화면이 자체 감속을 보내 값이 섞인다.
- `adb emu geo fix <lon> <lat>`: Pleos FusedLocation만 바뀌고 내비 엔진 위치는 고정이다.
- 내비 경로 모의 주행은 찾지 못했다. 회전·제한속도는 실주행 또는 대회 측 문의가 필요하다.

## 6. 협업 시 합치는 지점

점수 쪽이 노출하는 인터페이스. 아바타·음성 담당은 아래만 보면 된다.

```kotlin
// 입력: 1초마다 한 번 만든 차량 상태 (null = 미수신, 만점/0점으로 취급하지 않음)
PleosSignalSource(context).start()
val sample: VehicleSample = source.snapshot()
val events: List<DrivingEvent> = source.events()

// 평가
val report: ScoreReport = ScoreEngine().evaluate(samples, events)
report.total        // 0..100 또는 null(평가 불가)
report.coverage     // 평가 범위 0..1 (낮으면 신뢰 낮음)
report.windowOverall // 1분 구간별 점수
report.events       // 급가속·급제동 등 감지 목록 (시각 + 라벨)

// 감정 (아바타 표정용)
val emotion: Emotion = engine.emotion(report, finished)
// NEUTRAL / WORRY / RELIEF / JOY, 각각 label·face·line(기본 멘트) 포함
```

| 담당 | 필요한 입력 | 우리가 주는 것 |
|---|---|---|
| 아바타 | 현재 감정 | `Emotion` |
| TTS | 말할 문장 | `Emotion.line`, `report.events`의 라벨 |
| STT | (우리 쪽 사용 안 함) | 대화 결과를 점수에 반영할 계획 없음 |

## 7. 아직 안 된 것 / 합치기 전에 결정할 것

- 엑셀 관련 항목(브레이크·엑셀 동시, 주차·중립 중 엑셀), 추월 가속, 졸음·휴식, 사이드미러 접힘(SDK에 SideMirror API 있음), 연비·전비.
- 도로 유형(고속도로/일반) 선택 UI. 엔진은 지원한다.
- 급가속 기준값은 임시값이다. 한 번의 가속에 여러 건이 잡히는 문제가 있어 조정이 필요하다.
- 샘플링 주기 1초는 계기판보다 늦다. 0.2~0.5초로 줄일 예정.
- 눈티 상황별 멘트와 주행 종료 후기.
- release APK(`apk/팀명_앱이름_release.apk`)와 README 최종본.
