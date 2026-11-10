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
    /** 핸들 각도(도, +오른쪽/-왼쪽). 커브 판정에 쓴다. null = 미수신 → 커브 평가 안 함. */
    val steeringDeg: Float? = null,
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
    val curveMinKmh: Float = 20f,
    val curveEntryLookbackMs: Long = 5_000,
    /** 커브 안의 최저 속도가 진입 속도의 이 비율 이하면 "줄였다"고 본다. */
    val curveSlowRatio: Float = 0.9f,
    /** 횡가속도 한도(m/s²). 이 이하면 쾌적한 커브, 넘으면 속도를 못 줄인 것으로 감점한다. */
    val curveComfortLatAccel: Float = 2.5f,
    /** 조향비(핸들각 ÷ 바퀴각)와 축거(m): 핸들각으로 횡가속도를 어림하는 상수. 차종 값 확인 전 초안. */
    val steeringRatio: Float = 15f,
    val wheelbaseM: Float = 2.9f,
)

/** 점수 엔진이 찾아낸 순간 사건. 종류는 [kind] 로 구분하고, 화면에 보이는 한글 이름은 [label] 이다. */
data class DetectedEvent(val tMs: Long, val kind: Kind) {
    enum class Kind(val label: String) {
        HARD_ACCEL("급가속"),
        HARD_DECEL("급감속"),
        HARD_BRAKE("급제동"),
        /** 기어를 후진(R)에 넣은 순간. 감점 사건이 아니라 "지금 후진 중" 을 알리는 안내다. */
        REVERSE_ENGAGED("후진 기어"),
        /** 커브에서 속도를 줄이지 못해 횡가속도가 한도를 크게 넘은 순간. */
        CURVE_TOO_FAST("커브 과속"),
    }
    val label: String get() = kind.label
}

/** 항목 점수의 근거. 종류는 enum, 화면 글귀는 [text] 이고 [amount] 는 초/횟수다. */
enum class BasisKind {
    NO_SIGNAL, TOO_FEW, VALID_SECONDS, OPPORTUNITIES, NO_GEAR_SIGNAL, REVERSE_UNUSED, REVERSE_SECONDS,
}

data class Basis(val kind: BasisKind, val amount: Int = 0) {
    val text: String
        get() = when (kind) {
            BasisKind.NO_SIGNAL -> "수신 없음"
            BasisKind.TOO_FEW -> "표본 부족"
            BasisKind.VALID_SECONDS -> "유효 ${amount}초"
            BasisKind.OPPORTUNITIES -> "기회 ${amount}회"
            BasisKind.NO_GEAR_SIGNAL -> "기어 신호 없음"
            BasisKind.REVERSE_UNUSED -> "후진 기어 안 씀"
            BasisKind.REVERSE_SECONDS -> "후진 ${amount}초"
        }
}

data class ItemResult(
    val item: Item,
    val score: Float?,
    val basis: Basis,
    val windowScores: List<Float?>,
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
)

enum class Emotion(val label: String, val face: String, val line: String) {
    NEUTRAL("중립", "🙂", "함께 살펴보고 있어요."),
    WORRY("걱정", "😟", "앗, 조금 걱정돼요. 천천히 가요."),
    RELIEF("안도", "😮‍💨", "휴, 이제 좀 안심돼요."),
    JOY("기쁨", "😄", "오늘 편안하게 달려서 좋았어요!"),
}
