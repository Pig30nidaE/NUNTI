package ai.nunti.score

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class EventSpeakerTest {
    private val spoken = mutableListOf<String>()
    private val speaker = EventSpeaker({ t, _, _ -> spoken += t })
    private fun report(vararg e: DetectedEvent) =
        ScoreReport(null, 0f, emptyList(), emptyList(), emptyList(), e.toList())

    @Test fun existingEventsAreBaselineNotSpoken() {
        assertNull(speaker.onUpdate(report(DetectedEvent(1000, "급제동")), Emotion.NEUTRAL, 0))
        assertEquals(0, spoken.size)
    }

    @Test fun newEventSpokenOnceAndCooldownDropsNext() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        val a = DetectedEvent(2000, "급제동")
        assertNotNull(speaker.onUpdate(report(a), Emotion.WORRY, 1_000))
        assertNull(speaker.onUpdate(report(a), Emotion.WORRY, 2_000)) // 중복
        assertNull(speaker.onUpdate(report(a, DetectedEvent(5000, "급가속")), Emotion.WORRY, 5_000)) // 쿨다운
        assertNotNull(speaker.onUpdate(report(a, DetectedEvent(5000, "급가속"), DetectedEvent(30000, "급감속")), Emotion.WORRY, 31_000))
        assertEquals(2, spoken.size)
    }

    @Test fun reliefAfterWorryIsSpokenButWorryAloneIsNot() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        assertNull(speaker.onUpdate(report(), Emotion.WORRY, 1_000))
        assertEquals(Emotion.RELIEF.line, speaker.onUpdate(report(), Emotion.RELIEF, 20_000))
    }

    @Test fun resetRebaselines() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        speaker.reset()
        assertNull(speaker.onUpdate(report(DetectedEvent(1, "급제동")), Emotion.NEUTRAL, 100_000))
    }
}
