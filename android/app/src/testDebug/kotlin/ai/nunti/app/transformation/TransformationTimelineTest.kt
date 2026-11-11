package ai.nunti.app.transformation

import org.junit.Assert.*
import org.junit.Test

class TransformationTimelineTest {
    @Test fun exactIntervalsPreserveTheCoreAndFinishAtFourSeconds() {
        val base = TransformationTimeline.at(449)
        assertEquals(0f, base.road, 0f)
        assertEquals(1f, base.coreAlpha, 0f)
        assertEquals(1f, TransformationTimeline.at(1300).road, 0f)
        assertEquals(0f, TransformationTimeline.at(1300).scarf, 0f)
        assertEquals(1f, TransformationTimeline.at(1900).scarf, 0f)
        assertEquals(1f, TransformationTimeline.at(2500).pocket, 0f)
        assertEquals(0f, TransformationTimeline.at(2699).expression, 0f)
        assertEquals(0f, TransformationTimeline.at(2850).expression, 0f)
        assertEquals(1f, TransformationTimeline.at(3050).expression, 0f)
        assertEquals(1f, TransformationTimeline.at(3400).expression, 0f)
        assertEquals(0f, TransformationTimeline.at(450).trailOpacity, 0f)
        assertEquals(1f, TransformationTimeline.at(550).trailOpacity, 0f)
        assertEquals(1f, TransformationTimeline.at(1200).trailOpacity, 0f)
        assertEquals(0f, TransformationTimeline.at(1300).trailOpacity, 0f)
        assertFalse(TransformationTimeline.at(3999).complete)
        assertTrue(TransformationTimeline.at(4000).complete)
    }

    @Test fun everyFrameIsBoundedMonotonicAndDeterministic() {
        var previous = TransformationTimeline.at(0)
        for (time in 0L..4100L) {
            val frame = TransformationTimeline.at(time)
            assertEquals(frame, TransformationTimeline.at(time))
            assertEquals(1f, frame.coreAlpha, 0f)
            val values = listOf(frame.road, frame.scarf, frame.pocket, frame.expression, frame.settle)
            assertTrue(values.all { it in 0f..1f })
            assertTrue(frame.road >= previous.road && frame.scarf >= previous.scarf &&
                frame.pocket >= previous.pocket && frame.expression >= previous.expression && frame.settle >= previous.settle)
            previous = frame
        }
        assertEquals(0L, TransformationTimeline.at(-1).elapsedMs)
        assertEquals(4000L, TransformationTimeline.at(Long.MAX_VALUE).elapsedMs)
    }

    @Test fun permissionAndAssetCompletionNeverStartPlayback() {
        val playback = TransformationPlayback()
        assertFalse(playback.play(0, allowed = true, reducedMotion = false))
        playback.ready()
        assertFalse(playback.state.running)
        assertFalse(playback.play(0, allowed = false, reducedMotion = false))
        playback.advance(1000, allowed = true, foreground = true, reducedMotion = false)
        assertEquals(PlaybackStatus.BASE, playback.state.status)
    }

    @Test fun restrictionInterruptsToFinalAndDoesNotAutoResume() {
        val playback = readyPlayback()
        assertTrue(playback.play(100, allowed = true, reducedMotion = false))
        playback.advance(700, allowed = true, foreground = true, reducedMotion = false)
        assertEquals(600L, playback.state.elapsedMs)
        playback.advance(701, allowed = false, foreground = true, reducedMotion = false)
        assertEquals(StopReason.RESTRICTED, playback.state.stopReason)
        assertTrue(playback.state.finalVisible)
        playback.advance(800, allowed = true, foreground = true, reducedMotion = false)
        assertFalse(playback.state.running)
        assertEquals(4000L, playback.state.elapsedMs)
        assertTrue(playback.play(900, allowed = true, reducedMotion = false))
        assertEquals(0L, playback.state.elapsedMs)
    }

    @Test fun backgroundInterruptsAndDoesNotAutoResume() {
        val playback = readyPlayback()
        playback.play(0, true, false)
        playback.advance(500, true, false, false)
        assertEquals(StopReason.BACKGROUNDED, playback.state.stopReason)
        playback.advance(800, true, true, false)
        assertFalse(playback.state.running)
    }

    @Test fun skipWhileLoadingShowsBaseThenFinalWithoutStartingMotion() {
        val playback = TransformationPlayback()
        playback.stop(StopReason.SKIPPED)
        assertFalse(playback.state.finalVisible)
        playback.ready()
        assertTrue(playback.state.finalVisible)
        assertFalse(playback.state.running)
    }

    @Test fun reducedMotionBeforeOrDuringPlaybackSettlesImmediately() {
        val playback = readyPlayback()
        assertFalse(playback.play(0, true, true))
        assertTrue(playback.state.finalVisible)
        playback.play(0, true, false)
        playback.advance(800, true, true, true)
        assertEquals(StopReason.REDUCED_MOTION, playback.state.stopReason)
        assertTrue(playback.state.finalVisible)
    }

    @Test fun failureAndNewLoadingAlwaysReturnToBase() {
        val playback = readyPlayback()
        playback.stop(StopReason.COMPLETED)
        playback.failed()
        assertEquals(PlaybackStatus.FAILED, playback.state.status)
        assertFalse(playback.state.finalVisible)
        playback.loading()
        assertEquals(PlaybackStatus.LOADING, playback.state.status)
        assertFalse(playback.state.assetsReady)
    }

    @Test fun seekCannotBypassVehicleGate() {
        val playback = readyPlayback()
        assertFalse(playback.seek(1700, false))
        assertEquals(0L, playback.state.elapsedMs)
        assertTrue(playback.seek(1700, true))
        assertEquals(1700L, playback.state.elapsedMs)
        assertFalse(playback.state.running)
    }

    @Test fun completionAndClockReversalDoNotRestartOrRewind() {
        val playback = readyPlayback()
        playback.play(100, true, false)
        playback.advance(1200, true, true, false)
        playback.advance(1100, true, true, false)
        assertEquals(1100L, playback.state.elapsedMs)
        playback.advance(4100, true, true, false)
        assertEquals(StopReason.COMPLETED, playback.state.stopReason)
        playback.advance(4200, true, true, false)
        assertTrue(playback.state.finalVisible)
    }

    private fun readyPlayback() = TransformationPlayback().apply { ready() }
}
