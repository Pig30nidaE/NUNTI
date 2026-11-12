package ai.nunti.app.journey

import android.app.Activity
import android.app.Instrumentation
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.os.Bundle
import java.io.File

/** On-device pixel regressions exercise the real Android bitmap, mesh and cutout implementation. */
class CompanionRigInstrumentation : Instrumentation() {
    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        val result = Bundle()
        try {
            val source = targetContext.assets.open("nunti-motion/base.png").use {
                requireNotNull(BitmapFactory.decodeStream(it))
            }
            NuntiFaceRig.prepareSharedImage(source)
            NuntiPuppetParts.prepareShared(source)
            val output = File(targetContext.cacheDir, "companion-pixel-tests").apply { mkdirs() }
            val still = render(source, "idle", 0f, animated = false)
            check(still.sameAs(source)) { "Restricted/reduced-motion frame must preserve the exact source pixels" }
            still.recycle()
            for (reaction in listOf("wave-left", "wave-right", "stretch", "pat")) {
                val image = render(source, reaction, .45f)
                for (y in 430..510 step 4) for (x in 277..298 step 3) {
                    check(Color.alpha(image.getPixel(x, y)) >= 245) { "$reaction: left coat gap at $x,$y" }
                    check(Color.alpha(image.getPixel(768 - x, y)) >= 245) { "$reaction: right coat gap at ${768-x},$y" }
                }
                File(output, "$reaction.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
                image.recycle()
            }
            val wave = render(source, "wave-left", .45f)
            val bag = android.graphics.Rect(282, 521, 319, 558)
            var changed = 0
            for (y in bag.top until bag.bottom) for (x in bag.left until bag.right) {
                if (wave.getPixel(x, y) != source.getPixel(x, y)) changed++
            }
            check(changed < bag.width() * bag.height() / 50) { "Hand gesture moves the torso bag ($changed pixels)" }
            wave.recycle(); source.recycle()
            runOnMainSync {
                val view = JourneyCompanionView(targetContext)
                view.layout(0, 0, 768, 768)
                view.setFaceRig(NuntiCompanionMotion.VERSION)
                view.setEmotion("NEUTRAL", animate = false)
                check(!view.performClick()) { "Restricted companion accepts interaction" }
                if (android.animation.ValueAnimator.areAnimatorsEnabled()) {
                    var clicks = 0
                    view.setOnClickListener { clicks++ }
                    view.setEmotion("NEUTRAL", animate = true)
                    val now = android.os.SystemClock.uptimeMillis()
                    val down = android.view.MotionEvent.obtain(now, now, android.view.MotionEvent.ACTION_DOWN, 200f, 500f, 0)
                    val cancel = android.view.MotionEvent.obtain(now, now, android.view.MotionEvent.ACTION_CANCEL, 200f, 500f, 0)
                    val up = android.view.MotionEvent.obtain(now, now, android.view.MotionEvent.ACTION_UP, 200f, 500f, 0)
                    try { view.onTouchEvent(down); view.onTouchEvent(cancel); view.onTouchEvent(up) }
                    finally { down.recycle(); cancel.recycle(); up.recycle() }
                    check(clicks == 0) { "Canceled touch still triggers a gesture" }
                    view.stopMotion()
                    check(!view.performClick()) { "Background companion accepts interaction" }
                }
            }
            result.putString("stream", "PASS: exact static pixels; four articulated poses retain opaque coat sides; bag stays pinned.\n")
            result.putString("pixelChecks", "passed")
            finish(Activity.RESULT_OK, result)
        } catch (error: Exception) {
            result.putString("stream", "FAIL: ${error.stackTraceToString()}\n")
            result.putString("pixelChecks", "failed")
            finish(Activity.RESULT_CANCELED, result)
        }
    }

    private fun render(source: Bitmap, reaction: String, progress: Float, animated: Boolean = true): Bitmap {
        val output = Bitmap.createBitmap(768, 768, Bitmap.Config.ARGB_8888)
        NuntiSharedRenderer().draw(Canvas(output), source, 0f, reaction, progress, animated = animated)
        return output
    }
}
