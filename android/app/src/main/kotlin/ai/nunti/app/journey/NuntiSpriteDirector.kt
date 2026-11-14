package ai.nunti.app.journey

/**
 * 기본 눈티 손그림 동작(nunti-sprites)을 상황에 따라 고르는 순수 로직. 그리기·에셋과 분리해 시험한다.
 * 좌표는 캐릭터 768 공간 단위, 시간은 초. 프레임 루프에서 할당하지 않는다.
 */
internal object NuntiSpriteDirector {
    enum class Stage { EMPTY, PARKED, DRIVING, REPORT_GOOD, REPORT_LOW }

    class Shot { var clip = STAND; var frame = 0; var dx = 0f; var breath = 0f }

    const val WALK_R = "walkR"
    const val WALK_L = "walkL"
    const val FOLD = "fold"
    /** 서 있는 모습. 기본 눈티 원본 그림을 그대로 쓴다. */
    const val STAND = "stand"
    const val JUMP = "jump"
    const val SIT = "sit"

    /** 걷기 한 장 0.12초, 한 장에 19 단위 전진 → 발이 바닥에서 미끄러지지 않는 속도. */
    const val WALK_FRAME = .12f
    const val WALK_SPEED = 19f / WALK_FRAME
    private const val FOLD_FRAME = .12f
    private val JUMP_TIMES = floatArrayOf(.3f, .09f, .09f, .09f, .09f, .09f, .09f, .09f)
    val JUMP_SECONDS = JUMP_TIMES.sum()
    /** 돌아다니는 최대 거리. 화면이 좁으면 이보다 줄인다. */
    const val MAX_WANDER = 260f
    /** 이 거리보다 좁으면 걷지 않고 제자리에서만 움직인다. */
    private const val MIN_WANDER = 60f
    private const val REPORT_JUMP_PERIOD = 7f

    /** 두 점수 사이를 가르는 기준. 이 점수 이상이면 도착 화면에서 점프한다. */
    const val GOOD_SCORE = 80.0

    fun stageFor(screenParked: Boolean, screenDriving: Boolean, screenReport: Boolean, total: Double?) = when {
        screenReport -> if (total != null && total >= GOOD_SCORE) Stage.REPORT_GOOD else Stage.REPORT_LOW
        screenParked -> Stage.PARKED
        screenDriving -> Stage.DRIVING
        else -> Stage.EMPTY
    }

    /**
     * [t] 상황이 시작된 뒤 지난 시간, [sinceTap] 마지막 터치 뒤 시간(없으면 음수), [range] 좌우로 걸을 수 있는 거리.
     * [animated] 가 false 면(주행 중·애니메이션 끔) 움직이지 않는 대표 장면만 고른다.
     */
    fun sample(stage: Stage, t: Float, sinceTap: Float, animated: Boolean, range: Float, out: Shot) {
        out.dx = 0f; out.breath = 0f; out.frame = 0
        if (!animated) {
            when (stage) {
                Stage.DRIVING, Stage.EMPTY -> out.clip = SIT
                Stage.REPORT_LOW -> { out.clip = FOLD; out.frame = 3 }
                else -> stand(out)
            }
            return
        }
        out.breath = breath(t)
        when (stage) {
            Stage.DRIVING, Stage.EMPTY -> out.clip = SIT
            Stage.REPORT_GOOD -> {
                if (!tap(sinceTap, out)) jumpOrStand((t % REPORT_JUMP_PERIOD), out)
            }
            Stage.REPORT_LOW -> {
                if (!tap(sinceTap, out)) arms(foldIn(t - .6f), out)
            }
            Stage.PARKED -> {
                // 출발 준비 화면에 들어오면 한 번 뛰고, 그다음 돌아다니기 순서를 반복한다.
                if (t < JUMP_SECONDS) { jump(t, out); return }
                wander(t - JUMP_SECONDS, range, out)
                if (tapAt(sinceTap)) { val dx = out.dx; jump(sinceTap, out); out.dx = dx }
            }
        }
    }

    private fun breath(t: Float) = kotlin.math.sin(t * 1.35f)

    private fun tapAt(sinceTap: Float) = sinceTap in 0f..JUMP_SECONDS
    private fun tap(sinceTap: Float, out: Shot): Boolean { if (!tapAt(sinceTap)) return false; jump(sinceTap, out); return true }

    private fun jumpOrStand(t: Float, out: Shot) { if (t < JUMP_SECONDS) jump(t, out) else stand(out) }

    private fun stand(out: Shot) { out.clip = STAND; out.frame = 0 }

    /** 팔짱 장면 [frame]. 팔을 내린 첫 장은 서 있는 원본 그림으로 대신한다. */
    private fun arms(frame: Int, out: Shot) { if (frame == 0) stand(out) else { out.clip = FOLD; out.frame = frame } }

    fun jump(t: Float, out: Shot) {
        out.clip = JUMP
        var left = t
        for (i in JUMP_TIMES.indices) { if (left < JUMP_TIMES[i]) { out.frame = i; return }; left -= JUMP_TIMES[i] }
        stand(out)
    }

    /** 팔짱 끼는 장면 번호. 0.12초마다 한 장씩 넘어가 마지막 장에서 멈춘다. */
    private fun foldIn(t: Float) = if (t <= 0f) 0 else (t / FOLD_FRAME).toInt().coerceAtMost(3)

    private class Leg(val seconds: Float, val kind: Int, val from: Float, val to: Float)
    private const val STILL = 0
    private const val WALK = 1
    private const val ARMS = 2
    private const val FOLD_HOLD = 3f
    private var seq: Array<Leg> = emptyArray()
    private var period = 0f
    private var seqFor = Float.NaN

    /**
     * 가운데서 쉬다가 → 오른쪽으로 걸어가 잠깐 서고 → 왼쪽 끝까지 걸어가 → 팔짱 끼고 기다리다 풀고 → 가운데로 돌아온다.
     * 끝나면 처음부터 반복한다. 걸을 자리가 없으면 제자리에서 쉬고 팔짱만 낀다.
     */
    @Synchronized fun wander(t: Float, range: Float, out: Shot) {
        val d = range.coerceIn(0f, MAX_WANDER).let { if (it < MIN_WANDER) 0f else it }
        if (d != seqFor) { seq = legs(d); period = seq.fold(0f) { a, l -> a + l.seconds }; seqFor = d }
        var left = t % period
        for (leg in seq) {
            if (left >= leg.seconds) { left -= leg.seconds; continue }
            out.dx = leg.from + (leg.to - leg.from) * (left / leg.seconds)
            when (leg.kind) {
                WALK -> { out.clip = if (leg.to > leg.from) WALK_R else WALK_L; out.frame = (left / WALK_FRAME).toInt() % 8 }
                // 끼는 장면을 앞에서, 푸는 장면을 뒤에서 거꾸로 센다.
                ARMS -> arms(minOf(foldIn(left), foldIn(leg.seconds - left)), out)
                else -> stand(out)
            }
            return
        }
        stand(out)
    }

    private fun legs(d: Float): Array<Leg> {
        val walk = d / WALK_SPEED
        val arms = FOLD_HOLD + 2 * 4 * FOLD_FRAME
        return if (d == 0f) arrayOf(Leg(5f, STILL, 0f, 0f), Leg(arms, ARMS, 0f, 0f), Leg(7f, STILL, 0f, 0f))
        else arrayOf(
            Leg(4f, STILL, 0f, 0f), Leg(walk, WALK, 0f, d), Leg(1.5f, STILL, d, d),
            Leg(walk * 2, WALK, d, -d), Leg(1f, STILL, -d, -d), Leg(arms, ARMS, -d, -d),
            Leg(.8f, STILL, -d, -d), Leg(walk, WALK, -d, 0f), Leg(6f, STILL, 0f, 0f),
        )
    }
}
