package ai.nunti.avatar

import java.util.Collections
import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.hypot
import kotlin.math.sin

/** Normalized route coordinate, validated when the host parses its external input. */
data class GeneratedPoint(val x: Float, val y: Float) {
    init {
        require(x.isFinite() && y.isFinite() && x in 0f..1f && y in 0f..1f) {
            "Generated route points must be finite and normalized"
        }
    }
}

/** Describes an already verified source file. Hashing, decoding and actual alpha checks belong to the host. */
data class GeneratedImageMeta(
    val sha256: String,
    val mimeType: String,
    val width: Int,
    val height: Int,
    val byteSize: Long,
) {
    init {
        require(sha256.matches(Regex("[0-9a-f]{64}"))) { "Expected lowercase SHA-256" }
        require(mimeType == "image/png" || mimeType == "image/webp") { "Expected PNG or WebP" }
        require(width in 1..4096 && height in 1..4096) { "Image dimensions exceed the rendering boundary" }
        require(byteSize in 1..20_971_520) { "Image file must be at most 20 MiB" }
    }
}

/** No seed or shape presets. The original image and ordered route are the rendering inputs. */
internal class GeneratedRoute(points: List<GeneratedPoint>) {
    val points: List<GeneratedPoint> = Collections.unmodifiableList(ArrayList(points))
    val length: Double

    init {
        require(this.points.size in 2..512) { "Expected 2 to 512 route points" }
        length = generatedRouteLength(this.points)
        require(length > .0001) { "Route must have nonzero length" }
    }

    fun trace(fraction: Float): List<GeneratedPoint> {
        require(fraction.isFinite() && fraction in 0f..1f) { "Trace fraction must be within 0..1" }
        if (fraction == 1f) return points
        var remaining = length * fraction
        val result = mutableListOf(points.first())
        for ((a, b) in points.zipWithNext()) {
            val segment = hypot((b.x - a.x).toDouble(), (b.y - a.y).toDouble())
            if (segment == 0.0) continue
            if (remaining < segment) {
                if (remaining > 0) {
                    val t = (remaining / segment).toFloat()
                    result += GeneratedPoint(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
                }
                break
            }
            result += b
            remaining -= segment
        }
        return result
    }
}

internal fun generatedRouteLength(points: List<GeneratedPoint>): Double = points.zipWithNext().sumOf { (a, b) ->
    hypot((b.x - a.x).toDouble(), (b.y - a.y).toDouble())
}

internal enum class GeneratedBirthStage { ROUTE, LIGHT, REVEAL, READY, WAITING }

internal data class GeneratedBirthFrame(
    val stage: GeneratedBirthStage,
    val routeFraction: Float,
    val routeOpacity: Float,
    val revealFraction: Float,
    val glowOpacity: Float,
    val scaleX: Float,
    val scaleY: Float,
    val floatY: Float,
    val tilt: Float,
    val shadowScale: Float,
    val shadowOpacity: Float,
    val morphFraction: Float,
    val residualFraction: Float,
    val ribbonOpacity: Float,
    val brushWidth: Float,
    val tipOpacity: Float,
)

private fun generatedSmooth(value: Float): Float = value.coerceIn(0f, 1f).let { it * it * (3f - 2f * it) }

/** Display choreography only. Progress is never an estimate of network or model completion. */
internal fun generatedBirthFrame(
    progress: Float,
    ready: Boolean,
    imageAvailable: Boolean,
    idlePhase: Float = 0f,
    animate: Boolean = true,
): GeneratedBirthFrame {
    require(progress.isFinite() && progress in 0f..1f) { "Birth progress must be within 0..1" }
    require(idlePhase.isFinite() && idlePhase in 0f..1f) { "Idle phase must be within 0..1" }
    val prepared = ready && imageAvailable
    val reveal = if (prepared) generatedSmooth((progress - .50f) / .06f) else 0f
    val morph = if (prepared) generatedSmooth((progress - .18f) / .32f) else 0f
    val residual = if (prepared) generatedSmooth((progress - .88f) / .10f) else 0f
    val finished = ready && imageAvailable && progress == 1f
    val wave = if (finished && animate) sin(idlePhase * 2f * PI).toFloat() else 0f
    val sway = if (finished && animate) sin(idlePhase * 2f * PI).toFloat() else 0f
    val landingTime = ((progress - .90f) / .10f).coerceIn(0f, 1f)
    val landing = if (prepared && animate && !finished) {
        sin(landingTime * 2f * PI).toFloat() * exp(-landingTime * 4f) * (1f - landingTime)
    } else 0f
    val glow = when {
        finished -> .055f + wave * .015f
        progress <= .18f -> 0f
        progress < .50f -> morph * .10f
        reveal > 0f -> .10f * (1f - reveal) + .055f * reveal
        else -> if (prepared) .10f else 0f
    }
    return GeneratedBirthFrame(
        stage = when {
            finished -> GeneratedBirthStage.READY
            progress <= .18f -> GeneratedBirthStage.ROUTE
            progress < .50f -> GeneratedBirthStage.LIGHT
            !ready || !imageAvailable -> GeneratedBirthStage.WAITING
            else -> GeneratedBirthStage.REVEAL
        },
        routeFraction = generatedSmooth(progress / .90f),
        routeOpacity = 1f - morph,
        revealFraction = reveal,
        glowOpacity = glow,
        scaleX = 1f + wave * .012f + landing * .025f,
        scaleY = 1f - wave * .009f - landing * .035f,
        floatY = -wave * 3.2f - landing * .8f,
        tilt = sway * 1.2f + landing * .3f,
        shadowScale = 1f - wave * .035f,
        shadowOpacity = if (reveal > 0f) reveal * (.11f - wave * .015f) else 0f,
        morphFraction = morph,
        residualFraction = residual,
        ribbonOpacity = if (prepared) 1f - generatedSmooth((progress - .84f) / .14f) else 1f,
        brushWidth = 8f + 24f * generatedSmooth((progress - .50f) / .40f),
        tipOpacity = if (prepared) 1f - generatedSmooth((progress - .90f) / .08f) else 1f,
    )
}

internal data class GeneratedImageRect(val left: Float, val top: Float, val width: Float, val height: Float)

/** Letterbox once. Never crop a face, stretch a body, or alter the original image aspect ratio. */
internal fun generatedImageRect(width: Int, height: Int): GeneratedImageRect {
    require(width > 0 && height > 0)
    val factor = 264f / maxOf(width, height)
    val w = width * factor
    val h = height * factor
    return GeneratedImageRect((320f - w) / 2f, 148f - h / 2f, w, h)
}
