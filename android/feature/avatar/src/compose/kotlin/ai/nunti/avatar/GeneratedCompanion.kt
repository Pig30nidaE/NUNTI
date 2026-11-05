package ai.nunti.avatar

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Paint
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

/** Displays a prepared, face-included RGBA image; never generates, decodes, speaks or stores assets.
 * ready=false or image=null excludes both source pixels and image-derived geometry.
 * A restored/static thumbnail at progress=1 skips alpha analysis entirely.
 * The host holds birth progress at zero until onFormationPrepared, then runs its timeline.
 */
@Composable
fun GeneratedCompanion(
    image: ImageBitmap?,
    route: List<GeneratedPoint>,
    birthProgress: Float,
    ready: Boolean,
    modifier: Modifier = Modifier,
    animate: Boolean = true,
    onFormationPrepared: (() -> Unit)? = null,
) {
    val inputRoute = remember(route) { GeneratedRoute(route) }
    var geometry by remember(image, inputRoute) { mutableStateOf<GeneratedFormationGeometry?>(null) }
    val forming = birthProgress < 1f
    val latestOnFormationPrepared by rememberUpdatedState(onFormationPrepared)
    var formationNotified by remember(image, inputRoute, forming) { mutableStateOf(false) }
    LaunchedEffect(image, inputRoute, ready, forming) {
        if (ready && image != null && birthProgress < 1f && geometry == null) {
            geometry = withContext(Dispatchers.Default) {
                // One readback per prepared image/route, never during drawing or on each frame.
                val pixels = IntArray(image.width * image.height)
                image.readPixels(pixels)
                GeneratedFormationGeometry(inputRoute,
                    generatedAlphaGridFromArgb(image.width, image.height, pixels), image.width, image.height)
            }
        }
    }
    LaunchedEffect(image, inputRoute, ready, geometry, forming) {
        if (ready && image != null && geometry != null && forming && !formationNotified) {
            latestOnFormationPrepared?.let { callback ->
                formationNotified = true
                callback()
            }
        }
    }
    var idlePhase by remember(image) { mutableFloatStateOf(0f) }
    val idle = animate && ready && image != null && birthProgress == 1f
    LaunchedEffect(image, idle) {
        idlePhase = 0f
        if (idle) {
            val start = withFrameNanos { it }
            while (isActive) {
                withFrameNanos { now -> idlePhase = ((now - start) % 6_000_000_000L) / 6_000_000_000f }
            }
        }
    }
    // Until the off-thread geometry is prepared, only the supplied route can be shown.
    val prepared = image != null && (geometry != null || birthProgress == 1f)
    val frame = generatedBirthFrame(birthProgress, ready, prepared, idlePhase, animate)
    val currentGeometry = geometry.takeIf { ready && image != null }
    val stroke = remember(inputRoute, currentGeometry, frame.morphFraction, frame.routeFraction) {
        currentGeometry?.stroke(frame.morphFraction, frame.routeFraction)
            ?: inputRoute.trace(frame.routeFraction).map { it.formationPoint() }
    }
    val path = remember(stroke) { formationPath(stroke) }
    val front = remember(stroke, currentGeometry) { formationFrontPath(stroke, currentGeometry) }
    val guide = remember(inputRoute) { formationPath(inputRoute.points.map { it.formationPoint() }) }
    val label = when (frame.stage) {
        GeneratedBirthStage.ROUTE -> "입력한 경로를 그리는 중"
        GeneratedBirthStage.LIGHT -> "경로의 리본이 동반자의 모습을 만드는 중"
        GeneratedBirthStage.REVEAL -> "같은 리본이 동반자를 칠하는 중"
        GeneratedBirthStage.READY -> "완성된 여정 동반자"
        GeneratedBirthStage.WAITING -> "경로를 담은 동반자를 준비하는 중"
    }
    Canvas(modifier.clearAndSetSemantics { contentDescription = label }) {
        if (size.width <= 0f || size.height <= 0f) return@Canvas
        val factor = minOf(size.width, size.height) / 320f
        withTransform({
            translate((size.width - 320f * factor) / 2f, (size.height - 320f * factor) / 2f)
            scale(factor, factor, Offset.Zero)
        }) {
            if (ready && image != null && frame.revealFraction > 0f) drawGeneratedContact(image, frame)
            withTransform({
                translate(0f, frame.floatY)
                rotate(frame.tilt, Offset(160f, 148f))
                scale(frame.scaleX, frame.scaleY, Offset(160f, 148f))
            }) {
                // The complete actual input is visible from frame zero. The moving stroke never restarts.
                if (frame.routeOpacity > 0f) {
                    drawPath(guide, Color(0xFF578F93).copy(alpha = frame.routeOpacity * .30f),
                        style = Stroke(1.8f, cap = StrokeCap.Round, join = StrokeJoin.Round))
                }
                if (frame.ribbonOpacity > 0f) drawGeneratedRibbon(path, frame.ribbonOpacity, false)
                if (ready && image != null && frame.revealFraction > 0f) {
                    drawGeneratedPaintedImage(image, path, frame, currentGeometry?.minimumBrushWidth ?: 0f)
                }
                // Only the forward-facing portions of the very same stroke pass over the painted surface.
                if (currentGeometry != null && frame.morphFraction > 0f && frame.ribbonOpacity > 0f) {
                    drawGeneratedRibbon(front, frame.ribbonOpacity * frame.morphFraction * .58f, true)
                }
                if (frame.tipOpacity > 0f) drawGeneratedTip(stroke.last(), frame.tipOpacity)
            }
        }
    }
}

private fun GeneratedPoint.formationPoint() = GeneratedFormationPoint(36f + x * 248f, 24f + y * 248f)
private fun GeneratedFormationPoint.offset() = Offset(x, y)
private fun formationPath(points: List<GeneratedFormationPoint>) = Path().apply {
    moveTo(points.first().x, points.first().y)
    for (index in 1 until points.size) lineTo(points[index].x, points[index].y)
}

private fun formationFrontPath(points: List<GeneratedFormationPoint>, geometry: GeneratedFormationGeometry?) = Path().apply {
    if (geometry != null) {
        for (index in 1 until points.size) {
            if (geometry.front[minOf(index, geometry.front.lastIndex)]) {
                moveTo(points[index - 1].x, points[index - 1].y)
                lineTo(points[index].x, points[index].y)
            }
        }
    }
}

private fun DrawScope.drawGeneratedRibbon(path: Path, opacity: Float, front: Boolean) {
    val stroke = { width: Float -> Stroke(width, cap = StrokeCap.Round, join = StrokeJoin.Round) }
    if (!front) {
        drawPath(path, Color(0xFF578F93).copy(alpha = opacity * .12f), style = stroke(13f))
        drawPath(path, Color(0xFF8FD5CC).copy(alpha = opacity * .56f), style = stroke(5.4f))
    }
    drawPath(path, Color(0xFFFFE8BA).copy(alpha = opacity * .76f), style = stroke(if (front) 3.5f else 2.6f))
    drawPath(path, Color(0xFFF1FFF5).copy(alpha = opacity * .94f), style = stroke(if (front) 1.25f else 1.1f))
}

private fun DrawScope.drawGeneratedTip(point: GeneratedFormationPoint, opacity: Float) {
    val center = point.offset()
    drawCircle(Brush.radialGradient(listOf(Color(0xFFFFDF9C).copy(alpha = opacity * .40f),
        Color.Transparent), center, 11f), 11f, center)
    drawCircle(Color(0xFFFFECC7).copy(alpha = opacity), 3.4f, center)
    drawCircle(Color(0xFFFFFEEC).copy(alpha = opacity), 1.6f, center)
}

private fun DrawScope.drawGeneratedContact(image: ImageBitmap, frame: GeneratedBirthFrame) {
    val rect = generatedImageRect(image.width, image.height)
    repeat(4) { index ->
        val spread = (3 - index) * 4f
        val width = (rect.width * .56f + spread * 2f) * frame.shadowScale
        drawOval(Color(0xFF564A42).copy(alpha = frame.shadowOpacity * (.13f + index * .045f)),
            Offset(160f - width / 2f, 280f - spread * .12f), Size(width, 7f + spread * .36f))
    }
}

private fun DrawScope.drawGeneratedPaintedImage(
    image: ImageBitmap,
    path: Path,
    frame: GeneratedBirthFrame,
    minimumBrushWidth: Float,
) {
    val rect = generatedImageRect(image.width, image.height)
    if (frame.residualFraction == 1f) {
        drawGeneratedBitmap(image, rect)
        return
    }
    val bounds = Rect(rect.left.roundToInt().toFloat(), rect.top.roundToInt().toFloat(),
        (rect.left.roundToInt() + rect.width.roundToInt()).toFloat(),
        (rect.top.roundToInt() + rect.height.roundToInt()).toFloat())
    clipRect(bounds.left, bounds.top, bounds.right, bounds.bottom) {
        val canvas = drawContext.canvas
        canvas.saveLayer(bounds, Paint())
        try {
            // Form one union mask, then apply source alpha ONCE. A partial-alpha PNG is never overdrawn.
            if (frame.residualFraction > 0f) drawRect(Color.White.copy(alpha = frame.residualFraction),
                Offset(bounds.left, bounds.top), Size(bounds.width, bounds.height))
            drawPath(path, Color.White.copy(alpha = frame.revealFraction),
                style = Stroke(maxOf(frame.brushWidth, minimumBrushWidth), cap = StrokeCap.Round, join = StrokeJoin.Round))
            drawGeneratedBitmap(image, rect, BlendMode.SrcIn)
        } finally {
            canvas.restore()
        }
    }
}

private fun DrawScope.drawGeneratedBitmap(image: ImageBitmap, rect: GeneratedImageRect, blendMode: BlendMode = BlendMode.SrcOver) {
    // Preserve source alpha, face, colors and aspect. No replacement eyes, mouth, or color filter.
    drawImage(image, srcOffset = IntOffset.Zero, srcSize = IntSize(image.width, image.height),
        dstOffset = IntOffset(rect.left.roundToInt(), rect.top.roundToInt()),
        dstSize = IntSize(rect.width.roundToInt(), rect.height.roundToInt()),
        filterQuality = FilterQuality.High, blendMode = blendMode)
}
