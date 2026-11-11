package ai.nunti.score.live

import ai.pleos.playground.vehicle.IVehicleService
import ai.pleos.playground.vehicle.callback.IPropertyCallback
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import android.util.Log

/**
 * 실험: 공개 SDK(Vehicle 2.3.2)에 없는 PERF_VEHICLE_SPEED 를 Vehicle 서비스에 직접 구독한다.
 * SDK와 같은 프로토콜: registerPropertyCallback(패키지, 속성명, 영역, 콜백).
 * 앞차 거리와 밤 모드도 같은 서비스에서 속성 이름으로 함께 구독한다.
 * 구독 한 번(start~stop)마다 세대(epoch)를 두어, 멈춘 뒤 늦게 온 콜백이 다음 구독에 섞이지 않게 한다.
 */
class RawSpeedProbe(
    private val context: Context,
    /** 앞차 거리(mm). 적응형 크루즈가 앞차를 재는 동안에만 온다. */
    private val onLeadDistanceMm: (Int) -> Unit = {},
    /** NIGHT_MODE: 차량이 낮/밤을 판단한 최종 결과(밤이면 true). */
    private val onNightMode: (Boolean) -> Unit = {},
    /** 속도 값을 잃었다(오류·끊김·중지). 받는 쪽은 마지막 속도를 버린다. */
    private val onUnavailable: () -> Unit = {},
    private val onSpeed: (Float) -> Unit,
) {
    private val gate = SignalSessionGate()
    @Volatile var status: LinkStatus = LinkStatus(LinkState.IDLE)
        private set
    @Volatile var lastRaw: String? = null
        private set
    @Volatile var lastLeadRaw: String? = null
        private set
    /** 앞차 거리 구독 결과: 요청은 성공했는지(서비스가 이름을 받았는지)와 오류. */
    @Volatile var leadStatus: LinkStatus = LinkStatus(LinkState.IDLE)
        private set
    @Volatile var lastNightRaw: String? = null
        private set
    @Volatile private var service: IVehicleService? = null
    private var connection: ServiceConnection? = null
    private var callback: IPropertyCallback? = null
    private var bound = false

    @Synchronized
    fun start() {
        val epoch = gate.begin { status = LinkStatus(LinkState.IDLE); leadStatus = LinkStatus(LinkState.IDLE); lastRaw = null; lastLeadRaw = null } ?: return
        val cb = object : IPropertyCallback.Stub() {
            override fun onChangeEvent(prop: String?, area: Int, value: String?) {
                // 같은 패키지로 등록한 다른 속성 이벤트도 이 콜백으로 온다.
                val v = value?.trim()?.trim('"')
                gate.accept(epoch) {
                    when (prop) {
                        LEAD_PROPERTY -> {
                            lastLeadRaw = "$prop[$area]=$value"
                            v?.toFloatOrNull()?.takeIf { it.isFinite() }?.let { onLeadDistanceMm(it.toInt()) }
                        }
                        NIGHT_PROPERTY -> {
                            lastNightRaw = "$prop[$area]=$value"
                            when (v?.lowercase()) { "true", "1" -> onNightMode(true); "false", "0" -> onNightMode(false) }
                        }
                        SPEED_PROPERTY -> {
                            lastRaw = "$prop[$area]=$value"
                            // 서비스 값은 m/s (AAOS PERF_VEHICLE_SPEED 와 동일) → km/h
                            val speed = v?.toFloatOrNull()?.takeIf { it.isFinite() }
                            if (speed == null) onUnavailable() else onSpeed(speed * 3.6f)
                        }
                    }
                }
            }
            override fun onErrorEvent(prop: String?, message: String?) {
                gate.accept(epoch) {
                    when (prop) {
                        NIGHT_PROPERTY -> Log.w(TAG, "night: $message")
                        LEAD_PROPERTY -> { leadStatus = LinkStatus(LinkState.FAILED, message ?: "오류"); Log.w(TAG, "lead: $message") }
                        else -> { status = LinkStatus(LinkState.FAILED, "$prop: $message"); lastRaw = null; onUnavailable(); Log.w(TAG, status.text) }
                    }
                }
            }
        }
        callback = cb
        val conn = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                val svc = IVehicleService.Stub.asInterface(binder)
                if (!gate.accept(epoch) { service = svc; status = LinkStatus(LinkState.CONNECTED) }) return
                // Binder registration may synchronously call back on another thread. Never hold the gate across IPC.
                runCatching { svc.registerPropertyCallback(context.packageName, SPEED_PROPERTY, 0, cb) }
                    .onSuccess {
                        val lead = runCatching { svc.registerPropertyCallback(context.packageName, LEAD_PROPERTY, 0, cb) }
                            .fold({ LinkStatus(LinkState.SUBSCRIBED) }, { LinkStatus(LinkState.FAILED, it.javaClass.simpleName) })
                        runCatching { svc.registerPropertyCallback(context.packageName, NIGHT_PROPERTY, 0, cb) }
                        if (!gate.accept(epoch) { status = LinkStatus(LinkState.SUBSCRIBED); leadStatus = lead }) unregister(svc, cb)
                    }.onFailure { error ->
                        gate.accept(epoch) { status = LinkStatus(LinkState.FAILED, "구독 ${error.message}"); onUnavailable() }
                        Log.w(TAG, "Speed subscription failed", error)
                    }
            }
            override fun onServiceDisconnected(name: ComponentName) = disconnected(LinkStatus(LinkState.DISCONNECTED))
            override fun onBindingDied(name: ComponentName) = disconnected(LinkStatus(LinkState.FAILED, "바인딩 종료"))
            override fun onNullBinding(name: ComponentName) = disconnected(LinkStatus(LinkState.FAILED, "서비스 없음"))
            private fun disconnected(reason: LinkStatus) {
                gate.accept(epoch) { service = null; status = reason; lastRaw = null; onUnavailable() }
            }
        }
        connection = conn
        val intent = Intent("ai.pleos.playground.vehicle.VEHICLE_START").setComponent(
            ComponentName("ai.pleos.playground.service.vehicle", "ai.pleos.playground.service.vehicle.VehicleService"),
        )
        bound = runCatching { context.bindService(intent, conn, Context.BIND_AUTO_CREATE) }
            .onFailure { gate.accept(epoch) { status = LinkStatus(LinkState.FAILED, "바인드 ${it.message}") } }.getOrDefault(false)
        if (!bound) gate.accept(epoch) { if (status.state == LinkState.IDLE) status = LinkStatus(LinkState.FAILED, "바인드"); onUnavailable() }
    }

    /** Change-only readings stay valid while subscribed; callback silence alone is not failure. */
    fun isConnected(): Boolean = gate.read { gate.current() != null && service?.asBinder()?.isBinderAlive == true }

    @Synchronized
    fun stop() {
        val svc = service
        val cb = callback
        val conn = connection
        if (!gate.end { service = null; status = LinkStatus(LinkState.IDLE); leadStatus = LinkStatus(LinkState.IDLE); lastRaw = null; lastLeadRaw = null }) return
        if (svc != null && cb != null) unregister(svc, cb)
        if (bound && conn != null) runCatching { context.unbindService(conn) }
        bound = false; callback = null; connection = null
        onUnavailable()
    }

    private fun unregister(svc: IVehicleService, cb: IPropertyCallback) {
        for (p in listOf(SPEED_PROPERTY, LEAD_PROPERTY, NIGHT_PROPERTY)) runCatching { svc.unregisterPropertyCallback(context.packageName, p, 0, cb) }
    }

    private companion object {
        const val TAG = "NuntiRawSpeed"
        const val SPEED_PROPERTY = "PERF_VEHICLE_SPEED"
        const val NIGHT_PROPERTY = "NIGHT_MODE"
        const val LEAD_PROPERTY = "ADAPTIVE_CRUISE_CONTROL_LEAD_VEHICLE_MEASURED_DISTANCE"
    }
}
