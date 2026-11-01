package ai.nunti.avatar

import ai.nunti.emotion.Emotion

enum class TripPhase { PRE_DRIVE, DRIVING, POST_DRIVE }
data class PlatformDisplayPolicy(
    val observedAtMillis: Long,
    val restrictionsKnown: Boolean,
    val platformAllowsAvatarScreen: Boolean,
    val requiresDistractionOptimization: Boolean,
    val hostIsApprovedForDistractionOptimization: Boolean = false,
    val permitsStaticAvatarWhileDriving: Boolean = false,
    val parkedConfirmed: Boolean = false,
    val foreground: Boolean = true,
)
data class RenderState(val visible: Boolean, val emotion: Emotion, val animationsAllowed: Boolean,
    val interactionsAllowed: Boolean, val reason: String)
object RenderPolicy {
    fun resolve(phase: TripPhase, internalEmotion: Emotion, policy: PlatformDisplayPolicy?, now: Long): RenderState {
        fun hidden(reason: String) = RenderState(false, Emotion.NEUTRAL, false, false, reason)
        if (policy == null || !policy.restrictionsKnown || now < policy.observedAtMillis || now - policy.observedAtMillis > 5000) return hidden("PLATFORM_POLICY_UNKNOWN_OR_STALE")
        if (!policy.foreground || !policy.platformAllowsAvatarScreen) return hidden("PLATFORM_BLOCKED")
        if (policy.requiresDistractionOptimization && !policy.hostIsApprovedForDistractionOptimization) return hidden("DISTRACTION_OPTIMIZATION_NOT_APPROVED")
        if (phase == TripPhase.DRIVING || !policy.parkedConfirmed || policy.requiresDistractionOptimization) {
            if (!policy.permitsStaticAvatarWhileDriving || !policy.hostIsApprovedForDistractionOptimization) return hidden("DRIVING_DISPLAY_NOT_APPROVED")
            // Freeze expression, pose, explanatory text and semantics during the trip.
            return RenderState(true, Emotion.NEUTRAL, false, false, "APPROVED_STATIC_ONLY")
        }
        return RenderState(true, internalEmotion, false, true, "PARKED_STATIC_MVP")
    }
}

enum class PrimitiveKind { ELLIPSE, RECT, LINE, POLYLINE }
data class Point(val x: Double, val y: Double)
data class Primitive(val kind: PrimitiveKind, val bounds: Bounds, val color: String,
    val points: List<Point> = emptyList(), val strokeWidth: Double = 0.0, val layer: String)
data class CharacterScene(val primitives: List<Primitive>, val accessibilityLabel: String, val warnings: List<String>)
interface CharacterAssetProvider {
    val manifest: AssetManifest
    fun renderIdentity(emotion: Emotion): List<Primitive>
    fun renderPart(asset: PartAsset, palette: Palette): List<Primitive>
}

/** Replace this provider with authored vector assets without touching the generation engine. */
class CanvasPartProvider(override val manifest: AssetManifest) : CharacterAssetProvider {
    override fun renderIdentity(emotion: Emotion) = PlaceholderIdentity.render(manifest.identity, emotion)
    override fun renderPart(asset: PartAsset, palette: Palette): List<Primitive> {
        val b = asset.bounds
        val layer = asset.id
        fun rect(bounds: Bounds, color: String) = Primitive(PrimitiveKind.RECT, bounds, color, layer = layer)
        fun line(points: List<Point>, color: String, width: Double = 3.0) = Primitive(PrimitiveKind.POLYLINE, b, color, points, width, layer)
        return when (asset.shape) {
            "vest" -> listOf(rect(b, palette.fill), line(listOf(Point(b.x + b.width / 2, b.y), Point(b.x + b.width / 2, b.y + b.height)), palette.ink),
                rect(Bounds(b.x + 13, b.y + 23, 22.0, 16.0), palette.ink), rect(Bounds(b.x + b.width - 35, b.y + 23, 22.0, 16.0), palette.ink))
            "scarf" -> listOf(rect(b, palette.fill), line(listOf(Point(b.x + 4, b.y + 12), Point(b.x + b.width - 4, b.y + 12)), palette.ink))
            "bag" -> listOf(rect(b, palette.ink), rect(Bounds(b.x + 5, b.y + 9, b.width - 10, b.height - 14), palette.fill),
                line(listOf(Point(b.x + 12, b.y + 12), Point(b.x + b.width - 12, b.y + 12)), palette.ink))
            "ticket" -> listOf(rect(b, "#FFF8E9"), line(listOf(Point(b.x + 7, b.y + 11), Point(b.x + b.width - 7, b.y + 11)), palette.ink),
                line(listOf(Point(b.x + 7, b.y + 22), Point(b.x + b.width - 7, b.y + 22)), palette.ink))
            "bottle" -> listOf(rect(b, palette.fill), rect(Bounds(b.x + 5, b.y, b.width - 10, 8.0), palette.ink))
            "wave" -> listOf(line((0..12).map { Point(b.x + it * b.width / 12, b.y + b.height / 2 + kotlin.math.sin(it * Math.PI / 3) * b.height / 3) }, palette.ink))
            "mountain" -> listOf(line(listOf(Point(b.x, b.y + b.height), Point(b.x + b.width / 3, b.y), Point(b.x + b.width / 2, b.y + b.height / 2), Point(b.x + b.width * .7, b.y + 2), Point(b.x + b.width, b.y + b.height)), palette.ink))
            else -> emptyList()
        }
    }
}

private object PlaceholderIdentity {
    fun render(identity: IdentityLayer, e: Emotion): List<Primitive> {
        val shapes = mutableListOf<Primitive>()
        val ink = "#283B3C"
        fun ellipse(x: Double, y: Double, w: Double, h: Double, color: String, layer: String) {
            shapes += Primitive(PrimitiveKind.ELLIPSE, Bounds(x, y, w, h), color, layer = layer)
        }
        fun stroke(points: List<Point>, width: Double, layer: String, color: String = ink) {
            shapes += Primitive(PrimitiveKind.POLYLINE, Bounds(0.0, 0.0, 320.0, 320.0), color, points, width, layer)
        }
        // Fixed identity geometry: body, face, signature and face anchors never vary by route.
        ellipse(86.0, 77.0, 148.0, 182.0, identity.coreColor, "body")
        ellipse(63.0, 181.0, 43.0, 40.0, identity.coreColor, "body")
        ellipse(214.0, 181.0, 43.0, 40.0, identity.coreColor, "body")
        ellipse(102.0, 240.0, 46.0, 24.0, ink, "body")
        ellipse(174.0, 240.0, 46.0, 24.0, ink, "body")
        ellipse(101.0, 99.0, 118.0, 83.0, "#FFF8E9", "face")
        ellipse(151.0, 68.0, 18.0, 26.0, "#C4804C", "signature")
        if (e == Emotion.RELIEVED) {
            ellipse(115.0, 149.0, 13.0, 7.0, "#E5B29D", "face-expression")
            ellipse(192.0, 149.0, 13.0, 7.0, "#E5B29D", "face-expression")
        }
        for (x in listOf(131.0, 185.0)) {
            when (e) {
                Emotion.RELAXED, Emotion.RELIEVED, Emotion.JOYFUL -> stroke(listOf(Point(x - 7, 139.0), Point(x, 134.0), Point(x + 7, 139.0)), 4.0, "eyes")
                Emotion.STARTLED -> { ellipse(x - 9, 127.0, 18.0, 22.0, ink, "eyes"); ellipse(x - 3, 130.0, 5.0, 7.0, "#FFFFFF", "eyes") }
                else -> ellipse(x - 5, 131.0, 10.0, 15.0, ink, "eyes")
            }
        }
        val browOffset = if (e == Emotion.STARTLED) -6.0 else 0.0
        stroke(listOf(Point(122.0, 120.0 + browOffset), Point(139.0, if (e == Emotion.CONCERNED) 115.0 else 120.0 + browOffset)), 3.0, "eyebrows")
        stroke(listOf(Point(177.0, if (e == Emotion.CONCERNED) 115.0 else 120.0 + browOffset), Point(194.0, 120.0 + browOffset)), 3.0, "eyebrows")
        when (e) {
            Emotion.STARTLED -> ellipse(153.0, 153.0, 14.0, 18.0, ink, "mouth")
            Emotion.CONCERNED -> stroke(listOf(Point(149.0, 163.0), Point(160.0, 158.0), Point(171.0, 163.0)), 3.0, "mouth")
            Emotion.JOYFUL -> ellipse(148.0, 153.0, 24.0, 18.0, ink, "mouth")
            else -> stroke(listOf(Point(149.0, 157.0), Point(160.0, 163.0), Point(171.0, 157.0)), 3.0, "mouth")
        }
        return shapes
    }
}

class CharacterRenderer(private val provider: CharacterAssetProvider) {
    fun scene(spec: AvatarSpec, state: RenderState): CharacterScene {
        if (!state.visible) return CharacterScene(emptyList(), "", listOf(state.reason))
        val identity = provider.renderIdentity(state.emotion)
        val baseLayers = setOf("body", "face", "signature")
        val shapes = identity.filter { it.layer in baseLayers }.toMutableList()
        val warnings = ConstraintValidator(provider.manifest).violations(spec.journey.themeId, spec.journey.partIds, spec.journey.paletteId).toMutableList()
        if (spec.assetDigest != provider.manifest.digest) warnings += "ASSET_VERSION_MISMATCH"
        if (spec.identity != provider.manifest.identity) warnings += "IDENTITY_MISMATCH"
        if (warnings.isEmpty()) {
            val palette = provider.manifest.palettes.getValue(spec.journey.paletteId)
            spec.journey.partIds.forEach { shapes += provider.renderPart(provider.manifest.parts.getValue(it), palette) }
        }
        shapes += identity.filter { it.layer !in baseLayers }
        val label = if (!state.interactionsAllowed) "눈티" else "눈티 · ${spec.journey.themeId} · ${state.emotion.name}"
        return CharacterScene(shapes.toList(), label, warnings)
    }
}

fun xmlEscape(value: String) = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
fun CharacterScene.toSvg(width: Int = 320, height: Int = 320): String {
    require(width > 0 && height > 0)
    val content = primitives.joinToString("\n") { p ->
        val b = p.bounds
        when (p.kind) {
            PrimitiveKind.ELLIPSE -> "<ellipse cx=\"${b.x + b.width / 2}\" cy=\"${b.y + b.height / 2}\" rx=\"${b.width / 2}\" ry=\"${b.height / 2}\" fill=\"${p.color}\"/>"
            PrimitiveKind.RECT -> "<rect x=\"${b.x}\" y=\"${b.y}\" width=\"${b.width}\" height=\"${b.height}\" rx=\"5\" fill=\"${p.color}\"/>"
            else -> "<polyline points=\"${p.points.joinToString(" ") { "${it.x},${it.y}" }}\" stroke=\"${p.color}\" stroke-width=\"${p.strokeWidth}\" stroke-linecap=\"round\" stroke-linejoin=\"round\" fill=\"none\"/>"
        }
    }
    return "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"$width\" height=\"$height\" viewBox=\"0 0 320 320\" role=\"img\"><title>${xmlEscape(accessibilityLabel)}</title>$content</svg>"
}
