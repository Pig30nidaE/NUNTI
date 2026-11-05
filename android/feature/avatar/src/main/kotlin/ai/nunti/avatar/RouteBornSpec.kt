package ai.nunti.avatar

import java.util.Collections
import kotlin.math.abs
import kotlin.math.hypot

data class RouteBornPoint(val x: Float, val y: Float)
data class RouteBornFace(val cx: Float, val cy: Float, val scale: Float, val eyeSpacing: Float)

/** PC-authored geometry. No body registry, preset selection or inference from destination names.
 * Every list is copied and exposed read-only. Validation happens before any animation frame.
 */
class RouteBornSpec(
    val characterId: String,
    outline: List<RouteBornPoint>,
    route: List<RouteBornPoint>,
    palette: List<String>,
    val face: RouteBornFace,
) {
    val outline: List<RouteBornPoint> = Collections.unmodifiableList(ArrayList(outline))
    val route: List<RouteBornPoint> = Collections.unmodifiableList(ArrayList(route))
    val palette: List<String> = Collections.unmodifiableList(ArrayList(palette))

    init {
        require(characterId.matches(Regex("route-[0-9a-f]{24}"))) { "Invalid route-born characterId" }
        require(this.outline.size == 72 && this.route.size == 72) { "Expected 72 outline and 72 route points" }
        require(this.outline.all { it.valid(.05f, .95f) }) { "Outline coordinates must be finite and within .05.. .95" }
        require(this.route.all { it.valid(0f, 1f) }) { "Route coordinates must be finite and normalized" }
        require(this.palette.size == 3 && this.palette.all { it.matches(Regex("#[0-9A-Fa-f]{6}")) }) {
            "Expected three #RRGGBB palette colors"
        }
        require(face.cx.isFinite() && abs(face.cx - .5f) < .00001f &&
            face.cy.isFinite() && abs(face.cy - .43f) < .00001f &&
            face.scale.isFinite() && face.scale in .8f..1.1f &&
            face.eyeSpacing.isFinite() && face.eyeSpacing in .85f..1.15f) { "Invalid route-born face" }
        require(routeLength(this.route) > .0001) { "Route must have nonzero length" }
        require(abs(signedArea(this.outline)) > .0001) { "Outline must enclose an area" }
        require(simpleOutline(this.outline)) { "Outline must be a simple closed polygon" }
        require(faceEnclosed(this.outline, face)) { "Face ellipse must be inside the supplied outline" }
    }
}

private fun RouteBornPoint.valid(minimum: Float, maximum: Float) =
    x.isFinite() && y.isFinite() && x in minimum..maximum && y in minimum..maximum

internal const val ROUTE_BORN_FACE_RADIUS_X = .22f
internal const val ROUTE_BORN_FACE_RADIUS_Y = .145f

internal fun routeLength(points: List<RouteBornPoint>): Double = points.zipWithNext().sumOf { (a, b) ->
    hypot((b.x - a.x).toDouble(), (b.y - a.y).toDouble())
}

/** Lower silhouette intersection at a foot's x coordinate, rather than its rectangular bounding box. */
internal fun RouteBornSpec.lowerEdgeAt(x: Float): Float {
    val intersections = outline.indices.mapNotNull { index ->
        val a = outline[index]
        val b = outline[(index + 1) % outline.size]
        if (x < minOf(a.x, b.x) || x > maxOf(a.x, b.x)) null
        else if (abs(b.x - a.x) < 1e-8f) maxOf(a.y, b.y)
        else a.y + (b.y - a.y) * ((x - a.x) / (b.x - a.x))
    }
    return intersections.max()
}

private fun signedArea(points: List<RouteBornPoint>): Double = points.indices.sumOf { index ->
    val a = points[index]
    val b = points[(index + 1) % points.size]
    a.x.toDouble() * b.y - b.x.toDouble() * a.y
} / 2

private fun cross(a: RouteBornPoint, b: RouteBornPoint, p: RouteBornPoint): Double =
    (b.x - a.x).toDouble() * (p.y - a.y) - (b.y - a.y).toDouble() * (p.x - a.x)

private fun touchesSegment(a: RouteBornPoint, b: RouteBornPoint, p: RouteBornPoint) =
    abs(cross(a, b, p)) < 1e-8 && p.x >= minOf(a.x, b.x) - 1e-7 && p.x <= maxOf(a.x, b.x) + 1e-7 &&
        p.y >= minOf(a.y, b.y) - 1e-7 && p.y <= maxOf(a.y, b.y) + 1e-7

private fun intersects(a: RouteBornPoint, b: RouteBornPoint, c: RouteBornPoint, d: RouteBornPoint): Boolean {
    val ac = cross(a, b, c)
    val ad = cross(a, b, d)
    val ca = cross(c, d, a)
    val cb = cross(c, d, b)
    return ((ac > 0 && ad < 0 || ac < 0 && ad > 0) && (ca > 0 && cb < 0 || ca < 0 && cb > 0)) ||
        touchesSegment(a, b, c) || touchesSegment(a, b, d) || touchesSegment(c, d, a) || touchesSegment(c, d, b)
}

private fun simpleOutline(points: List<RouteBornPoint>): Boolean {
    for (index in points.indices) {
        val next = (index + 1) % points.size
        if (hypot((points[next].x - points[index].x).toDouble(), (points[next].y - points[index].y).toDouble()) < 1e-6) return false
        for (other in index + 1 until points.size) {
            val otherNext = (other + 1) % points.size
            if (index == otherNext || next == other) continue
            if (intersects(points[index], points[next], points[other], points[otherNext])) return false
        }
    }
    return true
}

private fun polygonContains(points: List<RouteBornPoint>, p: RouteBornPoint): Boolean {
    var inside = false
    var previous = points.last()
    for (current in points) {
        if ((current.y > p.y) != (previous.y > p.y) &&
            p.x < (previous.x - current.x) * (p.y - current.y) / (previous.y - current.y) + current.x) inside = !inside
        previous = current
    }
    return inside
}

/** Analytic containment: in ellipse-normalized coordinates, no polygon edge may enter the unit disk.
 * Center-inside plus nonintersecting boundary encloses the entire ellipse, including concave outlines.
 */
private fun faceEnclosed(points: List<RouteBornPoint>, face: RouteBornFace): Boolean {
    if (!polygonContains(points, RouteBornPoint(face.cx, face.cy))) return false
    val rx = ROUTE_BORN_FACE_RADIUS_X * face.scale
    val ry = ROUTE_BORN_FACE_RADIUS_Y * face.scale
    for (index in points.indices) {
        val a = points[index]
        val b = points[(index + 1) % points.size]
        val ax = (a.x - face.cx).toDouble() / rx
        val ay = (a.y - face.cy).toDouble() / ry
        val dx = (b.x - a.x).toDouble() / rx
        val dy = (b.y - a.y).toDouble() / ry
        val t = (-(ax * dx + ay * dy) / (dx * dx + dy * dy)).coerceIn(0.0, 1.0)
        val x = ax + t * dx
        val y = ay + t * dy
        if (x * x + y * y < 1.000001) return false
    }
    return true
}

internal data class RouteBornFrame(
    val contour: List<RouteBornPoint>,
    val tracedRoute: List<RouteBornPoint>,
    val closure: Float,
    val shellOpacity: Float,
    val pearlReveal: Float,
    val faceReveal: Float,
)

private fun smooth(value: Float): Float = value.coerceIn(0f, 1f).let { it * it * (3f - 2f * it) }
private fun lerp(a: RouteBornPoint, b: RouteBornPoint, t: Float) =
    RouteBornPoint(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)

/** Arc-length tracing preserves drawing order and the actual input segments. */
internal fun traceRoute(points: List<RouteBornPoint>, fraction: Float): List<RouteBornPoint> {
    require(fraction.isFinite() && fraction in 0f..1f)
    if (fraction == 1f) return points
    var remaining = routeLength(points) * fraction
    val result = mutableListOf(points.first())
    for ((a, b) in points.zipWithNext()) {
        val length = hypot((b.x - a.x).toDouble(), (b.y - a.y).toDouble())
        if (length == 0.0) continue
        if (remaining < length) {
            if (remaining > 0) result += lerp(a, b, (remaining / length).toFloat())
            break
        }
        result += b
        remaining -= length
    }
    return result
}

/** The host supplies progress. This function has no clock, RNG, animation state or preset geometry. */
internal fun RouteBornSpec.frame(progress: Float): RouteBornFrame {
    require(progress.isFinite() && progress in 0f..1f) { "progress must be finite and within 0..1" }
    val morph = smooth((progress - .35f) / .45f)
    return RouteBornFrame(
        contour = when {
            progress <= .35f -> route
            progress >= .8f -> outline
            else -> route.indices.map { lerp(route[it], outline[it], morph) }
        },
        tracedRoute = traceRoute(route, (progress / .35f).coerceAtMost(1f)),
        closure = morph,
        shellOpacity = smooth((morph - .28f) / .72f),
        pearlReveal = smooth((progress - .8f) / .2f),
        faceReveal = smooth((progress - .82f) / .18f),
    )
}
