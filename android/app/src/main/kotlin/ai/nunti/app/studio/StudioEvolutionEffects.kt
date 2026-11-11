package ai.nunti.app.studio

import android.annotation.TargetApi
import android.content.Context
import android.content.res.AssetManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.PorterDuffColorFilter
import android.graphics.PorterDuffXfermode
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.RuntimeShader
import android.graphics.Shader
import android.os.Build
import android.util.Log
import android.view.Choreographer
import android.view.View
import kotlin.math.abs
import kotlin.math.exp

internal interface StudioVfxScene {
    fun drawBehind(canvas: Canvas, frame: StudioVfxFrame)
    fun drawFront(canvas: Canvas, frame: StudioVfxFrame)
}

/** Shared clock in 768×768 character stage coordinates. */
internal data class StudioVfxFrame(
    val time: Float,
    val gather: Float,
    val charge: Float,
    val impact: Float,
    val release: Float,
    val direction: Float,
)

/** Two stage-local passes clocked from the character transformation start. */
internal class StudioEvolutionEffects(context: Context) : View(context) {
    internal class Masks internal constructor(internal val base: Mask, internal val skin: Mask)
    internal class Mask internal constructor(internal val distance: Bitmap, internal val halo: Bitmap)

    private enum class Theme(
        val energy: Int, val glint: Int,
    ) {
        SEA(0xff27c8df.toInt(), 0xfff3fbff.toInt()),
        CITY(0xffa084ff.toInt(), 0xfff3e9ff.toInt()),
        MOUNTAIN(0xffedbd66.toInt(), 0xfffff2cd.toInt()),
        FORMAL(0xffd6b477.toInt(),0xfffff3d7.toInt()), MEDICAL(0xff91ccb6.toInt(),0xfff2fff7.toInt()),
        FOOTBALL(0xff6ab58c.toInt(),0xffeefff2.toInt()), PERSONAL(0xffb9c5a4.toInt(),0xfff5f7e9.toInt());

        companion object {
            fun from(skin: String) = when (NuntiSkinStyle.theme(skin)) {
                "formal" -> FORMAL
                "medical" -> MEDICAL
                "football" -> FOOTBALL
                "personal" -> PERSONAL
                "hiking" -> MOUNTAIN
                "city" -> CITY
                "mountain" -> MOUNTAIN
                else -> SEA
            }
        }
    }

    private class Playback(
        val theme: Theme,
        val skin: String,
        val masks: Masks?,
        val authored: StudioAtlasVfx?,
        val direction: Float,
        val allowed: () -> Boolean,
        val onCameraScale: (Float) -> Unit,
    ) {
        val atelier:StudioVfxScene = if(NuntiSkinStyle.isWardrobe(skin)) StudioWardrobeVfx(skin) else StudioAtelierVfx(theme.name.lowercase())
        val startedAt = System.nanoTime()
        var frame = StudioVfxFrame(0f, 0f, 0f, 0f, 0f, direction)
        val tint = PorterDuffColorFilter(theme.energy, PorterDuff.Mode.SRC_IN)
        val bloom = RadialGradient(CENTER_X, CENTER_Y, 344f,
            intArrayOf(theme.glint and 0x66ffffff, theme.energy and 0x38ffffff, theme.energy and 0x00ffffff),
            floatArrayOf(0f, .43f, 1f), Shader.TileMode.CLAMP)
        var logged = false
    }

    private val choreographer = Choreographer.getInstance()
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val maskBounds = RectF()
    private val pose = BodyPose()
    private val screen = PorterDuffXfermode(PorterDuff.Mode.SCREEN)
    private var playback: Playback? = null
    private var hardware: HardwareGlow? = null
    private var shaderUnavailable = false
    val behind: View = object : View(context) {
        override fun onDraw(canvas: Canvas) = drawPass(canvas, width, height, background = true)
    }.apply {
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO
        visibility = GONE
    }
    private val tick = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            val active = playback ?: return
            val time = ((frameTimeNanos - active.startedAt) / 1_000_000_000.0).toFloat().coerceAtLeast(0f)
            if (!active.allowed() || time >= END) {
                stop()
                return
            }
            val release = ((time - BURST) / (END - BURST)).coerceIn(0f, 1f)
            val gather = smooth(time, .38f, 1.96f) * (1f - smooth(time, 2.87f, BURST))
            val charge = smooth(time, 1.20f, 2.77f) * (1f - smooth(time, BURST, BURST + .19f))
            val impact = smooth(time, BURST - .025f, BURST + .055f) *
                (1f - smooth(time, BURST + .055f, BURST + .43f))
            active.frame = StudioVfxFrame(time, gather, charge, impact, release, active.direction)
            pose.update(time)
            active.onCameraScale(pose.camera)
            behind.invalidate()
            invalidate()
            choreographer.postFrameCallback(this)
        }
    }

    init {
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO
        visibility = GONE
    }

    fun start(skin: String, masks: Masks?, authored: StudioAtlasVfx?, direction: Float, allowed: () -> Boolean, onCameraScale: (Float) -> Unit) {
        stop()
        if (!allowed()) return
        val active = Playback(Theme.from(skin), skin, masks, authored, direction.coerceIn(-1f, 1f), allowed, onCameraScale)
        if (Build.VERSION.SDK_INT >= 33 && masks != null && !shaderUnavailable) {
            try {
                hardware = (hardware ?: HardwareGlow()).apply { bind(active) }
            } catch (error: IllegalArgumentException) {
                shaderUnavailable = true
                hardware = null
                Log.w(TAG, "AGSL initialization failed; using Canvas", error)
            }
        }
        playback = active
        pose.update(0f)
        behind.visibility = VISIBLE
        visibility = VISIBLE
        onCameraScale(1f)
        choreographer.postFrameCallback(tick)
    }

    fun stop() {
        val active = playback ?: return
        playback = null
        choreographer.removeFrameCallback(tick)
        behind.visibility = GONE
        visibility = GONE
        active.onCameraScale(1f)
    }

    override fun onDetachedFromWindow() {
        stop()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) = drawPass(canvas, width, height, background = false)

    private fun drawPass(canvas: Canvas, width: Int, height: Int, background: Boolean) {
        val active = playback ?: return
        if (!active.allowed()) return
        val side = minOf(width, height).toFloat()
        if (side <= 0f) return

        val state = canvas.save()
        canvas.translate((width - side) * .5f, (height - side) * .5f)
        canvas.scale(side / SIZE, side / SIZE)
        canvas.clipRect(0f, 0f, SIZE, SIZE)
        val frame = active.frame
        if (background) {
            paint.shader = active.bloom
            paint.alpha = ((frame.gather * .23f + frame.charge * .32f + frame.impact * .62f) * 255)
                .toInt().coerceAtMost(255)
            canvas.drawRect(0f, 0f, SIZE, SIZE, paint)
            paint.shader = null
            active.authored?.drawBehind(canvas, frame)
            active.atelier.drawBehind(canvas, frame)
        } else {
            val shader = hardware
            var usedAgsl = false
            if (Build.VERSION.SDK_INT >= 33 && canvas.isHardwareAccelerated && shader != null && active.masks != null) {
                try {
                    paint.color = Color.WHITE
                    paint.shader = shader.frame(frame, pose)
                    canvas.drawRect(0f, 0f, SIZE, SIZE, paint)
                    usedAgsl = true
                } catch (error: IllegalArgumentException) {
                    shaderUnavailable = true
                    hardware = null
                    Log.w(TAG, "AGSL draw failed; using Canvas", error)
                } finally {
                    paint.shader = null
                }
            }
            if (!usedAgsl) drawCanvasHalo(canvas, active, frame)
            if (!active.logged) {
                active.logged = true
                Log.i(TAG, if (usedAgsl) "EVOLUTION_AGSL" else "EVOLUTION_CANVAS")
                if (active.authored != null) Log.i(TAG, "EVOLUTION_ATLAS theme=${active.theme.name}")
            }
            active.authored?.drawFront(canvas, frame)
            active.atelier.drawFront(canvas, frame)
        }
        canvas.restoreToCount(state)
    }

    private fun drawCanvasHalo(canvas: Canvas, active: Playback, frame: StudioVfxFrame) {
        val masks = active.masks ?: return
        val strength = frame.charge * .72f + frame.impact * .27f
        if (strength < .02f) return
        paint.color = Color.WHITE
        paint.alpha = (strength.coerceAtMost(1f) * 255).toInt()
        paint.xfermode = screen
        paint.colorFilter = active.tint
        maskBounds.set(0f, 0f, SIZE, SIZE)
        val save = canvas.save()
        canvas.scale(pose.camera, pose.camera, CENTER_X, CAMERA_PIVOT_Y)
        canvas.translate(0f, pose.y - FEET_Y)
        canvas.scale(pose.xScale, pose.yScale, CENTER_X, FEET_Y)
        val progress = smooth(frame.time, 2.34f, 3.32f)
        paint.alpha = (strength.coerceAtMost(1f) * (1f - progress) * 255).toInt()
        canvas.drawBitmap(masks.base.halo, null, maskBounds, paint)
        paint.alpha = (strength.coerceAtMost(1f) * progress * 255).toInt()
        canvas.drawBitmap(masks.skin.halo, null, maskBounds, paint)
        canvas.restoreToCount(save)
        paint.colorFilter = null
        paint.xfermode = null
    }

    @TargetApi(33)
    private class HardwareGlow {
        private val shader = RuntimeShader(GLOW_SHADER)

        fun bind(active: Playback) {
            val masks = requireNotNull(active.masks)
            shader.setInputShader("baseDistance", distanceTexture(masks.base.distance))
            shader.setInputShader("skinDistance", distanceTexture(masks.skin.distance))
            shader.setInputShader("materialTexture", distanceTexture(StudioAtelierMotion.materialMap))
            shader.color("energyColor", active.theme.energy)
            shader.color("highlightColor", active.theme.glint)
        }

        fun frame(frame: StudioVfxFrame, pose: BodyPose): Shader {
            shader.setFloatUniform("timing", frame.time, frame.charge)
            shader.setFloatUniform("release", frame.impact, frame.release)
            shader.setFloatUniform("pose", pose.xScale, pose.yScale, pose.y, pose.camera)
            return shader
        }

        private fun RuntimeShader.color(name: String, argb: Int) {
            setFloatUniform(name, Color.red(argb) / 255f, Color.green(argb) / 255f, Color.blue(argb) / 255f)
        }

        private fun distanceTexture(bitmap: Bitmap) = BitmapShader(bitmap, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP)
            .apply { filterMode = BitmapShader.FILTER_MODE_LINEAR }
    }

    private class BodyPose {
        var xScale = 1f
        var yScale = 1f
        var y = FEET_Y
        var camera = 1f

        fun update(time: Float) {
            camera = cameraScale(time)
            xScale = StudioAtelierMotion.scale(time)
            yScale = xScale
            y = FEET_Y + StudioAtelierMotion.offsetY(time)
        }
    }

    companion object {
        // Anchor the punch just above the frame so the sprout has headroom.
        const val CAMERA_PIVOT_FRACTION = -.12f
        private const val TAG = "NuntiVfx"
        private const val SIZE = 768f
        private const val CAMERA_PIVOT_Y = SIZE * CAMERA_PIVOT_FRACTION
        private const val MAP_SIZE = 256
        private const val CENTER_X = 384f
        private const val CENTER_Y = 424f
        private const val FEET_Y = 721f
        private const val BURST = 3.30f
        private const val END = 3.98f

        fun decodeMasks(assets: AssetManager, skin: String): Masks? {
            if (skin != "sea" && skin != "city" && skin != "mountain") return null
            return runCatching {
                Masks(mask(assets, "nunti-motion/base.png"), mask(assets, "skin-v2/atelier/$skin/final.png"))
            }.onFailure { Log.w(TAG, "Silhouette masks unavailable", it) }.getOrNull()
        }

        fun decodeMasks(base: Bitmap, travel: Bitmap): Masks = Masks(mask(base),mask(travel))

        private fun mask(assets: AssetManager, path: String): Mask {
            val image = assets.open(path).use { requireNotNull(BitmapFactory.decodeStream(it)) }
            return try { mask(image) } finally { image.recycle() }
        }

        private fun mask(image: Bitmap): Mask {
            val sample = Bitmap.createScaledBitmap(image, MAP_SIZE, MAP_SIZE, true)
            val pixels = IntArray(MAP_SIZE * MAP_SIZE)
            sample.getPixels(pixels, 0, MAP_SIZE, 0, 0, MAP_SIZE, MAP_SIZE)
            if(sample !== image) sample.recycle()
            val inside = BooleanArray(pixels.size) { Color.alpha(pixels[it]) >= 112 }
            val inner = distance(inside, source = false)
            val outer = distance(inside, source = true)
            val outline = IntArray(pixels.size)
            for (i in pixels.indices) {
                val signed = (if (inside[i]) -inner[i] else outer[i]) / 3f
                val value = (128 + signed * 4).toInt().coerceIn(0, 255)
                pixels[i] = value shl 24
                val alpha = (exp(-abs(signed) * .31f) * 255).toInt()
                outline[i] = (alpha shl 24) or 0x00ffffff
            }
            return Mask(
                Bitmap.createBitmap(pixels, MAP_SIZE, MAP_SIZE, Bitmap.Config.ARGB_8888),
                Bitmap.createBitmap(outline, MAP_SIZE, MAP_SIZE, Bitmap.Config.ARGB_8888),
            )
        }

        // A two-pass chamfer map approximates Euclidean distance from the opaque edge.
        private fun distance(inside: BooleanArray, source: Boolean): IntArray {
            val result = IntArray(inside.size) { if (inside[it] == source) 0 else MAP_SIZE * 6 }
            for (y in 0 until MAP_SIZE) for (x in 0 until MAP_SIZE) {
                val i = y * MAP_SIZE + x
                if (x > 0) result[i] = minOf(result[i], result[i - 1] + 3)
                if (y > 0) {
                    result[i] = minOf(result[i], result[i - MAP_SIZE] + 3)
                    if (x > 0) result[i] = minOf(result[i], result[i - MAP_SIZE - 1] + 4)
                    if (x < MAP_SIZE - 1) result[i] = minOf(result[i], result[i - MAP_SIZE + 1] + 4)
                }
            }
            for (y in MAP_SIZE - 1 downTo 0) for (x in MAP_SIZE - 1 downTo 0) {
                val i = y * MAP_SIZE + x
                if (x < MAP_SIZE - 1) result[i] = minOf(result[i], result[i + 1] + 3)
                if (y < MAP_SIZE - 1) {
                    result[i] = minOf(result[i], result[i + MAP_SIZE] + 3)
                    if (x > 0) result[i] = minOf(result[i], result[i + MAP_SIZE - 1] + 4)
                    if (x < MAP_SIZE - 1) result[i] = minOf(result[i], result[i + MAP_SIZE + 1] + 4)
                }
            }
            return result
        }

        private fun smooth(value: Float, start: Float, end: Float): Float {
            val progress = ((value - start) / (end - start)).coerceIn(0f, 1f)
            return progress * progress * (3f - 2f * progress)
        }

        private fun mix(a: Float, b: Float, fraction: Float) = a + (b - a) * fraction

        private fun cameraScale(time: Float): Float {
            val hit = smooth(time, BURST - .03f, BURST + .07f) * (1f - smooth(time, BURST + .07f, BURST + .29f))
            val rebound = smooth(time, BURST + .15f, BURST + .30f) * (1f - smooth(time, BURST + .30f, BURST + .51f))
            return 1f + hit * .052f - rebound * .012f
        }

        private const val GLOW_SHADER = """
            uniform shader baseDistance;
            uniform shader skinDistance;
            uniform float2 timing;
            uniform float2 release;
            uniform float4 pose;
            uniform float3 energyColor;
            uniform float3 highlightColor;

            ${StudioAtelierMotion.MATERIAL_FIELD}

            float silhouette(float2 p) {
                float2 cameraCenter = float2(384.0, $CAMERA_PIVOT_Y);
                float2 feet = float2(384.0, 721.0);
                float2 local = cameraCenter + (p - cameraCenter) / pose.w;
                float2 registered = (local - float2(feet.x, pose.z)) / pose.xy + feet;
                float a = baseDistance.eval(registered / 3.0).a;
                float b = skinDistance.eval(registered / 3.0).a;
                float field = materialField(registered);
                float revealed = smoothstep(field-.026, field+.026, smoothstep(2.34,3.32,timing.x));
                return (mix(a, b, revealed) - 0.502) * 191.25;
            }

            half4 main(float2 p) {
                float time = timing.x;
                float charge = timing.y;
                float impact = release.x;
                if (charge + impact < 0.002) return half4(0.0);
                float2 delta = p - float2(384.0, 424.0);
                float2 refraction = float2(sin(p.y * 0.052 - time * 7.0), cos(p.x * 0.041 + time * 8.0));
                refraction *= charge * 2.9 + impact * 3.5;
                float d = silhouette(p + refraction);
                float core = exp2(-abs(d) * 0.44);
                float scatter = exp2(-abs(d) * 0.075);
                float faceClear = smoothstep(86.0, 159.0, length((p - float2(384.0, 274.0)) * float2(1.0, 1.45)));
                float rim = (core * 0.76 + scatter * 0.31) * (charge * 0.88 + impact * 0.16);
                float reflected = smoothstep(5.0, 36.0, -d) * faceClear * charge * charge * 0.10;
                float echo = 0.0;
                if (impact > 0.002) {
                    float2 displaced = p - delta * (0.045 + release.y * 0.16) + refraction;
                    echo = exp2(-abs(silhouette(displaced)) * 0.15) * impact * 0.29;
                }
                float light = clamp(rim * mix(0.54, 1.0, faceClear) + reflected + echo, 0.0, 0.92);
                float3 tint = mix(energyColor, highlightColor, clamp(core * charge + impact * 0.64, 0.0, 1.0));
                float2 margin = min(p, float2(768.0) - p);
                float2 edge = smoothstep(float2(0.0), float2(72.0), margin);
                return half4(tint * light, light) * edge.x * edge.y;
            }
        """
    }
}
