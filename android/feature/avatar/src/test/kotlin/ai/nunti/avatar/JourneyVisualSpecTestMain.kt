package ai.nunti.avatar

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

/** CPU checks for the public recipe boundary and the actual curves consumed by Compose. */
object JourneyVisualSpecTestMain {
    private fun spec(body: JourneyBody = JourneyBody.DROPLET, shape: String = body.shapeIds.first(),
        seed: String = "0123456789abcdef", palette: List<String> = listOf("#93D6CF", "#F4C6A0", "#FFF0D4"),
        width: Float = 1f, height: Float = 1f) = JourneyVisualSpec(
        "nunti-cpu-check", seed, body, shape, palette, width, height,
        JourneyMotif.COASTAL_CITY, JourneyPattern.COASTAL, JourneyPurpose.REST,
    )

    private fun rejects(block: () -> Unit) {
        check(runCatching(block).exceptionOrNull() is IllegalArgumentException)
    }

    private fun contains(polygon: List<JourneyPoint>, point: JourneyPoint): Boolean {
        var inside = false
        var j = polygon.lastIndex
        for (i in polygon.indices) {
            val a = polygon[i]
            val b = polygon[j]
            if ((a.y > point.y) != (b.y > point.y) &&
                point.x < (b.x - a.x) * (point.y - a.y) / (b.y - a.y) + a.x) inside = !inside
            j = i
        }
        return inside
    }

    @JvmStatic
    fun main(args: Array<String>) {
        check(JourneyBody.entries.size == 8)
        check(JourneyBody.entries.sumOf { it.shapeIds.size } == 16)
        val signatures = mutableSetOf<List<JourneyPoint>>()
        var checkedLayouts = 0
        JourneyBody.entries.forEach { body ->
            body.shapeIds.forEach { shape ->
                val outline = journeyOutline(shape)
                check(outline.curves.size in 4..8)
                check(outline.curves.last().end == outline.start) { "Unclosed $shape" }
                val polygon = outline.sample(64)
                check(signatures.add(polygon)) { "Repeated silhouette $shape" }
                check(polygon.all { it.x.isFinite() && it.y.isFinite() && it.x in -.005f..1.005f && it.y in -.005f..1.005f }) {
                    "Contour escapes normalized shell: $shape ${polygon.minOf { it.x }}..${polygon.maxOf { it.x }}, ${polygon.minOf { it.y }}..${polygon.maxOf { it.y }}"
                }
                for (width in listOf(.75f, .96f, 1f, 1.08f, 1.25f)) {
                    for (height in listOf(.75f, .94f, 1f, 1.06f, 1.25f)) {
                        val recipe = spec(body, shape, width = width, height = height)
                        val g = recipe.geometry()
                        check(g.body.left >= 30f && g.body.right <= 290f && g.body.top >= 30.9f && g.body.bottom == 278f)
                        // Opaque face stays inside the shell, including non-convex bean/cloud bodies.
                        repeat(48) { index ->
                            val angle = index * 2 * PI / 48
                            val point = JourneyPoint(
                                (g.face.centerX + cos(angle).toFloat() * g.face.width / 2 - g.body.left) / g.body.width,
                                (g.face.centerY + sin(angle).toFloat() * g.face.height / 2 - g.body.top) / g.body.height,
                            )
                            check(contains(polygon, point)) { "Face leaves $shape at $point" }
                        }
                        check(g == recipe.geometry())
                        checkedLayouts++
                    }
                }
            }
        }
        rejects { spec(seed = "0123456789ABCDEf") }
        rejects { spec(seed = "0123") }
        rejects { spec(shape = "wide_flat_oval") }
        rejects { spec(width = Float.NaN) }
        rejects { spec(height = Float.POSITIVE_INFINITY) }
        rejects { spec(width = .74f) }
        rejects { spec(height = 1.26f) }
        rejects { spec(palette = listOf("#93D6CF", "#FFF0D4")) }
        rejects { spec(palette = listOf("#93D6CF00", "#F4C6A0", "#FFF0D4")) }
        rejects { spec(palette = listOf("#GGGGGG", "#F4C6A0", "#FFF0D4")) }
        rejects { JourneyVisualSpec("bad id", "0123456789abcdef", JourneyBody.DROPLET, "round_teardrop",
            listOf("#93D6CF", "#F4C6A0", "#FFF0D4"), 1f, 1f, JourneyMotif.UNSPECIFIED, JourneyPattern.UNSPECIFIED, JourneyPurpose.UNSPECIFIED) }
        val inputPalette = mutableListOf("#93D6CF", "#F4C6A0", "#FFF0D4")
        val recipe = spec(palette = inputPalette)
        inputPalette[0] = "invalid"
        check(recipe.palette[0] == "#93D6CF")
        check((0..15).all { recipe.variation(it) in 0f..1f })
        check(recipe.variation(0) == spec().variation(0))
        check(abs(recipe.variation(0) - spec(seed = "fedcba9876543210").variation(0)) > .1f)
        val wide = spec(width = 1.08f, height = .94f).geometry().body
        val tall = spec(width = .96f, height = 1.06f).geometry().body
        check(wide.width / wide.height > tall.width / tall.height)
        check(JOURNEY_RENDERER_VERSION == "journey-keepsake-canvas-1")
        println("PASS: 8 body families, 16 distinct closed silhouettes, $checkedLayouts bounded layouts and enclosed face ellipses")
        println("PASS: malformed recipe rejection, copied palette, stable seed channels, actual proportion geometry")
        println("Scope: CPU recipe/geometry only; Compose appearance, semantics and Android runtime require app QA")
    }
}
