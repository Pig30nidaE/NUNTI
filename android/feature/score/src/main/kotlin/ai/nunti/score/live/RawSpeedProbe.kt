package ai.nunti.score.live

import ai.pleos.playground.vehicle.IVehicleService
import ai.pleos.playground.vehicle.callback.IPropertyCallback
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import android.util.Log

/** Experimental AIDL subscription: this speed property is not part of the public Vehicle 2.3.2 API. */
class RawSpeedProbe(
    private val context: Context,
    private val onSpeed: (Float) -> Unit,
    private val onUnavailable: () -> Unit = {},
) {
    private val gate = SignalSessionGate()
    @Volatile var status = "대기"
        private set
    @Volatile var lastRaw: String? = null
        private set
    @Volatile private var service: IVehicleService? = null
    private var connection: ServiceConnection? = null
    private var callback: IPropertyCallback? = null
    private var bound = false

    @Synchronized
    fun start() {
        val epoch = gate.begin { status = "연결 중"; lastRaw = null } ?: return
        val cb = object : IPropertyCallback.Stub() {
            override fun onChangeEvent(prop: String?, area: Int, value: String?) {
                if (prop != "PERF_VEHICLE_SPEED") return
                gate.accept(epoch) {
                    lastRaw = "$prop[$area]=$value"
                    val speed = value?.trim()?.trim('"')?.toFloatOrNull()?.takeIf { it.isFinite() }
                    if (speed == null) onUnavailable() else onSpeed(speed * 3.6f)
                }
            }
            override fun onErrorEvent(prop: String?, message: String?) {
                if (prop != null && prop != "PERF_VEHICLE_SPEED") return
                gate.accept(epoch) { status = "오류 $prop: $message"; lastRaw = null; onUnavailable() }
            }
        }
        callback = cb
        val conn = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName, binder: IBinder) {
                val svc = IVehicleService.Stub.asInterface(binder)
                if (!gate.accept(epoch) { service = svc }) return
                // Binder registration may synchronously call back on another thread. Never hold the gate across IPC.
                runCatching { svc.registerPropertyCallback(context.packageName, "PERF_VEHICLE_SPEED", 0, cb) }
                    .onSuccess {
                        if (!gate.accept(epoch) { status = "구독 요청 완료" }) {
                            runCatching { svc.unregisterPropertyCallback(context.packageName, "PERF_VEHICLE_SPEED", 0, cb) }
                        }
                    }.onFailure { error ->
                        gate.accept(epoch) { status = "구독 실패: ${error.message}"; onUnavailable() }
                        Log.w("NuntiRawSpeed", "Speed subscription failed", error)
                    }
            }
            override fun onServiceDisconnected(name: ComponentName) = disconnected("연결 끊김")
            override fun onBindingDied(name: ComponentName) = disconnected("바인딩 종료")
            override fun onNullBinding(name: ComponentName) = disconnected("서비스 없음")
            private fun disconnected(reason: String) {
                gate.accept(epoch) { service = null; status = reason; lastRaw = null; onUnavailable() }
            }
        }
        connection = conn
        val intent = Intent("ai.pleos.playground.vehicle.VEHICLE_START").setComponent(
            ComponentName("ai.pleos.playground.service.vehicle", "ai.pleos.playground.service.vehicle.VehicleService"),
        )
        bound = runCatching { context.bindService(intent, conn, Context.BIND_AUTO_CREATE) }
            .onFailure { gate.accept(epoch) { status = "바인드 예외: ${it.message}" } }.getOrDefault(false)
        if (!bound) gate.accept(epoch) { status = "바인드 실패"; onUnavailable() }
    }

    /** Change-only readings stay valid while subscribed; callback silence alone is not failure. */
    fun isConnected(): Boolean = gate.read { gate.current() != null && service?.asBinder()?.isBinderAlive == true }

    @Synchronized
    fun stop() {
        val svc = service
        val cb = callback
        val conn = connection
        if (!gate.end { service = null; status = "중지"; lastRaw = null }) return
        if (cb != null) runCatching { svc?.unregisterPropertyCallback(context.packageName, "PERF_VEHICLE_SPEED", 0, cb) }
        if (bound && conn != null) runCatching { context.unbindService(conn) }
        bound = false; callback = null; connection = null
        onUnavailable()
    }
}
