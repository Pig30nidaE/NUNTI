package ai.nunti.avatar

import java.util.Collections
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.sin

internal const val GENERATED_FORMATION_POINTS = 384
internal const val GENERATED_ALPHA_EDGE = 192
internal const val GENERATED_RIBBON_TURNS = 7

/** A bounded, copied alpha sample. Contains no bitmap, painted face, or mutable public buffer. */
internal class GeneratedAlphaGrid(val width: Int, val height: Int, alpha: ByteArray) {
    private val values = alpha.copyOf()
    val maximum: Int
    init {
        require(width in 1..256 && height in 1..256 && values.size == width * height)
        maximum = values.maxOf { it.toInt() and 255 }
        require(maximum > 0) { "Prepared image has no visible sampled alpha" }
    }
    fun at(x: Int, y: Int): Int = values[y * width + x].toInt() and 255
}

/** Readback happens once in the Compose adapter. Max pooling preserves thin source features. */
internal fun generatedAlphaGridFromArgb(width: Int, height: Int, pixels: IntArray): GeneratedAlphaGrid {
    require(width in 1..4096 && height in 1..4096 && pixels.size == width * height)
    val factor = minOf(1f, GENERATED_ALPHA_EDGE.toFloat() / maxOf(width, height))
    val w = maxOf(1, (width * factor).toInt())
    val h = maxOf(1, (height * factor).toInt())
    val alpha = ByteArray(w * h)
    for (y in 0 until h) for (x in 0 until w) {
        val left = x * width / w
        val right = (x + 1) * width / w
        val top = y * height / h
        val bottom = (y + 1) * height / h
        var maximum = 0
        for (sy in top until bottom) for (sx in left until right) {
            maximum = maxOf(maximum, pixels[sy * width + sx].ushr(24))
        }
        alpha[y * w + x] = maximum.toByte()
    }
    return GeneratedAlphaGrid(w, h, alpha)
}

/** Renderer coordinates in a fixed 320-square stage. Route and image use this same coordinate space. */
internal data class GeneratedFormationPoint(val x: Float, val y: Float) {
    init { require(x.isFinite() && y.isFinite()) }
    fun mix(other: GeneratedFormationPoint, fraction: Float): GeneratedFormationPoint = when (fraction) {
        0f -> this
        1f -> other
        else -> GeneratedFormationPoint(x + (other.x - x) * fraction, y + (other.y - y) * fraction)
    }
}

internal data class GeneratedRowSpan(val left: Float, val right: Float) {
    init { require(left.isFinite() && right.isFinite() && left <= right) }
}

/** The same ordered N samples become a continuous, seven-turn row-width-derived ribbon.
 * No silhouette registry, radial body template, image recoloring, or separate face exists here.
 */
internal class GeneratedFormationGeometry(
    route: GeneratedRoute,
    alpha: GeneratedAlphaGrid,
    imageWidth: Int,
    imageHeight: Int,
) {
    val routePoints: List<GeneratedFormationPoint>
    val ribbonPoints: List<GeneratedFormationPoint>
    val front: List<Boolean>
    val imageRect = generatedImageRect(imageWidth, imageHeight)
    val minimumY: Float
    val maximumY: Float
    val minimumBrushWidth: Float
    private val spans: List<GeneratedRowSpan>

    init {
        val threshold = minOf(32, maxOf(1, alpha.maximum / 2))
        val raw = (0 until alpha.height).map { y ->
            val xs = (0 until alpha.width).filter { x -> alpha.at(x, y) >= threshold }
            if (xs.isEmpty()) null else GeneratedRowSpan(
                (xs.first() + .5f) / alpha.width, (xs.last() + .5f) / alpha.width,
            )
        }
        val first = raw.indexOfFirst { it != null }
        val last = raw.indexOfLast { it != null }
        require(first >= 0 && last >= first)
        minimumY = (first + .5f) / alpha.height
        maximumY = (last + .5f) / alpha.height
        // Overlap neighboring turns while painting, rather than cutting the source into horizontal bands.
        minimumBrushWidth = (maximumY - minimumY) * imageRect.height / GENERATED_RIBBON_TURNS * 1.2f
        // Empty rows between separate features interpolate neighboring observed spans.
        // This avoids inventing a full-width rectangle in an alpha gap.
        spans = raw.indices.map { y ->
            raw[y] ?: run {
                val before = (y downTo 0).firstOrNull { raw[it] != null }
                val after = (y until raw.size).firstOrNull { raw[it] != null }
                when {
                    before == null -> raw[after!!]!!
                    after == null -> raw[before]!!
                    else -> {
                        val t = (y - before).toFloat() / (after - before)
                        val a = raw[before]!!; val b = raw[after]!!
                        GeneratedRowSpan(a.left + (b.left - a.left) * t, a.right + (b.right - a.right) * t)
                    }
                }
            }
        }
        routePoints = immutableGeneratedPoints(resampleGeneratedRoute(route))
        ribbonPoints = immutableGeneratedPoints(List(GENERATED_FORMATION_POINTS) { index ->
            val t = index.toFloat() / (GENERATED_FORMATION_POINTS - 1)
            val y = maximumY + (minimumY - maximumY) * t
            val row = rowSpan(y, alpha.height)
            val u = (row.left + row.right) / 2f + sin(t * 2f * PI * GENERATED_RIBBON_TURNS).toFloat() * (row.right - row.left) * .49f
            GeneratedFormationPoint(imageRect.left + u * imageRect.width, imageRect.top + y * imageRect.height)
        })
        front = Collections.unmodifiableList(List(GENERATED_FORMATION_POINTS) { index ->
            cos(index.toDouble() / (GENERATED_FORMATION_POINTS - 1) * 2 * PI * GENERATED_RIBBON_TURNS) >= 0
        })
    }

    private fun rowSpan(y: Float, height: Int): GeneratedRowSpan {
        val position = (y * height - .5f).coerceIn(0f, (height - 1).toFloat())
        val lo = floor(position).toInt()
        val hi = minOf(lo + 1, height - 1)
        val t = position - lo
        val a = spans[lo]; val b = spans[hi]
        return GeneratedRowSpan(a.left + (b.left - a.left) * t, a.right + (b.right - a.right) * t)
    }

    fun stroke(morph: Float, head: Float): List<GeneratedFormationPoint> {
        require(morph.isFinite() && morph in 0f..1f && head.isFinite() && head in 0f..1f)
        val position = head * (routePoints.size - 1)
        val end = floor(position).toInt()
        val output = (0..end).mapTo(ArrayList()) { index -> routePoints[index].mix(ribbonPoints[index], morph) }
        if (end < routePoints.lastIndex && position > end) {
            output += routePoints[end].mix(ribbonPoints[end], morph)
                .mix(routePoints[end + 1].mix(ribbonPoints[end + 1], morph), position - end)
        }
        return output
    }
}

private fun immutableGeneratedPoints(points: List<GeneratedFormationPoint>): List<GeneratedFormationPoint> =
    Collections.unmodifiableList(ArrayList(points))

private fun resampleGeneratedRoute(route: GeneratedRoute): List<GeneratedFormationPoint> {
    val distances = DoubleArray(route.points.size)
    for (i in 1 until distances.size) distances[i] = distances[i - 1] + hypot(
        (route.points[i].x - route.points[i - 1].x).toDouble(),
        (route.points[i].y - route.points[i - 1].y).toDouble(),
    )
    var segment = 1
    return List(GENERATED_FORMATION_POINTS) { index ->
        val target = route.length * index / (GENERATED_FORMATION_POINTS - 1)
        while (segment < distances.lastIndex && distances[segment] < target) segment++
        val length = distances[segment] - distances[segment - 1]
        val t = if (length > 0) ((target - distances[segment - 1]) / length).toFloat() else 0f
        val a = route.points[segment - 1]; val b = route.points[segment]
        GeneratedFormationPoint(36f + (a.x + (b.x - a.x) * t) * 248f, 24f + (a.y + (b.y - a.y) * t) * 248f)
    }
}

/** Union of the ribbon brush mask with a residual veil, before the original is drawn ONCE via SrcIn. */
internal fun generatedMaskCoverage(brushCoverage: Float, brushOpacity: Float, residual: Float): Float {
    require(listOf(brushCoverage, brushOpacity, residual).all { it.isFinite() && it in 0f..1f })
    return residual + brushCoverage * brushOpacity * (1f - residual)
}
