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
class RawSpeedProbe(private val context: Context, private val onSpeed: (Float) -> Unit) {
    private val tag = "NuntiRawSpeed"
    @Volatile var status: String = "대기"
        private set
    @Volatile var lastRaw: String? = null
        private set
    /** 연비·전비 직접 구독 시험 결과 (속성명 → 값 또는 오류). */
    val extra = java.util.concurrent.ConcurrentHashMap<String, String>()
    private val extraProps = listOf(
        "INSTANTANEOUS_EV_EFFICIENCY", "CUMULATIVE_EV_EFFICIENCY", "SINCE_CHARGE_EV_EFFICIENCY", "TRIP_EV_EFFICIENCY",
        "INSTANTANEOUS_FUEL_ECONOMY", "CUMULATIVE_FUEL_ECONOMY", "TRIP_FUEL_ECONOMY",
    )
    private var service: IVehicleService? = null
    private var bound = false

    private val callback = object : IPropertyCallback.Stub() {
        override fun onChangeEvent(prop: String?, area: Int, value: String?) {
            // 같은 패키지로 등록된 다른 속성 이벤트도 이 콜백으로 오므로 속도만 거른다.
            if (prop != null && prop in extraProps) { extra[prop] = "$value"; return }
            if (prop != "PERF_VEHICLE_SPEED") return
            lastRaw = "$prop[$area]=$value"
            // 서비스 값은 m/s (AAOS PERF_VEHICLE_SPEED 와 동일) → km/h
            value?.trim()?.trim('"')?.toFloatOrNull()?.let { onSpeed(it * 3.6f) }
        }
        override fun onErrorEvent(prop: String?, message: String?) {
            if (prop != null && prop in extraProps) { extra[prop] = "오류: $message"; return }
            status = "오류 $prop: $message"
            Log.w(tag, status)
        }
    }

    private val conn = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, binder: IBinder) {
            val svc = IVehicleService.Stub.asInterface(binder)
            service = svc
            status = "연결됨"
            runCatching {
                svc.registerPropertyCallback(context.packageName, "PERF_VEHICLE_SPEED", 0, callback)
                status = "구독 요청 완료"
                extraProps.forEach { p ->
                    runCatching { svc.registerPropertyCallback(context.packageName, p, 0, callback) }
                        .onFailure { extra[p] = "구독 실패: ${it.message}" }
                }
            }.onFailure { status = "구독 실패: ${it.message}"; Log.w(tag, status, it) }
        }
        override fun onServiceDisconnected(name: ComponentName) { service = null; status = "연결 끊김" }
    }

    fun start() {
        val intent = Intent("ai.pleos.playground.vehicle.VEHICLE_START").setComponent(
            ComponentName("ai.pleos.playground.service.vehicle", "ai.pleos.playground.service.vehicle.VehicleService"),
        )
        bound = runCatching { context.bindService(intent, conn, Context.BIND_AUTO_CREATE) }
            .onFailure { status = "바인드 예외: ${it.message}" }.getOrDefault(false)
        if (!bound && status == "대기") status = "바인드 실패"
    }

    fun stop() {
        runCatching { service?.unregisterPropertyCallback(context.packageName, "PERF_VEHICLE_SPEED", 0, callback) }
        if (bound) runCatching { context.unbindService(conn) }
        bound = false; service = null
    }
}
