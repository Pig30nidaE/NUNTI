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

    /** Short, labelled simulator trip covering acceleration, braking, steering and recovery. */
    val contextDrive = Scenario("구간별 운전 연습", (0..150).map { t ->
        val speed = when {
            t < 15 -> t*2f
            t < 30 -> 30f
            t == 30 -> 55f
            t < 45 -> 55f
            t == 45 -> 20f
            t < 60 -> 20f+(t-45)*2f
            t < 100 -> 50f
            t < 110 -> 50f-(t-100)*4f
            t < 140 -> 14f+(t-110).coerceAtMost(10)*2f
            else -> (34f-(t-140)*3.4f).coerceAtLeast(0f)
        }
        VehicleSample(t*1000L,speed,brakePressed=t==45||t>=140,gear=Gear.D,
            driverSeat=full,passengerSeat=SeatState(false,null),doorOpen=false,
            leadDistanceM=if(t in 40..55) 5f else 50f,speedLimitKmh=60,
            steeringDeg=when(t){60->160f;61->170f;62->170f;63->80f;else->0f})
    }, listOf(DrivingEvent(80_000,DrivingEvent.Kind.TURN,TurnSignal.RIGHT),
        DrivingEvent(108_000,DrivingEvent.Kind.TURN,TurnSignal.LEFT)))

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

    /** 주행 중 주차장에 들어가 후진 주차: 3분 P → D → 4분 R(느림 → 한 번 빠름) → P. 기어별 분류 확인용. */
    val parking = build("후진 주차") { t ->
        val gear = when {
            t < 20 -> Gear.P
            t < 300 -> Gear.D
            t < 305 -> Gear.N
            t < 335 -> Gear.R
            t < 345 -> Gear.D
            t < 360 -> Gear.R
            else -> Gear.P
        }
        val speed = when (gear) {
            Gear.D -> if (t < 300) cruise(t) * 0.5f else 4f
            Gear.R -> if (t in 350..352) 14f else 4f // 한 번은 후진 제한(8km/h)을 넘긴다
            else -> 0f
        }
        VehicleSample(
            tMs = t * 1000L, speedKmh = speed, brakePressed = false, gear = gear,
            driverSeat = full, passengerSeat = SeatState(false, null), doorOpen = false,
            leadDistanceM = if (gear == Gear.R) 1f else 40f,
        )
    }

    /** 커브 두 번: 1분 40초 커브는 미리 감속, 4분 10초 커브는 속도를 유지한 채 진입(커브 과속). */
    val curves = build("커브 주행") { t ->
        val smoothCurve = t in 100..108
        val fastCurve = t in 250..258
        val speed = when {
            t in 92..99 -> 60f - (t - 91) * 2.5f // 커브 전에 부드럽게 감속
            smoothCurve -> 38f
            t in 109..120 -> 38f + (t - 108) * 1.5f
            fastCurve -> 62f
            else -> 60f
        }
        VehicleSample(
            tMs = t * 1000L, speedKmh = speed, brakePressed = false, gear = Gear.D, turnSignal = TurnSignal.NONE,
            driverSeat = full, passengerSeat = SeatState(false, null), doorOpen = false,
            steeringDeg = when { smoothCurve -> 45f; fastCurve -> -50f; else -> 0f },
        )
    }

    val all = listOf(calm, recovery, unsafe, sparse, parking, curves)
}
