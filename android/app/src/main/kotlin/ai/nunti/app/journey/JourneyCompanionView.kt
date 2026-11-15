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
    private val sprites = NuntiSpriteRig.Renderer()
    private val shot = NuntiSpriteDirector.Shot()
    private var spriteImage = false
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
    private var tapCount = 0
    /** 정차 중 눌러서 반응했을 때(빠르게 연달아 누른 건 빼고) 불린다. */
    var onTap: (() -> Unit)? = null
    private val touchReactions=arrayOf("wink","happy","curious","proud","signature","surprised","nod","sleepy")
    private fun touchReaction()=touchReactions[(tapCount-1).coerceAtLeast(0)%touchReactions.size]

    init {
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_YES
        isFocusable = true
        updateDescription()
    }

    fun setFaceRig(value: String) { if(rig!=value) { rig=value; invalidate() } }

    /** 그리는 그림이 번들 기본 눈티면 true. 그때는 손그림 동작 프레임으로 상황에 맞게 움직인다. */
    fun setSpriteImage(value: Boolean) { if(spriteImage!=value) { spriteImage=value; invalidate() } }

    /** 지금 화면 상황. 화면을 다시 만들어도 같은 상황이면 동작을 처음부터 다시 하지 않는다. */
    internal fun setStage(value: NuntiSpriteDirector.Stage) {
        if(stage!=value) { stage=value; stageAt=SystemClock.uptimeMillis() }
        invalidate()
    }
    private val usingSprites get() = spriteImage && NuntiSpriteRig.ready

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

    fun stopMotion() { allowed=false; motion?.cancel(); motion=null; invalidate() }
    override fun onDetachedFromWindow() { stopMotion(); super.onDetachedFromWindow() }
    override fun onTouchEvent(event: MotionEvent): Boolean {
        if(!allowed) return false
        if(event.action==MotionEvent.ACTION_UP) performClick()
        return true
    }
    override fun performClick(): Boolean {
        if(!allowed) return false
        val now=SystemClock.uptimeMillis()
        val busy=if(usingSprites) NuntiSpriteDirector.JUMP_SECONDS else NuntiLifeMotion.reactionSeconds(touchReaction())
        if(now-touchedAt<busy*1000)return true
        super.performClick()
        touchedAt=now; tapCount++
        onTap?.invoke()
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
        if(usingSprites) {
            // 화면 폭 안에서 캐릭터가 가장자리에 닿지 않을 만큼만 좌우로 걷는다.
            val range=width*768f/bw/2f-210f
            NuntiSpriteDirector.sample(stage,(now-stageAt)/1000f,if(touchedAt>stageAt) touchTime else -1f,allowed,range,shot)
            if(sprites.draw(canvas,shot)) { canvas.restore(); return }
        }
        if(rig!="none"&&!imageFallback) {
            val duration=NuntiLifeMotion.reactionSeconds(touchReaction())
            val reaction=if(touchTime in 0f..duration) touchReaction() else "idle"
            life.draw(canvas,bitmap,rig,time,reaction,(touchTime/duration).coerceIn(0f,1f),animated=allowed,
                worry=worry,joy=(smile-.2f).coerceAtLeast(0f)/.8f)

        } else {
            destination.set(0f,0f,768f,768f);canvas.drawBitmap(bitmap,null,destination,paint)
        }
        canvas.restore()
    }

    companion object {
        private var stage=NuntiSpriteDirector.Stage.EMPTY
        private var stageAt=SystemClock.uptimeMillis()
        fun emotionLabel(value:String)=when(value){"WORRY"->"조금 더 부드럽게";"RELIEF"->"다시 편안해졌어요";"JOY"->"기분 좋은 도착";else->"함께 달리는 중"}
        fun emotionColor(value:String):Int=when(value){"WORRY"->Color.rgb(158,100,42);"RELIEF"->Color.rgb(51,116,101);"JOY"->Color.rgb(106,101,164);else->Color.rgb(78,108,94)}
    }
}
