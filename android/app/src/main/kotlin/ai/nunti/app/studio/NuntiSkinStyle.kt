package ai.nunti.app.studio

/** Costume identity travels with the immutable image hash; unknown old records stay neutral. */
internal object NuntiSkinStyle {
    private val wardrobe = Regex("wardrobe-(?:(formal|medical|football|hiking|seaside|personal|shared1)-)?([0-9a-f]{64})(?:-([0-9a-f]{64}))?")
    fun isWardrobe(skin: String): Boolean {
        val match = wardrobe.matchEntire(skin) ?: return false
        return (match.groupValues[1] == "shared1") == match.groupValues[3].isNotEmpty()
    }
    fun imageHash(skin: String): String = requireNotNull(wardrobe.matchEntire(skin)).groupValues[2]
    fun rigHash(skin: String): String? = wardrobe.matchEntire(skin)?.groupValues?.get(3)?.takeIf { it.isNotEmpty() }
    fun theme(skin: String): String = wardrobe.matchEntire(skin)?.groupValues?.get(1)?.ifBlank { "personal" } ?: skin
    fun tint(skin: String): Int = when(theme(skin)) {
        "formal" -> 0xffd6b477.toInt()
        "medical" -> 0xff91ccb6.toInt()
        "football" -> 0xff6ab58c.toInt()
        "city" -> 0xffac98f2.toInt()
        "mountain", "hiking" -> 0xffdbb26f.toInt()
        "sea", "seaside" -> 0xff69c9d0.toInt()
        else -> 0xffb9c5a4.toInt()
    }
}
