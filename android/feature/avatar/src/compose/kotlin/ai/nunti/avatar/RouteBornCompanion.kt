package ai.nunti.avatar

import ai.nunti.emotion.Emotion
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription

/** Timer-free route birth. The host owns progress, visibility, lifecycle and vehicle policy.
 * progress=1 is a static finished keepsake. All contours come from the supplied 72 points.
 */
@Composable
fun RouteBornCompanion(spec: RouteBornSpec, progress: Float, emotion: Emotion = Emotion.NEUTRAL,
    modifier: Modifier = Modifier) {
    val frame = remember(spec, progress) { spec.frame(progress) }
    val colors = remember(spec) { spec.palette.map(::routeBornColor) }
    val sourceRoute = remember(spec) { rbPath(spec.route) }
    val shape = remember(frame.contour) { rbPath(frame.contour, closed = true) }
    val trace = remember(frame.tracedRoute) { rbPath(frame.tracedRoute) }
    val changingContour = remember(frame.contour, frame.closure) { rbMorphPath(frame.contour, frame.closure) }
    val label = when {
        progress < .35f -> "입력한 경로를 그리는 중"
        progress < .8f -> "경로에서 눈티가 태어나는 중"
        progress < 1f -> "여정 눈티의 빛과 얼굴이 나타나는 중"
        else -> "여정 눈티 · ${rbEmotionLabel(emotion)}"
    }
    Canvas(modifier.clearAndSetSemantics { contentDescription = label }) {
        if (size.width <= 0f || size.height <= 0f) return@Canvas
        val factor = minOf(size.width, size.height) / 320f
        withTransform({
            translate((size.width - 320f * factor) / 2f, (size.height - 320f * factor) / 2f)
            scale(factor, factor, Offset.Zero)
        }) {
            if (progress < .35f) {
                drawRouteTrace(trace, frame.tracedRoute.last(), colors)
            } else {
                drawRouteBody(spec, frame, shape, changingContour, sourceRoute, colors, emotion)
            }
        }
    }
}

// One transform for route, shell and face. Original normalized coordinates are not recentered per shape.
private fun RouteBornPoint.rbOffset() = Offset(24f + x * 272f, 12f + y * 272f)
private fun rbPath(points: List<RouteBornPoint>, closed: Boolean = false) = Path().apply {
    val first = points.first().rbOffset()
    moveTo(first.x, first.y)
    points.drop(1).forEach { val p = it.rbOffset(); lineTo(p.x, p.y) }
    if (closed) close()
}
private fun rbMorphPath(points: List<RouteBornPoint>, closure: Float) = rbPath(points).apply {
    val last = points.last().rbOffset()
    val first = points.first().rbOffset()
    lineTo(last.x + (first.x - last.x) * closure, last.y + (first.y - last.y) * closure)
}
private fun routeBornColor(value: String) = Color((0xFF000000L or value.substring(1).toLong(16)).toInt())
private fun Color.rbMix(other: Color, t: Float) = Color(red + (other.red - red) * t,
    green + (other.green - green) * t, blue + (other.blue - blue) * t, alpha + (other.alpha - alpha) * t)

private fun DrawScope.drawRouteTrace(path: Path, end: RouteBornPoint, colors: List<Color>) {
    drawPath(path, colors[0].copy(alpha = .10f), style = Stroke(13f, cap = StrokeCap.Round, join = StrokeJoin.Round))
    drawPath(path, colors[0].rbMix(Color(0xFF345C5B), .25f), style = Stroke(3.4f, cap = StrokeCap.Round, join = StrokeJoin.Round))
    drawPath(path, colors[2].copy(alpha = .70f), style = Stroke(1f, cap = StrokeCap.Round, join = StrokeJoin.Round))
    val center = end.rbOffset()
    drawCircle(colors[0].copy(alpha = .12f), 9f, center)
    drawCircle(colors[2], 4.1f, center)
    drawCircle(colors[0].rbMix(Color(0xFF365B5D), .35f), 4.1f, center, style = Stroke(1.3f))
}

private fun DrawScope.drawRouteBody(spec: RouteBornSpec, frame: RouteBornFrame, shell: Path,
    contour: Path, route: Path, colors: List<Color>, emotion: Emotion) {
    val base = colors[0]
    val accent = colors[1]
    val pearl = colors[2]
    val body = frame.shellOpacity
    val finish = frame.pearlReveal
    val left = spec.outline.minOf { it.x } * 272f + 24f
    val right = spec.outline.maxOf { it.x } * 272f + 24f
    val top = spec.outline.minOf { it.y } * 272f + 12f
    val bottom = spec.outline.maxOf { it.y } * 272f + 12f
    val width = right - left
    val height = bottom - top
    val center = Offset((left + right) / 2, (top + bottom) / 2)
    val shade = base.rbMix(Color(0xFF3A4A50), .55f)

    if (body > 0f) {
        repeat(6) { index ->
            val spread = (5 - index) * 4.5f
            drawOval(Color(0xFF4A3C35).copy(alpha = body * (.016f + index * .003f)),
                Offset(left + width * .13f - spread, bottom + 12f - spread * .10f),
                Size(width * .74f + spread * 2, 8f + spread * .42f))
        }
        // Feet and contact shadow stay below the actual supplied silhouette, not a preset baseline.
        if (frame.faceReveal > 0f) {
            for (side in listOf(-1, 1)) {
                val footCenter = center.x + side * width * .23f
                val footTop = 12f + 272f * spec.lowerEdgeAt((footCenter - 24f) / 272f) - 5f
                drawOval(Brush.linearGradient(listOf(pearl.copy(alpha = frame.faceReveal), base.copy(alpha = frame.faceReveal * .80f))),
                    Offset(footCenter - width * .08f, footTop), Size(width * .16f, 16f))
            }
        }
        translate(3.1f, 3.8f) {
            drawPath(shell, Brush.linearGradient(listOf(shade.copy(alpha = body * .12f), shade.copy(alpha = body * .44f)),
                Offset(left, top), Offset(right, bottom)))
        }
        drawPath(shell, Brush.linearGradient(
            0f to base.rbMix(Color.White, .60f).copy(alpha = body * .92f),
            .33f to base.copy(alpha = body * .73f),
            .73f to base.rbMix(accent, .22f).copy(alpha = body * .82f),
            1f to pearl.rbMix(accent, .14f).copy(alpha = body * .94f),
            start = Offset(left, top), end = Offset(right, bottom),
        ))
        clipPath(shell) {
            val inner = Offset(center.x - width * .02f, bottom - height * .19f)
            drawCircle(Brush.radialGradient(listOf(pearl.copy(alpha = body * (.50f + .34f * finish)),
                pearl.copy(alpha = body * .25f), pearl.copy(alpha = 0f)), inner, width * .60f), width * .60f, inner)
            val upper = Offset(left + width * .23f, top + height * .26f)
            drawCircle(Brush.radialGradient(listOf(Color.White.copy(alpha = body * .52f), Color.White.copy(alpha = 0f)),
                upper, width * .58f), width * .58f, upper)
            val side = Offset(right + width * .03f, center.y)
            drawCircle(Brush.radialGradient(listOf(shade.copy(alpha = body * .24f), shade.copy(alpha = 0f)),
                side, width * .72f), width * .72f, side)

            // Original route coordinates stay in the object, naturally occluded by its opaque face.
            drawPath(route, accent.rbMix(base, .30f).copy(alpha = body * .37f),
                style = Stroke(6f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            drawPath(route, pearl.copy(alpha = body * (.58f + .23f * finish)),
                style = Stroke(2.7f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            if (finish > 0f) {
                // Pearl ornaments use actual route samples, not one of the previous body families.
                for (index in listOf(9, 24, 43, 61)) {
                    val point = spec.route[index].rbOffset()
                    drawCircle(Brush.radialGradient(listOf(Color.White.copy(alpha = finish * .90f), pearl.copy(alpha = finish * .40f),
                        base.copy(alpha = 0f)), point - Offset(1.1f, 1.1f), 6f), 4f, point)
                }
                val refraction = Path().apply {
                    moveTo(left - 2f, bottom - height * .17f)
                    cubicTo(left + width * .27f, bottom + height * .025f,
                        left + width * .75f, bottom - height * .015f, right + 2f, bottom - height * .29f)
                }
                drawPath(refraction, Brush.linearGradient(listOf(pearl.copy(alpha = 0f), Color.White.copy(alpha = finish * .62f), pearl.copy(alpha = finish * .12f))),
                    style = Stroke(6.4f, cap = StrokeCap.Round))
                drawPath(refraction, Color.White.copy(alpha = finish * .45f), style = Stroke(1f, cap = StrokeCap.Round))
            }
        }
        drawPath(shell, Brush.linearGradient(listOf(Color.White.copy(alpha = body * .85f), shade.copy(alpha = body * .20f), pearl.copy(alpha = body * .95f))),
            style = Stroke(2.2f, join = StrokeJoin.Round))
        if (finish > 0f) {
            withTransform({ scale(.97f, .97f, center) }) {
                drawPath(shell, Brush.linearGradient(listOf(Color.White.copy(alpha = finish * .66f), Color.White.copy(alpha = 0f), pearl.copy(alpha = finish * .55f))),
                    style = Stroke(1.1f, join = StrokeJoin.Round))
            }
        }
    }
    if (frame.closure < 1f) {
        drawPath(contour, base.copy(alpha = .10f * (1f - body)),
            style = Stroke(13f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        drawPath(contour, base.rbMix(Color(0xFF345C5B), .25f).copy(alpha = 1f - body * .70f),
            style = Stroke(3.4f - body * 1.1f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        drawPath(contour, pearl.copy(alpha = .70f - body * .30f),
            style = Stroke(1f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        val first = frame.contour.first().rbOffset()
        val last = frame.contour.last().rbOffset()
        val tip = last + (first - last) * frame.closure
        drawCircle(base.copy(alpha = .12f * (1f - body)), 9f, tip)
        drawCircle(pearl.copy(alpha = 1f - body), 4.1f, tip)
        drawCircle(base.rbMix(Color(0xFF365B5D), .35f).copy(alpha = 1f - body), 4.1f, tip, style = Stroke(1.3f))
    }
    if (frame.faceReveal > 0f) drawRouteFace(spec.face, emotion, accent, frame.faceReveal)
}

private fun DrawScope.drawRouteFace(face: RouteBornFace, emotion: Emotion, accent: Color, opacity: Float) {
    val center = RouteBornPoint(face.cx, face.cy).rbOffset()
    val rx = ROUTE_BORN_FACE_RADIUS_X * face.scale * 272f
    val ry = ROUTE_BORN_FACE_RADIUS_Y * face.scale * 272f
    val ink = Color(0xFF493735).copy(alpha = opacity)
    val topLeft = center - Offset(rx, ry)
    drawOval(Color(0xFF77604B).copy(alpha = .10f * opacity), topLeft + Offset(0f, 2.6f), Size(rx * 2, ry * 2))
    drawOval(Brush.radialGradient(listOf(Color(0xFFFFF8E9).copy(alpha = opacity), Color(0xFFF8E6CB).copy(alpha = opacity),
        Color(0xFFF2D6B6).copy(alpha = opacity)), center - Offset(rx * .28f, ry * .44f), rx * 1.6f), topLeft, Size(rx * 2, ry * 2))
    drawOval(Color.White.copy(alpha = opacity * .46f), topLeft, Size(rx * 2, ry * 2), style = Stroke(1f))
    val eyeY = center.y - ry * .10f
    val eyeRadius = rx * .12f
    for (side in listOf(-1, 1)) {
        val x = center.x + side * rx * .50f * face.eyeSpacing
        when (emotion) {
            Emotion.RELAXED -> {
                // A half-lidded open eye differs from the closed, rosy relief expression.
                drawOval(ink, Offset(x - eyeRadius, eyeY - eyeRadius * .18f), Size(eyeRadius * 2, eyeRadius * .90f))
                drawLine(ink, Offset(x - eyeRadius * 1.1f, eyeY - eyeRadius * .14f), Offset(x + eyeRadius * 1.1f, eyeY - eyeRadius * .14f), 2f, StrokeCap.Round)
            }
            Emotion.RELIEVED -> {
                val eye = Path().apply {
                    moveTo(x - eyeRadius * 1.2f, eyeY + 1.2f)
                    cubicTo(x - eyeRadius * .6f, eyeY - eyeRadius, x + eyeRadius * .6f, eyeY - eyeRadius, x + eyeRadius * 1.2f, eyeY + 1.2f)
                }
                drawPath(eye, ink, style = Stroke(2.5f, cap = StrokeCap.Round))
            }
            Emotion.NEUTRAL, Emotion.JOYFUL, Emotion.CONCERNED, Emotion.STARTLED -> {
                val r = eyeRadius * if (emotion == Emotion.STARTLED || emotion == Emotion.JOYFUL) 1.10f else 1f
                val h = if (emotion == Emotion.STARTLED) 1.50f else 1.26f
                drawOval(ink, Offset(x - r, eyeY - r * h), Size(r * 2, r * h * 2))
                drawOval(Brush.verticalGradient(listOf(ink, accent.rbMix(Color(0xFF825B4A), .50f).copy(alpha = opacity)), eyeY - r, eyeY + r * h),
                    Offset(x - r * .70f, eyeY - r * .62f), Size(r * 1.4f, r * h * 1.3f))
                drawCircle(Color(0xFFFFF9EE).copy(alpha = opacity), r * .34f, Offset(x - r * .25f, eyeY - r * .50f))
                drawCircle(Color.White.copy(alpha = opacity * .62f), r * .12f, Offset(x + r * .28f, eyeY + r * .50f))
            }
        }
        val browY = eyeY - eyeRadius * if (emotion == Emotion.STARTLED) 2.35f else 2.05f
        val concerned = emotion == Emotion.CONCERNED
        val brow = Path().apply {
            moveTo(x - side * eyeRadius, browY - if (concerned) eyeRadius * .55f else 0f)
            quadraticTo(x, browY - 1f, x + side * eyeRadius * .75f, browY + if (concerned) eyeRadius * .25f else 0f)
        }
        drawPath(brow, ink.copy(alpha = opacity * if (concerned || emotion == Emotion.STARTLED) .70f else .22f),
            style = Stroke(1.7f, cap = StrokeCap.Round))
        val cheek = Offset(center.x + side * rx * .70f, center.y + ry * .34f)
        val blush = if (emotion == Emotion.RELIEVED || emotion == Emotion.JOYFUL) .62f else .34f
        drawOval(Color(0xFFF0A08A).copy(alpha = opacity * blush * .40f), cheek - Offset(rx * .105f, 3.3f), Size(rx * .21f, 6.6f))
        repeat(2) { index ->
            val start = cheek + Offset(-2.7f + index * 4.2f, -1f)
            drawLine(Color(0xFFD68772).copy(alpha = opacity * blush), start, start + Offset(1.7f, 3f), 1.15f, StrokeCap.Round)
        }
    }
    val mouth = center + Offset(0f, ry * .47f)
    val r = rx * .13f
    when (emotion) {
        Emotion.STARTLED -> drawOval(ink, mouth - Offset(r * .55f, r * .73f), Size(r * 1.1f, r * 1.46f))
        Emotion.JOYFUL -> {
            val path = Path().apply {
                moveTo(mouth.x - r * 1.15f, mouth.y - r * .45f)
                cubicTo(mouth.x - r * .5f, mouth.y - r * .25f, mouth.x + r * .5f, mouth.y - r * .25f, mouth.x + r * 1.15f, mouth.y - r * .45f)
                cubicTo(mouth.x + r * 1.1f, mouth.y + r * 1.35f, mouth.x - r * 1.1f, mouth.y + r * 1.35f, mouth.x - r * 1.15f, mouth.y - r * .45f)
                close()
            }
            drawPath(path, ink)
            clipPath(path) { drawOval(Color(0xFFECA18C).copy(alpha = opacity), mouth + Offset(-r, r * .40f), Size(r * 2, r)) }
        }
        Emotion.NEUTRAL, Emotion.RELAXED, Emotion.RELIEVED, Emotion.CONCERNED -> {
            val concerned = emotion == Emotion.CONCERNED
            val width = r * if (emotion == Emotion.RELIEVED) 1.35f else 1.10f
            val path = Path().apply {
                moveTo(mouth.x - width, mouth.y + if (concerned) 1.8f else -1.2f)
                cubicTo(mouth.x - width * .65f, mouth.y + if (concerned) -4f else 4.9f,
                    mouth.x + width * .65f, mouth.y + if (concerned) -4f else 4.9f,
                    mouth.x + width, mouth.y + if (concerned) 1.8f else -1.2f)
            }
            drawPath(path, if (concerned) ink else Color(0xFF9B5B43).copy(alpha = opacity), style = Stroke(2.1f, cap = StrokeCap.Round))
        }
    }
}

private fun rbEmotionLabel(emotion: Emotion) = when (emotion) {
    Emotion.NEUTRAL -> "차분한 표정"
    Emotion.RELAXED -> "편안한 표정"
    Emotion.CONCERNED -> "걱정하는 표정"
    Emotion.STARTLED -> "놀란 표정"
    Emotion.RELIEVED -> "안도하는 표정"
    Emotion.JOYFUL -> "기쁜 표정"
}
