package ai.nunti.avatar

import java.io.File
import java.security.MessageDigest
import javax.imageio.ImageIO
import kotlin.math.abs
import kotlin.math.hypot

/** CPU geometry and compositing contracts. Native Compose output is verified separately on Android. */
object GeneratedCompanionTestMain {
    private fun rejects(block: () -> Unit) = check(runCatching(block).exceptionOrNull() is IllegalArgumentException)
    private fun near(a: Float, b: Float, tolerance: Float = .0001f) = check(abs(a - b) < tolerance) { "$a != $b" }
    private fun distance(a: GeneratedFormationPoint, b: GeneratedFormationPoint) = hypot(a.x - b.x, a.y - b.y)
    private val routes = listOf(
        GeneratedRoute(listOf(GeneratedPoint(0f, 0f), GeneratedPoint(1f, 1f))),
        GeneratedRoute(listOf(GeneratedPoint(.05f, .8f), GeneratedPoint(.15f, .1f), GeneratedPoint(.8f, .3f), GeneratedPoint(.95f, .95f))),
        GeneratedRoute(listOf(GeneratedPoint(.2f, .2f), GeneratedPoint(.8f, .2f), GeneratedPoint(.8f, .8f), GeneratedPoint(.2f, .8f), GeneratedPoint(.2f, .2f))),
    )

    @JvmStatic
    fun main(args: Array<String>) {
        val points = mutableListOf(GeneratedPoint(0f, 0f), GeneratedPoint(.1f, 0f),
            GeneratedPoint(.1f, 0f), GeneratedPoint(1f, 0f))
        val route = GeneratedRoute(points)
        points.clear()
        check(route.points.size == 4)
        for (index in 0..1000) {
            val progress = index / 1000f
            near(generatedRouteLength(route.trace(progress)).toFloat(), progress)
            for (ready in listOf(false, true)) for (available in listOf(false, true)) {
                val frame = generatedBirthFrame(progress, ready, available, progress)
                check(listOf(frame.revealFraction, frame.routeFraction, frame.glowOpacity, frame.shadowOpacity,
                    frame.morphFraction, frame.residualFraction, frame.ribbonOpacity, frame.tipOpacity).all { it in 0f..1f })
                check(frame.brushWidth in 8f..32f)
                if (!ready || !available) {
                    near(frame.revealFraction, 0f); near(frame.morphFraction, 0f); near(frame.residualFraction, 0f)
                    near(frame.shadowOpacity, 0f)
                    check(frame.stage != GeneratedBirthStage.READY)
                }
                if (progress <= .50f) near(frame.revealFraction, 0f)
                if (progress <= .18f) near(frame.morphFraction, 0f)
                if (progress <= .88f) near(frame.residualFraction, 0f)
                if (ready && available && progress >= .98f) {
                    near(frame.revealFraction, 1f); near(frame.residualFraction, 1f)
                    near(frame.routeOpacity, 0f); near(frame.ribbonOpacity, 0f); near(frame.tipOpacity, 0f)
                }
                if (ready && available && progress == 1f) check(frame.stage == GeneratedBirthStage.READY)
            }
            val still = generatedBirthFrame(1f, true, true, progress, animate = false)
            near(still.scaleX, 1f); near(still.scaleY, 1f); near(still.floatY, 0f); near(still.tilt, 0f)
        }
        check(generatedBirthFrame(.18f, true, true).stage == GeneratedBirthStage.ROUTE)
        check(generatedBirthFrame(.35f, true, true).stage == GeneratedBirthStage.LIGHT)
        check(generatedBirthFrame(.7f, true, true).stage == GeneratedBirthStage.REVEAL)
        check(generatedBirthFrame(1f, false, true).stage == GeneratedBirthStage.WAITING)
        check(generatedBirthFrame(1f, true, false).stage == GeneratedBirthStage.WAITING)
        for (progress in listOf(.18f, .50f, .56f, .84f, .88f, .90f, .98f)) {
            val a = generatedBirthFrame(progress - .00001f, true, true)
            val b = generatedBirthFrame(progress + .00001f, true, true)
            near(a.routeFraction, b.routeFraction, .001f); near(a.revealFraction, b.revealFraction, .001f)
            near(a.morphFraction, b.morphFraction, .001f); near(a.residualFraction, b.residualFraction, .001f)
            near(a.ribbonOpacity, b.ribbonOpacity, .001f); near(a.tipOpacity, b.tipOpacity, .001f)
        }
        rejects { GeneratedPoint(Float.NaN, .5f) }
        rejects { GeneratedPoint(.5f, Float.POSITIVE_INFINITY) }
        rejects { GeneratedPoint(-.001f, .5f) }
        rejects { GeneratedRoute(emptyList()) }
        rejects { GeneratedRoute(List(2) { GeneratedPoint(.5f, .5f) }) }
        rejects { GeneratedRoute(List(513) { GeneratedPoint(if (it % 2 == 0) 0f else 1f, .5f) }) }
        rejects { route.trace(Float.NaN) }
        rejects { generatedBirthFrame(1.1f, true, true) }
        rejects { generatedBirthFrame(1f, true, true, -.1f) }
        checkGeometry()
        checkMask()
        checkMetadata()
        if (args.isNotEmpty()) checkOriginal(File(args[0]))
        println("PASS: 4,004 readiness frames; no source pixels, derived morph, residual, or shadow before ready")
        println("PASS: 3 route shapes x 2 alpha-width shapes, 384 ordered samples, 7 turns, continuous morph and pen tip")
        println("PASS: portrait/landscape alpha geometries use paint brushes at least 1.2x actual turn spacing")
        println("PASS: brush-only reveal before .88, one source-alpha application, residual complete and ribbon/tip absent by .98")
        println("PASS: final/static transforms, proportional 64/128px fit, copied bounded alpha sample, rejected invalid inputs")
        println("Scope: CPU geometry/compositing contracts and original bytes; native Compose pixels and appeal require Android QA")
    }

    private fun checkGeometry() {
        val grids = listOf(
            GeneratedAlphaGrid(32, 32, ByteArray(1024) { i -> if (i % 32 in 3..28 && i / 32 in 2..29) 255.toByte() else 0 }),
            GeneratedAlphaGrid(32, 32, ByteArray(1024) { i ->
                val y = i / 32; val half = if (y < 16) 3 else 11
                if (y in 5..26 && abs(i % 32 - 16) <= half) 255.toByte() else 0
            }),
        )
        for (input in routes) for (grid in grids) {
            val geometry = GeneratedFormationGeometry(input, grid, 320, 320)
            check(geometry.routePoints.size == 384 && geometry.ribbonPoints.size == 384)
            near(geometry.routePoints.first().x, 36 + input.points.first().x * 248)
            near(geometry.routePoints.first().y, 24 + input.points.first().y * 248)
            near(geometry.routePoints.last().x, 36 + input.points.last().x * 248)
            near(geometry.routePoints.last().y, 24 + input.points.last().y * 248)
            for (index in geometry.routePoints.indices) {
                val sampled = input.trace(index / 383f).last()
                near(geometry.routePoints[index].x, 36 + sampled.x * 248, .0002f)
                near(geometry.routePoints[index].y, 24 + sampled.y * 248, .0002f)
            }
            check(geometry.stroke(0f, 1f) == geometry.routePoints)
            check(geometry.stroke(1f, 1f) == geometry.ribbonPoints)
            for (i in 1 until 384) check(geometry.ribbonPoints[i].y < geometry.ribbonPoints[i - 1].y)
            check(geometry.front.zipWithNext().count { it.first != it.second } == 14)
            // Fractional final points prevent one-sample jumps even at sample and phase boundaries.
            for (index in 1 until 383) for (morph in listOf(0f, .5f, 1f)) {
                val head = index / 383f
                val a = geometry.stroke(morph, head - .000001f).last()
                val b = geometry.stroke(morph, head + .000001f).last()
                check(distance(a, b) < .02f)
            }
            var previous: GeneratedFormationPoint? = null
            for (index in 0..2000) {
                val frame = generatedBirthFrame(index / 2000f, true, true, animate = false)
                val stroke = geometry.stroke(frame.morphFraction, frame.routeFraction)
                check(stroke.size in 1..384)
                check(stroke.all { it.x in 0f..320f && it.y in 0f..320f })
                val tip = stroke.last()
                previous?.let { check(distance(it, tip) < 7f) { "Pen tip discontinuity: ${distance(it, tip)}" } }
                previous = tip
            }
            rejects { geometry.stroke(Float.NaN, .5f) }
            rejects { geometry.stroke(.5f, 1.1f) }
        }
        val wide = GeneratedFormationGeometry(routes[0], grids[0], 320, 320)
        val narrow = GeneratedFormationGeometry(routes[0], grids[1], 320, 320)
        check(wide.ribbonPoints != narrow.ribbonPoints)
        check(wide.maximumY > narrow.maximumY && wide.minimumY < narrow.minimumY)
        // Upper rows in the second source really are narrower; no common oval/body template.
        val upperWide = wide.ribbonPoints.takeLast(160).maxOf { abs(it.x - 160f) }
        val upperNarrow = narrow.ribbonPoints.takeLast(160).maxOf { abs(it.x - 160f) }
        check(upperWide > upperNarrow * 2)
        for (grid in grids) {
            val portrait = GeneratedFormationGeometry(routes[0], grid, 320, 640)
            val landscape = GeneratedFormationGeometry(routes[0], grid, 640, 320)
            for (geometry in listOf(portrait, landscape)) {
                val turnSpacing = (geometry.maximumY - geometry.minimumY) * geometry.imageRect.height / 7f
                near(geometry.minimumBrushWidth, turnSpacing * 1.2f)
                for (progress in listOf(.501f, .55f, .60f, .80f, .90f)) {
                    val frame = generatedBirthFrame(progress, true, true)
                    check(maxOf(frame.brushWidth, geometry.minimumBrushWidth) >= turnSpacing * 1.199f)
                }
            }
            near(portrait.minimumBrushWidth, landscape.minimumBrushWidth * 2f)
        }
        val mutable = byteArrayOf(0, 255.toByte(), 0, 0)
        val copied = GeneratedAlphaGrid(2, 2, mutable)
        mutable[1] = 0
        check(copied.at(1, 0) == 255)
        rejects { GeneratedAlphaGrid(257, 1, ByteArray(257) { 1 }) }
        rejects { GeneratedAlphaGrid(2, 2, ByteArray(4)) }
        rejects { generatedAlphaGridFromArgb(10, 10, IntArray(2)) }
    }

    private fun checkMask() {
        // A pixel outside the drawn ribbon remains invisible until the explicitly scheduled final veil.
        for (i in 0..880) {
            val frame = generatedBirthFrame(i / 1000f, true, true)
            near(generatedMaskCoverage(0f, frame.revealFraction, frame.residualFraction), 0f)
        }
        var previous = 0f
        for (i in 880..1000) {
            val frame = generatedBirthFrame(i / 1000f, true, true)
            val coverage = generatedMaskCoverage(0f, frame.revealFraction, frame.residualFraction)
            check(coverage >= previous)
            previous = coverage
        }
        for (brush in listOf(0f, .2f, 1f)) {
            val completed = generatedBirthFrame(.98f, true, true)
            near(generatedMaskCoverage(brush, completed.revealFraction, completed.residualFraction), 1f)
            for (source in 0..255) {
                // SrcIn keeps source alpha, unlike drawing the same partial-alpha PNG twice.
                val result = source * generatedMaskCoverage(brush, completed.revealFraction, completed.residualFraction)
                near(result, source.toFloat())
            }
        }
        near(generatedMaskCoverage(.5f, .8f, .2f), .52f)
        rejects { generatedMaskCoverage(-.1f, 1f, 1f) }
    }

    private fun checkMetadata() {
        val hash = "0123456789abcdef".repeat(4)
        GeneratedImageMeta(hash, "image/png", 1312, 1199, 892805)
        GeneratedImageMeta(hash, "image/webp", 1024, 1024, 1)
        rejects { GeneratedImageMeta(hash.uppercase(), "image/png", 100, 100, 1) }
        rejects { GeneratedImageMeta(hash, "image/jpeg", 100, 100, 1) }
        rejects { GeneratedImageMeta(hash, "image/png", 0, 100, 1) }
        rejects { GeneratedImageMeta(hash, "image/png", 100, 4097, 1) }
        rejects { GeneratedImageMeta(hash, "image/png", 100, 100, 0) }
        rejects { GeneratedImageMeta(hash, "image/png", 100, 100, 20_971_521) }
        for ((w, h) in listOf(1312 to 1199, 1024 to 1024, 1024 to 1536, 1536 to 1024)) {
            val rect = generatedImageRect(w, h)
            near(rect.width / rect.height, w.toFloat() / h)
            for (pixels in listOf(64, 128, 320)) {
                val scale = pixels / 320f
                check(rect.left * scale >= 0 && rect.top * scale >= 0)
                check((rect.left + rect.width) * scale <= pixels)
                check((rect.top + rect.height) * scale <= pixels)
            }
        }
        rejects { generatedImageRect(-1, 1024) }
    }

    private fun checkOriginal(file: File) {
        val actualHash = MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString("") { "%02x".format(it) }
        check(actualHash == "528a216abbe0f39006090676b6a128bf7c309a08af36ac03c61ca8f68510e0dd")
        val image = ImageIO.read(file)
        check(image.width == 768 && image.height == 768 && image.colorModel.hasAlpha())
        val pixels = image.getRGB(0, 0, image.width, image.height, null, 0, image.width)
        check(pixels.count { it.ushr(24) == 0 } == 406_762)
        check(pixels.count { it.ushr(24) in 1..254 } == 18_303)
        val grid = generatedAlphaGridFromArgb(image.width, image.height, pixels)
        check(maxOf(grid.width, grid.height) <= 192)
        check(grid.maximum > 0)
        for (route in routes) {
            val geometry = GeneratedFormationGeometry(route, grid, image.width, image.height)
            check(geometry.ribbonPoints.size <= 512)
            val rect = geometry.imageRect
            check(geometry.ribbonPoints.all { it.x in rect.left..(rect.left + rect.width) && it.y in rect.top..(rect.top + rect.height) })
        }
        println("PASS: canonical PNG SHA, 768x768 native alpha, 406,762 transparent / 18,303 partial-alpha pixels")
        println("PASS: actual source alpha downsampled once to ${grid.width}x${grid.height}; route/target geometry bounded")
    }
}
