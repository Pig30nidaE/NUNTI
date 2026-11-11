package ai.nunti.emotion

import java.io.File
import kotlin.random.Random

/**
 * 동작 고정(characterization) 시험. 같은 입력열을 EmotionMachine 에 통과시켜
 * 결과(disposition)·감정·감정 ID·전환 이유를 모두 기록하고 golden.txt 와 비교한다.
 * 리팩터링은 이 출력이 한 글자도 바뀌지 않아야 한다.
 *   gradlew :feature:emotion:verifyEmotion        → golden 과 비교
 *   gradlew :feature:emotion:verifyEmotion -Pupdate  → golden 다시 쓰기 (동작을 의도적으로 바꿀 때만)
 */
private val rules = EmotionRules(confidenceMin = 0.80, eventExpiry = 15000, debounce = 700, cooldown = 8000,
    minimumDwell = 2000, stableWindow = 3000, stableGap = 2000, startledMax = 6000, concernedMax = 12000,
    reliefDwell = 3000, dataExpiry = 30000)
private val machine = EmotionMachine(rules)

private fun ev(id: String, type: EventType, at: Long, recovery: String? = null, incident: String? = null,
    verified: Boolean = true, confidence: Double? = 0.95, trip: String = "trip") =
    DrivingEvent(id, trip, type, at, verified, confidence, incident, recovery)

/** null 이벤트는 시계만 진행(tick). */
private class Step(val now: Long, val event: DrivingEvent?)

private fun scenario(name: String, startAt: Long = 0, steps: List<Step>, out: StringBuilder, counts: MutableMap<String, Int>) {
    out.appendLine("## $name")
    var s = machine.start("trip", "avatar", startAt)
    steps.forEach { step ->
        if (step.event == null) {
            s = machine.tick(s, step.now)
            out.appendLine("t=${step.now} tick -> ${s.snapshot.emotion} ${s.snapshot.emotionId} ${s.snapshot.reason} pending=${s.pending?.emotion}")
        } else {
            val r = machine.accept(s, step.event, step.now)
            s = r.state
            counts.merge("${r.disposition}", 1, Int::plus)
            out.appendLine("t=${step.now} ${step.event.type}:${step.event.eventId} -> ${r.disposition} | ${s.snapshot.emotion} ${s.snapshot.emotionId} ${s.snapshot.reason} pending=${s.pending?.emotion}")
        }
    }
    val sum = machine.summary(s)
    out.appendLine("summary final=${sum.finalEmotion} dominant=${sum.dominantEmotion} recov=${sum.recoveryCount} processed=${sum.processedEventCount} ended=${sum.endedAt} dur=${sum.durationMillis}")
    out.appendLine("timeline " + s.timeline.joinToString(" ") { "${it.emotion}@${it.since}:${it.reason}:${it.triggeredByEventId}" })
}

fun transcript(): String {
    val out = StringBuilder(); val counts = sortedMapOf<String, Int>()
    fun t(now: Long) = Step(now, null)
    fun e(now: Long, event: DrivingEvent) = Step(now, event)
    scenario("calm-startled-relieved-calm", steps = listOf(
        e(0, ev("s0", EventType.STABLE_DRIVING, 0)), e(1500, ev("s1", EventType.STABLE_DRIVING, 1500)),
        e(3000, ev("s2", EventType.STABLE_DRIVING, 3000)), e(6000, ev("brake", EventType.HARSH_BRAKING, 6000)),
        e(9000, ev("rec", EventType.SAFETY_RECOVERED, 9000, "brake")), t(12000), t(20000)), out = out, counts = counts)
    scenario("dup-event-and-incident", steps = listOf(
        e(1000, ev("brake", EventType.HARSH_BRAKING, 1000, incident = "inc")), e(2000, ev("brake", EventType.HARSH_BRAKING, 1000, incident = "inc")),
        e(3000, ev("other", EventType.HARSH_BRAKING, 3000, incident = "inc")),
        e(3000, ev("recovered", EventType.SAFETY_RECOVERED, 3000, "brake", "inc"))), out = out, counts = counts)
    scenario("order-future-expired-trip", steps = listOf(
        e(3000, ev("b", EventType.HARSH_BRAKING, 3000)), e(4000, ev("late", EventType.SAFETY_CONCERN, 2000)),
        e(4000, ev("future", EventType.HARSH_BRAKING, 5000)),
        e(4000, ev("other", EventType.HARSH_BRAKING, 4000, trip = "different")),
        e(17000, ev("old", EventType.HARSH_BRAKING, 1000))), out = out, counts = counts)
    scenario("same-timestamp-priority", steps = listOf(
        e(1000, ev("concern", EventType.SAFETY_CONCERN, 1000)), e(1000, ev("brake", EventType.HARSH_BRAKING, 1000))), out = out, counts = counts)
    scenario("startle-timeout", steps = listOf(e(1000, ev("b", EventType.HARSH_BRAKING, 1000)), t(7000), t(9000)), out = out, counts = counts)
    scenario("min-dwell-pending", steps = listOf(
        e(1000, ev("b", EventType.HARSH_BRAKING, 1000)), e(1500, ev("r", EventType.SAFETY_RECOVERED, 1500, "b")), t(3000)), out = out, counts = counts)
    scenario("cooldown", steps = listOf(
        e(1000, ev("b", EventType.HARSH_BRAKING, 1000)), e(3000, ev("r", EventType.SAFETY_RECOVERED, 3000, "b")),
        e(5000, ev("b2", EventType.HARSH_BRAKING, 5000))), out = out, counts = counts)
    scenario("debounce", steps = listOf(
        e(1000, ev("c", EventType.SAFETY_CONCERN, 1000)), e(1200, ev("c2", EventType.SAFETY_CONCERN, 1200))), out = out, counts = counts)
    scenario("unmatched-recovery-unresolved-concern", steps = listOf(
        e(1000, ev("c", EventType.SAFETY_CONCERN, 1000)), e(4000, ev("r", EventType.SAFETY_RECOVERED, 4000, "not-c")),
        e(5000, ev("p", EventType.POSITIVE_FEEDBACK, 5000))), out = out, counts = counts)
    scenario("unverified-nan-lowconf-unknown", steps = listOf(
        e(0, ev("u", EventType.HARSH_BRAKING, 0, verified = false)), e(0, ev("nan", EventType.HARSH_BRAKING, 0, confidence = Double.NaN)),
        e(0, ev("low", EventType.HARSH_BRAKING, 0, confidence = 0.5)), e(0, ev("nul", EventType.HARSH_BRAKING, 0, confidence = null)),
        e(0, ev("unk", EventType.UNKNOWN, 0)), e(0, ev("", EventType.STABLE_DRIVING, 0))), out = out, counts = counts)
    scenario("hysteresis-gap-and-relief-dwell", steps = listOf(
        e(0, ev("s1", EventType.STABLE_DRIVING, 0)), e(4000, ev("s2", EventType.STABLE_DRIVING, 4000)),
        e(5000, ev("s3", EventType.STABLE_DRIVING, 5000)), e(6500, ev("s4", EventType.STABLE_DRIVING, 6500)),
        e(8000, ev("s5", EventType.STABLE_DRIVING, 8000)), e(8500, ev("s6", EventType.STABLE_DRIVING, 8500)),
        e(9000, ev("c", EventType.SAFETY_CONCERN, 9000)), e(11000, ev("s7", EventType.STABLE_DRIVING, 11000)),
        e(12500, ev("s8", EventType.STABLE_DRIVING, 12500)), e(14000, ev("s9", EventType.STABLE_DRIVING, 14000)),
        e(14500, ev("s10", EventType.STABLE_DRIVING, 14500)), t(18000)), out = out, counts = counts)
    scenario("relief-dwell", steps = listOf(
        e(0, ev("c", EventType.SAFETY_CONCERN, 0)), e(2000, ev("s1", EventType.STABLE_DRIVING, 2000)),
        e(3000, ev("s2", EventType.STABLE_DRIVING, 3000)), e(5000, ev("s3", EventType.STABLE_DRIVING, 5000)),
        e(5800, ev("s4", EventType.STABLE_DRIVING, 5800)), t(9000)), out = out, counts = counts)
    scenario("concern-timeout-and-data-expiry", steps = listOf(
        e(1000, ev("c", EventType.SAFETY_CONCERN, 1000)), t(13500), e(14000, ev("j", EventType.POSITIVE_FEEDBACK, 14000)), t(50000)), out = out, counts = counts)
    scenario("trip-ended", steps = listOf(
        e(0, ev("s0", EventType.STABLE_DRIVING, 0)), e(7000, ev("end", EventType.TRIP_ENDED, 7000)),
        e(8000, ev("late", EventType.HARSH_BRAKING, 8000)), t(99000)), out = out, counts = counts)
    scenario("invalid-event-before-start", startAt = 1000, steps = listOf(e(1500, ev("old", EventType.HARSH_BRAKING, 500))), out = out, counts = counts)
    scenario("no-change", steps = listOf(
        e(0, ev("c", EventType.SAFETY_CONCERN, 0)), e(1500, ev("c2", EventType.SAFETY_CONCERN, 1500))), out = out, counts = counts)
    // 결정적 난수열: 분기 커버리지를 넓힌다. 전체 출력을 그대로 기록한다.
    val types = EventType.entries
    for (seed in 1..40) {
        val rnd = Random(seed); var now = 0L
        val steps = (0 until 80).map {
            now += rnd.nextLong(0, 3500)
            if (rnd.nextInt(6) == 0) t(now) else {
                val type = if (rnd.nextInt(60) == 0) EventType.TRIP_ENDED else types.filter { it != EventType.TRIP_ENDED }[rnd.nextInt(types.size - 1)]
                val at = (now - rnd.nextLong(0, 4000)).coerceAtLeast(0)
                val rec = if (type == EventType.SAFETY_RECOVERED && rnd.nextBoolean()) "e${maxOf(0, it - 1 - rnd.nextInt(4))}" else null
                e(now, ev("e$it", type, at, rec, if (rnd.nextInt(4) == 0) "inc${rnd.nextInt(3)}" else null,
                    verified = rnd.nextInt(10) != 0, confidence = if (rnd.nextInt(12) == 0) 0.6 else 0.95))
            }
        }
        scenario("fuzz-$seed", steps = steps, out = out, counts = counts)
    }
    out.appendLine("## disposition counts"); counts.forEach { (k, v) -> out.appendLine("$k=$v") }
    return out.toString()
}

fun main(args: Array<String>) {
    val golden = File(args[0]); val update = args.getOrNull(1) == "update"
    val actual = transcript()
    if (update || !golden.exists()) { golden.writeText(actual); println("golden written: ${golden} (${actual.lines().size} lines)"); return }
    val expected = golden.readText()
    if (expected == actual) { println("emotion golden OK (${actual.lines().size} lines)"); return }
    val e = expected.lines(); val a = actual.lines()
    val i = (0 until minOf(e.size, a.size)).firstOrNull { e[it] != a[it] } ?: minOf(e.size, a.size)
    System.err.println("emotion golden MISMATCH at line ${i + 1}\n expected: ${e.getOrNull(i)}\n actual:   ${a.getOrNull(i)}")
    kotlin.system.exitProcess(1)
}
