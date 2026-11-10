package ai.nunti.score

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
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

    @Test fun sameKindRotatesAndNeverRepeatsBackToBack() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        val events = mutableListOf<DetectedEvent>()
        repeat(4) { i ->
            events += DetectedEvent(1000L + i, "급제동")
            speaker.onUpdate(report(*events.toTypedArray()), Emotion.WORRY, 20_000L * (i + 1))
        }
        assertEquals(4, spoken.size)
        spoken.zipWithNext().forEach { (a, b) -> assertNotEquals(a, b) }
        assertEquals(spoken[0], spoken[2])
    }

    @Test fun droppedEventDoesNotConsumeVariant() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        val a = DetectedEvent(1, "급제동"); val b = DetectedEvent(2, "급제동"); val c = DetectedEvent(3, "급제동")
        speaker.onUpdate(report(a), Emotion.WORRY, 1_000)
        speaker.onUpdate(report(a, b), Emotion.WORRY, 2_000) // 쿨다운으로 버려짐
        speaker.onUpdate(report(a, b, c), Emotion.WORRY, 20_000)
        assertEquals(EventSpeaker.eventLine("급제동", 0), spoken[0])
        assertEquals(EventSpeaker.eventLine("급제동", 1), spoken[1])
    }

    @Test fun linesDifferByKindAndFitLimit() {
        val labels = listOf("급제동", "급가속", "급감속", "기타")
        val all = EventSpeaker.Companion.EventKind.entries.flatMap { it.lines }
        assertEquals(all.size, all.toSet().size)
        labels.forEach { l ->
            (0..3).forEach { v -> val t = EventSpeaker.eventLine(l, v); assertTrue(t.codePointCount(0, t.length) <= 80) }
        }
        assertEquals(4, labels.map { EventSpeaker.kindOf(it) }.toSet().size)
        assertEquals(EventSpeaker.eventLine("급제동", 2), EventSpeaker.eventLine("급제동", 0))
    }
}
