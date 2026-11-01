package ai.nunti.avatar

import ai.nunti.emotion.EmotionSnapshot
import ai.nunti.emotion.TripEmotionSummary
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private fun sceneColor(hex: String) = Color((0xFF000000L or hex.removePrefix("#").toLong(16)).toInt())

@Composable
fun NuntiAvatar(spec: AvatarSpec, renderState: RenderState, provider: CharacterAssetProvider, modifier: Modifier = Modifier) {
    if (!renderState.visible) return
    val scene = remember(spec, renderState, provider) { CharacterRenderer(provider).scene(spec, renderState) }
    Canvas(modifier.semantics { contentDescription = scene.accessibilityLabel }) {
        val factor = minOf(size.width, size.height) / 320f
        withTransform({
            translate((size.width - 320f * factor) / 2f, (size.height - 320f * factor) / 2f)
            scale(factor, factor, Offset.Zero)
        }) {
            scene.primitives.forEach { p ->
                val b = p.bounds
                val color = sceneColor(p.color)
                val topLeft = Offset(b.x.toFloat(), b.y.toFloat())
                val dimensions = Size(b.width.toFloat(), b.height.toFloat())
                when (p.kind) {
                    PrimitiveKind.ELLIPSE -> drawOval(color, topLeft, dimensions)
                    PrimitiveKind.RECT -> drawRoundRect(color, topLeft, dimensions, CornerRadius(5f, 5f))
                    else -> {
                        val path = Path().apply { p.points.forEachIndexed { i, point ->
                            if (i == 0) moveTo(point.x.toFloat(), point.y.toFloat()) else lineTo(point.x.toFloat(), point.y.toFloat())
                        } }
                        drawPath(path, color, style = Stroke(p.strokeWidth.toFloat(), cap = StrokeCap.Round, join = StrokeJoin.Round))
                    }
                }
            }
        }
    }
}

/** Host-driven shell: actual vehicle/UX state is supplied externally and never inferred from phase.
 * Pass a stable AvatarSpec during DRIVING. Refresh policy age using a host monotonic clock.
 * Missing permission removes the whole screen, including accessibility content.
 */
@Composable
fun NuntiAppShell(spec: AvatarSpec, emotion: EmotionSnapshot, phase: TripPhase,
    platformPolicy: PlatformDisplayPolicy?, nowMillis: Long, provider: CharacterAssetProvider,
    tripSummary: TripEmotionSummary? = null, modifier: Modifier = Modifier,
    postDriveActions: @Composable () -> Unit = {}) {
    val render = RenderPolicy.resolve(phase, emotion.emotion, platformPolicy, nowMillis)
    if (!render.visible) return
    val frozenSpec = remember(render.interactionsAllowed) { spec }
    if (!render.interactionsAllowed) {
        Box(modifier.fillMaxSize()) { NuntiAvatar(frozenSpec, render, provider, Modifier.fillMaxSize()) }
        return
    }
    Column(modifier.fillMaxSize().background(Color(0xFFF5F2E9)).verticalScroll(rememberScrollState()).padding(28.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)) {
        BasicText(if (phase == TripPhase.POST_DRIVE) "눈티와 돌아보는 오늘" else "오늘의 경로에 맞춰 준비했어요",
            style = TextStyle(color = Color(0xFF283B3C), fontSize = 28.sp, fontWeight = FontWeight.Bold))
        if (spec.mock) BasicText("시연용 Mock 경로", style = TextStyle(color = Color(0xFF536360), fontSize = 16.sp))
        NuntiAvatar(spec, render, provider, Modifier.fillMaxWidth().heightIn(min = 200.dp, max = 360.dp).aspectRatio(1.5f))
        BasicText(spec.generationExplanation, style = TextStyle(color = Color(0xFF283B3C), fontSize = 20.sp))
        if (phase == TripPhase.POST_DRIVE && tripSummary != null) {
            BasicText("감정의 흐름", style = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.Bold))
            // Host may provide a bounded presentation summary; full timeline remains in the report.
            BasicText(tripSummary.timeline.takeLast(12).joinToString(" → ") { it.emotion.name }, style = TextStyle(fontSize = 18.sp))
            postDriveActions() // TTS owns synthesis/playback and its own safety policy.
        }
    }
}
