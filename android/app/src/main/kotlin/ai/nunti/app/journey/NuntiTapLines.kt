package ai.nunti.app.journey

import ai.nunti.app.journey.NuntiSpriteDirector.Stage

/**
 * 정차 중 눈티를 눌렀을 때 하는 말. 상황마다 정해 둔 대사를 누를 때마다 차례로 돌린다.
 * 음원은 assets/nunti-voice/<id>.mp3 (미리 합성한 캐릭터 음성). 주행 중에는 반응하지 않는다.
 */
internal object NuntiTapLines {
    class Line(val id: String, val text: String, val seconds: Float) {
        val asset get() = "nunti-voice/$id.mp3"
    }

    enum class Moment { READY, REST, GOOD, LOW, NO_SCORE, IDLE }

    /** 이만큼 달렸으면 출발 전이 아니라 여정 중간에 세운 것으로 본다. */
    const val DRIVEN_KM = .05

    private val READY_1 = Line("tap_ready_1", "오늘은 어디로 가볼까요?", 2.19f)
    private val LOW_1 = Line("tap_low_1", "무사히 도착했어요!", 2.3f)
    private val LOW_2 = Line("tap_low_2", "수고했어요, 푹 쉬어요.", 2.9f)

    private val lines = mapOf(
        Moment.READY to listOf(READY_1,
            Line("tap_ready_2", "출발 준비 됐어요!", 2.25f),
            Line("tap_ready_3", "안전벨트 꼭 매요!", 2.35f),
            Line("tap_ready_4", "오늘도 같이 가요!", 1.72f)),
        Moment.REST to listOf(
            Line("tap_rest_1", "잠깐 쉬어 가요!", 1.83f),
            Line("tap_rest_2", "기지개 한 번 쭉 켜요~", 2.9f),
            Line("tap_rest_3", "물 한 모금 어때요?", 1.72f),
            Line("tap_rest_4", "준비되면 다시 출발해요!", 2.38f)),
        Moment.GOOD to listOf(
            Line("tap_good_1", "오늘 운전 최고였어요!", 2.48f),
            Line("tap_good_2", "부드럽게 잘 왔어요!", 2.56f),
            Line("tap_good_3", "다음에도 같이 가요!", 1.96f)),
        Moment.LOW to listOf(LOW_1, LOW_2, Line("tap_low_3", "다음엔 더 천천히 가 봐요.", 3.13f)),
        // 점수가 없으면 운전 습관 이야기는 하지 않는다.
        Moment.NO_SCORE to listOf(LOW_1, LOW_2),
        Moment.IDLE to listOf(Line("tap_idle_1", "여정을 시작하면 같이 갈게요!", 2.79f), READY_1),
    )

    val all get() = lines.values.flatten().distinctBy { it.id }

    /** 주행 중이면 null — 눌러도 말하지 않는다. */
    fun momentFor(stage: Stage, drivenKm: Double, total: Double?): Moment? = when (stage) {
        Stage.DRIVING -> null
        Stage.PARKED -> if (drivenKm >= DRIVEN_KM) Moment.REST else Moment.READY
        Stage.REPORT_GOOD -> Moment.GOOD
        Stage.REPORT_LOW -> if (total == null) Moment.NO_SCORE else Moment.LOW
        Stage.EMPTY -> Moment.IDLE
    }

    /** [count] 번째 누름(0부터)의 대사. */
    fun pick(moment: Moment, count: Int): Line = lines.getValue(moment).let { it[Math.floorMod(count, it.size)] }
}
