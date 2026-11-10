package ai.nunti.app.journey

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.view.View
import android.view.animation.DecelerateInterpolator
import kotlin.math.min
import kotlin.math.sin

/** FIT the collected source pixels. Labels and card decoration belong to the native layout. */
class JourneyCompanionView(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val destination = RectF()
    private var illustration: Bitmap? = null
    private var imageLoaded = false
    private var imageFallback = false
    private var emotion = "NEUTRAL"
    private var characterName = "눈티"
    private var phase = 1f
    private var motion: ValueAnimator? = null

    init {
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_YES
        updateDescription()
    }

    fun setIllustration(bitmap: Bitmap?, name: String, loaded: Boolean = false, fallback: Boolean = false) {
        illustration = bitmap
        imageLoaded = loaded
        imageFallback = fallback
        characterName = name
        updateDescription()
        invalidate()
    }

    fun setEmotion(value: String, animate: Boolean) {
        // Revocation must stop an existing pose even when the emotion has not changed.
        if (!animate) stopMotion()
        if (emotion == value) return
        emotion = value
        updateDescription()
        stopMotion()
        if (animate && ValueAnimator.areAnimatorsEnabled()) {
            motion = ValueAnimator.ofFloat(0f, 1f).apply {
                duration = 850
                interpolator = DecelerateInterpolator()
                addUpdateListener { phase = it.animatedValue as Float; invalidate() }
                start()
            }
        }
        invalidate()
    }

    fun stopMotion() {
        motion?.cancel()
        motion = null
        if (phase != 1f) { phase = 1f; invalidate() }
    }

    private fun updateDescription() {
        contentDescription = if (imageFallback) {
            "$characterName, 기본 눈티. 여정 그림을 사용할 수 없어 기본 모습을 보여줘요."
        } else {
            "$characterName, ${emotionLabel(emotion)}" +
                if (illustration == null) if (imageLoaded) ", 그림을 불러오지 못했어요" else ", 그림을 불러오는 중" else ""
        }
    }

    override fun onDetachedFromWindow() {
        stopMotion()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val bitmap = illustration ?: return
        if (bitmap.isRecycled || width <= 0 || height <= 0) return
        val scale = min(width.toFloat() / bitmap.width, height.toFloat() / bitmap.height)
        val bw = bitmap.width * scale
        val bh = bitmap.height * scale
        val cx = width / 2f
        val cy = height / 2f
        val wave = sin(phase * Math.PI).toFloat()
        val hop = if (emotion == "JOY") min(bw, bh) * .035f * wave else 0f
        val tilt = when (emotion) { "WORRY" -> -3.5f * wave; "RELIEF" -> 2.5f * wave; else -> 0f }
        destination.set(cx - bw / 2, cy - bh / 2 - hop, cx + bw / 2, cy + bh / 2 - hop)
        canvas.save()
        canvas.rotate(tilt, cx, cy)
        canvas.drawBitmap(bitmap, null, destination, paint)
        canvas.restore()
    }

    companion object {
        fun emotionLabel(value: String) = when (value) {
            "WORRY" -> "조금 걱정돼요"
            "RELIEF" -> "다시 안심돼요"
            "JOY" -> "기분 좋은 여정"
            else -> "함께 살피는 중"
        }

        fun emotionColor(value: String): Int = when (value) {
            "WORRY" -> Color.rgb(158, 100, 42)
            "RELIEF" -> Color.rgb(51, 116, 101)
            "JOY" -> Color.rgb(106, 101, 164)
            else -> Color.rgb(78, 108, 94)
        }
    }
}
