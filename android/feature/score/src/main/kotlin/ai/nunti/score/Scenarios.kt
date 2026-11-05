package ai.nunti.score

/**
 * 시연용 가상 주행 데이터. 실제 Pleos 수신값이 아니다 (UI에 "시연 데이터"로 표기).
 * 1초 간격, 8분 주행.
 */
class Scenario(val name: String, val samples: List<VehicleSample>, val events: List<DrivingEvent>)

object Scenarios {
    private const val DURATION_S = 480
    private val full = SeatState(occupied = true, buckled = true)

    private fun build(
        name: String,
        events: List<DrivingEvent> = emptyList(),
        sample: (t: Int) -> VehicleSample,
    ) = Scenario(name, (0..DURATION_S).map(sample), events)

    private fun cruise(t: Int) = 55f + 5f * kotlin.math.sin(t / 20f)

    val calm = build(
        "안정 주행",
        events = listOf(
            DrivingEvent(150_000, DrivingEvent.Kind.TURN, TurnSignal.RIGHT),
            DrivingEvent(300_000, DrivingEvent.Kind.LANE_CHANGE, TurnSignal.LEFT),
        ),
    ) { t ->
        val turning = t in 145..150
        val speed = if (turning) 55f - (t - 144) * 6f else cruise(t)
        VehicleSample(
            tMs = t * 1000L, speedKmh = speed, brakePressed = false, gear = Gear.D,
            turnSignal = when {
                turning -> TurnSignal.RIGHT
                t in 296..300 -> TurnSignal.LEFT
                else -> TurnSignal.NONE
            },
            driverSeat = full, passengerSeat = SeatState(false, null), doorOpen = false,
            isNight = true, headlightOn = true, leadDistanceM = 45f,
        )
    }

    /** 2분에 급제동, 3분까지 짧은 앞차 거리, 이후 안정 → 걱정 → 안도. */
    val recovery = build(
        "급제동 후 회복",
        events = listOf(DrivingEvent(360_000, DrivingEvent.Kind.TURN, TurnSignal.RIGHT)),
    ) { t ->
        val speed = when {
            t < 120 -> 70f
            t in 120..122 -> 70f - (t - 119) * 18f
            t in 123..140 -> 16f + (t - 122) * 3f
            else -> cruise(t)
        }
        val tight = t in 100..200
        VehicleSample(
            tMs = t * 1000L, speedKmh = speed,
            brakePressed = t in 120..122, gear = Gear.D, turnSignal = TurnSignal.NONE,
            driverSeat = full, passengerSeat = SeatState(false, null), doorOpen = false,
            isNight = false, leadDistanceM = if (tight) speed / 3.6f * 0.6f else 50f,
        )
    }

    /** 동승자 벨트 미착용 구간과 주행 중 문 열림, 차선 변경 시 지시등 누락. */
    val unsafe = build(
        "벨트·문·지시등",
        events = listOf(DrivingEvent(200_000, DrivingEvent.Kind.LANE_CHANGE, TurnSignal.RIGHT)),
    ) { t ->
        VehicleSample(
            tMs = t * 1000L, speedKmh = cruise(t), brakePressed = false, gear = Gear.D,
            turnSignal = TurnSignal.NONE,
            driverSeat = full,
            passengerSeat = SeatState(true, buckled = t >= 180),
            doorOpen = t in 60..75,
            isNight = true, headlightOn = t >= 240,
        )
    }

    /** 속도만 수신. 나머지는 평가 불가여야 하며 만점/0점이 되면 안 된다. */
    val sparse = build("데이터 부족") { t ->
        VehicleSample(tMs = t * 1000L, speedKmh = cruise(t))
    }

    val all = listOf(calm, recovery, unsafe, sparse)
}
