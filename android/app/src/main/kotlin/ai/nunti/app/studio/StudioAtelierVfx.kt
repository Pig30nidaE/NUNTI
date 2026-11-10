package ai.nunti.app.studio

import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** Perspective light ribbons and finite material fragments, sampled from the shared stage clock. */
internal class StudioAtelierVfx(private val skin: String) : StudioVfxScene {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val path = Path()
    private val xs = FloatArray(81)
    private val ys = FloatArray(81)
    private val zs = FloatArray(81)
    private val color = when (skin) { "city" -> 0xffac98f2.toInt(); "mountain" -> 0xffdbb26f.toInt(); else -> 0xff69c9d0.toInt() }
    override fun drawBehind(canvas: Canvas, frame: StudioVfxFrame) = draw(canvas, frame, false)
    override fun drawFront(canvas: Canvas, frame: StudioVfxFrame) = draw(canvas, frame, true)

    private fun draw(canvas: Canvas, frame: StudioVfxFrame, front: Boolean) {
        val t = frame.time
        val lift = ease(t, .45f, 2.83f)
        val fade = ease(t, .45f, .95f) * (1f - ease(t, 3.12f, 3.55f))
        if (fade > .001f) for (strand in 0..1) {
            val phase = t * 2.85f + strand * PI.toFloat()
            for (i in 0..80) {
                val u = i / 80f
                val angle = phase - u * 4.8f
                val radius = (220f - 65f * lift) * (.72f + .28f * sin(u * PI.toFloat()))
                val depth = sin(angle)
                val perspective = 1f + depth * .17f
                xs[i] = 384f + cos(angle) * radius * perspective + frame.direction * (u - .5f) * 45f
                ys[i] = 627f - lift * 370f + (u - .5f) * 220f + depth * 45f
                zs[i] = depth
            }
            paint.style = Paint.Style.STROKE
            paint.strokeCap = Paint.Cap.ROUND
            // Batch adjacent ribbon segments. The same tapered trail now needs 30 paths
            // across both depth passes instead of 480 individual GPU draw commands.
            for (section in 0..4) {
                path.rewind()
                var connected = false
                for (i in section * 16 + 1..(section + 1) * 16) {
                    if ((zs[i] > 0f) != front) { connected = false; continue }
                    if (!connected) path.moveTo(xs[i-1], ys[i-1])
                    path.lineTo(xs[i], ys[i]); connected = true
                }
                val tail = sin((section + .5f) / 5f * PI.toFloat())
                for (pass in 0..2) {
                    val opacity = fade * tail * when (pass) { 0 -> .07f; 1 -> .24f; else -> .85f }
                    paint.color = if (pass == 2) 0xfffff7de.toInt() else color
                    paint.alpha = (opacity * 255).toInt()
                    paint.strokeWidth = when (pass) { 0 -> 14f; 1 -> 5f; else -> 1.8f } * (.65f + tail * .5f)
                    canvas.drawPath(path, paint)
                }
            }
        }
        paint.style = Paint.Style.FILL
        // Each fragment has a fixed seed, onset, trajectory and lifetime. No per-frame randomness.
        for (i in 0 until 42) {
            val seed = ((i * 73 + 19) % 101) / 101f
            val start = .65f + seed * 1.15f
            val progress = ((t - start) / 2.55f).coerceIn(0f, 1f)
            if (progress <= 0f || progress >= 1f) continue
            val angle = i * 2.399963f + progress * 4.2f
            val depth = sin(angle)
            if ((depth > 0f) != front) continue
            val gather = ease(t, start, 2.95f)
            val burst = ease(t, 3.20f, 3.92f)
            val radius = 260f * (1f - gather * .69f) + burst * 245f
            val x = 384f + cos(angle) * radius
            val y = 640f - gather * (260f + seed * 220f) + depth * 38f + burst * (seed - .7f) * 210f
            val opacity = ease(progress, 0f, .14f) * (1f - ease(progress, .73f, 1f)) * (.38f + .32f * seed)
            val size = (2.3f + seed * 4.0f) * (1f + depth * .18f)
            paint.color = if (i % 5 == 0) 0xfffff1cd.toInt() else color
            paint.alpha = (opacity * 255).toInt()
            val save = canvas.save(); canvas.translate(x, y); canvas.rotate(angle * 57.2958f)
            path.rewind()
            when (skin) {
                "mountain" -> { path.moveTo(-size,0f); path.quadTo(0f,-size,size*1.8f,0f); path.quadTo(0f,size,-size,0f) }
                "city" -> { path.moveTo(0f,-size*1.6f); path.lineTo(size,0f); path.lineTo(0f,size*1.6f); path.lineTo(-size,0f) }
                else -> { path.moveTo(0f,-size*1.6f); path.cubicTo(size*1.4f,0f,size,size,0f,size); path.cubicTo(-size,size,-size*1.4f,0f,0f,-size*1.6f) }
            }
            path.close(); canvas.drawPath(path,paint)
            canvas.restoreToCount(save)
        }
        paint.alpha = 255
    }
    private fun ease(t: Float, a: Float, b: Float): Float {
        val f = ((t-a)/(b-a)).coerceIn(0f,1f); return f*f*(3f-2f*f)
    }
}
