package ai.nunti.app.transformation

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.view.View
import kotlin.math.min

/** Only approved local layers are drawn; the core never fades, moves, scales or disappears. */
internal class TransformationCanvasView(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private var base: Bitmap? = null
    private var assets: TransformationAssets? = null
    private var frame = TransformationTimeline.at(0)
    private var style = TransformationStyle.LIGHT_TRAIL
    var frameCount = 0L
        private set

    init { importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_YES }

    fun update(base: Bitmap?, assets: TransformationAssets?, state: TransformationState, style: TransformationStyle) {
        this.base = base
        this.assets = if (state.assetsReady) assets else null
        this.frame = TransformationTimeline.at(state.elapsedMs)
        this.style = style
        contentDescription = when {
            state.running -> "같은 눈티에 여행의 장식과 표정이 더해지고 있어요"
            state.finalVisible -> assets?.label ?: "기본 친근한 눈티"
            else -> "기본 친근한 눈티"
        }
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width <= 0 || height <= 0) return
        frameCount++
        val extent = min(width * .94f, height * .96f)
        canvas.save()
        canvas.translate((width - extent) / 2, (height - extent) / 2)
        canvas.scale(extent / 768, extent / 768)
        drawArtwork(canvas)
        canvas.restore()
    }

    /** Debug evidence uses exactly the same transparent 768² artwork routine as the screen. */
    fun captureArtwork(): Bitmap = Bitmap.createBitmap(768, 768, Bitmap.Config.ARGB_8888).also {
        drawArtwork(Canvas(it))
    }

    private fun drawArtwork(canvas: Canvas) {
        val value = assets
        if (value == null) { base?.let { draw(canvas, it) }; return }
        if (frame.complete) { draw(canvas, value.finalImage); return }
        draw(canvas, value.core)
        if (value.expressionIsBase) draw(canvas, value.baseExpression)
        else {
            draw(canvas, value.baseExpression, 1 - frame.expression)
            draw(canvas, value.expression, frame.expression)
        }
        value.scarf?.let { draw(canvas, it, frame.scarf) }
        value.pocket?.let {
            if (style == TransformationStyle.QUIET_COLOR) draw(canvas, it, frame.pocket)
            else reveal(canvas, it, value.pocketBounds, frame.pocket)
        }
        value.road?.let {
            if (style == TransformationStyle.QUIET_COLOR) draw(canvas, it, frame.road)
            else reveal(canvas, it, value.roadBounds, frame.road)
        }
        if (style == TransformationStyle.LIGHT_TRAIL && frame.road > 0f && frame.road < 1f) {
            value.roadBounds?.let { bounds ->
                val x = bounds.left + bounds.width() * frame.road
                val y = bounds.centerY()
                val opacity = frame.trailOpacity
                paint.color = Color.rgb(249, 216, 146)
                paint.alpha = (opacity * 255 * .16f).toInt()
                canvas.drawCircle(x, y, 8f, paint)
                paint.alpha = (opacity * 255 * .7f).toInt()
                canvas.drawCircle(x, y, 3f, paint)
                paint.alpha = 255
            }
        }
    }

    private fun reveal(canvas: Canvas, bitmap: Bitmap, bounds: RectF?, progress: Float) {
        if (progress <= 0f || bounds == null) return
        if (progress >= 1f) { draw(canvas, bitmap); return }
        canvas.save()
        canvas.clipRect(bounds.left - 1, bounds.top - 1, bounds.left + bounds.width() * progress, bounds.bottom + 1)
        draw(canvas, bitmap)
        canvas.restore()
    }

    private fun draw(canvas: Canvas, bitmap: Bitmap, opacity: Float = 1f) {
        if (opacity <= 0f || bitmap.isRecycled) return
        paint.color = Color.WHITE
        paint.alpha = (opacity.coerceIn(0f, 1f) * 255).toInt()
        canvas.drawBitmap(bitmap, 0f, 0f, paint)
        paint.alpha = 255
    }
}
