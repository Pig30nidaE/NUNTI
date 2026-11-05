package ai.nunti.avatar

import kotlin.math.min

const val JOURNEY_RENDERER_VERSION = "journey-keepsake-canvas-1"

/** Tokens and shape pairs from prototypes/journey_characters/registry.json. */
enum class JourneyBody(vararg shapes: String) {
    PEBBLE("wide_flat_oval", "asymmetric_low_dome"),
    DROPLET("round_teardrop", "tilted_water_drop"),
    BEAN("crescent_bean", "upright_kidney"),
    SPROUT("split_top_pear", "unequal_twin_lobe"),
    PILLOW("rounded_square", "tilted_cushion"),
    LANTERN("tall_egg", "tapered_oval"),
    CLOUD("low_three_lobe", "stacked_round_lobes"),
    ACORN("broad_top_oval", "round_bottom_dome");

    val shapeIds: Set<String> = shapes.toSet()
}

enum class JourneyMotif { ART, COASTAL_CITY, MOUNTAIN, FOREST, LAKESIDE, CITY, UNSPECIFIED }
enum class JourneyPattern { COASTAL, MOUNTAIN, URBAN, TREE_LINED, CURVING, HIGHWAY, MIXED, STRAIGHT, UNSPECIFIED }
enum class JourneyPurpose { REST, CAMPING, EXHIBITION, COMMUTE, VISIT, ERRAND, UNSPECIFIED }

/** Validated local visual recipe. It asserts no facts about roads or driving quality.
 * Palette input is copied so a caller cannot mutate an already validated recipe.
 */
class JourneyVisualSpec(
    val characterId: String,
    val seed: String,
    val bodyFamily: JourneyBody,
    val shapeId: String,
    palette: List<String>,
    val widthMultiplier: Float,
    val heightMultiplier: Float,
    val motif: JourneyMotif,
    val routePattern: JourneyPattern,
    val purpose: JourneyPurpose,
) {
    val palette: List<String> = palette.toList()

    init {
        require(characterId.matches(Regex("[A-Za-z0-9][A-Za-z0-9._:-]{0,127}"))) { "Invalid characterId" }
        require(seed.matches(Regex("[0-9a-f]{16}"))) { "seed must be 16 lowercase hexadecimal characters" }
        require(shapeId in bodyFamily.shapeIds) { "shapeId does not belong to bodyFamily" }
        require(this.palette.size == 3 && this.palette.all { it.matches(Regex("#[0-9A-Fa-f]{6}")) }) {
            "palette must contain three #RRGGBB colors"
        }
        require(widthMultiplier.isFinite() && widthMultiplier in 0.75f..1.25f) { "Invalid widthMultiplier" }
        require(heightMultiplier.isFinite() && heightMultiplier in 0.75f..1.25f) { "Invalid heightMultiplier" }
    }

    /** Independent fixed seed channels. No clock, mutable RNG, journey history, or draw order. */
    internal fun variation(channel: Int): Float {
        require(channel >= 0)
        val start = (channel % 4) * 4
        return seed.substring(start, start + 4).toInt(16) / 65535f
    }
}

internal data class JourneyPoint(val x: Float, val y: Float)
internal data class JourneyCurve(val control1: JourneyPoint, val control2: JourneyPoint, val end: JourneyPoint)
internal data class JourneyOutline(val start: JourneyPoint, val curves: List<JourneyCurve>) {
    /** CPU geometry inspection uses the same cubic outline as Compose. */
    fun sample(stepsPerCurve: Int = 24): List<JourneyPoint> {
        require(stepsPerCurve in 2..256)
        val points = mutableListOf(start)
        var previous = start
        curves.forEach { curve ->
            for (index in 1..stepsPerCurve) {
                val t = index.toFloat() / stepsPerCurve
                val u = 1f - t
                points += JourneyPoint(
                    u * u * u * previous.x + 3 * u * u * t * curve.control1.x + 3 * u * t * t * curve.control2.x + t * t * t * curve.end.x,
                    u * u * u * previous.y + 3 * u * u * t * curve.control1.y + 3 * u * t * t * curve.control2.y + t * t * t * curve.end.y,
                )
            }
            previous = curve.end
        }
        return points
    }
}

internal data class JourneyRect(val left: Float, val top: Float, val width: Float, val height: Float) {
    val right get() = left + width
    val bottom get() = top + height
    val centerX get() = left + width / 2
    val centerY get() = top + height / 2
    fun point(x: Float, y: Float) = JourneyPoint(left + width * x, top + height * y)
}

internal data class JourneyGeometry(val body: JourneyRect, val outline: JourneyOutline, val face: JourneyRect)

/** A 320 square contains the shell, feet, highlights and contact shadow, including extreme ratios. */
internal fun JourneyVisualSpec.geometry(): JourneyGeometry {
    val dimensions = when (bodyFamily) {
        JourneyBody.PEBBLE -> 244f to 187f
        JourneyBody.DROPLET -> 208f to 240f
        JourneyBody.BEAN -> 218f to 226f
        JourneyBody.SPROUT -> 218f to 246f
        JourneyBody.PILLOW -> 229f to 211f
        JourneyBody.LANTERN -> 191f to 246f
        JourneyBody.CLOUD -> 252f to 195f
        JourneyBody.ACORN -> 226f to 223f
    }
    val requestedWidth = dimensions.first * widthMultiplier
    val requestedHeight = dimensions.second * heightMultiplier
    val fit = min(1f, min(260f / requestedWidth, 247f / requestedHeight))
    val width = requestedWidth * fit
    val height = requestedHeight * fit
    val body = JourneyRect(160f - width / 2, 278f - height, width, height)
    // The bean's concave waist needs a slightly smaller, right-shifted face patch.
    val faceWidth = if (bodyFamily == JourneyBody.BEAN) 0.55f else 0.62f
    val faceX = if (bodyFamily == JourneyBody.BEAN) 0.265f else 0.19f
    val faceY = when (bodyFamily) {
        JourneyBody.DROPLET, JourneyBody.SPROUT, JourneyBody.LANTERN -> 0.32f
        else -> 0.24f
    }
    return JourneyGeometry(body, journeyOutline(shapeId), JourneyRect(
        body.left + body.width * faceX, body.top + body.height * faceY,
        body.width * faceWidth, body.height * 0.38f,
    ))
}

private fun c(x1: Float, y1: Float, x2: Float, y2: Float, x: Float, y: Float) =
    JourneyCurve(JourneyPoint(x1, y1), JourneyPoint(x2, y2), JourneyPoint(x, y))
private fun outline(x: Float, y: Float, vararg curves: JourneyCurve) = JourneyOutline(JourneyPoint(x, y), curves.toList())

/** Authored closed contours, not a generic oval with sixteen labels. Coordinates are shell-local. */
internal fun journeyOutline(shapeId: String): JourneyOutline = when (shapeId) {
    "wide_flat_oval" -> outline(.50f, .02f,
        c(.79f, .01f, .99f, .24f, .99f, .53f), c(.99f, .86f, .80f, .98f, .48f, .98f),
        c(.14f, .98f, .01f, .83f, .01f, .54f), c(.01f, .23f, .22f, .02f, .50f, .02f))
    "asymmetric_low_dome" -> outline(.43f, .03f,
        c(.70f, .00f, .93f, .20f, .98f, .49f), c(1f, .75f, .88f, .94f, .65f, .97f),
        c(.44f, 1f, .09f, .99f, .03f, .79f), c(-.02f, .60f, .05f, .36f, .18f, .19f),
        c(.25f, .10f, .34f, .05f, .43f, .03f))
    "round_teardrop" -> outline(.50f, .01f,
        c(.58f, .01f, .61f, .17f, .77f, .34f), c(.93f, .50f, 1f, .67f, .94f, .82f),
        c(.87f, 1f, .13f, 1f, .06f, .82f), c(0f, .65f, .09f, .47f, .25f, .31f),
        c(.40f, .16f, .42f, .01f, .50f, .01f))
    "tilted_water_drop" -> outline(.70f, .015f,
        c(.79f, -.01f, .78f, .15f, .84f, .34f), c(.89f, .51f, 1f, .66f, .94f, .82f),
        c(.88f, .99f, .21f, 1f, .08f, .86f), c(-.03f, .73f, .04f, .48f, .22f, .31f),
        c(.40f, .15f, .55f, .04f, .70f, .015f))
    "crescent_bean" -> outline(.50f, .02f,
        c(.82f, -.01f, .98f, .23f, .98f, .55f), c(.99f, .84f, .77f, .99f, .49f, .98f),
        c(.16f, .97f, .02f, .80f, .05f, .65f), c(.08f, .53f, .24f, .56f, .23f, .43f),
        c(.22f, .25f, .25f, .05f, .50f, .02f))
    "upright_kidney" -> outline(.48f, .02f,
        c(.79f, -.01f, .94f, .15f, .98f, .43f), c(1f, .69f, .91f, .95f, .64f, .98f),
        c(.37f, 1f, .10f, .92f, .06f, .74f), c(.01f, .53f, .24f, .56f, .21f, .36f),
        c(.19f, .16f, .26f, .04f, .48f, .02f))
    "split_top_pear" -> outline(.49f, .17f,
        c(.30f, -.10f, .10f, -.01f, .23f, .25f), c(.12f, .43f, .02f, .62f, .07f, .80f),
        c(.12f, 1f, .87f, 1f, .94f, .80f), c(1f, .60f, .84f, .39f, .76f, .26f),
        c(.98f, .00f, .73f, -.10f, .49f, .17f))
    "unequal_twin_lobe" -> outline(.48f, .17f,
        c(.31f, -.02f, .10f, .03f, .22f, .28f), c(.09f, .43f, .02f, .66f, .08f, .83f),
        c(.16f, 1f, .85f, 1f, .93f, .82f), c(1f, .65f, .87f, .41f, .74f, .27f),
        c(.98f, -.015f, .70f, -.04f, .48f, .17f))
    "rounded_square" -> outline(.27f, .035f,
        c(.40f, .01f, .68f, .01f, .80f, .06f), c(.98f, .11f, .99f, .26f, .98f, .48f),
        c(1f, .75f, .96f, .94f, .78f, .97f), c(.59f, 1f, .24f, 1f, .11f, .91f),
        c(-.01f, .81f, .01f, .55f, .02f, .31f), c(.03f, .12f, .09f, .07f, .27f, .035f))
    "tilted_cushion" -> outline(.28f, .03f,
        c(.48f, .00f, .75f, .10f, .90f, .19f), c(1f, .27f, .98f, .50f, .91f, .77f),
        c(.86f, .98f, .67f, 1f, .42f, .94f), c(.18f, .90f, .00f, .80f, .025f, .57f),
        c(.04f, .32f, .08f, .07f, .28f, .03f))
    "tall_egg" -> outline(.50f, .02f,
        c(.73f, .01f, .88f, .28f, .95f, .52f), c(1f, .73f, .92f, .97f, .55f, .98f),
        c(.16f, 1f, -.01f, .83f, .05f, .59f), c(.10f, .34f, .25f, .02f, .50f, .02f))
    "tapered_oval" -> outline(.51f, .02f,
        c(.72f, .03f, .78f, .26f, .85f, .43f), c(.94f, .63f, 1f, .83f, .81f, .93f),
        c(.65f, 1f, .30f, 1f, .15f, .93f), c(-.03f, .84f, .07f, .58f, .16f, .37f),
        c(.23f, .18f, .30f, .01f, .51f, .02f))
    "low_three_lobe" -> outline(.30f, .16f,
        c(.33f, -.03f, .65f, -.03f, .70f, .18f), c(.91f, .05f, 1f, .25f, .97f, .52f),
        c(1f, .77f, .87f, .96f, .68f, .97f), c(.44f, 1f, .11f, .98f, .04f, .77f),
        c(-.05f, .49f, .01f, .13f, .30f, .16f))
    "stacked_round_lobes" -> outline(.41f, .09f,
        c(.63f, -.07f, .83f, .04f, .82f, .28f), c(1.04f, .34f, 1f, .61f, .89f, .76f),
        c(.95f, .99f, .48f, 1f, .29f, .96f), c(.05f, .93f, -.01f, .76f, .05f, .59f),
        c(-.01f, .36f, .14f, .21f, .30f, .26f), c(.26f, .16f, .32f, .10f, .41f, .09f))
    "broad_top_oval" -> outline(.50f, .025f,
        c(.78f, .02f, 1f, .18f, .98f, .43f), c(.96f, .68f, .82f, .96f, .55f, .98f),
        c(.29f, 1f, .08f, .80f, .03f, .51f), c(-.02f, .25f, .19f, .025f, .50f, .025f))
    "round_bottom_dome" -> outline(.43f, .025f,
        c(.73f, .00f, .93f, .10f, .95f, .31f), c(.95f, .51f, .99f, .72f, .82f, .89f),
        c(.66f, 1f, .33f, 1f, .17f, .88f), c(.02f, .75f, .03f, .47f, .06f, .29f),
        c(.10f, .11f, .22f, .04f, .43f, .025f))
    else -> error("Unknown journey shapeId: $shapeId")
}
