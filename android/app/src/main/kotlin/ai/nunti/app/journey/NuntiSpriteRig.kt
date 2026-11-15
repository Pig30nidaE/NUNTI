package ai.nunti.app.journey

import android.content.res.AssetManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import org.json.JSONObject
import java.io.IOException
import java.security.MessageDigest

/**
 * 기본 눈티의 손그림 동작 프레임(걷기·팔짱·점프·앉기). 부위를 잘라 돌리지 않고 그린 장면을 차례로 넘긴다.
 * 프레임은 캐릭터 영역만 잘라 두고 768 공간 안의 위치(x, y)를 함께 기록한다.
 * 에셋이 없거나 읽지 못하면 준비하지 않으며, 그때는 기존 리그가 그대로 그린다.
 */
internal object NuntiSpriteRig {
    const val VERSION = "nunti-sprites-1"
    private const val DEFAULT_IMAGE = "skin-v2/default/final.png"

    class Frame(val bitmap: Bitmap, val x: Float, val y: Float) {
        val bottom get() = y + bitmap.height
    }

    @Volatile private var clips: Map<String, List<Frame>> = emptyMap()
    @Volatile private var defaultHash = ""
    @Volatile var sitSeat = 552f; private set
    val ready get() = clips.isNotEmpty()

    fun frame(clip: String, index: Int): Frame? = clips[clip]?.let { it[index.coerceIn(0, it.size - 1)] }

    /** 작업자 스레드에서 한 번 부른다. */
    @Synchronized fun prepare(assets: AssetManager) {
        if (ready) return
        defaultHash = try { assets.open(DEFAULT_IMAGE).use { sha(it.readBytes()) } } catch (_: IOException) { "" }
        val manifest = try {
            assets.open("nunti-sprites/manifest.json").bufferedReader().use { JSONObject(it.readText()) }
        } catch (_: IOException) { return }
        if (manifest.optString("version") != VERSION) return
        sitSeat = manifest.optDouble("sitSeat", 552.0).toFloat()
        val data = manifest.getJSONObject("clips")
        val loaded = HashMap<String, List<Frame>>()
        for (name in data.keys()) {
            val rows = data.getJSONArray(name)
            loaded[name] = List(rows.length()) { i ->
                val row = rows.getJSONObject(i)
                val bitmap = assets.open(row.getString("path")).use { requireNotNull(BitmapFactory.decodeStream(it)) }
                Frame(bitmap, row.getDouble("x").toFloat(), row.getDouble("y").toFloat())
            }
        }
        clips = loaded
    }

    /** 여정에 쓰는 그림 파일이 번들 기본 눈티와 같은 그림인지. 같을 때만 손그림 동작으로 바꿔 그린다. */
    fun isDefaultImage(bytes: ByteArray) = defaultHash.isNotEmpty() && sha(bytes) == defaultHash

    private fun sha(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** 768 공간에 [shot] 장면을 그린다. 그림자는 코드로 그려 배경과 따로 움직인다. */
    class Renderer {
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
        private val shadow = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0x22000000 }
        private val oval = RectF()

        fun draw(canvas: Canvas, shot: NuntiSpriteDirector.Shot): Boolean {
            if (shot.clip == NuntiSpriteDirector.SIT) {
                val chair = frame(CHAIR, 0) ?: return false
                val body = frame(BODY, 0) ?: return false
                // 의자 다리 네 개가 닿는 넓은 바닥 그림자. 발은 의자에 앉아 바닥에서 살짝 떠 있을 수 있다.
                oval.set(chair.x - 14f, chair.bottom - 40f, chair.x + chair.bitmap.width + 20f, maxOf(chair.bottom, body.bottom) + 9f)
                canvas.drawOval(oval, shadow)
                // 의자는 그대로, 몸만 엉덩이(의자 상판)를 축으로 아주 살짝 숨쉰다.
                canvas.drawBitmap(chair.bitmap, chair.x, chair.y, paint)
                val saved = canvas.save()
                val s = 1f + shot.breath * .008f
                canvas.scale(1f, s, 384f, sitSeat)
                canvas.drawBitmap(body.bitmap, body.x, body.y, paint)
                canvas.restoreToCount(saved)
                return true
            }
            val f = frame(shot.clip, shot.frame) ?: return false
            val x = f.x + shot.dx
            // 높이 뜰수록 그림자가 작아진다.
            val lift = (FEET - f.bottom).coerceAtLeast(0f)
            val k = (1f - lift / 260f).coerceAtLeast(.45f)
            val cx = 384f + shot.dx
            oval.set(cx - 150f * k, FEET - 12f, cx + 150f * k, FEET + 12f)
            canvas.drawOval(oval, shadow)
            val saved = canvas.save()
            val s = 1f + shot.breath * .004f
            canvas.scale(s, s, cx, FEET)
            canvas.drawBitmap(f.bitmap, x, f.y, paint)
            canvas.restoreToCount(saved)
            return true
        }
    }

    const val FEET = 718f
    private const val CHAIR = "sitChair"
    private const val BODY = "sitBody"
}
