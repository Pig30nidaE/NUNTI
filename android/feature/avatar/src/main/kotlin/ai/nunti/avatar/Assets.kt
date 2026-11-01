package ai.nunti.avatar

import java.util.Properties
import kotlin.math.pow

enum class Theme { BASE, CITY, JOURNEY, COASTAL, MOUNTAIN }
data class Bounds(val x: Double, val y: Double, val width: Double, val height: Double) {
    fun overlaps(other: Bounds) = x < other.x + other.width && x + width > other.x && y < other.y + other.height && y + height > other.y
    fun inside(other: Bounds) = x >= other.x && y >= other.y && x + width <= other.x + other.width && y + height <= other.y + other.height
}
data class PartAsset(val id: String, val slot: String, val anchor: String, val bounds: Bounds,
    val themes: Set<Theme>, val incompatible: Set<String>, val shape: String)
data class Palette(val id: String, val fill: String, val ink: String)
data class IdentityLayer(
    val baseCharacterId: String = "nunti-v1",
    val faceId: String = "face-round-v1",
    val silhouetteId: String = "body-bean-v1",
    val coreColor: String = "#F7EBC6",
    val signatureId: String = "forehead-seed-v1",
    val persona: String = "차분하고 다정한 여행 동승자",
    val voiceProfileId: String = "nunti-default-v1",
)

data class AssetManifest(val assetVersion: String, val identity: IdentityLayer, val parts: Map<String, PartAsset>,
    val palettes: Map<String, Palette>, val digest: String) {
    companion object {
        fun load(p: Properties): AssetManifest {
            val parts = p.stringPropertyNames().filter { it.startsWith("part.") }.associate { key ->
                val id = key.removePrefix("part.")
                val fields = p.getProperty(key).split('|')
                require(fields.size == 10) { "Invalid manifest part $id" }
                id to PartAsset(id, fields[0], fields[1], Bounds(fields[2].toDouble(), fields[3].toDouble(), fields[4].toDouble(), fields[5].toDouble()),
                    fields[6].split(',').map { Theme.valueOf(it) }.toSet(), fields[7].split(',').filter { it.isNotBlank() }.toSet(), fields[8]).also {
                    require(fields[9] == "1") { "Unsupported part format" }
                }
            }
            val palettes = p.stringPropertyNames().filter { it.startsWith("palette.") }.associate { key ->
                val id = key.removePrefix("palette.")
                val colors = p.getProperty(key).split('|')
                require(colors.size == 2 && colors.all { Regex("#[0-9A-Fa-f]{6}").matches(it) })
                id to Palette(id, colors[0], colors[1])
            }
            require("plain" in palettes)
            val identity = IdentityLayer(p.getProperty("identity.baseCharacterId"), p.getProperty("identity.faceId"),
                p.getProperty("identity.silhouetteId"), p.getProperty("identity.coreColor"), p.getProperty("identity.signatureId"),
                p.getProperty("identity.persona"), p.getProperty("identity.voiceProfileId"))
            require(Regex("#[0-9A-Fa-f]{6}").matches(identity.coreColor))
            return AssetManifest(p.getProperty("asset.version"), identity, parts.toSortedMap(), palettes.toSortedMap(), propertyDigest(p))
        }
    }
}

fun propertyDigest(p: Properties) = ai.nunti.navigation.sha256(p.stringPropertyNames().sorted().joinToString("\n") { "$it=${p.getProperty(it)}" })
fun loadProperties(name: String): Properties = Properties().apply {
    val stream = requireNotNull(AssetManifest::class.java.getResourceAsStream("/$name")) { "Missing resource $name" }
    stream.reader(Charsets.UTF_8).use { load(it) }
}

fun contrast(a: String, b: String): Double {
    fun luminance(hex: String): Double {
        val rgb = listOf(1, 3, 5).map { hex.substring(it, it + 2).toInt(16) / 255.0 }.map {
            if (it <= 0.04045) it / 12.92 else ((it + 0.055) / 1.055).pow(2.4)
        }
        return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
    }
    val x = luminance(a); val y = luminance(b)
    return (maxOf(x, y) + 0.05) / (minOf(x, y) + 0.05)
}

class ConstraintValidator(private val manifest: AssetManifest) {
    fun violations(theme: Theme, partIds: List<String>, paletteId: String): List<String> {
        val errors = mutableListOf<String>()
        val face = Bounds(106.0, 100.0, 108.0, 78.0)
        val envelope = Bounds(42.0, 50.0, 236.0, 240.0)
        val parts = partIds.mapNotNull { id -> manifest.parts[id].also { if (it == null) errors += "MISSING_PART:$id" } }
        if (partIds.distinct().size != partIds.size) errors += "DUPLICATE_PART"
        parts.groupBy { it.slot }.filter { it.value.size > 1 }.keys.forEach { errors += "SLOT_COLLISION:$it" }
        parts.forEach {
            if (theme !in it.themes) errors += "THEME:${it.id}"
            if (it.incompatible.any { other -> other in partIds }) errors += "INCOMPATIBLE:${it.id}"
            if (it.anchor !in setOf("torso", "left-hand", "right-hand", "ground")) errors += "ANCHOR:${it.id}"
            if (listOf(it.bounds.x, it.bounds.y, it.bounds.width, it.bounds.height).any { v -> !v.isFinite() } ||
                it.bounds.width <= 0 || it.bounds.height <= 0 || !it.bounds.inside(envelope)) errors += "SILHOUETTE:${it.id}"
            if (it.bounds.overlaps(face)) errors += "FACE_OCCLUSION:${it.id}"
            if (it.shape !in setOf("vest", "bag", "ticket", "wave", "mountain", "scarf", "bottle")) errors += "SHAPE:${it.id}"
        }
        val palette = manifest.palettes[paletteId]
        if (palette == null) errors += "MISSING_PALETTE:$paletteId"
        else if (contrast(palette.fill, palette.ink) < 3.0) errors += "LOW_CONTRAST"
        return errors.distinct().sorted()
    }
}
