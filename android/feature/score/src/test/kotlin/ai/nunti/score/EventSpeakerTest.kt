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
        assertNull(speaker.onUpdate(report(DetectedEvent(1000, DetectedEvent.Kind.HARD_BRAKE)), Emotion.NEUTRAL, 0))
        assertEquals(0, spoken.size)
    }

    @Test fun newEventSpokenOnceAndCooldownDropsNext() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        val a = DetectedEvent(2000, DetectedEvent.Kind.HARD_BRAKE)
        assertNotNull(speaker.onUpdate(report(a), Emotion.WORRY, 1_000))
        assertNull(speaker.onUpdate(report(a), Emotion.WORRY, 2_000)) // 중복
        assertNull(speaker.onUpdate(report(a, DetectedEvent(5000, DetectedEvent.Kind.HARD_ACCEL)), Emotion.WORRY, 5_000)) // 쿨다운
        assertNotNull(speaker.onUpdate(report(a, DetectedEvent(5000, DetectedEvent.Kind.HARD_ACCEL), DetectedEvent(30000, DetectedEvent.Kind.HARD_DECEL)), Emotion.WORRY, 31_000))
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
        assertNull(speaker.onUpdate(report(DetectedEvent(1, DetectedEvent.Kind.HARD_BRAKE)), Emotion.NEUTRAL, 100_000))
    }

    @Test fun sameKindRotatesAndNeverRepeatsBackToBack() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        val events = mutableListOf<DetectedEvent>()
        repeat(4) { i ->
            events += DetectedEvent(1000L + i, DetectedEvent.Kind.HARD_BRAKE)
            speaker.onUpdate(report(*events.toTypedArray()), Emotion.WORRY, 20_000L * (i + 1))
        }
        assertEquals(4, spoken.size)
        spoken.zipWithNext().forEach { (a, b) -> assertNotEquals(a, b) }
        val n = EventSpeaker.lines.getValue(DetectedEvent.Kind.HARD_BRAKE).size
        assertEquals(spoken[0], spoken[n % 4]) // 대사 수만큼 지나면 처음으로 돌아온다
    }

    @Test fun droppedEventDoesNotConsumeVariant() {
        speaker.onUpdate(report(), Emotion.NEUTRAL, 0)
        val a = DetectedEvent(1, DetectedEvent.Kind.HARD_BRAKE); val b = DetectedEvent(2, DetectedEvent.Kind.HARD_BRAKE); val c = DetectedEvent(3, DetectedEvent.Kind.HARD_BRAKE)
        speaker.onUpdate(report(a), Emotion.WORRY, 1_000)
        speaker.onUpdate(report(a, b), Emotion.WORRY, 2_000) // 쿨다운으로 버려짐
        speaker.onUpdate(report(a, b, c), Emotion.WORRY, 20_000)
        assertEquals(EventSpeaker.eventLine(DetectedEvent.Kind.HARD_BRAKE, 0), spoken[0])
        assertEquals(EventSpeaker.eventLine(DetectedEvent.Kind.HARD_BRAKE, 1), spoken[1])
    }

    @Test fun everyKindHasDistinctLinesWithinLimit() {
        // 새 종류를 추가하면 대사 표에도 넣어야 한다 (넣지 않으면 getValue 가 실패해 이 시험이 잡는다).
        DetectedEvent.Kind.entries.forEach { kind -> assertTrue(EventSpeaker.lines.getValue(kind).isNotEmpty()) }
        val all = EventSpeaker.lines.values.distinct().flatten() // 같은 목록을 공유하는 종류(후진 과속 = 급가속)는 한 번만 센다
        assertEquals(all.size, all.toSet().size)
        DetectedEvent.Kind.entries.forEach { kind ->
            (0..3).forEach { v -> val t = EventSpeaker.eventLine(kind, v); assertTrue(t.codePointCount(0, t.length) <= 80) }
        }
        val n = EventSpeaker.lines.getValue(DetectedEvent.Kind.HARD_BRAKE).size
        assertEquals(EventSpeaker.eventLine(DetectedEvent.Kind.HARD_BRAKE, n), EventSpeaker.eventLine(DetectedEvent.Kind.HARD_BRAKE, 0))
    }

    @Test fun scoreEngineLabelsAreDerivedFromKind() {
        assertEquals("급제동", DetectedEvent(0, DetectedEvent.Kind.HARD_BRAKE).label)
    }
}
