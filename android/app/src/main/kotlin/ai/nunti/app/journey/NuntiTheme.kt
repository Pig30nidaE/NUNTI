package ai.nunti.app.journey

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface

/** Shared Atelier day/night colors, matched to the Studio app window. */
internal data class NuntiTheme(
    val night: Boolean,
    val background: Int,
    val surface: Int,
    val soft: Int,
    val ink: Int,
    val muted: Int,
    val accent: Int,
    val onAccent: Int,
    val warm: Int,
) {
    companion object {
        fun from(context: Context): NuntiTheme {
            val night = context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK ==
                Configuration.UI_MODE_NIGHT_YES
            fun color(day: String, dark: String) = Color.parseColor(if (night) dark else day)
            return NuntiTheme(night,
                color("#F5F3ED", "#111D20"), color("#FFFEFB", "#1A2B2E"),
                color("#E8EEEA", "#22393B"), color("#203C3D", "#F3F2E9"),
                color("#526965", "#B4C8C3"), color("#195057", "#B5DDD2"),
                color("#FFFEFB", "#173A3C"), color("#955434", "#EFBA8D"))
        }
    }
}

/** The bundled OFL font is loaded once, outside any drawing or polling loop. */
internal object NuntiFonts {
    private val weights = mutableMapOf<Int, Typeface>()

    @Synchronized
    fun get(context: Context, weight: Int): Typeface = weights.getOrPut(weight) {
        // The variable font defaults to Thin; choose its actual weight axis,
        // rather than relying on synthetic weight selection after loading it.
        runCatching {
            Typeface.Builder(context.assets, "assets/fonts/noto-sans-kr.ttf")
                .setFontVariationSettings("'wght' $weight")
                .setWeight(weight)
                .build()
        }.getOrElse { Typeface.create(Typeface.create("sans-serif", Typeface.NORMAL), weight, false) }
    }
}
