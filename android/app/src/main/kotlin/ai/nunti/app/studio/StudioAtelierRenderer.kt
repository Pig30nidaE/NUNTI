package ai.nunti.app.studio

import android.annotation.TargetApi
import android.graphics.Bitmap
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.PorterDuffColorFilter
import android.graphics.RectF
import android.graphics.RuntimeShader
import android.graphics.Shader
import android.os.Build
import android.util.Log
import kotlin.math.PI
import kotlin.math.floor
import kotlin.math.sin
import kotlin.math.sqrt

/** One registered pose and material field shared by the character and its silhouette glow. */
internal object StudioAtelierMotion {
    fun ease(t: Float, a: Float, b: Float): Float {
        val f = ((t - a) / (b - a)).coerceIn(0f, 1f)
        return f * f * (3f - 2f * f)
    }
    private fun charge(t: Float) = ease(t, .5f, 2.7f) * (1f - ease(t, 3.25f, 3.75f))
    fun offsetY(t: Float) = -16f * charge(t) - 13f * sin(PI.toFloat() * ease(t, 3.34f, 4.25f))
    fun scale(t: Float) = 1f + .008f * sin(PI.toFloat() * ease(t, 0f, .6f)) + .012f * charge(t)
    // The spatial field is constant throughout playback. Build it once on the
    // asset worker instead of evaluating eight sine hashes per screen pixel.
    val materialMap: Bitmap by lazy {
        val pixels = IntArray(256 * 256)
        for (y in 0 until 256) for (x in 0 until 256) {
            val px = (x + .5f) * 3f; val py = (y + .5f) * 3f
            val grain = noise(px * .035f, py * .035f)
            val textile = ((1f-py/768f)*.57f + noise(px*.025f,py*.025f)*.26f + noise(px*.061f,py*.061f)*.12f).coerceIn(.02f,.97f)
            val dx=(px-384f)/147f; val dy=(py-310f)/151f
            val face=1f-ease(sqrt(dx*dx+dy*dy),.75f,1f)
            val value=textile+(.84f-textile)*face
            pixels[y*256+x]=Color.rgb((value*255f+.5f).toInt(),(grain*255f+.5f).toInt(),0)
        }
        Bitmap.createBitmap(pixels,256,256,Bitmap.Config.ARGB_8888)
    }
    private fun noise(x: Float, y: Float): Float {
        val ix=floor(x); val iy=floor(y)
        val fx=ease(x-ix,0f,1f); val fy=ease(y-iy,0f,1f)
        fun hash(a: Float,b: Float): Float { val h=sin(a*127.1+b*311.7)*43758.5453; return (h-floor(h)).toFloat() }
        val top=hash(ix,iy)*(1f-fx)+hash(ix+1f,iy)*fx
        val bottom=hash(ix,iy+1f)*(1f-fx)+hash(ix+1f,iy+1f)*fx
        return top*(1f-fy)+bottom*fy
    }
    const val MATERIAL_FIELD = """
        uniform shader materialTexture;
        uniform float wardrobeMode;
        float materialField(float2 p) {
            float4 tex = materialTexture.eval(p/3.0);
            float wave = clamp((1.0 - p.y / 768.0) * .72 + tex.g * .25, .04, .96);
            return mix(tex.r, wave, wardrobeMode);
        }
    """
}

/** Registered artwork stays rigid. Light materializes the outfit without rubber-sheet deformation. */
internal class StudioAtelierRenderer {
    private val life = ai.nunti.app.journey.NuntiLifeRenderer()
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val bounds = RectF(0f, 0f, 768f, 768f)
    private val white = PorterDuffColorFilter(Color.WHITE, PorterDuff.Mode.SRC_IN)
    private var art: StudioCharacterAssets? = null
    private var shader: Materialization? = null
    private var shaderFailed = false

    fun draw(canvas: Canvas, assets: StudioCharacterAssets, time: Float?, pose: StudioCharacterPose) {
        if (art !== assets) {
            art = assets
            shader = if (Build.VERSION.SDK_INT >= 33 && !shaderFailed) runCatching { Materialization(assets) }
                .onFailure { shaderFailed = true; Log.w("NuntiAtelier", "Material shader unavailable", it) }.getOrNull() else null
        }
        paint.alpha = 255
        if (time == null || time >= 4.6f) {
            life.draw(canvas, assets.travel, assets.skin, pose.faceTime/60f, pose.faceReaction, pose.faceReactionTime, focusX = pose.focusX, focusY = pose.focusY)
            return
        }
        val t = time.coerceAtLeast(0f)
        val state = canvas.save()
        canvas.translate(0f, StudioAtelierMotion.offsetY(t))
        val scale = StudioAtelierMotion.scale(t)
        canvas.scale(scale, scale, 384f, 721f)
        val material = shader
        if (Build.VERSION.SDK_INT >= 33 && material != null) {
            try {
                paint.shader = material.at(t)
                canvas.drawRect(bounds, paint)
            } catch (error: IllegalArgumentException) {
                shaderFailed = true; shader = null
                Log.w("NuntiAtelier", "Material shader draw fallback", error)
                fallback(canvas, assets, t)
            } finally { paint.shader = null }
        } else fallback(canvas, assets, t)
        canvas.restoreToCount(state)
    }

    private fun fallback(canvas: Canvas, assets: StudioCharacterAssets, t: Float) {
        paint.shader = null
        val image = if (t < 3.14f) assets.base else assets.travel
        paint.alpha = 255
        canvas.drawBitmap(image, null, bounds, paint)
        val light = ease(t, 2.35f, 3.10f) * (1f - ease(t, 3.23f, 3.7f))
        paint.colorFilter = white; paint.alpha = (light * 235).toInt()
        canvas.drawBitmap(image, null, bounds, paint)
        paint.colorFilter = null; paint.alpha = 255
    }

    @TargetApi(33)
    private class Materialization(assets: StudioCharacterAssets) {
        private val shader = RuntimeShader(SOURCE)
        init {
            shader.setInputShader("before", BitmapShader(assets.base, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP))
            shader.setInputShader("after", BitmapShader(assets.travel, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP))
            shader.setInputShader("materialTexture", BitmapShader(StudioAtelierMotion.materialMap, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP).apply {
                filterMode = BitmapShader.FILTER_MODE_LINEAR
            })
            val tint = NuntiSkinStyle.tint(assets.skin)
            val color = floatArrayOf(Color.red(tint)/255f,Color.green(tint)/255f,Color.blue(tint)/255f)
            shader.setFloatUniform("tint", color)
            shader.setFloatUniform("wardrobeMode", if (assets.skin.startsWith("wardrobe-")) 1f else 0f)
        }
        fun at(time: Float): Shader { shader.setFloatUniform("time", time); return shader }
    }
    companion object {
        private fun ease(t: Float, a: Float, b: Float): Float {
            val f = ((t - a) / (b - a)).coerceIn(0f, 1f); return f * f * (3f - 2f * f)
        }
        private const val SOURCE = """
            uniform shader before;
            uniform shader after;
            uniform float time;
            uniform float3 tint;
            ${StudioAtelierMotion.MATERIAL_FIELD}
            half4 main(float2 p) {
                half4 a=before.eval(p), b=after.eval(p);
                if(time<1.65) return a;
                if(time>=3.96) return b;
                float progress=smoothstep(2.34,3.32,time);
                float field=materialField(p);
                float revealed=smoothstep(field-.026,field+.026,progress);
                half4 color=mix(a,b,revealed);
                float unionAlpha=mix(a.a,b.a,revealed);
                float charge=smoothstep(1.65,2.92,time)*(1.0-smoothstep(3.20,3.72,time));
                float edge=exp2(-abs(field-progress)*72.0)*smoothstep(.005,.08,progress)*(1.0-smoothstep(.91,1.0,progress));
                float flare=smoothstep(3.10,3.19,time)*(1.0-smoothstep(3.24,3.59,time));
                float textile=pow(materialTexture.eval(p/3.0).g,7.0)*charge*.5;
                // Hide the interpolated artwork while two features occupy the
                // same pixel. The local light reveals one complete face.
                float changing=smoothstep(.02,.20,revealed)*(1.0-smoothstep(.80,.98,revealed));
                float light=clamp(charge*.22+edge*.89+flare*.80+textile+changing*1.2,0.0,1.0);
                float3 hue=mix(tint,float3(1.0,.99,.94),clamp(edge*.6+flare*.4+changing,0.0,1.0));
                return half4(mix(color.rgb,hue*unionAlpha,light),unionAlpha);
            }
        """
    }
}
