package ai.nunti.app.transformation

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.RectF
import org.json.JSONObject
import java.io.IOException
import java.security.MessageDigest

internal data class TransformationAssets(
    val core: Bitmap,
    val baseExpression: Bitmap,
    val expression: Bitmap,
    val expressionIsBase: Boolean,
    val scarf: Bitmap?,
    val pocket: Bitmap?,
    val road: Bitmap?,
    val pocketBounds: RectF?,
    val roadBounds: RectF?,
    val finalImage: Bitmap,
    val finalSourceHash: String,
    val label: String,
    val variantId: String,
    val sourceAssetVersion: String,
) {
    companion object {
        const val ROOT = "nunti_motion_v1"
        val SAMPLE_IDS = listOf("coast", "mountain", "city").flatMap { destination ->
            listOf("calm", "curious", "adventurous").map { "$destination-$it" }
        } + "base"

        /** Packaged canonical fallback has no server or active-manifest dependency. */
        fun base(context: Context): Bitmap? = runCatching {
            decode(context.assets.open("$ROOT/base.png").use { it.readBytes() })
        }.getOrNull()

        fun load(context: Context, sample: String, simulateMissingAsset: Boolean = false): TransformationAssets {
            require(sample in SAMPLE_IDS)
            val manifest = JSONObject(context.assets.open("$ROOT/manifest.json").bufferedReader().use { it.readText() })
            check(manifest.getInt("schemaVersion") == 1 && manifest.getString("assetVersion") == "nunti-motion-v1")
            val canvas = manifest.getJSONArray("canvas")
            check(canvas.length() == 2 && canvas.getInt(0) == 768 && canvas.getInt(1) == 768)
            val files = manifest.getJSONObject("files")
            val record = manifest.getJSONObject("samples").getJSONObject(sample)
            fun read(path: String): ByteArray {
                require(path.matches(Regex("[A-Za-z0-9_/-]+\\.(png|json)")) && ".." !in path && !path.startsWith('/'))
                val expected = files.getJSONObject(path).getString("sha256")
                check(expected.matches(Regex("[0-9a-f]{64}")))
                val bytes = context.assets.open("$ROOT/$path").use { input ->
                    val output = java.io.ByteArrayOutputStream()
                    val buffer = ByteArray(8192)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        check(output.size() + count <= 8_000_000)
                        output.write(buffer, 0, count)
                    }
                    output.toByteArray()
                }
                check(hash(bytes) == expected) { "ASSET_HASH_MISMATCH" }
                return bytes
            }
            fun optional(name: String): Bitmap? = if (record.isNull(name)) null else decode(read(record.getString(name)))
            if (simulateMissingAsset) throw IOException("SIMULATED_ASSET_UNAVAILABLE")
            val spec = JSONObject(String(read(record.getString("spec")), Charsets.UTF_8))
            check(spec.getString("schemaVersion") == "nunti.avatar.layers/1")
            check(spec.getString("characterId") == "nunti-a-v1" && spec.getString("assetVersion") == "nunti-a-layers-v1")
            check(record.getString("expression") == "expression-${spec.getString("expression")}.png")
            val finalBytes = read(record.getString("final"))
            val core = decode(read("core.png"))
            val baseExpression = decode(read("expression-base.png"))
            val expressionIsBase = record.getString("expression") == "expression-base.png"
            val expression = if (expressionIsBase) baseExpression else decode(read(record.getString("expression")))
            val scarf = optional("scarf")
            val pocket = optional("pocket")
            val road = optional("road")
            return TransformationAssets(core, baseExpression, expression, expressionIsBase,
                scarf, pocket, road, pocket?.let(::alphaBounds), road?.let(::alphaBounds),
                decode(finalBytes), hash(finalBytes), record.getString("label"),
                spec.getString("variantId"), manifest.getString("sourceAssetVersion"))
        }

        private fun decode(bytes: ByteArray): Bitmap {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            check(bounds.outWidth == 768 && bounds.outHeight == 768 && bounds.outMimeType == "image/png") { "ASSET_FORMAT_INVALID" }
            return checkNotNull(BitmapFactory.decodeByteArray(bytes, 0, bytes.size,
                BitmapFactory.Options().apply { inPreferredConfig = Bitmap.Config.ARGB_8888; inScaled = false }))
        }

        private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }

        private fun alphaBounds(bitmap: Bitmap): RectF? {
            val pixels = IntArray(768 * 768)
            bitmap.getPixels(pixels, 0, 768, 0, 0, 768, 768)
            var left = 768; var top = 768; var right = -1; var bottom = -1
            for (y in 0 until 768) for (x in 0 until 768) if ((pixels[y * 768 + x] ushr 24) != 0) {
                left = minOf(left, x); top = minOf(top, y); right = maxOf(right, x); bottom = maxOf(bottom, y)
            }
            return if (right < left) null else RectF(left.toFloat(), top.toFloat(), right + 1f, bottom + 1f)
        }
    }
}
