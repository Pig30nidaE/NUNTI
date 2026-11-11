package ai.nunti.score

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TripLifecycleTest {
    private val engine = ScoreEngine()
    private fun readiness(s: Scenario) = TripLifecycle.readiness(engine.evaluate(s.samples, s.events))

    @Test fun enoughRichDrivingIsReady() {
        assertEquals(Readiness.READY, readiness(Scenarios.calm))
        assertEquals(TripStatus.FINISHED, Scenarios.calm.let { TripLifecycle.onEndRequested(engine.evaluate(it.samples, it.events)) })
    }

    @Test fun speedOnlyTripIsPausedForMissingSignals() {
        assertEquals(Readiness.WAITING_FOR_SIGNALS, readiness(Scenarios.sparse))
        assertEquals(TripStatus.PAUSED, Scenarios.sparse.let { TripLifecycle.onEndRequested(engine.evaluate(it.samples, it.events)) })
    }

    @Test fun standingStillIsWaitingForMovementNotMissingSignals() {
        val belted = SeatState(true, true)
        val still = (0..120).map { VehicleSample(it * 1000L, speedKmh = 0f, gear = Gear.D, driverSeat = belted, doorOpen = false) }
        val r = engine.evaluate(still, emptyList())
        assertEquals(Readiness.WAITING_FOR_MOVEMENT, TripLifecycle.readiness(r))
        assertEquals(0, r.movingSeconds)
        assertTrue(r.speedSeconds >= 100)
    }

    @Test fun noSpeedSignalIsMissingSignals() {
        val none = (0..60).map { VehicleSample(it * 1000L) }
        assertEquals(Readiness.WAITING_FOR_SIGNALS, TripLifecycle.readiness(engine.evaluate(none, emptyList())))
        assertEquals(Readiness.WAITING_FOR_SIGNALS, TripLifecycle.readiness(engine.evaluate(emptyList(), emptyList())))
    }

    @Test fun pausedTripBecomesFinishedOnceSignalsArrive() {
        val belted = SeatState(true, true)
        // 처음 60초는 속도만, 이후 신호가 모두 들어온다
        val samples = (0..240).map {
            if (it < 60) VehicleSample(it * 1000L, speedKmh = 50f)
            else VehicleSample(it * 1000L, speedKmh = 50f, gear = Gear.D, driverSeat = belted, doorOpen = false)
        }
        assertEquals(TripStatus.PAUSED, TripLifecycle.onEndRequested(engine.evaluate(samples.take(60), emptyList())))
        assertEquals(TripStatus.FINISHED, TripLifecycle.onEndRequested(engine.evaluate(samples, emptyList())))
    }

    @Test fun pauseNoticeExplainsTheReasonAndOnlyWhenPaused() {
        assertNull(TripLifecycle.pauseNotice(Readiness.READY))
        val moving = TripLifecycle.pauseNotice(Readiness.WAITING_FOR_MOVEMENT)!!
        val signals = TripLifecycle.pauseNotice(Readiness.WAITING_FOR_SIGNALS)!!
        assertTrue(moving != signals)
        assertNotNull(PauseFollowUp.SAVED_FOR_NOW.variants.firstOrNull { moving.endsWith(it) })
        listOf(moving, signals).forEach { assertTrue(it.codePointCount(0, it.length) <= 80 && it.none { c -> c.isDigit() }) }
    }
}
