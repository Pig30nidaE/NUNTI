package ai.nunti.app

import ai.nunti.avatar.*
import ai.nunti.emotion.*
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.SystemClock
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

/** Runnable fixture viewer. Vehicle devices remain blocked until a real host feeds UX + parked approval.
 * No network, scores, final report generation, or synthetic vehicle permission is enabled on AAOS.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)) {
            setContent { /* Fail closed: production host must wire CarUxPolicyBinding + actual trip state. */ }
            return
        }
        val engine = AvatarEngine()
        val provider = CanvasPartProvider(engine.manifest)
        val preferences = getSharedPreferences("avatar-demo", MODE_PRIVATE)
        setContent {
            var routeIndex by rememberSaveable { mutableIntStateOf(preferences.getInt("routeIndex", 0).coerceIn(0, 3)) }
            var phaseName by rememberSaveable { mutableStateOf(TripPhase.PRE_DRIVE.name) }
            var emotionName by rememberSaveable { mutableStateOf(Emotion.NEUTRAL.name) }
            var replayRequest by remember { mutableIntStateOf(0) }
            var replayFrame by remember { mutableIntStateOf(-1) }
            val routes = remember { MockRoutes.representative() }
            val spec = remember(routeIndex) { engine.generate(routes[routeIndex], preferences.getLong("seed", 42L)).avatar }
            val emotion = Emotion.valueOf(emotionName)
            val now = SystemClock.elapsedRealtime()
            val phase = TripPhase.valueOf(phaseName)
            val timeline = remember(spec.avatarId) { MockEmotionTimeline.run(spec.avatarId) }
            LaunchedEffect(replayRequest, phase, spec.avatarId) {
                replayFrame = -1
                if (replayRequest > 0 && phase == TripPhase.POST_DRIVE) {
                    for (i in timeline.indices) { replayFrame = i; if (i < timeline.lastIndex) delay(3000) }
                }
            }
            val state = if (replayFrame >= 0) timeline[replayFrame].snapshot else remember(emotion, spec) {
                EmotionSnapshot("mock-preview", "mock-trip", spec.avatarId, emotion, 0, null, 0.0, "MOCK_PREVIEW") }
            Column(Modifier.fillMaxSize()) {
                BasicText("개발용 Mock · 일반 Android 기기 전용", Modifier.padding(16.dp), style = TextStyle(fontSize = 16.sp))
                Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    listOf("도심", "장거리", "해안", "산악").forEachIndexed { i, label ->
                        BasicText(label, Modifier.clickable { routeIndex = i; preferences.edit().putInt("routeIndex", i).putLong("seed", 42L).apply() }.padding(8.dp))
                    }
                }
                Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    listOf("출발 전" to TripPhase.PRE_DRIVE, "주행 제한" to TripPhase.DRIVING, "주행 종료" to TripPhase.POST_DRIVE).forEach { (label, target) ->
                        BasicText(label, Modifier.clickable { phaseName = target.name }.padding(8.dp))
                    }
                }
                if (phase == TripPhase.POST_DRIVE) Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    BasicText("이벤트 재생", Modifier.clickable { replayRequest++ }.padding(6.dp), style = TextStyle(fontSize = 12.sp))
                    listOf(Emotion.RELAXED, Emotion.STARTLED, Emotion.RELIEVED, Emotion.JOYFUL).forEach { e ->
                        BasicText(e.name, Modifier.clickable { replayRequest = 0; replayFrame = -1; emotionName = e.name }.padding(6.dp), style = TextStyle(fontSize = 12.sp))
                    }
                }
                if (phase == TripPhase.DRIVING) BasicText("아바타 표시 중지 · 내부 감정과 화면은 분리됩니다.", Modifier.padding(24.dp))
                NuntiAppShell(spec, state, phase, PlatformDisplayPolicy(now, true, true, false, parkedConfirmed = true), now, provider,
                    tripSummary = if (replayFrame >= 0) EmotionMachine(EmotionRules.from(loadProperties("emotion.properties"))).summary(timeline[replayFrame]) else null,
                    modifier = Modifier.weight(1f))
            }
        }
    }
}
