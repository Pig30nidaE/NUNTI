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
 * 실험: 공개 SDK에 없는 PERF_VEHICLE_SPEED 를 Vehicle 서비스에 직접 구독한다.
 * SDK(Vehicle 2.3.2)와 같은 프로토콜: registerPropertyCallback(패키지, 속성명, 영역, 콜백).
 */
class RawSpeedProbe(
    private val context: Context,
    /** 앞차 거리(mm). 적응형 크루즈가 앞차를 재는 동안에만 온다. 같은 서비스에서 속성 이름으로 함께 구독해 본다. */
    private val onLeadDistanceMm: (Int) -> Unit = {},
    /** NIGHT_MODE: 차량이 낮/밤을 판단한 최종 결과(밤이면 true). */
    private val onNightMode: (Boolean) -> Unit = {},
    private val onSpeed: (Float) -> Unit,
) {
    private val tag = "NuntiRawSpeed"
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
    private var service: IVehicleService? = null
    private var bound = false

    private val callback = object : IPropertyCallback.Stub() {
        override fun onChangeEvent(prop: String?, area: Int, value: String?) {
            // 같은 패키지로 등록된 다른 속성 이벤트도 이 콜백으로 오므로 속도만 거른다.
            if (prop == LEAD_PROPERTY) {
                lastLeadRaw = "$prop[$area]=$value"
                value?.trim()?.trim('"')?.toFloatOrNull()?.let { onLeadDistanceMm(it.toInt()) }
                return
            }
            if (prop == NIGHT_PROPERTY) {
                lastNightRaw = "$prop[$area]=$value"
                when (value?.trim()?.trim('"')?.lowercase()) {
                    "true", "1" -> onNightMode(true)
                    "false", "0" -> onNightMode(false)
                }
                return
            }
            if (prop != "PERF_VEHICLE_SPEED") return
            lastRaw = "$prop[$area]=$value"
            // 서비스 값은 m/s (AAOS PERF_VEHICLE_SPEED 와 동일) → km/h
            value?.trim()?.trim('"')?.toFloatOrNull()?.let { onSpeed(it * 3.6f) }
        }
        override fun onErrorEvent(prop: String?, message: String?) {
            if (prop == NIGHT_PROPERTY) { Log.w(tag, "night: $message"); return }
            if (prop == LEAD_PROPERTY) { leadStatus = LinkStatus(LinkState.FAILED, message ?: "오류"); Log.w(tag, "lead: $message"); return }
            status = LinkStatus(LinkState.FAILED, "$prop: $message")
            Log.w(tag, status.text)
        }
    }

    private val conn = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, binder: IBinder) {
            val svc = IVehicleService.Stub.asInterface(binder)
            service = svc
            status = LinkStatus(LinkState.CONNECTED)
            runCatching {
                svc.registerPropertyCallback(context.packageName, "PERF_VEHICLE_SPEED", 0, callback)
                status = LinkStatus(LinkState.SUBSCRIBED)
                leadStatus = runCatching { svc.registerPropertyCallback(context.packageName, LEAD_PROPERTY, 0, callback) }
                    .fold({ LinkStatus(LinkState.SUBSCRIBED) }, { LinkStatus(LinkState.FAILED, it.javaClass.simpleName) })
                runCatching { svc.registerPropertyCallback(context.packageName, NIGHT_PROPERTY, 0, callback) }
            }.onFailure { status = LinkStatus(LinkState.FAILED, "구독 ${it.message}"); Log.w(tag, status.text, it) }
        }
        override fun onServiceDisconnected(name: ComponentName) { service = null; status = LinkStatus(LinkState.DISCONNECTED) }
    }

    fun start() {
        val intent = Intent("ai.pleos.playground.vehicle.VEHICLE_START").setComponent(
            ComponentName("ai.pleos.playground.service.vehicle", "ai.pleos.playground.service.vehicle.VehicleService"),
        )
        bound = runCatching { context.bindService(intent, conn, Context.BIND_AUTO_CREATE) }
            .onFailure { status = LinkStatus(LinkState.FAILED, "바인드 ${it.message}") }.getOrDefault(false)
        if (!bound && status.state == LinkState.IDLE) status = LinkStatus(LinkState.FAILED, "바인드")
    }

    fun stop() {
        runCatching { service?.unregisterPropertyCallback(context.packageName, "PERF_VEHICLE_SPEED", 0, callback) }
        runCatching { service?.unregisterPropertyCallback(context.packageName, LEAD_PROPERTY, 0, callback) }
        runCatching { service?.unregisterPropertyCallback(context.packageName, NIGHT_PROPERTY, 0, callback) }
        if (bound) runCatching { context.unbindService(conn) }
        bound = false; service = null
    }

    private companion object {
        const val NIGHT_PROPERTY = "NIGHT_MODE"
        const val LEAD_PROPERTY = "ADAPTIVE_CRUISE_CONTROL_LEAD_VEHICLE_MEASURED_DISTANCE" }
}
