package ai.nunti.app.studio

import android.content.res.AssetManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject

/** Samples authored flipbooks on the existing Studio stage clock. */
internal class StudioAtlasVfx private constructor(private val back: List<Cue>, private val front: List<Cue>) : StudioVfxScene {
    private class Sheet(val bitmap: Bitmap, val width: Int, val height: Int, val columns: Int, val frames: Int, val fps: Float)
    private class Cue(
        val sheet: Sheet, val start: Float, val rate: Float, val opacity: Float, val fadeIn: Float,
        val fadeOut: Float, val rect: RectF, val clipTop: Float, val clipBottom: Float, val followRoute: Boolean,
    )

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val source = Rect()

    override fun drawBehind(canvas: Canvas, frame: StudioVfxFrame) = draw(canvas, frame, back)

    override fun drawFront(canvas: Canvas, frame: StudioVfxFrame) = draw(canvas, frame, front)

    private fun draw(canvas: Canvas, frame: StudioVfxFrame, cues: List<Cue>) {
        for (cue in cues) {
            val elapsed = frame.time - cue.start
            val sheet = cue.sheet
            val samplesPerSecond = sheet.fps * cue.rate
            val sample = elapsed * samplesPerSecond
            if (sample < 0f || sample >= sheet.frames) continue
            val index = sample.toInt()
            val x = index % sheet.columns * sheet.width
            val y = index / sheet.columns * sheet.height
            source.set(x, y, x + sheet.width, y + sheet.height)
            val remaining = (sheet.frames - sample) / samplesPerSecond
            val fadeIn = if (cue.fadeIn == 0f) 1f else (elapsed / cue.fadeIn).coerceAtMost(1f)
            val fadeOut = if (cue.fadeOut == 0f) 1f else (remaining / cue.fadeOut).coerceAtMost(1f)
            paint.alpha = (cue.opacity * fadeIn * fadeOut * 255).toInt()
            if (paint.alpha == 0) continue
            val save = canvas.save()
            canvas.clipRect(0f, cue.clipTop, 768f, cue.clipBottom)
            if (cue.followRoute && frame.direction < 0f) canvas.scale(-1f, 1f, 384f, 384f)
            canvas.drawBitmap(sheet.bitmap, source, cue.rect, paint)
            canvas.restoreToCount(save)
        }
    }

    companion object {
        fun load(assets: AssetManager, skin: String): StudioAtlasVfx? = runCatching {
            val root = "nunti-vfx/$skin"
            val manifest = assets.open("$root/manifest.json").bufferedReader().use { JSONObject(it.readText()) }
            val sheets = mutableMapOf<String, Sheet>()
            var pixels = 0L
            manifest.getJSONArray("sheets").forEachObject { spec ->
                val path = spec.getString("file")
                require(path.matches(Regex("[a-z0-9_-]+\\.png")))
                val bitmap = assets.open("$root/$path").use { requireNotNull(BitmapFactory.decodeStream(it)) }
                val width = spec.getInt("width")
                val height = spec.getInt("height")
                val columns = spec.getInt("columns")
                val frames = spec.getInt("frames")
                val fps = spec.getDouble("fps").toFloat()
                require(width > 0 && height > 0 && columns > 0 && frames > 0 && fps in 1f..60f)
                require(bitmap.width <= 4096 && bitmap.height <= 4096 && bitmap.width / width == columns)
                require(bitmap.width % width == 0 && bitmap.height % height == 0)
                require(frames <= columns * (bitmap.height / height))
                pixels += bitmap.width.toLong() * bitmap.height
                require(pixels <= 5_000_000)
                sheets[path] = Sheet(bitmap, width, height, columns, frames, fps)
            }
            val back = mutableListOf<Cue>()
            val front = mutableListOf<Cue>()
            manifest.getJSONArray("cues").forEachObject { spec ->
                val sheet = checkNotNull(sheets[spec.getString("file")])
                val bounds = spec.getJSONArray("bounds")
                require(bounds.length() == 4)
                val rect = RectF(bounds.float(0), bounds.float(1), bounds.float(2), bounds.float(3))
                require(rect.width() > 0 && rect.height() > 0)
                val cue = Cue(sheet, spec.getDouble("at").toFloat(), spec.optDouble("rate", 1.0).toFloat(),
                    spec.optDouble("opacity", 1.0).toFloat(), spec.optDouble("fadeIn", 0.0).toFloat(),
                    spec.optDouble("fadeOut", 0.0).toFloat(), rect, spec.optDouble("clipTop", 0.0).toFloat(),
                    spec.optDouble("clipBottom", 768.0).toFloat(), spec.optBoolean("followRoute"))
                require(cue.start in 0f..3.98f && cue.rate in .25f..3f && cue.opacity in 0f..1f)
                require(cue.fadeIn >= 0f && cue.fadeOut >= 0f && cue.clipTop in 0f..cue.clipBottom && cue.clipBottom <= 768f)
                when (spec.getString("pass")) {
                    "back" -> back.add(cue)
                    "front" -> front.add(cue)
                    else -> error("Unknown VFX pass")
                }
            }
            require(back.isNotEmpty() || front.isNotEmpty())
            StudioAtlasVfx(back, front)
        }.onFailure {
            Log.w("NuntiVfx", "Authored $skin flipbook unavailable", it)
        }.getOrNull()

        private fun JSONArray.float(index: Int) = getDouble(index).toFloat().also { require(it.isFinite()) }

        private inline fun JSONArray.forEachObject(read: (JSONObject) -> Unit) {
            for (index in 0 until length()) read(getJSONObject(index))
        }
    }
}
