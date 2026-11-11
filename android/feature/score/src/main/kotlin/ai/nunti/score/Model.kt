package ai.nunti.score

enum class RoadType { HIGHWAY, GENERAL }
enum class Gear { P, R, N, D }
enum class TurnSignal { NONE, LEFT, RIGHT }

/** occupied/buckled 가 null 이면 "수신 안 됨" 이다. 빈 좌석·미수신을 미착용으로 보지 않는다. */
data class SeatState(val occupied: Boolean?, val buckled: Boolean?)

/**
 * 한 시점의 차량 신호. 모든 신호는 nullable: null = 미수신/미지원이며 정상(만점)도 0점도 아니다.
 * headlightOn 은 AUTO 설정이 아니라 실제 점등 상태.
 */
data class VehicleSample(
    val tMs: Long,
    val speedKmh: Float? = null,
    val brakePressed: Boolean? = null,
    val gear: Gear? = null,
    val turnSignal: TurnSignal? = null,
    val driverSeat: SeatState? = null,
    val passengerSeat: SeatState? = null,
    val doorOpen: Boolean? = null,
    val headlightOn: Boolean? = null,
    val isNight: Boolean? = null,
    val leadDistanceM: Float? = null,
    /** 내비가 알려 주는 현재 도로 제한속도 (km/h). null = 정보 없음 → 평가하지 않는다. */
    val speedLimitKmh: Int? = null,
    val roadType: RoadType = RoadType.GENERAL,
    /** 내비 연결 여부. null = 내비 미연결 → 회전 이벤트가 없어도 "기회 없음"이 아니라 미연동으로 본다. */
    val naviConnected: Boolean? = null,
    /** 핸들 각도(도, +오른쪽/-왼쪽). 커브 판정에 쓴다. null = 미수신 → 커브 평가 안 함. */
    val steeringDeg: Float? = null,
    /** 계기판 과속 경고등(OVER_SPEED). 내비 제한속도가 없을 때 대신 쓴다. */
    val overSpeedWarning: Boolean? = null,
    /** 이번 주행 평균 전비(km/kWh, 클수록 좋음). 단위는 문서에 없어 가정이다. */
    val evEfficiencyKmPerKwh: Float? = null,
)

/** 기회 기반 평가(회전 전 감속, 차선 변경 지시등)를 위한 실제 행동 이벤트. */
data class DrivingEvent(val tMs: Long, val kind: Kind, val direction: TurnSignal) {
    enum class Kind { TURN, LANE_CHANGE }
}

enum class Area(val label: String, val maxPoints: Int) {
    CONTROL("속도·차량 제어", 35),
    SURROUND("주변 상황 대응", 35),
    SAFETY("주행 안전 상태", 20),
    EFFICIENCY("효율적 운전", 10),
}

/**
 * [sharesDriveTime] 인 항목끼리는 영역 안에서 단순 평균하지 않고 각자 평가한 시간만큼 비중을 나눠 갖는다.
 * 후진처럼 잠깐 쓰는 항목이 몇 초만으로 전체 주행과 같은 비중을 갖지 않게 하기 위함이다.
 */
enum class Item(
    val label: String,
    val area: Area,
    val byOpportunity: Boolean = false,
    val sharesDriveTime: Boolean = false,
) {
    ACCEL_DECEL("급가속·급감속·급제동", Area.CONTROL, sharesDriveTime = true),
    REVERSE_SPEED("후진 속도", Area.CONTROL, sharesDriveTime = true),
    /** P단으로 바꾼 때마다 한 번의 기회: 완전히 멈춘 뒤였으면 100, 아직 굴러가고 있었으면 속도만큼 감점. */
    PARK_SHIFT("멈춘 뒤 P단", Area.CONTROL, byOpportunity = true),
    LEAD_GAP("앞차 거리", Area.SURROUND),
    SPEED_LIMIT("제한속도 준수", Area.SURROUND),
    TURN_DECEL("회전 전 감속", Area.SURROUND, byOpportunity = true),
    CURVE_SPEED("커브 속도 조절", Area.SURROUND, byOpportunity = true),
    LANE_SIGNAL("차선 변경 지시등", Area.SURROUND, byOpportunity = true),
    SEATBELT("안전벨트", Area.SAFETY),
    DOOR("주행 중 문 열림", Area.SAFETY),
    HEADLIGHT("야간 전조등", Area.SAFETY),
    EFFICIENCY("연비·전비", Area.EFFICIENCY),
}

/** 모든 수치는 논의용 초안(placeholder)이며 확정 기준이 아니다. */
data class ScoreConfig(
    val windowMs: Long = 60_000,
    val maxGapMs: Long = 2_000,
    val minValidSec: Double = 10.0,
    val movingKmh: Float = 5f,
    val harshAccelGeneral: Float = 10f, // km/h per s
    val harshAccelHighway: Float = 7f,
    /** 이 속도(km/h) 미만에서 시작한 가속은 출발로 보고 더 높은 기준을 쓴다 (초안). */
    val launchSpeedKmh: Float = 20f,
    val harshAccelLaunch: Float = 15f, // km/h per s
    val harshDecelGeneral: Float = 12f,
    val harshDecelHighway: Float = 9f,
    val reverseOkKmh: Float = 8f,
    /** P단으로 바꾼 순간 속도가 이 값(km/h) 이하면 멈춘 것으로 본다 (속도 센서 떨림 여유, 초안). */
    val parkShiftOkKmh: Float = 1f,
    /** 그보다 빠르면 1km/h 마다 이만큼 감점한다 (초안: 6km/h 이상이면 0점). */
    val parkShiftPenaltyPerKmh: Float = 20f,
    val overLimitToleranceKmh: Float = 5f,
    val overLimitPenaltyPerKmh: Float = 4f,
    val gapFullSec: Float = 2.0f,
    val gapZeroSec: Float = 0.5f,
    val turnDecelRatio: Float = 0.85f,
    val turnLowSpeedKmh: Float = 20f,
    val turnLookbackMs: Long = 5_000,
    val laneSignalLookbackMs: Long = 3_000,
    // 커브: 핸들을 curveSteeringDeg 이상 curveMinHoldMs 동안 유지하면 한 번의 커브(평가 기회)로 본다.
    val curveSteeringDeg: Float = 40f,
    val curveMinHoldMs: Long = 2_000,
    val curveMinKmh: Float = 30f,
    /** 횡가속도 한도(m/s²). 이 이하면 쾌적한 커브, 넘으면 속도를 못 줄인 것으로 감점한다. */
    val curveComfortLatAccel: Float = 2.5f,
    /** 조향비(핸들각 ÷ 바퀴각)와 축거(m): 핸들각으로 횡가속도를 어림하는 상수. 차종 값 확인 전 초안. */
    val steeringRatio: Float = 15f,
    val wheelbaseM: Float = 2.9f,
    /** 커브 안에서 제한속도 이하로 줄였으면 주는 가점. 제한속도를 모르면 가점 없음. */
    val curveWithinLimitBonus: Float = 20f,
    /** 전비(km/kWh) 점수: poor 이하 0점, good 이상 100점, 사이는 직선. 차종 값 확인 전 초안. */
    val efficiencyPoorKmPerKwh: Float = 3f,
    val efficiencyGoodKmPerKwh: Float = 6f,
)

/** 점수 엔진이 찾아낸 순간 사건. 종류는 [kind] 로 구분하고, 화면에 보이는 한글 이름은 [label] 이다. */
data class DetectedEvent(val tMs: Long, val kind: Kind) {
    enum class Kind(val label: String) {
        HARD_ACCEL("급가속"),
        HARD_DECEL("급감속"),
        HARD_BRAKE("급제동"),
        /** 후진 중 속도가 [ScoreConfig.reverseOkKmh] 를 넘은 순간. 후진 속도 항목이 감점되기 시작하는 지점이다. */
        REVERSE_TOO_FAST("후진 과속"),
        /** 커브에서 속도를 줄이지 못해 횡가속도가 한도를 크게 넘은 순간. */
        CURVE_TOO_FAST("커브 과속"),
        /** 차가 아직 움직이는 중에 P단으로 바꾼 순간. 변속기에 무리가 가고 차가 덜컥 멈춘다. */
        PARK_WHILE_MOVING("움직이며 P단"),
    }
    val label: String get() = kind.label
}

/**
 * 평가하지 못한 이유를 둘로 나눈다. 둘을 섞으면 "되는 척"하는 항목과 진짜 해당 상황이 없던 항목을 구별할 수 없다.
 * - [NOT_CONNECTED]: 이 항목에 필요한 신호를 한 번도 받지 못했다 (기능 미연동·미지원).
 * - [NOT_APPLICABLE]: 신호는 받았지만 평가할 상황이 없었다 (낮이라 전조등, 커브 없음, 정차만 함 등).
 */
enum class Availability { EVALUATED, NOT_CONNECTED, NOT_APPLICABLE, TOO_FEW }

/** 항목 점수의 근거. 종류는 enum, 화면 글귀는 [text] 이고 [amount] 는 초/횟수다. */
enum class BasisKind(val availability: Availability) {
    NOT_CONNECTED(Availability.NOT_CONNECTED),
    NOT_APPLICABLE(Availability.NOT_APPLICABLE),
    REVERSE_UNUSED(Availability.NOT_APPLICABLE),
    TOO_FEW(Availability.TOO_FEW),
    VALID_SECONDS(Availability.EVALUATED),
    OPPORTUNITIES(Availability.EVALUATED),
    REVERSE_SECONDS(Availability.EVALUATED),
}

data class Basis(val kind: BasisKind, val amount: Int = 0) {
    val text: String
        get() = when (kind) {
            BasisKind.NOT_CONNECTED -> "미연동"
            BasisKind.NOT_APPLICABLE -> "해당 상황 없음"
            BasisKind.REVERSE_UNUSED -> "후진 기어 안 씀"
            BasisKind.TOO_FEW -> "표본 부족"
            BasisKind.VALID_SECONDS -> "유효 ${amount}초"
            BasisKind.OPPORTUNITIES -> "기회 ${amount}회"
            BasisKind.REVERSE_SECONDS -> "후진 ${amount}초"
        }
}

data class ItemResult(
    val item: Item,
    val score: Float?,
    val basis: Basis,
    val windowScores: List<Float?>,
    /** 평가에 쓰인 시간(초) 또는 기회 수. [Item.sharesDriveTime] 항목의 비중 계산에 쓴다. */
    val weight: Double = 0.0,
    val windowWeights: List<Double> = emptyList(),
)

data class AreaResult(val area: Area, val score: Float?, val points: Float?)

/** 기어별 유효 주행 시간(초). 신호가 끊긴 구간은 어느 기어에도 넣지 않는다. */
data class GearUsage(val gear: Gear, val seconds: Int)

data class ScoreReport(
    val total: Float?,
    /** 평가 가능한 영역의 배점 비율 (0..1). 낮으면 점수의 신뢰가 낮다. */
    val coverage: Float,
    val areas: List<AreaResult>,
    val items: List<ItemResult>,
    /** 구간별 종합 점수 (평가 가능 항목이 없으면 null). */
    val windowOverall: List<Float?>,
    val events: List<DetectedEvent>,
    /** 기어별 시간. 기어 신호를 한 번도 못 받았으면 빈 목록. */
    val gears: List<GearUsage> = emptyList(),
    /** 속도를 받은 유효 시간(초)과 그 중 실제로 움직인 시간(초). 종료해도 되는지(일시저장 여부) 판단에 쓴다. */
    val speedSeconds: Int = 0,
    val movingSeconds: Int = 0,
) {
    /** 신호를 한 번도 받지 못한 항목. 최종 보고서의 미연동 신호 목록에 쓴다. */
    val notConnected: List<Item> get() = items.filter { it.basis.kind.availability == Availability.NOT_CONNECTED }.map { it.item }
}

enum class Emotion(val label: String, val face: String, val line: String) {
    NEUTRAL("중립", "🙂", "함께 살펴보고 있어요."),
    WORRY("걱정", "😟", "앗, 조금 걱정돼요. 천천히 가요."),
    RELIEF("안도", "😮‍💨", "휴, 이제 좀 안심돼요."),
    JOY("기쁨", "😄", "오늘 편안하게 달려서 좋았어요!"),
}
