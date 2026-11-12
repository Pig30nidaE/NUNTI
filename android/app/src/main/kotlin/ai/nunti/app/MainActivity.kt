package ai.nunti.app

import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity

/**
 * Production and Debug use the same parked avatar-generation host.
 * 진행 중인 여정이 있으면 여정 화면으로 간다. 여정 없이 주행 중이면 스튜디오(주행 중 차단됨) 대신
 * 마지막으로 함께한 눈티로 실제 차량 신호 여정을 시작하고 여정 화면을 연다.
 */
class MainActivity : ComponentActivity() {
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())
    private var gate: ai.nunti.app.studio.StudioCarGate? = null
    private var decided = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (ai.nunti.app.journey.JourneyRuntime.isRunning || !packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)) {
            open(ai.nunti.app.journey.JourneyRuntime.isRunning); return
        }
        gate = ai.nunti.app.studio.StudioCarGate(this) { gate?.let { if (it.known()) decide(driving = !it.canDisplay()) } }
        handler.postDelayed({ decide(driving = false) }, 1_500) // 차 상태를 못 받으면 예전처럼 스튜디오로
    }

    private fun decide(driving: Boolean) {
        if (decided || isFinishing) return
        decided = true
        handler.removeCallbacksAndMessages(null)
        gate?.close(); gate = null
        if (driving) runCatching { ai.nunti.app.journey.JourneyLauncher.startLiveFromLast(this) }
            .onFailure { android.util.Log.w("NuntiMain", "live journey not started", it) }
        // 주행 중에는 여정 화면(주행 중 사용 가능)만 연다. 시작할 눈티가 없으면 빈 여정 화면이 안내한다.
        open(journey = driving)
    }

    private fun open(journey: Boolean) {
        val host = if (journey) ai.nunti.app.journey.JourneyActivity::class.java else ai.nunti.app.studio.AvatarStudioActivity::class.java
        startActivity(Intent(this, host).addFlags(
            Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP,
        ))
        finish()
    }

    override fun onDestroy() { handler.removeCallbacksAndMessages(null); gate?.close(); gate = null; super.onDestroy() }
}
