package ai.nunti.avatar

import java.awt.BasicStroke
import java.awt.Color
import java.awt.GradientPaint
import java.awt.RenderingHints
import java.awt.geom.Ellipse2D
import java.awt.geom.Path2D
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

/** Pure recipe/transition checks. Optional Java2D sketches are design comparisons, not Compose QA. */
object RouteBornGeometryTestMain {
    private fun outline(variant: Int = 0) = (0 until 72).map { index ->
        val angle = -PI / 2 + index * PI * 2 / 72
        val radius = .355 + .016 * sin(angle * 3 + variant * .31) + .012 * cos(angle * 5 + variant * .17)
        val aspect = .94 + (variant % 9) * .012
        RouteBornPoint((.5 + cos(angle) * radius * aspect).toFloat(), (.5 + sin(angle) * radius).toFloat())
    }
    private fun route(variant: Int = 0) = (0 until 72).map { index ->
        val t = index / 71.0
        RouteBornPoint((.1 + .8 * t).toFloat(), (.5 + .28 * sin(t * PI * (2 + variant % 3) + variant * .1)).toFloat())
    }
    private fun spec(outline: List<RouteBornPoint> = outline(), route: List<RouteBornPoint> = route(),
        palette: List<String> = listOf("#96D6CF", "#E7C197", "#FFF0D4"), face: RouteBornFace = RouteBornFace(.5f, .43f, 1f, 1f)) =
        RouteBornSpec("route-0123456789abcdef01234567", outline, route, palette, face)

    private fun rejects(message: String? = null, block: () -> Unit) {
        val error = runCatching(block).exceptionOrNull()
        check(error is IllegalArgumentException && (message == null || error.message.orEmpty().contains(message))) { "Expected $message, received $error" }
    }
    private fun near(a: Float, b: Float, epsilon: Float = .0001f) = check(abs(a - b) <= epsilon) { "$a != $b" }

    @JvmStatic
    fun main(args: Array<String>) {
        val fingerprints = mutableSetOf<List<RouteBornPoint>>()
        var framesChecked = 0
        repeat(96) { variant ->
            val o = outline(variant)
            val r = route(variant)
            val recipe = spec(o, r, face = RouteBornFace(.5f, .43f,
                listOf(.8f, .9f, 1f, 1.1f)[variant % 4], listOf(.85f, .95f, 1.05f, 1.15f)[variant % 4]))
            check(fingerprints.add(recipe.outline))
            check(recipe.outline == o && recipe.route == r) // No preset lookup, smoothing, recentering or reordered points.
            for (side in listOf(-1, 1)) {
                val footX = (o.minOf { it.x } + o.maxOf { it.x }) / 2 + side * (o.maxOf { it.x } - o.minOf { it.x }) * .23f
                check(recipe.lowerEdgeAt(footX) in .5f.. .95f)
            }
            check(recipe.frame(.35f).contour == r)
            check(recipe.frame(.8f).contour == o && recipe.frame(1f).contour == o)
            check(recipe.frame(.35f).tracedRoute == r)
            near(recipe.frame(0f).closure, 0f)
            near(recipe.frame(1f).closure, 1f)
            near(recipe.frame(1f).shellOpacity, 1f)
            near(recipe.frame(.8f).faceReveal, 0f)
            near(recipe.frame(1f).faceReveal, 1f)
            for (index in 0..100) {
                val progress = index / 100f
                val frame = recipe.frame(progress)
                check(frame.contour.size == 72)
                check(frame.contour.all { it.x.isFinite() && it.y.isFinite() && it.x in 0f..1f && it.y in 0f..1f })
                check(listOf(frame.closure, frame.shellOpacity, frame.pearlReveal, frame.faceReveal).all { it in 0f..1f })
                if (progress <= .8f) near(frame.faceReveal, 0f)
                check(frame == recipe.frame(progress))
                framesChecked++
            }
            for (boundary in listOf(.35f, .8f)) {
                val before = recipe.frame(boundary - .00001f)
                val after = recipe.frame(boundary + .00001f)
                before.contour.zip(after.contour).forEach { (a, b) -> near(a.x, b.x); near(a.y, b.y) }
                near(before.shellOpacity, after.shellOpacity)
                near(before.pearlReveal, after.pearlReveal)
                near(before.faceReveal, after.faceReveal)
            }
        }
        // Trace length, rather than point count, drives the visible route.
        val uneven = listOf(RouteBornPoint(0f, 0f), RouteBornPoint(.1f, 0f), RouteBornPoint(.1f, 0f), RouteBornPoint(1f, 0f))
        for (step in 0..100) {
            val fraction = step / 100f
            val traced = traceRoute(uneven, fraction)
            near(routeLength(traced).toFloat(), fraction)
            check(traced.first() == uneven.first())
        }
        rejects { spec(outline = outline().dropLast(1)) }
        rejects { spec(route = route().dropLast(1)) }
        rejects { spec(route = List(72) { RouteBornPoint(.5f, .5f) }) }
        rejects { spec(route = route().toMutableList().apply { this[3] = RouteBornPoint(Float.NaN, .5f) }) }
        rejects { spec(outline = outline().toMutableList().apply { this[3] = RouteBornPoint(.96f, .5f) }) }
        rejects { spec(outline = outline().toMutableList().apply { this[4] = this[3] }) }
        rejects { spec(outline = outline().toMutableList().apply { val temp = this[18]; this[18] = this[54]; this[54] = temp }) }
        rejects("Face ellipse") { spec(outline = outline().toMutableList().apply { this[18] = RouteBornPoint(.68f, .5f) }, face = RouteBornFace(.5f, .43f, 1.1f, 1f)) }
        rejects { spec(face = RouteBornFace(.6f, .43f, 1f, 1f)) }
        rejects { spec(face = RouteBornFace(.5f, .43f, Float.POSITIVE_INFINITY, 1f)) }
        rejects { spec(face = RouteBornFace(.5f, .43f, 1.11f, 1f)) }
        rejects { spec(face = RouteBornFace(.5f, .43f, 1f, .84f)) }
        rejects { spec(palette = listOf("#ABCDEF", "#123456")) }
        rejects { spec(palette = listOf("#00000000", "#123456", "#FFFFFF")) }
        rejects { spec(palette = listOf("#GGGGGG", "#123456", "#FFFFFF")) }
        rejects { spec().frame(Float.NaN) }
        rejects { spec().frame(-.01f) }
        rejects { spec().frame(1.01f) }
        val rawOutline = outline().toMutableList()
        val rawRoute = route().toMutableList()
        val rawPalette = mutableListOf("#96D6CF", "#E7C197", "#FFF0D4")
        val copied = spec(rawOutline, rawRoute, rawPalette)
        rawOutline.clear(); rawRoute.clear(); rawPalette[0] = "corrupt"
        check(copied.outline.size == 72 && copied.route.size == 72 && copied.palette[0] == "#96D6CF")
        println("PASS: 96 supplied continuous outlines preserved, $framesChecked deterministic bounded frames")
        println("PASS: exact route/body endpoints, stage continuity, arc-length trace with zero-length segments")
        println("PASS: shape/route/face/palette/progress boundary rejection, concave ellipse cut rejection, copied inputs")
        if (args.isNotEmpty()) sketchVariants(spec(), File(args[0]))
        println("Scope: CPU geometry and procedural design sketches; no Compose pixels, Android runtime, policy or model execution")
    }

    private fun sketchVariants(spec: RouteBornSpec, output: File) {
        output.parentFile.mkdirs()
        val image = BufferedImage(1140, 400, BufferedImage.TYPE_INT_RGB)
        val g = image.createGraphics()
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
        g.color = Color(0xF6F1E9); g.fillRect(0, 0, 1140, 400)
        val titles = listOf("A / clear line", "B / satin volume", "C / pearl keepsake")
        repeat(3) { index ->
            val x = index * 380
            g.color = Color(0x354748); g.font = java.awt.Font("SansSerif", java.awt.Font.BOLD, 18)
            g.drawString(titles[index], x + 28, 34)
            val shell = Path2D.Float().apply {
                moveTo(x + 54 + spec.outline[0].x * 272, 35 + spec.outline[0].y * 272)
                spec.outline.drop(1).forEach { lineTo(x + 54 + it.x * 272, 35 + it.y * 272) }
                closePath()
            }
            g.color = Color(60, 49, 41, 18); g.fill(Ellipse2D.Float(x + 112f, 278f, 160f, 14f))
            g.paint = when (index) {
                0 -> GradientPaint(x + 100f, 80f, Color(150, 214, 207, 65), x + 250f, 285f, Color(255, 240, 212, 80))
                1 -> GradientPaint(x + 100f, 80f, Color(180, 226, 218), x + 250f, 285f, Color(133, 176, 173))
                else -> GradientPaint(x + 100f, 80f, Color(194, 233, 223), x + 250f, 285f, Color(255, 234, 197))
            }
            g.fill(shell)
            val oldClip = g.clip
            g.clip(shell)
            val route = Path2D.Float().apply {
                moveTo(x + 54 + spec.route[0].x * 272, 35 + spec.route[0].y * 272)
                spec.route.drop(1).forEach { lineTo(x + 54 + it.x * 272, 35 + it.y * 272) }
            }
            g.color = if (index == 1) Color(67, 117, 119, 90) else Color(255, 255, 240, 185)
            g.stroke = BasicStroke(if (index == 2) 4f else 2f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
            g.draw(route)
            if (index == 2) {
                g.color = Color(255, 255, 255, 135)
                g.stroke = BasicStroke(8f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
                g.drawArc(x + 100, 75, 185, 180, 90, 70)
                g.color = Color(255, 251, 227, 100); g.fill(Ellipse2D.Float(x + 112f, 220f, 175f, 55f))
            }
            g.clip = oldClip
            g.color = if (index == 1) Color(109, 153, 151) else Color(245, 250, 239)
            g.stroke = BasicStroke(if (index == 2) 3f else 1.5f); g.draw(shell)
            val cx = x + 54 + spec.face.cx * 272
            val cy = 35 + spec.face.cy * 272
            g.paint = GradientPaint(cx - 30, cy - 30, Color(255, 248, 230), cx + 30, cy + 30, Color(245, 220, 187))
            g.fill(Ellipse2D.Float(cx - 60, cy - 39, 120f, 78f))
            g.color = Color(0x4A3734)
            g.fill(Ellipse2D.Float(cx - 36, cy - 10, 12f, 18f)); g.fill(Ellipse2D.Float(cx + 24, cy - 10, 12f, 18f))
            g.color = Color.WHITE
            g.fill(Ellipse2D.Float(cx - 33, cy - 7, 3.5f, 4f)); g.fill(Ellipse2D.Float(cx + 27, cy - 7, 3.5f, 4f))
            g.color = Color(0xA56446); g.stroke = BasicStroke(2f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
            g.drawArc(cx.toInt() - 9, cy.toInt() + 12, 18, 12, 180, 180)
            g.font = java.awt.Font("SansSerif", java.awt.Font.PLAIN, 13)
            g.color = Color(0x536867); g.drawString("Same supplied polygon and input route", x + 48, 351)
        }
        g.dispose()
        ImageIO.write(image, "png", output)
        println("Design sketches: ${output.absolutePath}")
    }
}
