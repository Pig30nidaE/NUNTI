package ai.nunti.score

/**
 * 지금 주행을 끝내고 점수를 확정해도 되는지. 못 되면 이유가 곧 안내 문구다.
 * 정차(신호는 오는데 움직이지 않음)와 신호 부족(못 받음)은 원인이 달라서 따로 안내한다.
 */
enum class Readiness(vararg val notices: String) {
    READY,
    WAITING_FOR_MOVEMENT("아직 평가할 만큼 달리지 않았어요.", "지금은 멈춰 있어서 평가할 게 없어요."),
    WAITING_FOR_SIGNALS("차량 신호가 부족해서 평가를 못 했어요.", "받은 신호가 적어서 점수를 낼 수 없어요."),
}

/** 일시저장 안내의 뒷문장. 앞에 [Readiness.notices] 한 문장이 붙는다. */
enum class PauseFollowUp(vararg val variants: String) {
    SAVED_FOR_NOW("점수는 잠깐 저장해 둘게요.", "일단 여기까지 저장해 둘게요."),
}

/** 주행의 진행 상태. 종료를 요청했는데 아직 확정할 수 없으면 PAUSED(일시저장)이고, 이후 충분해지면 FINISHED 가 된다. */
enum class TripStatus { DRIVING, PAUSED, FINISHED }

object TripLifecycle {
    /** 실제로 움직인 시간이 이 값(초) 미만이면 평가할 주행이 아직 없다 (초안). */
    const val MIN_MOVING_SECONDS = 30
    /** 평가 범위가 이 값 미만이면(속도만 받은 경우 35%) 점수를 믿기 어렵다 (초안). */
    const val MIN_COVERAGE = 0.5f

    fun readiness(report: ScoreReport): Readiness = when {
        report.speedSeconds == 0 -> Readiness.WAITING_FOR_SIGNALS // 속도 신호가 아예 없다
        report.movingSeconds < MIN_MOVING_SECONDS -> Readiness.WAITING_FOR_MOVEMENT
        report.total == null || report.coverage < MIN_COVERAGE -> Readiness.WAITING_FOR_SIGNALS
        else -> Readiness.READY
    }

    /** 종료가 요청됐을 때의 상태. 확정할 수 없으면 종료하지 않고 일시저장한다. */
    fun onEndRequested(report: ScoreReport): TripStatus =
        if (readiness(report) == Readiness.READY) TripStatus.FINISHED else TripStatus.PAUSED

    /** 일시저장 안내 멘트: 이유 한 문장 + 저장 안내 한 문장. [variant] 로 문구를 번갈아 쓴다. */
    fun pauseNotice(readiness: Readiness, variant: Int = 0): String? {
        if (readiness == Readiness.READY) return null
        val reason = readiness.notices[Math.floorMod(variant, readiness.notices.size)]
        val follow = PauseFollowUp.SAVED_FOR_NOW.variants.let { it[Math.floorMod(variant, it.size)] }
        return "$reason $follow"
    }
}
