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

enum class Item(val label: String, val area: Area, val byOpportunity: Boolean = false) {
    ACCEL_DECEL("급가속·급감속·급제동", Area.CONTROL),
    REVERSE_SPEED("후진 속도", Area.CONTROL),
    LEAD_GAP("앞차 거리", Area.SURROUND),
    SPEED_LIMIT("제한속도 준수", Area.SURROUND),
    TURN_DECEL("회전 전 감속", Area.SURROUND, byOpportunity = true),
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
    val harshDecelGeneral: Float = 12f,
    val harshDecelHighway: Float = 9f,
    val reverseOkKmh: Float = 8f,
    val overLimitToleranceKmh: Float = 5f,
    val overLimitPenaltyPerKmh: Float = 4f,
    val gapFullSec: Float = 2.0f,
    val gapZeroSec: Float = 0.5f,
    val turnDecelRatio: Float = 0.85f,
    val turnLowSpeedKmh: Float = 20f,
    val turnLookbackMs: Long = 5_000,
    val laneSignalLookbackMs: Long = 3_000,
)

data class DetectedEvent(val tMs: Long, val label: String)

data class ItemResult(
    val item: Item,
    val score: Float?,
    val basis: String,
    val windowScores: List<Float?>,
)

data class AreaResult(val area: Area, val score: Float?, val points: Float?)

data class ScoreReport(
    val total: Float?,
    /** 평가 가능한 영역의 배점 비율 (0..1). 낮으면 점수의 신뢰가 낮다. */
    val coverage: Float,
    val areas: List<AreaResult>,
    val items: List<ItemResult>,
    /** 구간별 종합 점수 (평가 가능 항목이 없으면 null). */
    val windowOverall: List<Float?>,
    val events: List<DetectedEvent>,
)

enum class Emotion(val label: String, val face: String, val line: String) {
    NEUTRAL("중립", "🙂", "함께 살펴보고 있어요."),
    WORRY("걱정", "😟", "앗, 조금 걱정돼요. 천천히 가요."),
    RELIEF("안도", "😮‍💨", "휴, 이제 좀 안심돼요."),
    JOY("기쁨", "😄", "오늘 편안하게 달려서 좋았어요!"),
}
