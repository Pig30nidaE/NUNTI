package ai.nunti.avatar

import ai.nunti.emotion.Emotion
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription

/** Static, locally drawn C keepsake. No image service, animation clock or audio side effect.
 * A hidden render state creates no layout node or accessibility semantics.
 */
@Composable
fun JourneyKeepsake(spec: JourneyVisualSpec, renderState: RenderState, modifier: Modifier = Modifier) {
    if (!renderState.visible) return
    // An approved static driving presentation must not change its character or expression.
    val frozen = remember(renderState.interactionsAllowed) { spec }
    val shown = if (renderState.interactionsAllowed) spec else frozen
    val emotion = if (renderState.interactionsAllowed) renderState.emotion else Emotion.NEUTRAL
    val geometry = remember(shown) { shown.geometry() }
    val shell = remember(geometry) { geometry.outline.path(geometry.body) }
    val colors = remember(shown) { shown.palette.map(::journeyColor) }
    val label = if (renderState.interactionsAllowed) "여정 눈티 · ${shown.bodyFamily.korean()} · ${emotion.korean()}" else "눈티"
    Canvas(modifier.clearAndSetSemantics { contentDescription = label }) {
        if (size.width <= 0f || size.height <= 0f) return@Canvas
        val factor = minOf(size.width, size.height) / 320f
        withTransform({
            translate((size.width - 320f * factor) / 2f, (size.height - 320f * factor) / 2f)
            scale(factor, factor, Offset.Zero)
        }) {
            drawKeepsake(shown, geometry, shell, colors, emotion)
        }
    }
}

private fun journeyColor(value: String) = Color((0xFF000000L or value.substring(1).toLong(16)).toInt())
private fun Color.towards(other: Color, amount: Float) = Color(
    red + (other.red - red) * amount, green + (other.green - green) * amount,
    blue + (other.blue - blue) * amount, alpha + (other.alpha - alpha) * amount,
)
private fun JourneyPoint.offset() = Offset(x, y)
private fun JourneyRect.topLeft() = Offset(left, top)
private fun JourneyRect.size() = Size(width, height)
private fun JourneyOutline.path(rect: JourneyRect) = Path().apply {
    val first = rect.point(start.x, start.y)
    moveTo(first.x, first.y)
    curves.forEach { curve ->
        val a = rect.point(curve.control1.x, curve.control1.y)
        val b = rect.point(curve.control2.x, curve.control2.y)
        val end = rect.point(curve.end.x, curve.end.y)
        cubicTo(a.x, a.y, b.x, b.y, end.x, end.y)
    }
    close()
}

private fun DrawScope.drawKeepsake(spec: JourneyVisualSpec, geometry: JourneyGeometry, shell: Path,
    colors: List<Color>, emotion: Emotion) {
    val b = geometry.body
    val base = colors[0]
    val accent = colors[1]
    val pearl = colors[2]
    val shade = base.towards(Color(0xFF33454B), .57f)
    val light = base.towards(Color.White, .73f)
    val center = Offset(b.centerX, b.centerY)

    // A wide penumbra and compact contact shadow put the resin above the surface.
    for (layer in 7 downTo 0) {
        val spread = layer * 3.7f
        drawOval(Color(0xFF44382F).copy(alpha = .012f + (7 - layer) * .002f),
            Offset(b.left + b.width * .12f - spread, 279f - spread * .12f),
            Size(b.width * .76f + spread * 2, 12f + spread * .48f))
    }
    drawOval(Color(0xFF463A32).copy(alpha = .13f), Offset(b.left + b.width * .23f, 281f), Size(b.width * .54f, 9f))

    // Small translucent feet sit behind the body. Their color belongs to the same material.
    for (side in listOf(-1, 1)) {
        drawOval(Brush.linearGradient(listOf(pearl.copy(alpha = .94f), base.towards(shade, .20f))),
            Offset(b.centerX + side * b.width * .235f - b.width * .092f, 267f), Size(b.width * .184f, 23f))
    }
    translate(3.8f, 4.2f) {
        drawPath(shell, Brush.linearGradient(listOf(shade.copy(alpha = .17f), shade.copy(alpha = .58f)),
            Offset(b.left, b.top), Offset(b.right, b.bottom)))
    }
    drawPath(shell, Brush.linearGradient(
        .0f to light.copy(alpha = .91f), .25f to base.copy(alpha = .77f),
        .66f to base.towards(accent, .25f).copy(alpha = .80f), 1f to accent.towards(pearl, .45f).copy(alpha = .95f),
        start = Offset(b.left, b.top), end = Offset(b.right, b.bottom),
    ))

    clipPath(shell) {
        // The far wall and lower chamber remain visible behind miniature contents.
        drawOval(Brush.radialGradient(listOf(shade.copy(alpha = .25f), shade.copy(alpha = 0f)),
            Offset(b.right, b.centerY + b.height * .08f), b.width * .70f),
            Offset(b.centerX, b.top), Size(b.width, b.height * 1.1f))
        drawOval(Brush.radialGradient(listOf(pearl.copy(alpha = .80f), pearl.copy(alpha = 0f)),
            Offset(b.centerX, b.bottom - b.height * .10f), b.width * .51f),
            Offset(b.left - b.width * .04f, b.centerY), Size(b.width * 1.08f, b.height * .65f))
        drawPurposeLight(spec.purpose, b)
        drawMotif(spec, b, colors)
        drawRoutePattern(spec, b, colors)

        // Broad internal refraction, followed by the narrow high-gloss edge.
        val glint = Path().apply {
            moveTo(b.left + b.width * .11f, b.top + b.height * .74f)
            cubicTo(b.left + b.width * .32f, b.bottom + b.height * .04f,
                b.left + b.width * .84f, b.bottom - b.height * .06f,
                b.right + b.width * .02f, b.top + b.height * .54f)
        }
        drawPath(glint, Brush.linearGradient(listOf(pearl.copy(alpha = .02f), Color.White.copy(alpha = .76f), pearl.copy(alpha = .15f))),
            style = Stroke(b.height * .037f, cap = StrokeCap.Round))
        drawPath(glint, Color.White.copy(alpha = .47f), style = Stroke(1.35f, cap = StrokeCap.Round))

        val upper = Path().apply {
            moveTo(b.left + b.width * .13f, b.top + b.height * .43f)
            cubicTo(b.left + b.width * .13f, b.top + b.height * .22f,
                b.left + b.width * .28f, b.top + b.height * .10f,
                b.left + b.width * (.50f + spec.variation(0) * .09f), b.top + b.height * .10f)
        }
        drawPath(upper, Brush.linearGradient(listOf(Color.White.copy(alpha = .08f), Color.White.copy(alpha = .80f), Color.White.copy(alpha = .05f))),
            style = Stroke(b.width * .050f, cap = StrokeCap.Round))
        drawPath(upper, Color.White.copy(alpha = .65f), style = Stroke(1.5f, cap = StrokeCap.Round))
    }
    drawPath(shell, Brush.linearGradient(listOf(light.copy(alpha = .98f), shade.copy(alpha = .24f), pearl.copy(alpha = .90f))),
        style = Stroke(2.6f))
    withTransform({ scale(.965f, .967f, center) }) {
        drawPath(shell, Brush.linearGradient(listOf(Color.White.copy(alpha = .72f), Color.White.copy(alpha = .01f), pearl.copy(alpha = .57f))),
            style = Stroke(1.3f))
    }
    rotate((spec.variation(1) - .5f) * 3.0f, Offset(geometry.face.centerX, geometry.face.centerY)) {
        drawKeepsakeFace(geometry.face, emotion, accent)
    }
}

private data class InnerLight(val color: Color, val x: Float, val y: Float, val radius: Float, val flatten: Float)
private fun DrawScope.drawPurposeLight(purpose: JourneyPurpose, b: JourneyRect) {
    val light = when (purpose) {
        JourneyPurpose.REST -> InnerLight(Color(0xFFFFE8BB), .50f, .82f, .55f, .67f)
        JourneyPurpose.CAMPING -> InnerLight(Color(0xFFFFD39B), .50f, .64f, .36f, .94f)
        JourneyPurpose.EXHIBITION -> InnerLight(Color(0xFFD9C9FF), .37f, .63f, .47f, .90f)
        JourneyPurpose.COMMUTE -> InnerLight(Color(0xFFF3E6CF), .50f, .64f, .48f, .57f)
        JourneyPurpose.VISIT -> InnerLight(Color(0xFFFFCEC4), .50f, .80f, .45f, .72f)
        JourneyPurpose.ERRAND -> InnerLight(Color(0xFFE2F2DC), .50f, .64f, .31f, .89f)
        JourneyPurpose.UNSPECIFIED -> InnerLight(Color(0xFFEFE6D8), .50f, .66f, .44f, .62f)
    }
    val center = b.point(light.x, light.y).offset()
    val radius = b.width * light.radius
    withTransform({ scale(1f, light.flatten, center) }) {
        drawCircle(Brush.radialGradient(listOf(Color.White.copy(alpha = .92f), light.color.copy(alpha = .78f), light.color.copy(alpha = 0f)), center, radius), radius, center)
    }
    if (purpose == JourneyPurpose.EXHIBITION) {
        val second = b.point(.73f, .77f).offset()
        drawCircle(Brush.radialGradient(listOf(Color(0xFFFFE2BA).copy(alpha = .72f), Color.Transparent), second, radius * .56f), radius * .56f, second)
    }
}

private fun DrawScope.drawMotif(spec: JourneyVisualSpec, b: JourneyRect, colors: List<Color>) {
    val base = colors[0]
    val accent = colors[1]
    val pearl = colors[2]
    val shift = (spec.variation(2) - .5f) * .07f
    val depth = spec.variation(3)
    fun at(x: Float, y: Float) = b.point(x + shift, y).offset()
    when (spec.motif) {
        JourneyMotif.ART -> repeat(4) { index ->
            val center = at(.23f + index * .18f, .68f + (index % 2) * .10f)
            rotate(-35f + index * 29f + depth * 18f, center) {
                drawOval(Brush.linearGradient(listOf(accent.copy(alpha = .68f), pearl.copy(alpha = .32f))),
                    center - Offset(b.width * .038f, b.height * .075f), Size(b.width * .076f, b.height * .15f))
                drawLine(Color.White.copy(alpha = .45f), center - Offset(0f, b.height * .035f), center + Offset(0f, b.height * .035f), 1.2f, StrokeCap.Round)
            }
        }
        JourneyMotif.COASTAL_CITY -> repeat(6) { index ->
            val center = at(.16f + index * .135f, .72f + (index % 3) * .065f)
            val radius = b.width * (.017f + (index % 3) * .009f)
            drawCircle(Brush.radialGradient(listOf(Color.White.copy(alpha = .95f), pearl.copy(alpha = .57f), base.copy(alpha = .15f)), center - Offset(radius * .3f, radius * .3f), radius * 1.5f), radius, center)
            drawCircle(Color.White.copy(alpha = .56f), radius, center, style = Stroke(.9f))
        }
        JourneyMotif.MOUNTAIN -> repeat(3) { index ->
            val y = .66f + index * .09f
            val mist = Path().apply {
                moveTo(at(.13f, y + .02f).x, at(.13f, y + .02f).y)
                cubicTo(at(.30f, y - .11f).x, at(.30f, y - .11f).y, at(.35f, y + .03f).x, at(.35f, y + .03f).y, at(.52f, y - .04f).x, at(.52f, y - .04f).y)
                cubicTo(at(.70f, y - .13f).x, at(.70f, y - .13f).y, at(.81f, y + .04f).x, at(.81f, y + .04f).y, at(.91f, y).x, at(.91f, y).y)
                lineTo(b.right, b.bottom)
                lineTo(b.left, b.bottom)
                close()
            }
            drawPath(mist, Brush.verticalGradient(listOf(accent.towards(base, .60f).copy(alpha = .34f), pearl.copy(alpha = .04f)), b.top + b.height * y, b.bottom))
        }
        JourneyMotif.FOREST -> repeat(3) { index ->
            val center = at(.26f + index * .23f, .74f + (index % 2) * .04f)
            rotate(-28f + index * 23f + depth * 13f, center) {
                val leaf = Path().apply {
                    moveTo(center.x, center.y - b.height * .09f)
                    cubicTo(center.x + b.width * .09f, center.y - b.height * .03f, center.x + b.width * .05f, center.y + b.height * .07f, center.x, center.y + b.height * .085f)
                    cubicTo(center.x - b.width * .07f, center.y + b.height * .02f, center.x - b.width * .05f, center.y - b.height * .06f, center.x, center.y - b.height * .09f)
                    close()
                }
                drawPath(leaf, Brush.linearGradient(listOf(pearl.copy(alpha = .70f), base.towards(Color(0xFF587F55), .40f).copy(alpha = .70f))))
                drawLine(pearl.copy(alpha = .80f), center - Offset(0f, b.height * .045f), center + Offset(0f, b.height * .06f), 1.1f, StrokeCap.Round)
            }
        }
        JourneyMotif.LAKESIDE -> repeat(3) { index ->
            val center = at(.27f + index * .23f, .72f + (index % 2) * .09f)
            drawOval(pearl.copy(alpha = .62f), center - Offset(b.width * .095f, b.height * .022f), Size(b.width * .19f, b.height * .044f), style = Stroke(2f))
            drawOval(accent.copy(alpha = .38f), center - Offset(b.width * .065f, b.height * .014f), Size(b.width * .13f, b.height * .028f), style = Stroke(1f))
            drawCircle(Color.White.copy(alpha = .86f), b.width * .014f, center - Offset(b.width * .025f, b.height * .045f))
        }
        JourneyMotif.CITY -> repeat(4) { index ->
            val center = at(.22f + index * .185f, .71f + (index % 2) * .085f)
            rotate(-12f + index * 8f, center) {
                drawRoundRect(Brush.linearGradient(listOf(pearl.copy(alpha = .85f), accent.copy(alpha = .48f))),
                    center - Offset(b.width * .047f, b.height * .055f), Size(b.width * .094f, b.height * .11f), CornerRadius(4f))
                drawLine(Color.White.copy(alpha = .86f), center - Offset(b.width * .021f, b.height * .023f), center + Offset(b.width * .021f, -b.height * .023f), 1.5f, StrokeCap.Round)
            }
        }
        JourneyMotif.UNSPECIFIED -> repeat(5) { index ->
            val center = at(.20f + index * .15f, .72f + (index % 2) * .09f)
            drawCircle(pearl.copy(alpha = .58f + depth * .15f), b.width * (.012f + (index % 3) * .006f), center)
        }
    }
}

private fun DrawScope.drawRoutePattern(spec: JourneyVisualSpec, b: JourneyRect, colors: List<Color>) {
    val light = colors[2].towards(Color.White, .43f)
    val shadow = colors[1].towards(colors[0], .34f)
    val jitter = (spec.variation(0) - .5f) * .035f
    fun p(x: Float, y: Float) = b.point(x, y + jitter).offset()
    fun ribbon(path: Path, width: Float = 4f) {
        translate(0f, 1.5f) { drawPath(path, shadow.copy(alpha = .38f), style = Stroke(width + 2f, cap = StrokeCap.Round)) }
        drawPath(path, light.copy(alpha = .77f), style = Stroke(width, cap = StrokeCap.Round))
        translate(0f, -1f) { drawPath(path, Color.White.copy(alpha = .50f), style = Stroke(1f, cap = StrokeCap.Round)) }
    }
    fun line(x1: Float, y1: Float, x2: Float, y2: Float, width: Float = 2.4f) =
        drawLine(light.copy(alpha = .76f), p(x1, y1), p(x2, y2), width, StrokeCap.Round)
    when (spec.routePattern) {
        JourneyPattern.COASTAL -> repeat(3) { index ->
            val y = .75f + index * .071f
            val path = Path().apply {
                moveTo(p(.04f, y).x, p(.04f, y).y)
                cubicTo(p(.28f, y - .10f).x, p(.28f, y - .10f).y, p(.55f, y + .12f).x, p(.55f, y + .12f).y, p(.98f, y - .015f).x, p(.98f, y - .015f).y)
            }
            ribbon(path, 4f - index * .65f)
        }
        JourneyPattern.MOUNTAIN -> repeat(3) { index ->
            val y = .78f + index * .065f
            val path = Path().apply {
                moveTo(p(.08f, y + .03f).x, p(.08f, y + .03f).y)
                cubicTo(p(.25f, y - .02f).x, p(.25f, y - .02f).y, p(.28f, y - .13f).x, p(.28f, y - .13f).y, p(.43f, y - .07f).x, p(.43f, y - .07f).y)
                cubicTo(p(.63f, y + .02f).x, p(.63f, y + .02f).y, p(.72f, y - .16f).x, p(.72f, y - .16f).y, p(.92f, y - .06f).x, p(.92f, y - .06f).y)
            }
            ribbon(path, 2.3f)
        }
        JourneyPattern.URBAN -> {
            repeat(3) { index -> line(.18f, .72f + index * .08f, .83f, .72f + index * .08f, 2f) }
            repeat(4) { index -> line(.23f + index * .17f, .69f, .23f + index * .17f, .90f, 2f) }
        }
        JourneyPattern.TREE_LINED -> repeat(4) { index ->
            val x = .23f + index * .18f
            line(x, .91f, x, .70f, 2.1f)
            line(x, .79f, x - .055f, .73f, 1.7f)
            line(x, .83f, x + .057f, .76f, 1.7f)
        }
        JourneyPattern.CURVING -> repeat(2) { index ->
            val y = .75f + index * .11f
            val path = Path().apply {
                moveTo(p(.06f, y + .06f).x, p(.06f, y + .06f).y)
                cubicTo(p(.32f, y + .18f).x, p(.32f, y + .18f).y, p(.81f, y - .18f).x, p(.81f, y - .18f).y, p(.51f, y - .11f).x, p(.51f, y - .11f).y)
                cubicTo(p(.29f, y - .06f).x, p(.29f, y - .06f).y, p(.68f, y + .10f).x, p(.68f, y + .10f).y, p(.95f, y - .01f).x, p(.95f, y - .01f).y)
            }
            ribbon(path, 4f)
        }
        JourneyPattern.HIGHWAY -> repeat(3) { index ->
            val y = .73f + index * .07f
            val path = Path().apply {
                moveTo(p(.08f, y + .05f).x, p(.08f, y + .05f).y)
                cubicTo(p(.35f, y + .06f).x, p(.35f, y + .06f).y, p(.68f, y - .04f).x, p(.68f, y - .04f).y, p(.93f, y - .03f).x, p(.93f, y - .03f).y)
            }
            ribbon(path, 2f)
        }
        JourneyPattern.MIXED -> repeat(4) { index ->
            val y = .73f + index * .05f
            line(.18f + (index % 2) * .11f, y + .02f, .53f + (index % 2) * .21f, y - .02f, 2.8f)
        }
        JourneyPattern.STRAIGHT -> repeat(4) { index ->
            val x = .21f + index * .17f
            line(x, .76f, x + .09f, .89f, 3f)
        }
        JourneyPattern.UNSPECIFIED -> repeat(3) { index ->
            drawCircle(light.copy(alpha = .65f), 2.0f, p(.34f + index * .15f, .86f))
        }
    }
}

private fun DrawScope.drawKeepsakeFace(face: JourneyRect, emotion: Emotion, accent: Color) {
    val ink = Color(0xFF4B3836)
    val f = face
    val center = Offset(f.centerX, f.centerY)
    drawOval(Color(0xFF80634C).copy(alpha = .10f), f.topLeft() + Offset(1f, 2.7f), f.size())
    drawOval(Brush.radialGradient(listOf(Color(0xFFFFF8E8), Color(0xFFF8E8D1), Color(0xFFF1D6B5)),
        Offset(f.centerX - f.width * .13f, f.top + f.height * .22f), f.width * .75f), f.topLeft(), f.size())
    drawOval(Color.White.copy(alpha = .48f), f.topLeft(), f.size(), style = Stroke(1.0f))

    val eyeY = f.top + f.height * .46f
    val eyeRadius = f.width * .058f
    for (side in listOf(-1, 1)) {
        val x = f.centerX + side * f.width * .255f
        val eye = Offset(x, eyeY)
        when (emotion) {
            Emotion.RELAXED, Emotion.RELIEVED -> {
                val relaxed = emotion == Emotion.RELAXED
                val path = Path().apply {
                    moveTo(x - eyeRadius * 1.32f, eyeY + if (relaxed) 1f else 2f)
                    cubicTo(x - eyeRadius * .7f, eyeY - eyeRadius * if (relaxed) .65f else 1.0f,
                        x + eyeRadius * .7f, eyeY - eyeRadius * if (relaxed) .65f else 1.0f,
                        x + eyeRadius * 1.32f, eyeY + if (relaxed) 1f else 2f)
                }
                drawPath(path, ink, style = Stroke(2.6f, cap = StrokeCap.Round))
            }
            Emotion.NEUTRAL, Emotion.JOYFUL, Emotion.STARTLED, Emotion.CONCERNED -> {
                val tall = if (emotion == Emotion.STARTLED) 1.55f else 1.25f
                val radius = eyeRadius * if (emotion == Emotion.STARTLED || emotion == Emotion.JOYFUL) 1.15f else 1f
                drawOval(ink, eye - Offset(radius, radius * tall), Size(radius * 2, radius * tall * 2))
                drawOval(Brush.verticalGradient(listOf(ink, accent.towards(Color(0xFF795951), .35f)), eyeY - radius, eyeY + radius * tall),
                    eye - Offset(radius * .67f, radius * .55f), Size(radius * 1.34f, radius * tall * 1.28f))
                drawCircle(Color(0xFFFFFAEE), radius * .33f, eye - Offset(radius * .25f, radius * .48f))
                drawCircle(Color.White.copy(alpha = .67f), radius * .13f, eye + Offset(radius * .28f, radius * .48f))
            }
        }
        val browY = eyeY - eyeRadius * if (emotion == Emotion.STARTLED) 2.5f else 2.05f
        val inner = x - side * eyeRadius * .75f
        val outer = x + side * eyeRadius * .65f
        val rise = if (emotion == Emotion.CONCERNED) eyeRadius * .72f else 0f
        val brow = Path().apply {
            moveTo(inner, browY - rise)
            quadraticTo(x, browY - 1.1f, outer, browY + rise * .32f)
        }
        drawPath(brow, ink.copy(alpha = if (emotion == Emotion.CONCERNED || emotion == Emotion.STARTLED) .72f else .23f),
            style = Stroke(1.8f, cap = StrokeCap.Round))
        val blushAlpha = if (emotion == Emotion.RELIEVED || emotion == Emotion.JOYFUL) .62f else .35f
        val cheek = Offset(f.centerX + side * f.width * .345f, f.top + f.height * .66f)
        drawOval(Color(0xFFF2A08A).copy(alpha = blushAlpha * .42f), cheek - Offset(f.width * .054f, 3.4f), Size(f.width * .108f, 6.8f))
        repeat(2) { index ->
            val start = cheek + Offset(-2.7f + index * 4f, -.8f)
            drawLine(Color(0xFFDA8C76).copy(alpha = blushAlpha), start, start + Offset(1.7f, 3.1f), 1.2f, StrokeCap.Round)
        }
    }
    val mouth = Offset(center.x, f.top + f.height * .72f)
    val r = f.width * .062f
    when (emotion) {
        Emotion.STARTLED -> {
            drawOval(ink, mouth - Offset(r * .57f, r * .76f), Size(r * 1.14f, r * 1.52f))
            drawOval(Color(0xFFD68C79), mouth + Offset(-r * .28f, r * .27f), Size(r * .56f, r * .32f))
        }
        Emotion.JOYFUL -> {
            val smile = Path().apply {
                moveTo(mouth.x - r * 1.20f, mouth.y - r * .50f)
                cubicTo(mouth.x - r * .50f, mouth.y - r * .30f, mouth.x + r * .50f, mouth.y - r * .30f, mouth.x + r * 1.20f, mouth.y - r * .50f)
                cubicTo(mouth.x + r * 1.23f, mouth.y + r * 1.40f, mouth.x - r * 1.23f, mouth.y + r * 1.40f, mouth.x - r * 1.20f, mouth.y - r * .50f)
                close()
            }
            drawPath(smile, ink)
            clipPath(smile) {
                drawOval(Color(0xFFEAA08C), mouth + Offset(-r, r * .40f), Size(r * 2, r))
            }
        }
        Emotion.NEUTRAL, Emotion.RELAXED, Emotion.RELIEVED, Emotion.CONCERNED -> {
            val concerned = emotion == Emotion.CONCERNED
            val width = r * if (emotion == Emotion.RELIEVED) 1.35f else 1.12f
            val path = Path().apply {
                moveTo(mouth.x - width, mouth.y + if (concerned) 2f else -1.1f)
                cubicTo(mouth.x - width * .7f, mouth.y + if (concerned) -4f else 5.2f,
                    mouth.x + width * .7f, mouth.y + if (concerned) -4f else 5.2f,
                    mouth.x + width, mouth.y + if (concerned) 2f else -1.1f)
            }
            drawPath(path, if (concerned) ink else Color(0xFF9B5C44), style = Stroke(2.1f, cap = StrokeCap.Round))
        }
    }
}

private fun JourneyBody.korean() = when (this) {
    JourneyBody.PEBBLE -> "조약돌"
    JourneyBody.DROPLET -> "물방울"
    JourneyBody.BEAN -> "콩알"
    JourneyBody.SPROUT -> "새싹"
    JourneyBody.PILLOW -> "폭신한 쿠션"
    JourneyBody.LANTERN -> "작은 등불"
    JourneyBody.CLOUD -> "뭉게구름"
    JourneyBody.ACORN -> "도토리"
}
private fun Emotion.korean() = when (this) {
    Emotion.NEUTRAL -> "차분한 표정"
    Emotion.RELAXED -> "편안한 표정"
    Emotion.JOYFUL -> "기쁜 표정"
    Emotion.STARTLED -> "놀란 표정"
    Emotion.CONCERNED -> "걱정하는 표정"
    Emotion.RELIEVED -> "안도하는 표정"
}
