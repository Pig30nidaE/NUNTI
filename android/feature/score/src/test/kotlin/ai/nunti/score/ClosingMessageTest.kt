package ai.nunti.score

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ClosingMessageTest {
    private fun report(total: Float?, coverage: Float = 1f, vararg kinds: DetectedEvent.Kind) = ScoreReport(
        total, coverage, emptyList(), emptyList(), emptyList(),
        kinds.mapIndexed { i, k -> DetectedEvent(1000L * (i + 1), k) },
    )

    private val brake = DetectedEvent.Kind.HARD_BRAKE

    @Test fun classifiesByFactsNotByLuck() {
        assertEquals(TripTone.UNKNOWN, ClosingMessage.tone(report(null, 0f), Emotion.NEUTRAL))
        assertEquals(TripTone.UNKNOWN, ClosingMessage.tone(report(95f, 0.4f), Emotion.JOY)) // 범위가 너무 낮음
        assertEquals(TripTone.RECOVERED, ClosingMessage.tone(report(95f, 1f, brake, brake), Emotion.RELIEF))
        assertEquals(TripTone.RUSHED, ClosingMessage.tone(report(92f, 1f, brake, DetectedEvent.Kind.HARD_ACCEL), Emotion.NEUTRAL))
        assertEquals(TripTone.RUSHED, ClosingMessage.tone(report(60f), Emotion.WORRY)) // 점수 자체가 낮음
        assertEquals(TripTone.CURVY, ClosingMessage.tone(report(90f, 1f, DetectedEvent.Kind.CURVE_TOO_FAST), Emotion.JOY))
        assertEquals(TripTone.CALM, ClosingMessage.tone(report(96f, 1f, brake), Emotion.JOY)) // 급제동 한 번은 급한 주행이 아니다
    }

    @Test fun onlyWorryingTripsAskAfterTheDriver() {
        assertEquals(setOf(TripTone.RUSHED, TripTone.CURVY), TripTone.entries.filter { it.checkIn.asks }.toSet())
        TripTone.entries.forEach { tone ->
            val everyVariantAsks = tone.checkIn.variants.all { it.trimEnd().endsWith("?") }
            assertEquals(tone.checkIn.asks, everyVariantAsks) // 질문 부품은 전부 질문, 인사 부품에는 질문이 없다
        }
        assertEquals("오늘 주행은 약간 급한 감이 있었어요. 무슨 안 좋은 일 있나요?", ClosingMessage.compose(TripTone.RUSHED, 0))
    }

    @Test fun everyPartIsWithinLimitAndHasNoScoreNumbers() {
        val parts = Observation.entries.flatMap { it.variants.toList() } + CheckIn.entries.flatMap { it.variants.toList() }
        parts.forEach { assertTrue(it.none { c -> c.isDigit() }) }
        TripTone.entries.forEach { tone ->
            repeat(8) { v ->
                val line = ClosingMessage.compose(tone, v)
                assertTrue(line.codePointCount(0, line.length) <= 80)
            }
        }
    }

    @Test fun variantsWalkThroughEveryCombination() {
        val tone = TripTone.RUSHED
        val n = tone.observation.variants.size * tone.checkIn.variants.size
        val seen = (0 until n).map { ClosingMessage.compose(tone, it) }
        assertEquals(n, seen.toSet().size) // 모든 조합이 서로 다르다
        assertEquals(seen[0], ClosingMessage.compose(tone, n)) // 한 바퀴 돌면 처음으로
        assertNotEquals(seen[0], seen[1])
    }

    @Test fun demoScenariosGetTheExpectedClosing() {
        val engine = ScoreEngine()
        fun tone(s: Scenario): TripTone {
            val r = engine.evaluate(s.samples, s.events)
            return ClosingMessage.tone(r, engine.emotion(r, finished = true))
        }
        assertEquals(TripTone.CALM, tone(Scenarios.calm))
        assertEquals(TripTone.RECOVERED, tone(Scenarios.recovery))
        assertEquals(TripTone.UNKNOWN, tone(Scenarios.sparse))
    }
}
