package ai.nunti.app

import ai.pleos.playground.navi.constants.NaviErrorCode
import ai.pleos.playground.navi.constants.NavigationStatus
import ai.pleos.playground.navi.constants.RouteOption
import ai.pleos.playground.navi.data.CurrentLocationInfo
import ai.pleos.playground.navi.data.RouteInfo
import ai.pleos.playground.navi.data.RouteStartInfo
import ai.pleos.playground.navi.data.TBTInfo
import ai.pleos.playground.navi.helper.NaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener
import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.util.Log

/**
 * 디버그 전용 ADB 진입점: 내비 콜백을 전부 logcat(NaviProbe)에 남기고, 인텐트로 경로를 요청한다.
 *   am start -n .../ai.nunti.app.NaviProbeActivity --ed lat 37.40 --ed lng 127.11 --es name test
 * 위치 주입이 내비 앱에 닿는지(onCurrentLocationInfo 변화), TBT·제한속도 콜백이 오는지 확인하는 용도다.
 */
class NaviProbeActivity : Activity() {
    private var helper: NaviHelper? = null
    private val tag = "NaviProbe"

    private val listener = object : NaviHelperEventListener {
        override fun onCurrentLocationInfo(p0: CurrentLocationInfo) {
            Log.i(tag, "LOC lat=${p0.latitude} lng=${p0.longitude} heading=${p0.heading} idx=${p0.currentRouteIndex}")
        }
        override fun onTBTInfo(p0: List<TBTInfo>) {
            Log.i(tag, "TBT " + p0.take(3).joinToString { "${it.type.name}@${it.distance.toInt()}m" })
        }
        override fun onCurrentRoadSpeedLimit(p0: Int) { Log.i(tag, "LIMIT $p0") }
        override fun onNavigationStatus(p0: NavigationStatus) { Log.i(tag, "STATUS ${p0.name}") }
        override fun onRouteStarted(p0: RouteStartInfo) { Log.i(tag, "ROUTE_STARTED") }
        override fun onRoutingCompleted() { Log.i(tag, "ROUTING_COMPLETED") }
        override fun onReRouteEnded() { Log.i(tag, "REROUTE_ENDED") }
        override fun onRouteEnded() { Log.i(tag, "ROUTE_ENDED") }
        override fun onRouteCancelled() { Log.i(tag, "ROUTE_CANCELLED") }
        override fun onError(p0: NaviErrorCode) { Log.i(tag, "ERROR ${p0.name}") }
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val h = NaviHelper(this)
        helper = h
        h.initialize({ Log.i(tag, "INIT_OK"); h.addListener(listener); handle(intent) }, { Log.i(tag, "INIT_FAIL ${it.message}") })
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); handle(intent) }

    private fun handle(i: Intent) {
        val h = helper ?: return
        if (i.hasExtra("lat")) {
            val lat = i.getDoubleExtra("lat", 0.0); val lng = i.getDoubleExtra("lng", 0.0)
            Log.i(tag, "REQUEST_ROUTE $lat,$lng")
            h.requestRoute(RouteInfo(lat, lng, null, null, i.getStringExtra("name") ?: "probe", "probe", "", "", RouteOption.RECOMMENDED, "probe", false))
        }
        if (i.getBooleanExtra("poll", false)) { h.getCurrentLocationInfo(); h.getTBTInfo() }
        if (i.getBooleanExtra("reroute", false)) h.requestReRoute()
        if (i.getBooleanExtra("cancel", false)) h.cancelRoute()
    }

    override fun onDestroy() { runCatching { helper?.removeListener(listener); helper?.release() }; super.onDestroy() }
}
