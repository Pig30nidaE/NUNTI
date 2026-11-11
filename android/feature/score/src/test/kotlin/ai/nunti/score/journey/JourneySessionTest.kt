package ai.nunti.score.journey

import ai.nunti.score.DrivingEvent
import ai.nunti.score.Emotion
import ai.nunti.score.Item
import ai.nunti.score.ScoreConfig
import ai.nunti.score.ScoreEngine
import ai.nunti.score.SeatState
import ai.nunti.score.TurnSignal
import ai.nunti.score.VehicleSample
import org.junit.Assert.*
import org.junit.Test

class JourneySessionTest {
    private fun session(id: String = "journey-1", config: ScoreConfig = ScoreConfig()) = JourneySession(
        id, "character-1", "route-1", JourneySource.LIVE, 1_000L, ScoreEngine(config),
    )

    private fun sample(t: Long, safe: Boolean = true) = VehicleSample(
        t, speedKmh = 60f, driverSeat = SeatState(true, safe), doorOpen = !safe,
    )

    @Test
    fun allMissingIsNeutralAndUnscoredIncludingFinalReport() {
        val journey = session()
        for (t in 0..20) journey.add(VehicleSample(t * 1000L))
        val current = journey.snapshot()
        assertNull(current.report.total)
        assertEquals(0f, current.report.coverage, 0f)
        assertTrue(current.report.items.all { it.score == null })
        assertEquals(Emotion.NEUTRAL, current.emotion)
        assertNull(current.feedback)
        val final = journey.finish()
        assertNull(final.report.total)
        assertEquals(Emotion.NEUTRAL, final.feedback?.kind)
        assertTrue(final.feedback!!.text.contains("정보가 부족"))
    }

    @Test
    fun finishAndLateCallbacksCannotCreateAnotherReportOrFeedback() {
        val journey = session()
        for (t in 0..15) journey.add(sample(t * 1000L))
        val final = journey.finish()
        assertTrue(final.finished)
        assertEquals(Emotion.JOY, final.emotion)
        assertEquals("journey-1:1", final.feedback?.key)
        assertSame(final, journey.finish())
        assertSame(final, journey.snapshot())
        assertSame(final, journey.add(sample(20_000, safe = false)))
        assertSame(final, journey.interrupt(30_000))
        assertEquals(16, final.sampleCount)
    }

    @Test
    fun interruptionPreservesUnknownTimeAndDoesNotInventHarshAcceleration() {
        val journey = session()
        journey.add(VehicleSample(0, speedKmh = 0f))
        journey.add(VehicleSample(1000, speedKmh = 0f))
        val paused = journey.interrupt(1500)
        assertNull(paused.currentSample)
        assertEquals(2, paused.sampleCount)
        assertEquals(1500L, paused.elapsedMs)
        journey.add(VehicleSample(120_000, speedKmh = 100f))
        val resumed = journey.add(VehicleSample(121_000, speedKmh = 100f))
        assertEquals(121_000L, resumed.elapsedMs)
        assertEquals(4, resumed.sampleCount)
        assertTrue(resumed.report.events.isEmpty())
        assertNull(resumed.report.total) // Only two seconds were observed; the pause adds none.
        assertEquals("표본 부족", resumed.report.items.first { it.item == Item.ACCEL_DECEL }.basis.text)
    }

    @Test
    fun interruptedSessionCanResumeAtItsBoundaryWithoutCountingSyntheticSamples() {
        val journey = session()
        journey.interrupt(50_000)
        assertEquals(0, journey.snapshot().sampleCount)
        val resumed = journey.add(sample(50_000))
        assertEquals(1, resumed.sampleCount)
        assertEquals(50_000L, resumed.elapsedMs)
    }

    @Test
    fun identicalSamplesAndRepeatedCumulativeEventsAreIdempotent() {
        val journey = session()
        val turn = DrivingEvent(20_000, DrivingEvent.Kind.TURN, TurnSignal.RIGHT)
        for (t in 0..30) journey.add(sample(t * 1000L), if (t >= 20) listOf(turn) else emptyList())
        val before = journey.snapshot()
        val after = journey.add(sample(30_000), listOf(turn, turn))
        assertEquals(before, after)
        assertEquals(31, after.sampleCount)
        assertEquals("기회 1회", after.report.items.first { it.item == Item.TURN_DECEL }.basis.text)
    }

    @Test
    fun changingInputAtTheSameTimeAndGoingBackwardsAreRejected() {
        val journey = session()
        journey.add(sample(1000))
        assertThrows(IllegalArgumentException::class.java) { journey.add(sample(1000, safe = false)) }
        assertThrows(IllegalArgumentException::class.java) { journey.add(sample(999)) }
        assertThrows(IllegalArgumentException::class.java) { journey.interrupt(999) }
        assertThrows(IllegalArgumentException::class.java) {
            journey.add(sample(2000), listOf(DrivingEvent(3000, DrivingEvent.Kind.TURN, TurnSignal.LEFT)))
        }
        assertEquals(1, journey.snapshot().sampleCount)
    }

    @Test
    fun feedbackWaitsForCooldownAndUsesMonotonicKeysWithoutRepeatingUnchangedEmotion() {
        val journey = session(config = ScoreConfig(windowMs = 1000, minValidSec = 1.0))
        journey.add(sample(0, safe = false))
        val worry = journey.add(sample(1000, safe = false))
        assertEquals(Emotion.WORRY, worry.emotion)
        assertEquals("journey-1:1", worry.feedback?.key)
        for (t in 2..30) journey.add(sample(t * 1000L))
        val waiting = journey.snapshot()
        assertEquals(Emotion.RELIEF, waiting.emotion)
        assertEquals("journey-1:1", waiting.feedback?.key)
        val relief = journey.add(sample(31_000))
        assertEquals(Emotion.RELIEF, relief.feedback?.kind)
        assertEquals("journey-1:2", relief.feedback?.key)
        for (t in 32..70) journey.add(sample(t * 1000L))
        assertEquals("journey-1:2", journey.snapshot().feedback?.key)
        assertEquals("journey-1:3", journey.finish().feedback?.key)
        assertEquals("journey-1:3", journey.finish().feedback?.key)
    }

    @Test
    fun sessionsNeverShareReadingsOrFeedbackIdentity() {
        val previous = session("previous")
        for (t in 0..15) previous.add(sample(t * 1000L))
        previous.finish()
        val next = session("next")
        assertNull(next.snapshot().report.total)
        assertNull(next.snapshot().currentSample)
        assertEquals(0, next.snapshot().sampleCount)
        assertEquals("next:1", next.finish().feedback?.key)
        assertEquals("character-1", next.characterId)
        assertEquals("route-1", next.routePlanId)
    }
}
