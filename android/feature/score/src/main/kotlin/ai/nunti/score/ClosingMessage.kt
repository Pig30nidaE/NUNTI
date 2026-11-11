package ai.nunti.score

/**
 * 마무리 멘트의 부품. "전체 총평 + 기억에 남은 장면 + 안부" 세 부품을 이어 붙인다.
 * 부품마다 따로 녹음하므로, 문구를 고치려면 해당 enum 항목의 문장만 바꾸고 그 음원을 다시 만든다.
 * 모든 부품은 80자 이하이고 점수 숫자를 말하지 않는다 (시험으로 확인).
 */

/** 주행 전체에 대한 총평. 최종 점수 구간으로 고르고, 사건이 있으면 한 단계씩 낮춘다. */
enum class Verdict(vararg val variants: String) {
    UNKNOWN(
        "음, 오늘은 제가 놓친 게 많아서 어땠는지 다 말하긴 어려워요.",
        "오늘은 차가 알려 준 게 적어서 점수를 매기기 어려워요.",
    ),
    GREAT(
        "와, 오늘은 처음부터 끝까지 구름 위를 달리는 것 같았어요!",
        "오늘 진짜 편안했어요. 타는 내내 콧노래가 나왔어요.",
    ),
    GOOD(
        "오늘은 대부분 편안해서 기분이 좋았어요.",
        "오늘 같이 달린 거, 전체적으로 포근했어요.",
    ),
    FAIR(
        "오늘은 편안할 때도 있었는데, 가끔 마음이 콩닥콩닥했어요.",
        "오늘은 괜찮았어요. 그래도 몇 번은 저도 모르게 꽉 붙잡았어요.",
    ),
    LOW(
        "오늘은 같이 타는 내내 조금 바짝 긴장했어요.",
        "오늘은 마음이 계속 조마조마했어요.",
    ),
}

/** 총평 뒤에 붙는, 그날 가장 기억에 남은 장면. 확인된 사건과 감정 흐름에서만 고른다. */
enum class Highlight(vararg val variants: String) {
    RECOVERED("중간엔 걱정했는데, 갈수록 차분해져서 마음이 놓였어요.", "처음엔 조금 급했는데, 끝에는 편안하게 와 줘서 다행이에요."),
    /** 급제동과 급감속(브레이크 신호 없는 같은 세기의 감속)을 함께 맡는다. */
    BRAKES("갑자기 멈출 땐 심장이 쿵 했어요.", "속도가 확 줄 때마다 앞으로 데굴 구를 뻔했어요."),
    ACCEL("속도가 확 붙을 땐 의자에 착 달라붙었어요.", "출발할 때 슝 하고 날아가는 줄 알았어요."),
    CURVES("커브에서 몸이 옆으로 기우뚱했어요.", "커브 돌 때 빙글빙글 조금 어지러웠어요."),
    SMOOTH("한 번도 몸이 쏠리지 않았어요. 대단해요!", "덕분에 창밖 구경하면서 편하게 왔어요."),
}

/** 마지막 안부·인사. 걱정스러운 주행에만 질문([asks])이 붙는다. */
enum class CheckIn(val asks: Boolean, vararg val variants: String) {
    ASK_TROUBLE(true, "무슨 안 좋은 일 있나요?", "혹시 무슨 일 있었어요?"),
    ASK_HURRY(true, "오늘 많이 바빴나요?", "혹시 급한 일 있었어요?"),
    CHEER(false, "같이 와서 좋았어요!", "오늘도 수고했어요!"),
}

/** 한 번의 마무리 멘트에 쓸 부품. [highlight] 가 없으면 총평 바로 뒤에 안부가 온다. */
data class ClosingPlan(val verdict: Verdict, val highlight: Highlight?, val checkIn: CheckIn)

/**
 * 주행이 끝났을 때 눈티가 하는 마무리 멘트 (순수 Kotlin, 규칙 기반).
 * 사실은 점수 엔진 결과(최종 점수·사건·감정 흐름·평가 범위)에서만 가져온다. 나중에 LLM 으로 바꾸면 [compose] 가 실패 시 대체 문구가 된다.
 */
object ClosingMessage {
    /** 급한 사건이 이 횟수 이상이면 점수가 높아도 총평을 [Verdict.FAIR] 이하로 둔다 (초안). */
    private const val RUSHED_EVENTS = 2

    /** 몸이 쏠리는 사건을 장면별로 묶는다. 급감속은 급제동과, 후진 과속은 급가속과 같은 장면으로 본다. */
    private val scene = mapOf(
        DetectedEvent.Kind.HARD_BRAKE to Highlight.BRAKES,
        DetectedEvent.Kind.HARD_DECEL to Highlight.BRAKES,
        DetectedEvent.Kind.CURVE_TOO_FAST to Highlight.CURVES,
        DetectedEvent.Kind.HARD_ACCEL to Highlight.ACCEL,
        DetectedEvent.Kind.REVERSE_TOO_FAST to Highlight.ACCEL,
    )
    /** 같은 횟수면 이 순서로 고른다 (더 놀라운 장면 먼저). */
    private val sceneOrder = listOf(Highlight.BRAKES, Highlight.CURVES, Highlight.ACCEL)

    fun plan(report: ScoreReport, emotion: Emotion): ClosingPlan {
        val total = report.total
        if (total == null || report.coverage < TripLifecycle.MIN_COVERAGE) return ClosingPlan(Verdict.UNKNOWN, null, CheckIn.CHEER)

        val scenes = report.events.mapNotNull { scene[it.kind] }
        val byScore = when {
            total >= 90f -> Verdict.GREAT
            total >= 80f -> Verdict.GOOD
            total >= 70f -> Verdict.FAIR
            else -> Verdict.LOW
        }
        val cap = when {
            scenes.size >= RUSHED_EVENTS -> Verdict.FAIR
            scenes.isNotEmpty() -> Verdict.GOOD
            else -> Verdict.GREAT
        }
        val verdict = if (byScore.ordinal >= cap.ordinal) byScore else cap

        val counts = scenes.groupingBy { it }.eachCount()
        val highlight = when {
            emotion == Emotion.RELIEF -> Highlight.RECOVERED
            counts.isNotEmpty() -> sceneOrder.maxBy { counts[it] ?: 0 } // 동률이면 앞의 것
            verdict == Verdict.GREAT || verdict == Verdict.GOOD -> Highlight.SMOOTH
            else -> null
        }
        val checkIn = when {
            highlight == Highlight.RECOVERED -> CheckIn.CHEER
            verdict == Verdict.LOW -> CheckIn.ASK_TROUBLE
            verdict == Verdict.FAIR -> CheckIn.ASK_HURRY
            else -> CheckIn.CHEER
        }
        return ClosingPlan(verdict, highlight, checkIn)
    }

    fun compose(report: ScoreReport, emotion: Emotion, variant: Int = 0): String = compose(plan(report, emotion), variant)

    /**
     * [variant] 가 늘 때마다 총평 문구가 먼저 바뀌고, 한 바퀴 돌면 장면 문구, 그다음 안부 문구가 바뀌어
     * 모든 조합을 차례로 돈다 (결정적).
     */
    fun compose(plan: ClosingPlan, variant: Int = 0): String {
        val parts = listOfNotNull(plan.verdict.variants, plan.highlight?.variants, plan.checkIn.variants)
        var rest = variant
        return parts.joinToString(" ") { options ->
            options[Math.floorMod(rest, options.size)].also { rest = Math.floorDiv(rest, options.size) }
        }
    }
}
