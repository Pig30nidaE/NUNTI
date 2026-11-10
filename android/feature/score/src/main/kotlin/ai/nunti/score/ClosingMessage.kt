package ai.nunti.score

/**
 * 마무리 멘트의 부품. 한 문장을 통째로 적지 않고 "총평 + 안부"로 나눠 조합한다.
 * 문구를 고치려면 해당 enum 항목의 문장만 바꾸면 되고, 새 조합은 [TripTone] 에서 부품을 고르면 된다.
 * 모든 문장은 80자 이하여야 하고 점수 숫자를 말하지 않는다 (시험으로 확인).
 */
enum class Observation(vararg val variants: String) {
    NOT_ENOUGH_DATA("오늘은 잘 못 봐서 점수는 말씀 못 드려요.", "오늘은 정보가 부족해서 평가는 못 했어요."),
    RUSHED("오늘 주행은 약간 급한 감이 있었어요.", "오늘은 마음이 급해 보였어요."),
    CURVES_FAST("커브에서 몸이 몇 번 쏠렸어요.", "커브가 조금 빨랐어요."),
    RECOVERED("중간엔 조금 급했는데 끝에는 편안하게 와 줘서 다행이에요.", "처음엔 걱정했는데 점점 차분해졌어요."),
    CALM("오늘 정말 편안했어요.", "차분하게 잘 달렸어요."),
}

/** 총평 뒤에 붙는 안부·인사. 걱정스러운 주행에만 질문([asks])이 붙는다. */
enum class CheckIn(val asks: Boolean, vararg val variants: String) {
    ASK_TROUBLE(true, "무슨 안 좋은 일 있나요?", "혹시 무슨 일 있었어요?"),
    ASK_HURRY(true, "오늘 많이 바빴나요?", "혹시 급한 일 있었어요?"),
    CHEER(false, "같이 와서 좋았어요!", "오늘도 수고했어요!"),
}

/** 주행 전체의 분류. 분류마다 쓸 총평·안부 부품이 정해져 있다. 위에서부터 먼저 맞는 것을 쓴다. */
enum class TripTone(val observation: Observation, val checkIn: CheckIn) {
    UNKNOWN(Observation.NOT_ENOUGH_DATA, CheckIn.CHEER),
    RECOVERED(Observation.RECOVERED, CheckIn.CHEER),
    RUSHED(Observation.RUSHED, CheckIn.ASK_TROUBLE),
    CURVY(Observation.CURVES_FAST, CheckIn.ASK_HURRY),
    CALM(Observation.CALM, CheckIn.CHEER),
}

/**
 * 주행이 끝났을 때 눈티가 하는 마무리 멘트 (순수 Kotlin, 규칙 기반).
 * 사실은 점수 엔진 결과(사건 횟수·감정 흐름·평가 범위)에서만 가져온다. 나중에 LLM 으로 바꾸면 [compose] 가 실패 시 대체 문구가 된다.
 */
object ClosingMessage {
    /** 급가속·급감속·급제동이 이 횟수 이상이거나 최종 점수가 이 값 미만이면 "급한 주행" (초안). */
    private const val RUSHED_EVENTS = 2
    private const val RUSHED_BELOW = 70f

    private val harsh = setOf(DetectedEvent.Kind.HARD_ACCEL, DetectedEvent.Kind.HARD_DECEL, DetectedEvent.Kind.HARD_BRAKE)

    fun tone(report: ScoreReport, emotion: Emotion): TripTone {
        val total = report.total
        return when {
            total == null || report.coverage < TripLifecycle.MIN_COVERAGE -> TripTone.UNKNOWN
            emotion == Emotion.RELIEF -> TripTone.RECOVERED
            total < RUSHED_BELOW || report.events.count { it.kind in harsh } >= RUSHED_EVENTS -> TripTone.RUSHED
            report.events.any { it.kind == DetectedEvent.Kind.CURVE_TOO_FAST } -> TripTone.CURVY
            else -> TripTone.CALM
        }
    }

    /**
     * 총평 + 안부를 조합한다. [variant] 가 늘 때마다 총평 문구가 먼저 바뀌고, 한 바퀴 돌면 안부 문구가 바뀌어
     * 두 부품의 모든 조합을 차례로 돈다 (결정적).
     */
    fun compose(report: ScoreReport, emotion: Emotion, variant: Int = 0): String = compose(tone(report, emotion), variant)

    fun compose(tone: TripTone, variant: Int = 0): String {
        val obs = tone.observation.variants
        val checkIn = tone.checkIn.variants
        val first = obs[Math.floorMod(variant, obs.size)]
        val second = checkIn[Math.floorMod(Math.floorDiv(variant, obs.size), checkIn.size)]
        return "$first $second"
    }
}
