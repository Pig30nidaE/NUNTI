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
        assertEquals(Basis(BasisKind.NO_GEAR_SIGNAL), item(noGear, Item.REVERSE_SPEED).basis)
        assertTrue(noGear.gears.isEmpty())

        val forwardOnly = engine.evaluate(gearSamples(0..30, { Gear.D }, { 40f }), emptyList())
        assertEquals(Basis(BasisKind.REVERSE_UNUSED), item(forwardOnly, Item.REVERSE_SPEED).basis)
        assertNull(item(forwardOnly, Item.REVERSE_SPEED).score)
    }

    @Test
    fun reverseEngagedIsDetectedOncePerEntryAndScoredEvenWhenShort() {
        // D 10초 → R 5초(느림) → D 5초 → R 4초(빠름)
        val g = { t: Int -> if (t in 10..14 || t in 20..23) Gear.R else Gear.D }
        val v = { t: Int -> if (t in 20..23) 15f else if (g(t) == Gear.R) 4f else 30f }
        val r = engine.evaluate(gearSamples(0..30, g, v), emptyList())
        assertEquals(
            listOf(10_000L to DetectedEvent.Kind.REVERSE_ENGAGED, 20_000L to DetectedEvent.Kind.REVERSE_ENGAGED),
            r.events.filter { it.kind == DetectedEvent.Kind.REVERSE_ENGAGED }.map { it.tMs to it.kind },
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
        assertTrue(r.events.none { it.kind != DetectedEvent.Kind.REVERSE_ENGAGED }) // 음수 속도가 급감속으로 오인되지 않는다
    }

    @Test
    fun parkingScenarioClassifiesByGear() {
        val r = Scenarios.parking.let { engine.evaluate(it.samples, it.events) }
        assertTrue(r.gears.first { it.gear == Gear.R }.seconds > 0)
        assertTrue(r.gears.first { it.gear == Gear.P }.seconds > 0)
        assertEquals(2, r.events.count { it.kind == DetectedEvent.Kind.REVERSE_ENGAGED })
        assertNotNull(item(r, Item.REVERSE_SPEED).score)
    }

    private fun curveSamples(entry: Float, inCurve: Float, steer: Float = 50f, gear: Gear = Gear.D) = (0..40).map { t ->
        val inside = t in 20..26
        VehicleSample(
            t * 1000L, speedKmh = if (inside) inCurve else if (t in 15..19) (entry + inCurve) / 2 else entry,
            gear = gear, steeringDeg = if (inside) steer else 0f,
        )
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

    @Test
    fun curveNeedsSteeringSignalSustainedSpeedAndForwardGear() {
        val noSteering = engine.evaluate(curveSamples(60f, 60f).map { it.copy(steeringDeg = null) }, emptyList())
        assertNull(item(noSteering, Item.CURVE_SPEED).score) // 핸들 신호가 없으면 평가하지 않는다

        val reversing = engine.evaluate(curveSamples(60f, 60f, gear = Gear.R), emptyList())
        assertNull(item(reversing, Item.CURVE_SPEED).score)

        val slow = engine.evaluate(curveSamples(15f, 15f), emptyList()) // 20km/h 미만은 커브로 보지 않는다
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
