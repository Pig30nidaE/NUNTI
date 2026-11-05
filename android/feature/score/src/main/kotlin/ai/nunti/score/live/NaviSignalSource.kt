package ai.nunti.score.live

import ai.pleos.playground.navi.constants.TurnType
import ai.pleos.playground.navi.data.TBTInfo
import ai.pleos.playground.navi.helper.NaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener
import android.content.Context
import android.util.Log
import ai.nunti.score.DrivingEvent
import ai.nunti.score.TurnSignal
import java.util.concurrent.CopyOnWriteArrayList

/**
 * NaviHelper 이벤트로 "실제 회전 이벤트"와 도로 제한속도를 만든다.
 * 회전 이벤트: 다음 회전 안내(TBT)의 남은 거리가 가까워졌다가 안내가 바뀌면 그 회전을 지난 것으로 본다.
 * (안내만 있고 실제로 회전하지 않았을 가능성은 남아 있어, 방향 전환 확인은 추후 검증 대상.)
 */
class NaviSignalSource(private val context: Context, private val clockMs: () -> Long) {
    private val tag = "NuntiNavi"
    private var helper: NaviHelper? = null

    @Volatile var speedLimitKmh: Int? = null
        private set
    @Volatile var status: String = "대기"
        private set
    @Volatile var nextTurn: String = "-"
        private set
    val events = CopyOnWriteArrayList<DrivingEvent>()

    private var head: TBTInfo? = null
    private var headDistance = Double.MAX_VALUE

    private val listener = object : NaviHelperEventListener {
        override fun onTBTInfo(list: List<TBTInfo>) {
            val next = list.firstOrNull { it.type != TurnType.TURN_UNKNOWN }
            nextTurn = next?.let { "${it.type.name.removePrefix("TURN_")} ${it.distance.toInt()}m" } ?: "없음"
            val prev = head
            val changed = prev == null || next == null || next.type != prev.type ||
                next.distance > headDistance + 50.0
            if (prev != null && changed && headDistance < PASSED_WITHIN_M) {
                direction(prev.type)?.let { events.add(DrivingEvent(clockMs(), DrivingEvent.Kind.TURN, it)) }
            }
            if (next == null || changed) headDistance = Double.MAX_VALUE
            head = next
            if (next != null) headDistance = minOf(headDistance, next.distance)
        }

        override fun onCurrentRoadSpeedLimit(limit: Int) {
            speedLimitKmh = limit.takeIf { it > 0 }
        }

        override fun onRouteEnded() { head = null; headDistance = Double.MAX_VALUE; nextTurn = "경로 종료" }
        override fun onRouteCancelled() { head = null; headDistance = Double.MAX_VALUE; nextTurn = "경로 취소" }
        override fun onError(code: ai.pleos.playground.navi.constants.NaviErrorCode) { status = "오류 ${code.name}" }
    }

    fun start() {
        val h = NaviHelper(context)
        helper = h
        runCatching {
            h.initialize({ status = "연결됨"; h.addListener(listener); h.getTBTInfo() }, { status = "초기화 실패: ${it.message}" })
        }.onFailure { status = "예외: ${it.message}"; Log.w(tag, "init", it) }
    }

    /** 경로가 이미 진행 중이면 현재 안내를 한 번 요청해 초기 상태를 채운다. */
    fun poll() { runCatching { helper?.getTBTInfo() } }

    fun stop() {
        runCatching { helper?.removeListener(listener) }
        runCatching { helper?.release() }
        helper = null
    }

    private fun direction(t: TurnType): TurnSignal? = when (t) {
        TurnType.TURN_RIGHT, TurnType.TURN_SHARP_R, TurnType.TURN_KEEP_R -> TurnSignal.RIGHT
        TurnType.TURN_LEFT, TurnType.TURN_SHARP_L, TurnType.TURN_KEEP_L -> TurnSignal.LEFT
        else -> null
    }

    private companion object { const val PASSED_WITHIN_M = 60.0 }
}
