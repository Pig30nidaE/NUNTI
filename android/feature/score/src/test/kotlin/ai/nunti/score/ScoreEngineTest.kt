package ai.nunti.score

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ScoreEngineTest {
    private val engine = ScoreEngine()
    private val belted = SeatState(true, true)

    private fun item(r: ScoreReport, i: Item) = r.items.first { it.item == i }

    @Test
    fun missingSignalsAreNotEvaluated() {
        val samples = (0..120).map { VehicleSample(it * 1000L) }
        val r = engine.evaluate(samples, emptyList())
        assertNull(r.total)
        assertEquals(0f, r.coverage, 0f)
        assertTrue(r.items.all { it.score == null })
    }

    @Test
    fun emptySeatAndUnknownBeltAreNotPenalized() {
        val samples = (0..60).map {
            VehicleSample(it * 1000L, speedKmh = 60f, driverSeat = belted, passengerSeat = SeatState(false, null))
        }
        assertEquals(100f, item(engine.evaluate(samples, emptyList()), Item.SEATBELT).score!!, 0.01f)

        val unknown = (0..60).map {
            VehicleSample(it * 1000L, speedKmh = 60f, passengerSeat = SeatState(true, null))
        }
        assertNull(item(engine.evaluate(unknown, emptyList()), Item.SEATBELT).score)
    }

    @Test
    fun recoveryAveragesOverValidTime() {
        // 첫 1분은 18초 미착용(70점), 이후 9분은 정상 → 문서 예시와 같은 97점
        val samples = (0..600).map {
            VehicleSample(
                it * 1000L, speedKmh = 60f, driverSeat = belted,
                passengerSeat = SeatState(true, buckled = !(it < 18)),
            )
        }
        val s = item(engine.evaluate(samples, emptyList()), Item.SEATBELT)
        assertEquals(70f, s.windowScores.first()!!, 1f)
        assertEquals(97f, s.score!!, 1f)
    }

    @Test
    fun hardBrakeIsCountedOnceAndLabelledAsBrake() {
        val samples = (0..120).map { t ->
            val speed = when {
                t < 60 -> 80f
                t in 60..62 -> 80f - (t - 59) * 20f
                else -> 20f
            }
            VehicleSample(t * 1000L, speedKmh = speed, brakePressed = t in 60..62)
        }
        val r = engine.evaluate(samples, emptyList())
        assertEquals(listOf("급제동"), r.events.map { it.label })
        assertNotNull(item(r, Item.ACCEL_DECEL).score)
        assertTrue(item(r, Item.ACCEL_DECEL).score!! < 100f)
    }

    @Test
    fun onlyEvaluableAreasAreRenormalized() {
        val samples = (0..60).map { VehicleSample(it * 1000L, speedKmh = 60f, driverSeat = belted, doorOpen = false) }
        val r = engine.evaluate(samples, emptyList())
        assertEquals(100f, r.total!!, 0.01f)
        // 속도만 있어도 제어(35) 영역의 급가속 항목은 평가되므로 제어 35 + 안전 20
        assertEquals(0.55f, r.coverage, 0.001f)
    }

    @Test
    fun turnWithoutSlowingScoresZeroButNoOpportunityIsNull() {
        val samples = (0..30).map { VehicleSample(it * 1000L, speedKmh = 60f) }
        val none = engine.evaluate(samples, emptyList())
        assertNull(item(none, Item.TURN_DECEL).score)

        val turn = engine.evaluate(samples, listOf(DrivingEvent(20_000, DrivingEvent.Kind.TURN, TurnSignal.RIGHT)))
        assertEquals(0f, item(turn, Item.TURN_DECEL).score!!, 0f)
    }

    @Test
    fun scenariosBehaveAsDesigned() {
        val calm = Scenarios.calm.let { engine.evaluate(it.samples, it.events) }
        assertTrue(calm.total!! >= 90f)

        val rec = Scenarios.recovery.let { engine.evaluate(it.samples, it.events) }
        assertTrue(rec.windowOverall.filterNotNull().any { it < 90f })
        assertEquals(Emotion.RELIEF, engine.emotion(rec, finished = true))

        val sparse = Scenarios.sparse.let { engine.evaluate(it.samples, it.events) }
        assertEquals(0.35f, sparse.coverage, 0.001f)
    }

    private fun gearSamples(range: IntRange, gear: (Int) -> Gear, speed: (Int) -> Float, lead: Float? = null, limit: Int? = null) =
        range.map { VehicleSample(it * 1000L, speedKmh = speed(it), gear = gear(it), leadDistanceM = lead, speedLimitKmh = limit) }

    @Test
    fun reverseItemExplainsWhyItIsEmpty() {
        val noGear = engine.evaluate((0..30).map { VehicleSample(it * 1000L, speedKmh = 40f) }, emptyList())
        assertEquals(Basis(BasisKind.NOT_CONNECTED), item(noGear, Item.REVERSE_SPEED).basis)
        assertTrue(noGear.gears.isEmpty())

        val forwardOnly = engine.evaluate(gearSamples(0..30, { Gear.D }, { 40f }), emptyList())
        assertEquals(Basis(BasisKind.REVERSE_UNUSED), item(forwardOnly, Item.REVERSE_SPEED).basis)
        assertNull(item(forwardOnly, Item.REVERSE_SPEED).score)
    }

    @Test
    fun reverseTooFastIsDetectedOncePerCrossingAndScoredEvenWhenShort() {
        // D 10초 → R 5초(느림) → D 5초 → R 4초(빠름). 느린 후진은 사건이 아니고, 빠른 후진은 넘은 순간 한 번만 남는다.
        val g = { t: Int -> if (t in 10..14 || t in 20..23) Gear.R else Gear.D }
        val v = { t: Int -> if (t in 20..23) 15f else if (g(t) == Gear.R) 4f else 30f }
        val r = engine.evaluate(gearSamples(0..30, g, v), emptyList())
        assertEquals(
            listOf(20_000L to DetectedEvent.Kind.REVERSE_TOO_FAST),
            r.events.filter { it.kind == DetectedEvent.Kind.REVERSE_TOO_FAST }.map { it.tMs to it.kind },
        )
        val rev = item(r, Item.REVERSE_SPEED)
        assertEquals(Basis(BasisKind.REVERSE_SECONDS, 9), rev.basis)
        assertTrue(rev.score!! in 1f..99f) // 느린 구간 만점 + 빠른 구간 감점
        assertEquals(9, r.gears.first { it.gear == Gear.R }.seconds)
    }

    @Test
    fun reversingIsNotJudgedByForwardRules() {
        // 후진 중 속도 -12 km/h(음수), 앞 장애물 1m, 제한속도 5 → 전진 규칙으로는 심한 감점이지만 평가하지 않는다.
        val r = engine.evaluate(gearSamples(0..30, { Gear.R }, { -12f }, lead = 1f, limit = 5), emptyList())
        assertNull(item(r, Item.LEAD_GAP).score)
        assertNull(item(r, Item.SPEED_LIMIT).score)
        assertTrue(r.events.none { it.kind != DetectedEvent.Kind.REVERSE_TOO_FAST }) // 음수 속도가 급감속으로 오인되지 않는다 (12km/h 후진 자체는 과속)
    }

    @Test
    fun parkingScenarioClassifiesByGear() {
        val r = Scenarios.parking.let { engine.evaluate(it.samples, it.events) }
        assertTrue(r.gears.first { it.gear == Gear.R }.seconds > 0)
        assertTrue(r.gears.first { it.gear == Gear.P }.seconds > 0)
        assertEquals(1, r.events.count { it.kind == DetectedEvent.Kind.REVERSE_TOO_FAST }) // 한 번 8km/h 를 넘긴다
        assertNotNull(item(r, Item.REVERSE_SPEED).score)
    }

    private fun curveSamples(entry: Float, inCurve: Float, steer: Float = 50f, gear: Gear = Gear.D) = (0..40).map { t ->
        val inside = t in 20..26
        VehicleSample(
            t * 1000L, speedKmh = if (inside) inCurve else if (t in 15..19) (entry + inCurve) / 2 else entry,
            gear = gear, steeringDeg = if (inside) steer else 0f,
        )
    }

    private fun withLimit(samples: List<VehicleSample>, limit: Int) = samples.map { it.copy(speedLimitKmh = limit) }

    @Test
    fun slowingToTheLimitInACurveEarnsABonusButDangerStaysAnEvent() {
        // 커브를 돌기엔 빠르지만(62 km/h) 제한속도(70) 안: 가점은 받되 커브 과속 사건은 남는다
        val fast = curveSamples(entry = 62f, inCurve = 62f)
        val raw = item(engine.evaluate(fast, emptyList()), Item.CURVE_SPEED).score!!
        val legal = engine.evaluate(withLimit(fast, 70), emptyList())
        assertEquals(raw + 20f, item(legal, Item.CURVE_SPEED).score!!, 0.5f)
        assertEquals(1, legal.events.count { it.kind == DetectedEvent.Kind.CURVE_TOO_FAST })

        // 제한속도(50)보다 빠르면 가점이 없다
        val over = engine.evaluate(withLimit(fast, 50), emptyList())
        assertEquals(raw, item(over, Item.CURVE_SPEED).score!!, 0.5f)
    }

    @Test
    fun reverseCountsByItsShareOfTheDriveNotAsHalfTheArea() {
        // 10분 거친 주행 + 2초 천천히 후진: 후진 100점이 거친 주행을 가리면 안 된다
        val rough = (0..600).map { VehicleSample(it * 1000L, speedKmh = if (it % 20 < 2) 20f else 60f, gear = Gear.D) }
        val park = (601..604).map { VehicleSample(it * 1000L, speedKmh = 4f, gear = Gear.R) }
        val alone = engine.evaluate(rough, emptyList())
        val withPark = engine.evaluate(rough + park, emptyList())
        val control = { r: ScoreReport -> r.areas.first { it.area == Area.CONTROL }.score!! }
        assertEquals(100f, item(withPark, Item.REVERSE_SPEED).score!!, 0.1f)
        assertTrue(control(alone) < 90f)
        assertEquals(control(alone), control(withPark), 1f)
    }

    @Test
    fun slowingIntoACurveScoresWellAndCarryingSpeedDoesNot() {
        val slowed = engine.evaluate(curveSamples(entry = 60f, inCurve = 35f), emptyList())
        assertTrue(item(slowed, Item.CURVE_SPEED).score!! >= 80f)
        assertEquals(Basis(BasisKind.OPPORTUNITIES, 1), item(slowed, Item.CURVE_SPEED).basis)
        assertTrue(slowed.events.none { it.kind == DetectedEvent.Kind.CURVE_TOO_FAST })

        val fast = engine.evaluate(curveSamples(entry = 65f, inCurve = 65f), emptyList())
        assertTrue(item(fast, Item.CURVE_SPEED).score!! < 50f)
        assertEquals(1, fast.events.count { it.kind == DetectedEvent.Kind.CURVE_TOO_FAST })
    }

    private fun drive(n: Int = 40, f: (Int) -> VehicleSample) = engine.evaluate((0..n).map(f), emptyList())

    @Test
    fun efficiencyScoresTripEfficiencyAndNeedsMovementAndSignal() {
        val good = drive { VehicleSample(it * 1000L, speedKmh = 50f, evEfficiencyKmPerKwh = 6f) }
        val poor = drive { VehicleSample(it * 1000L, speedKmh = 50f, evEfficiencyKmPerKwh = 3f) }
        val mid = drive { VehicleSample(it * 1000L, speedKmh = 50f, evEfficiencyKmPerKwh = 4.5f) }
        assertEquals(100f, item(good, Item.EFFICIENCY).score!!, 0.1f)
        assertEquals(0f, item(poor, Item.EFFICIENCY).score!!, 0.1f)
        assertEquals(50f, item(mid, Item.EFFICIENCY).score!!, 0.1f)
        assertNull(item(drive { VehicleSample(it * 1000L, speedKmh = 50f) }, Item.EFFICIENCY).score)
        assertNull(item(drive { VehicleSample(it * 1000L, speedKmh = 0f, evEfficiencyKmPerKwh = 6f) }, Item.EFFICIENCY).score)
    }

    @Test
    fun overSpeedWarningStandsInForNaviSpeedLimit() {
        val warned = drive { VehicleSample(it * 1000L, speedKmh = 100f, overSpeedWarning = it > 20) }
        val clean = drive { VehicleSample(it * 1000L, speedKmh = 100f, overSpeedWarning = false) }
        assertTrue(item(warned, Item.SPEED_LIMIT).score!! < 70f)
        assertEquals(100f, item(clean, Item.SPEED_LIMIT).score!!, 0.1f)
        // 내비 제한속도가 있으면 그쪽이 우선한다
        val navi = drive { VehicleSample(it * 1000L, speedKmh = 100f, speedLimitKmh = 100, overSpeedWarning = true) }
        assertEquals(100f, item(navi, Item.SPEED_LIMIT).score!!, 0.1f)
    }

    @Test
    fun stoppedTimeDoesNotDiluteSpeedingOrHarshAccel() {
        // 20초 과속 + 10분 정차: 정차 시간이 감점을 묽히면 안 된다
        val speeding = (0..20).map { VehicleSample(it * 1000L, speedKmh = 100f, speedLimitKmh = 60) }
        val parked = (21..620).map { VehicleSample(it * 1000L, speedKmh = 0f, speedLimitKmh = 60) }
        assertEquals(0f, item(engine.evaluate(speeding + parked, emptyList()), Item.SPEED_LIMIT).score!!, 0.1f)

        // 10분 신호 대기 뒤 급출발: 대기 시간이 급가속 감점을 묽히면 안 된다
        fun launch(from: Int) = (from..from + 20).map { VehicleSample(it * 1000L, speedKmh = if (it < from + 2) 0f else 50f) }
        val idle = (0 until 600).map { VehicleSample(it * 1000L, speedKmh = 0f) }
        val alone = item(engine.evaluate(launch(0), emptyList()), Item.ACCEL_DECEL).score!!
        val afterIdle = item(engine.evaluate(idle + launch(600), emptyList()), Item.ACCEL_DECEL).score!!
        assertTrue(alone < 100f)
        assertEquals(alone, afterIdle, 1f)
    }

    @Test
    fun zeroLeadDistanceMeansNoTargetNotTailgating() {
        val none = drive { VehicleSample(it * 1000L, speedKmh = 50f, leadDistanceM = 0f) }
        assertNull(item(none, Item.LEAD_GAP).score)
    }

    @Test
    fun notConnectedAndNotApplicableAreDifferentReasons() {
        val kind = { r: ScoreReport, i: Item -> item(r, i).basis.kind }
        // 낮 주행: 밤 신호·전조등은 받았지만 밤이 아니다 → 해당 상황 없음. 전비는 한 번도 안 왔다 → 미연동
        val day = drive { VehicleSample(it * 1000L, speedKmh = 50f, isNight = false, headlightOn = false, steeringDeg = 0f) }
        assertEquals(BasisKind.NOT_APPLICABLE, kind(day, Item.HEADLIGHT))
        assertEquals(BasisKind.NOT_APPLICABLE, kind(day, Item.CURVE_SPEED)) // 핸들 신호는 있는데 커브가 없었다
        assertEquals(BasisKind.NOT_CONNECTED, kind(day, Item.EFFICIENCY))
        assertEquals(BasisKind.NOT_CONNECTED, kind(day, Item.LANE_SIGNAL))
        assertTrue(Item.EFFICIENCY in day.notConnected && Item.HEADLIGHT !in day.notConnected)

        // 내비가 연결돼 있으면 회전이 없던 것은 해당 상황 없음, 연결이 없으면 미연동
        val naviOn = drive { VehicleSample(it * 1000L, speedKmh = 50f, naviConnected = true) }
        assertEquals(BasisKind.NOT_APPLICABLE, kind(naviOn, Item.TURN_DECEL))
        assertEquals(BasisKind.NOT_CONNECTED, kind(day, Item.TURN_DECEL))

        // 정차만 했다: 벨트 신호는 있지만 주행이 없어 평가할 상황이 아니다
        val parked = drive { VehicleSample(it * 1000L, speedKmh = 0f, driverSeat = SeatState(true, true)) }
        assertEquals(BasisKind.NOT_APPLICABLE, kind(parked, Item.SEATBELT))
    }

    @Test
    fun parkingManeuversWithFullLockAreNeverSharpTurns() {
        val lot = (0..40).map { VehicleSample(it * 1000L, speedKmh = 8f, steeringDeg = 540f, gear = Gear.D) }
        val r = engine.evaluate(lot, emptyList())
        assertNull(item(r, Item.CURVE_SPEED).score)
        assertTrue(r.events.none { it.kind == DetectedEvent.Kind.CURVE_TOO_FAST })
    }

    @Test
    fun curveNeedsSteeringSignalSustainedSpeedAndForwardGear() {
        val noSteering = engine.evaluate(curveSamples(60f, 60f).map { it.copy(steeringDeg = null) }, emptyList())
        assertNull(item(noSteering, Item.CURVE_SPEED).score) // 핸들 신호가 없으면 평가하지 않는다

        val reversing = engine.evaluate(curveSamples(60f, 60f, gear = Gear.R), emptyList())
        assertNull(item(reversing, Item.CURVE_SPEED).score)

        val slow = engine.evaluate(curveSamples(25f, 25f), emptyList()) // 30km/h 미만은 커브로 보지 않는다
        assertNull(item(slow, Item.CURVE_SPEED).score)

        val brief = engine.evaluate(
            (0..40).map { VehicleSample(it * 1000L, speedKmh = 60f, steeringDeg = if (it == 20) 60f else 0f) },
            emptyList(),
        )
        assertNull(item(brief, Item.CURVE_SPEED).score) // 한두 순간의 핸들 움직임은 커브가 아니다
    }

    @Test
    fun curveScenarioHasOneGoodAndOneFastCurve() {
        val r = Scenarios.curves.let { engine.evaluate(it.samples, it.events) }
        assertEquals(Basis(BasisKind.OPPORTUNITIES, 2), item(r, Item.CURVE_SPEED).basis)
        assertEquals(1, r.events.count { it.kind == DetectedEvent.Kind.CURVE_TOO_FAST })
        assertEquals(250_000L, r.events.first { it.kind == DetectedEvent.Kind.CURVE_TOO_FAST }.tMs)
    }

    private fun hardAccels(r: ScoreReport) = r.events.count { it.kind == DetectedEvent.Kind.HARD_ACCEL }

    @Test
    fun pullingAwayFromStandstillIsNotHardAccelButTheSameJumpAtSpeedIs() {
        // 같은 14 km/h 증가: 정차에서 출발하면 보통의 출발, 50 km/h 에서 붙으면 급가속
        val fromStop = (0..40).map { t -> VehicleSample(t * 1000L, speedKmh = if (t < 20) 0f else 14f) }
        val atSpeed = (0..40).map { t -> VehicleSample(t * 1000L, speedKmh = if (t < 20) 50f else 64f) }
        assertEquals(0, hardAccels(engine.evaluate(fromStop, emptyList())))
        assertEquals(1, hardAccels(engine.evaluate(atSpeed, emptyList())))
    }

    @Test
    fun aViolentLaunchIsStillHardAccel() {
        val violent = (0..40).map { t -> VehicleSample(t * 1000L, speedKmh = if (t < 20) 0f else 30f) } // 한 번에 +30
        assertEquals(1, hardAccels(engine.evaluate(violent, emptyList())))
    }
}
