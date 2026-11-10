package ai.nunti.score.live

import ai.nunti.score.DrivingEvent
import ai.nunti.score.TurnSignal
import ai.pleos.playground.navi.constants.NaviErrorCode
import ai.pleos.playground.navi.constants.TurnType
import ai.pleos.playground.navi.data.CurrentLocationInfo
import ai.pleos.playground.navi.data.RouteStartInfo
import ai.pleos.playground.navi.data.TBTInfo
import ai.pleos.playground.navi.helper.NaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener
import android.content.Context
import android.util.Log

data class NavigationLocation(val latitude: Double, val longitude: Double, val receivedAtElapsedMs: Long)

/** TBT passage is only an inferred turn opportunity, not a verified change in vehicle heading. */
class NaviSignalSource(private val context: Context, private val clockMs: () -> Long) {
    private val gate = SignalSessionGate()
    private var helper: NaviHelper? = null
    private var listener: NaviHelperEventListener? = null
    @Volatile var speedLimitKmh: Int? = null
        private set
    @Volatile var status = "대기"
        private set
    @Volatile var nextTurn = "-"
        private set
    @Volatile var location: NavigationLocation? = null
        private set
    private val recordedEvents = mutableListOf<DrivingEvent>()
    val events: List<DrivingEvent> get() = gate.read { recordedEvents.toList() }
    private var head: TBTInfo? = null
    private var headDistance = Double.MAX_VALUE

    private fun reset() {
        speedLimitKmh = null; location = null; nextTurn = "-"
        head = null; headDistance = Double.MAX_VALUE; recordedEvents.clear()
    }

    @Synchronized
    fun start() {
        val epoch = gate.begin { reset(); status = "연결 중" } ?: return
        val l = object : NaviHelperEventListener {
            override fun onTBTInfo(list: List<TBTInfo>) {
                gate.accept(epoch) {
                    val next = list.firstOrNull { it.type != TurnType.TURN_UNKNOWN }
                    nextTurn = next?.let { "${it.type.name.removePrefix("TURN_")} ${it.distance.toInt()}m" } ?: "없음"
                    val prev = head
                    val changed = prev == null || next == null || next.type != prev.type || next.distance > headDistance + 50.0
                    if (prev != null && changed && headDistance < 60.0) {
                        direction(prev.type)?.let { recordedEvents += DrivingEvent(clockMs(), DrivingEvent.Kind.TURN, it) }
                    }
                    if (next == null || changed) headDistance = Double.MAX_VALUE
                    head = next
                    if (next != null) headDistance = minOf(headDistance, next.distance)
                }
            }
            override fun onCurrentRoadSpeedLimit(limit: Int) { gate.accept(epoch) { speedLimitKmh = limit.takeIf { it > 0 } } }
            override fun onCurrentLocationInfo(info: CurrentLocationInfo) {
                gate.accept(epoch) {
                    val lat = info.latitude
                    val lon = info.longitude
                    location = if (lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0 && (lat != 0.0 || lon != 0.0))
                        NavigationLocation(lat, lon, clockMs()) else null
                }
            }
            override fun onRouteStarted(info: RouteStartInfo) {
                gate.accept(epoch) { head = null; headDistance = Double.MAX_VALUE; speedLimitKmh = null; nextTurn = "경로 계산 중" }
            }
            override fun onRoutingCompleted() { gate.accept(epoch) { status = "경로 계산 완료" } }
            @Deprecated("NaviHelper onRouteEnded means routing completion, not journey arrival")
            override fun onRouteEnded() { onRoutingCompleted() }
            override fun onRouteCancelled() {
                gate.accept(epoch) { head = null; headDistance = Double.MAX_VALUE; speedLimitKmh = null; nextTurn = "경로 취소" }
            }
            override fun onError(code: NaviErrorCode) {
                gate.accept(epoch) { status = "오류 ${code.name}"; speedLimitKmh = null; head = null; headDistance = Double.MAX_VALUE }
            }
        }
        listener = l
        runCatching {
            val h = NaviHelper(context)
            helper = h
            h.initialize({
                if (gate.accept(epoch) { status = "연결됨" }) {
                    runCatching {
                        h.addListener(l)
                        if (gate.current() == epoch) { h.getTBTInfo(); h.getCurrentLocationInfo() }
                        else { h.removeListener(l); h.release() }
                    }.onFailure { error -> gate.accept(epoch) { status = "조회 실패: ${error.message}" } }
                }
            }, { error -> gate.accept(epoch) { status = "초기화 실패: ${error.message}" } })
        }.onFailure { gate.accept(epoch) { status = "예외: ${it.message}" }; Log.w("NuntiNavi", "init", it) }
    }

    @Synchronized
    fun poll() {
        if (gate.current() == null) return
        runCatching { helper?.getTBTInfo(); helper?.getCurrentLocationInfo() }
    }

    @Synchronized
    fun stop() {
        val h = helper
        val l = listener
        if (!gate.end { reset(); status = "중지" }) return
        if (l != null) runCatching { h?.removeListener(l) }
        runCatching { h?.release() }
        helper = null; listener = null
    }

    private fun direction(t: TurnType): TurnSignal? = when (t) {
        TurnType.TURN_RIGHT, TurnType.TURN_SHARP_R, TurnType.TURN_KEEP_R -> TurnSignal.RIGHT
        TurnType.TURN_LEFT, TurnType.TURN_SHARP_L, TurnType.TURN_KEEP_L -> TurnSignal.LEFT
        else -> null
    }
}
