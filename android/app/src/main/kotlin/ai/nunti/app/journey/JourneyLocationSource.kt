package ai.nunti.app.journey

import ai.nunti.score.journey.TripPosition
import ai.pleos.playground.location.fused.FusedLocation
import ai.pleos.playground.location.fused.listener.FusedLocationListener
import ai.pleos.playground.location.fused.model.LocationData
import android.content.Context
import android.content.pm.PackageManager
import android.os.SystemClock

/** Official vehicle GPS updates, independent of whether Hyundai navigation has an active route. */
internal class JourneyLocationSource(private val context:Context) : AutoCloseable {
    private var sdk:FusedLocation?=null
    private var listener:FusedLocationListener?=null
    private var unsupported=false
    @Volatile private var closed=false
    @Volatile private var fix:Pair<Long,TripPosition.Geographic>?=null
    @Volatile var status="위치 연결 중"
        private set

    fun position():TripPosition.Geographic? {
        if(closed)return null
        if(context.checkSelfPermission(PERMISSION)!=PackageManager.PERMISSION_GRANTED) {
            status="위치 권한 없음";fix=null;return null
        }
        if(sdk==null&&!unsupported)start()
        return fix?.takeIf { SystemClock.elapsedRealtime()-it.first in 0..3000 }?.second
    }

    private fun start() {
        val candidate=FusedLocation(context)
        if(!candidate.isSupported()) { unsupported=true;status="차량 위치 서비스 미지원";return }
        val callback=object:FusedLocationListener {
            override fun onChanged(location:LocationData?) {
                if(closed)return
                val valid=location?.takeIf { it.latitude.isFinite()&&it.longitude.isFinite() &&
                    it.latitude in -90.0..90.0&&it.longitude in -180.0..180.0 &&
                    (it.latitude!=0.0||it.longitude!=0.0) && System.currentTimeMillis()-it.timestampMillis in -1000..3000 }
                fix=valid?.let { SystemClock.elapsedRealtime() to TripPosition.Geographic(it.latitude,it.longitude) }
                status=if(valid!=null)"차량 GPS 수신" else "새 위치 대기 중"
            }
            override fun onError(exception:Exception) { if(!closed){fix=null;status="위치 수신 불가"} }
        }
        sdk=candidate;listener=callback
        runCatching { candidate.initialize();candidate.registerFusedLocationCallback(callback) }
            .onFailure { fix=null;status="위치 연결 실패" }
    }

    override fun close() {
        closed=true;fix=null
        listener?.let { runCatching { sdk?.unregisterFusedLocationCallback(it) } }
        runCatching { sdk?.release() };sdk=null;listener=null
    }
    companion object {
        const val PERMISSION="pleos.car.permission.FUSED_LOCATION"
        fun supported(context:Context)=runCatching { FusedLocation(context).isSupported() }.getOrDefault(false)
    }
}
