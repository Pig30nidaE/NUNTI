package ai.nunti.app.journey

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.min
import kotlin.math.sin

/** A persistent companion with separately animated face features and parked-only touch response. */
class JourneyCompanionView(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val destination = RectF()
    private val life = NuntiLifeRenderer()
    private var illustration: Bitmap? = null
    private var imageLoaded = false
    private var imageFallback = false
    private var emotion = "NEUTRAL"
    private var characterName = "눈티"
    private var rig = "none"
    private var allowed = false
    private var motion: ValueAnimator? = null
    private var startedAt = SystemClock.uptimeMillis()
    private var changedAt = startedAt
    private var touchedAt = -10000L
    private var fromSmile = .12f
    private var fromWorry = 0f
    private var smile = .12f
    private var worry = 0f
    private var reaction = "wave-right"
    private var pendingReaction = "wave-right"
    private var focusX = 0f
    private var focusY = 0f
    private var lastFocusAt = 0L
    private var touching = false
    private fun sharedRig() = rig == NuntiCompanionMotion.VERSION || rig == "base-v1"
    private fun reactionSeconds() = if (sharedRig()) NuntiCompanionMotion.duration(reaction) else NuntiLifeMotion.reactionSeconds(reaction)

    init {
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_YES
        isFocusable = true
        updateDescription()
    }

    fun setFaceRig(value: String) { if(rig!=value) { rig=value; invalidate() } }

    fun setIllustration(bitmap: Bitmap?, name: String, loaded: Boolean = false, fallback: Boolean = false) {
        val changed = illustration !== bitmap || characterName != name || imageLoaded != loaded || imageFallback != fallback
        illustration=bitmap; imageLoaded=loaded; imageFallback=fallback; characterName=name
        if(changed) { updateDescription(); invalidate() }
    }

    fun setEmotion(value: String, animate: Boolean) {
        allowed = animate && ValueAnimator.areAnimatorsEnabled()
        isClickable = allowed
        if (emotion != value) {
            fromSmile=smile; fromWorry=worry; changedAt=SystemClock.uptimeMillis()
            emotion=value; updateDescription()
        }
        if(!allowed) {
            cancelInteraction()
            motion?.cancel(); motion=null
            smile=targetSmile(); worry=if(emotion=="WORRY") 1f else 0f
            invalidate()
        } else if(motion==null && isAttachedToWindow) {
            startedAt=SystemClock.uptimeMillis()
            motion=ValueAnimator.ofFloat(0f,1f).apply {
                duration=5700; repeatCount=ValueAnimator.INFINITE; interpolator=LinearInterpolator()
                addUpdateListener { invalidate() }; start()
            }
        }
    }

    private fun cancelInteraction() {
        touching=false; focusX=0f; focusY=0f; touchedAt=-10000L; pendingReaction="wave-right"
    }
    fun stopMotion() { allowed=false; isClickable=false; cancelInteraction(); motion?.cancel(); motion=null; invalidate() }
    override fun onDetachedFromWindow() { stopMotion(); super.onDetachedFromWindow() }
    override fun onTouchEvent(event: MotionEvent): Boolean {
        if(!allowed) return false
        val side = min(width, height).toFloat()
        if (side <= 0f) return false
        val x = (event.x - (width - side) / 2f) / side
        val y = (event.y - (height - side) / 2f) / side
        if (event.actionMasked == MotionEvent.ACTION_CANCEL || x !in 0f..1f || y !in 0f..1f) {
            touching=false; focusX=0f; focusY=0f
            return false
        }
        focusX = (x - .5f) * 2f; focusY = (y - .4f) * 2f
        lastFocusAt = SystemClock.uptimeMillis()
        if (event.actionMasked == MotionEvent.ACTION_DOWN) {
            touching=true
            pendingReaction = if (!sharedRig()) "wink" else when {
                y < .51f -> "pat"
                x < .38f -> "wave-left"
                x > .62f -> "wave-right"
                y > .72f -> "stretch"
                else -> "curious"
            }
        }
        if(event.actionMasked==MotionEvent.ACTION_UP && touching) { touching=false; performClick() }
        return true
    }
    override fun performClick(): Boolean {
        if(!allowed) return false
        val now=SystemClock.uptimeMillis()
        if(now-touchedAt<450)return true
        super.performClick()
        touchedAt=now; reaction=pendingReaction; pendingReaction="wave-right"
        performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY)
        invalidate(); return true
    }

    private fun targetSmile()=when(emotion){"JOY"->1f;"RELIEF"->.68f;"WORRY"->0f;else->.12f}
    private fun updateDescription() {
        contentDescription=if(imageFallback) "$characterName, 기본 모습" else "$characterName, ${emotionLabel(emotion)}. 주차 중 눌러 인사하기"
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val bitmap=illustration ?: return
        if(bitmap.isRecycled || width<=0 || height<=0) return
        val now=SystemClock.uptimeMillis()
        val progress=if(allowed) ((now-changedAt)/700f).coerceIn(0f,1f) else 1f
        val eased=progress*progress*(3-2*progress)
        smile=fromSmile+(targetSmile()-fromSmile)*eased
        worry=fromWorry+((if(emotion=="WORRY") 1f else 0f)-fromWorry)*eased
        val time=(now-startedAt)/1000f
        val touchTime=(now-touchedAt)/1000f
        val scale=min(width.toFloat()/bitmap.width,height.toFloat()/bitmap.height)
        val bw=bitmap.width*scale; val bh=bitmap.height*scale
        canvas.save()
        canvas.translate((width-bw)/2f,(height-bh)/2f)
        canvas.scale(bw/768f,bh/768f)
        if(rig!="none"&&!imageFallback) {
            val duration=reactionSeconds()
            val activeReaction=if(touchTime in 0f..duration) reaction else "idle"
            val following = now-lastFocusAt<1400
            life.draw(canvas,bitmap,rig,time,activeReaction,(touchTime/duration).coerceIn(0f,1f),animated=allowed,
                worry=worry,joy=(smile-.2f).coerceAtLeast(0f)/.8f,
                focusX=if(following)focusX else 0f,focusY=if(following)focusY else 0f)

        } else {
            destination.set(0f,0f,768f,768f);canvas.drawBitmap(bitmap,null,destination,paint)
        }
        canvas.restore()
    }

    companion object {
        fun emotionLabel(value:String)=when(value){"WORRY"->"조금 더 부드럽게";"RELIEF"->"다시 편안해졌어요";"JOY"->"기분 좋은 도착";else->"함께 달리는 중"}
        fun emotionColor(value:String):Int=when(value){"WORRY"->Color.rgb(158,100,42);"RELIEF"->Color.rgb(51,116,101);"JOY"->Color.rgb(106,101,164);else->Color.rgb(78,108,94)}
    }
}
