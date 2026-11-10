package ai.nunti.score

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ClosingMessageTest {
    private fun report(total: Float?, coverage: Float = 1f, vararg kinds: DetectedEvent.Kind) = ScoreReport(
        total, coverage, emptyList(), emptyList(), emptyList(),
        kinds.mapIndexed { i, k -> DetectedEvent(1000L * (i + 1), k) },
    )

    private val brake = DetectedEvent.Kind.HARD_BRAKE
    private val curve = DetectedEvent.Kind.CURVE_TOO_FAST

    @Test fun verdictFollowsTheOverallScore() {
        assertEquals(Verdict.UNKNOWN, ClosingMessage.plan(report(null, 0f), Emotion.NEUTRAL).verdict)
        assertEquals(Verdict.UNKNOWN, ClosingMessage.plan(report(95f, 0.4f), Emotion.JOY).verdict) // 범위가 너무 낮음
        assertEquals(Verdict.GREAT, ClosingMessage.plan(report(95f), Emotion.JOY).verdict)
        assertEquals(Verdict.GOOD, ClosingMessage.plan(report(85f), Emotion.JOY).verdict)
        assertEquals(Verdict.FAIR, ClosingMessage.plan(report(75f), Emotion.NEUTRAL).verdict)
        assertEquals(Verdict.LOW, ClosingMessage.plan(report(60f), Emotion.WORRY).verdict)
    }

    @Test fun eventsLowerAHighVerdict() {
        // 점수가 높아도 "처음부터 끝까지 편안" 이라고 말하면서 급제동 장면을 이어 말하지 않는다.
        assertEquals(Verdict.GOOD, ClosingMessage.plan(report(96f, 1f, brake), Emotion.JOY).verdict)
        assertEquals(Verdict.FAIR, ClosingMessage.plan(report(92f, 1f, brake, DetectedEvent.Kind.HARD_ACCEL), Emotion.NEUTRAL).verdict)
        assertEquals(Verdict.LOW, ClosingMessage.plan(report(50f, 1f, brake), Emotion.WORRY).verdict) // 원래 낮으면 그대로
    }

    @Test fun highlightIsTheMostFrequentSceneOrRecovery() {
        assertEquals(Highlight.CURVES, ClosingMessage.plan(report(80f, 1f, brake, curve, curve), Emotion.NEUTRAL).highlight)
        assertEquals(Highlight.BRAKES, ClosingMessage.plan(report(80f, 1f, curve, brake), Emotion.NEUTRAL).highlight) // 동률이면 급제동
        assertEquals(Highlight.ACCEL, ClosingMessage.plan(report(90f, 1f, DetectedEvent.Kind.REVERSE_TOO_FAST), Emotion.JOY).highlight)
        assertEquals(Highlight.BRAKES, ClosingMessage.plan(report(80f, 1f, curve, DetectedEvent.Kind.HARD_DECEL, brake), Emotion.NEUTRAL).highlight) // 급감속은 급제동과 합산
        assertEquals(Highlight.RECOVERED, ClosingMessage.plan(report(85f, 1f, brake, brake), Emotion.RELIEF).highlight)
        assertEquals(Highlight.SMOOTH, ClosingMessage.plan(report(95f), Emotion.JOY).highlight)
        assertNull(ClosingMessage.plan(report(60f), Emotion.WORRY).highlight) // 쏠림 사건 없이 낮은 점수: 지어내지 않는다
        assertNull(ClosingMessage.plan(report(null, 0f), Emotion.NEUTRAL).highlight)
    }

    @Test fun onlyWorryingTripsAskAfterTheDriver() {
        assertEquals(CheckIn.ASK_TROUBLE, ClosingMessage.plan(report(60f), Emotion.WORRY).checkIn)
        assertEquals(CheckIn.ASK_HURRY, ClosingMessage.plan(report(92f, 1f, brake, brake), Emotion.NEUTRAL).checkIn)
        assertEquals(CheckIn.CHEER, ClosingMessage.plan(report(75f, 1f, brake, brake), Emotion.RELIEF).checkIn) // 회복했으면 묻지 않는다
        assertEquals(CheckIn.CHEER, ClosingMessage.plan(report(95f), Emotion.JOY).checkIn)
        CheckIn.entries.forEach { c -> assertEquals(c.asks, c.variants.all { it.trimEnd().endsWith("?") }) }
        assertEquals(
            "오늘은 괜찮았어요. 그래도 몇 번은 저도 모르게 꽉 붙잡았어요. 갑자기 멈출 땐 심장이 쿵 했어요. 오늘 많이 바빴나요?",
            ClosingMessage.compose(report(92f, 1f, brake, brake), Emotion.NEUTRAL, 1),
        )
    }

    @Test fun everyPartIsWithinLimitAndHasNoScoreNumbers() {
        val parts = Verdict.entries.flatMap { it.variants.toList() } +
            Highlight.entries.flatMap { it.variants.toList() } + CheckIn.entries.flatMap { it.variants.toList() }
        assertEquals(parts.size, parts.toSet().size) // 부품마다 따로 녹음하므로 문장이 겹치지 않는다
        parts.forEach {
            assertTrue(it.none { c -> c.isDigit() })
            assertTrue(it.codePointCount(0, it.length) <= 80)
        }
    }

    @Test fun variantsWalkThroughEveryCombination() {
        val plan = ClosingPlan(Verdict.FAIR, Highlight.BRAKES, CheckIn.ASK_HURRY)
        val n = 2 * 2 * 2
        val seen = (0 until n).map { ClosingMessage.compose(plan, it) }
        assertEquals(n, seen.toSet().size)
        assertEquals(seen[0], ClosingMessage.compose(plan, n))
        assertNotEquals(seen[0], seen[1])
        assertEquals(2, ClosingMessage.compose(ClosingPlan(Verdict.LOW, null, CheckIn.ASK_TROUBLE), 0).count { it == '.' || it == '?' })
    }

    @Test fun demoScenariosGetTheExpectedClosing() {
        val engine = ScoreEngine()
        fun plan(s: Scenario): ClosingPlan {
            val r = engine.evaluate(s.samples, s.events)
            return ClosingMessage.plan(r, engine.emotion(r, finished = true))
        }
        assertTrue(plan(Scenarios.calm).verdict in setOf(Verdict.GREAT, Verdict.GOOD))
        assertEquals(CheckIn.CHEER, plan(Scenarios.calm).checkIn)
        assertEquals(Highlight.RECOVERED, plan(Scenarios.recovery).highlight)
        assertEquals(Verdict.UNKNOWN, plan(Scenarios.sparse).verdict)
    }
}
