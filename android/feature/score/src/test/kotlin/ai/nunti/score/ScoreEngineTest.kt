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
}
