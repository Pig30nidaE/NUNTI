package ai.nunti.app.studio

import android.content.Context
import android.content.res.AssetManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.view.View
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/** The approved 768-square plates and their registered expression patches. */
internal class StudioCharacterAssets private constructor(
    val skin: String,
    val base: Bitmap,
    val travel: Bitmap,
    val face: List<Bitmap>,
) {
    companion object {
        private val faceNames = listOf(
            "blink-left", "blink-right", "wide", "happy-eyes", "happy-mouth", "blink-left-half", "blink-right-half",
        )

        fun load(assets: AssetManager, skin: String): StudioCharacterAssets {
            ai.nunti.app.journey.NuntiLifeMotion.prepare(assets)
            ai.nunti.app.journey.NuntiFaceRig.prepare(assets)
            require(skin == "base" || skin == "sea" || skin == "city" || skin == "mountain")
            val base = plate(assets, "nunti-motion/base.png")
            ai.nunti.app.journey.NuntiFaceRig.prepareSharedImage(base)
            ai.nunti.app.journey.NuntiPuppetParts.prepareShared(base)
            val travel = if (skin == "base") base else plate(assets, "skin-v2/atelier/$skin/final.png")
            if (skin != "base") StudioAtelierMotion.materialMap // Prepare off the UI thread.
            val face = if (skin == "base") faceNames.map { name -> bitmap(assets, "plates/expressions/base-$name.png") } else emptyList()
            return StudioCharacterAssets(skin, base, travel, face)
        }

        fun generated(context: Context, skin: String): StudioCharacterAssets {
            ai.nunti.app.journey.NuntiLifeMotion.prepare(context.assets)
            ai.nunti.app.journey.NuntiFaceRig.prepare(context.assets)
            val sha = NuntiSkinStyle.imageHash(skin)
            require(sha.matches(Regex("[0-9a-f]{64}")))
            val connection = ai.nunti.app.journey.JourneyAssets(context)
            val file = connection.image(sha)
            val bitmap = requireNotNull(BitmapFactory.decodeFile(file.path))
            require(bitmap.width == 768 && bitmap.height == 768)
            if (skin.startsWith("wardrobe-shared1-")) {
                val eyes = connection.rigEyes(sha, requireNotNull(NuntiSkinStyle.rigHash(skin))).map { eye ->
                    requireNotNull(BitmapFactory.decodeFile(eye.path))
                }
                try { ai.nunti.app.journey.NuntiFaceRig.prepareSharedImage(bitmap, eyes) }
                finally { eyes.forEach { it.recycle() } }
                ai.nunti.app.journey.NuntiPuppetParts.prepareShared(bitmap)
            }
            StudioAtelierMotion.materialMap
            if (!skin.startsWith("wardrobe-shared1-")) ai.nunti.app.journey.NuntiPuppetParts.prepare(context.assets,skin,bitmap)
            return StudioCharacterAssets(skin, plate(context.assets, "nunti-motion/base.png"), bitmap, emptyList())
        }

        private fun plate(assets: AssetManager, path: String): Bitmap =
            bitmap(assets, path).also { require(it.width == 768 && it.height == 768) }

        private fun bitmap(assets: AssetManager, path: String): Bitmap = assets.open(path).use {
            requireNotNull(BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply {
                inScaled = false
                inPreferredConfig = Bitmap.Config.ARGB_8888
            })) { "Unable to decode $path" }
        }
    }
}

/** Mutable sample of the original rig's authored property tracks. */
internal class StudioCharacterPose {
    var faceTime = 0f
    var faceReactionTime = 0f
    var faceReaction = "idle"
    var focusX = 0f
    var focusY = 0f
    var bodyY = 721f
        private set
    var scaleX = 1f
        private set
    var scaleY = 1f
        private set
    val rotation = FloatArray(6)
    var base = 1f
        private set
    var travel = 0f
        private set
    var resting = 0f
        private set
    val face = FloatArray(7)

    @Suppress("UNUSED_PARAMETER")
    fun reset(skin: String, phase: String) {
        faceReaction = phase
        bodyY = 721f
        scaleX = 1f
        scaleY = 1f
        rotation.fill(0f)
        base = 0f
        travel = 0f
        resting = 0f
        face.fill(0f)
        when (phase) {
            "base", "anticipation", "transform" -> base = 1f
            "reveal" -> travel = 1f
            else -> resting = 1f
        }
    }

    fun set(joint: Int, property: String, value: Float) {
        when (property) {
            "y" -> if (joint == 10) bodyY = value
            "scaleX" -> if (joint == 10) scaleX = value
            "scaleY" -> if (joint == 10) scaleY = value
            "rotation" -> if (joint in 11..16) rotation[joint - 11] = value
            "opacity" -> when (joint) {
                20 -> base = value
                21 -> travel = value
                26 -> resting = value
                in 51..57 -> face[joint - 51] = value
            }
        }
    }
}

/** Paints the registered character at the current stage pose. Playback belongs to the Studio host. */
internal class StudioCharacterCanvas(context: Context) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val stage = RectF(0f, 0f, SIZE, SIZE)
    private val patchRect = RectF()
    private val joints = Array(6) { Joint() }
    private val transformMesh = RigMesh(null)
    private var assets: StudioCharacterAssets? = null
    private var pose: StudioCharacterPose? = null
    private val atelier = StudioAtelierRenderer()
    private val companion = ai.nunti.app.journey.NuntiSharedRenderer()
    private var evolutionTime: Float? = null

    init {
        isClickable = false
        isFocusable = false
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO
    }

    fun show(assets: StudioCharacterAssets, pose: StudioCharacterPose) {
        this.assets = assets
        this.pose = pose
        evolutionTime = null
        invalidate()
    }

    fun showEvolution(assets: StudioCharacterAssets, pose: StudioCharacterPose, seconds: Float) {
        this.assets = assets
        this.pose = pose
        evolutionTime = seconds
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        val assets = assets ?: return
        val pose = pose ?: return
        val side = minOf(width, height).toFloat()
        if (side <= 0f) return

        val state = canvas.save()
        canvas.translate((width - side) * .5f, (height - side) * .5f)
        canvas.scale(side / SIZE, side / SIZE)
        canvas.clipRect(stage)
        if (assets.skin == "base" && evolutionTime == null) {
            companion.draw(canvas, assets.base, pose.faceTime / 60f, pose.faceReaction, pose.faceReactionTime, pose.focusX, pose.focusY)
            canvas.restoreToCount(state)
            return
        }
        if (assets.skin != "base") {
            atelier.draw(canvas, assets, evolutionTime, pose)
            canvas.restoreToCount(state)
            return
        }
        canvas.translate(0f, pose.bodyY - ROOT_Y)
        canvas.scale(pose.scaleX, pose.scaleY, CENTER_X, ROOT_Y)

        val bent = pose.rotation.any { it != 0f }
        val original = if (bent && (pose.base > 0f || pose.travel > 0f)) transformMesh else null
        if (bent) {
            moveJoints(pose.rotation)
            original?.deform(joints)
        }

        drawPlate(canvas, assets.travel, pose.resting, null)
        drawPlate(canvas, assets.travel, pose.travel, original)
        drawPlate(canvas, assets.base, pose.base, original)
        drawFace(canvas, assets, pose)
        canvas.restoreToCount(state)
    }

    private fun moveJoints(angle: FloatArray) {
        val head = joints[0]
        head.turn(angle[0], CENTER_X, HEAD_Y)
        joints[1].turn(angle[1], 293f, 425f)
        joints[2].turn(angle[2], 475f, 425f)
        joints[3].turn(angle[3], CENTER_X, 108f, head)
        joints[4].turn(angle[4], 217f, 278f, head)
        joints[5].turn(angle[5], 551f, 278f, head)
    }

    private fun drawPlate(canvas: Canvas, image: Bitmap?, opacity: Float, mesh: RigMesh?) {
        if (image == null || opacity <= 0f) return
        paint.alpha = alpha(opacity)
        if (mesh == null) {
            // Preserve the exact approved pixels when all joints are at rest.
            canvas.drawBitmap(image, null, stage, paint)
        } else {
            canvas.drawBitmapMesh(image, DIVISIONS, DIVISIONS, mesh.vertices, 0, null, 0, paint)
        }
    }

    private fun drawFace(canvas: Canvas, assets: StudioCharacterAssets, pose: StudioCharacterPose) {
        if (pose.face.none { it > 0f }) return
        val state = canvas.save()
        canvas.rotate(pose.rotation[0] * DEGREES_PER_RADIAN, CENTER_X, HEAD_Y)
        // Rive's first face node is the topmost, so Canvas draws the patches in reverse.
        for (index in pose.face.indices.reversed()) {
            val opacity = pose.face[index]
            if (opacity <= 0f) continue
            val bitmap = assets.face[index]
            val left = FACE_LEFT[index]
            val top = FACE_TOP[index]
            patchRect.set(left, top, left + bitmap.width, top + bitmap.height)
            paint.alpha = alpha(opacity)
            canvas.drawBitmap(bitmap, null, patchRect, paint)
        }
        canvas.restoreToCount(state)
    }

    private fun alpha(opacity: Float) = (opacity.coerceIn(0f, 1f) * 255f).roundToInt()

    private class Joint {
        private var c = 1f
        private var s = 0f
        private var xOffset = 0f
        private var yOffset = 0f

        fun turn(angle: Float, centerX: Float, centerY: Float, parent: Joint? = null) {
            val cosine = cos(angle)
            val sine = sin(angle)
            val dx = centerX - cosine * centerX + sine * centerY
            val dy = centerY - sine * centerX - cosine * centerY
            if (parent == null) {
                c = cosine
                s = sine
                xOffset = dx
                yOffset = dy
            } else {
                c = parent.c * cosine - parent.s * sine
                s = parent.s * cosine + parent.c * sine
                xOffset = parent.x(dx, dy)
                yOffset = parent.y(dx, dy)
            }
        }

        fun x(x: Float, y: Float) = c * x - s * y + xOffset
        fun y(x: Float, y: Float) = s * x + c * y + yOffset
    }

    private class RigMesh(restSkin: String?) {
        val vertices = FloatArray(VERTEX_COUNT * 2)
        private val weights = FloatArray(VERTEX_COUNT * JOINT_COUNT)

        init {
            // drawBitmapMesh supplies uniform UVs. Sample the original rig weights on
            // that grid, so the unposed texture is never resampled with mismatched UVs.
            for (row in 0..DIVISIONS) for (column in 0..DIVISIONS) {
                val x = column * CELL
                val y = row * CELL
                val index = (row * (DIVISIONS + 1) + column) * JOINT_COUNT
                if (y <= 412f) {
                    val head = 1f - smooth(y, 372f, 412f)
                    val sprout = 1f - smooth(y, 77f, 115f)
                    val ear = if (restSkin == null) 0f else {
                        (head - sprout) * smooth(y, 155f, 225f) * (1f - smooth(y, 325f, 378f))
                    }
                    val left = ear * (1f - smooth(x, 210f, 260f))
                    val right = ear * smooth(x, 508f, 558f)
                    weights[index] = head - sprout - left - right
                    weights[index + 3] = sprout
                    weights[index + 4] = left
                    weights[index + 5] = right
                } else {
                    val sleeve = smooth(y, 412f, 494f) * (1f - smooth(y, 554f, 595f))
                    weights[index + 1] = sleeve * (1f - if (restSkin == null) smooth(x, 251f, 307f) else smooth(x, 217f, 258f))
                    weights[index + 2] = sleeve * when (restSkin) {
                        null -> smooth(x, 461f, 517f)
                        "sea" -> smooth(x, 503f, 530f)
                        else -> smooth(x, 509f, 548f)
                    }
                }
            }
        }

        fun deform(joints: Array<Joint>) {
            for (row in 0..DIVISIONS) for (column in 0..DIVISIONS) {
                val index = row * (DIVISIONS + 1) + column
                val x = column * CELL
                val y = row * CELL
                var outX = x
                var outY = y
                for (joint in joints.indices) {
                    val weight = weights[index * JOINT_COUNT + joint]
                    if (weight == 0f) continue
                    val transform = joints[joint]
                    outX += (transform.x(x, y) - x) * weight
                    outY += (transform.y(x, y) - y) * weight
                }
                vertices[index * 2] = outX
                vertices[index * 2 + 1] = outY
            }
        }

        private fun smooth(value: Float, low: Float, high: Float): Float {
            val t = ((value - low) / (high - low)).coerceIn(0f, 1f)
            return t * t * (3f - 2f * t)
        }
    }

    private companion object {
        const val SIZE = 768f
        const val CENTER_X = 384f
        const val ROOT_Y = 721f
        const val HEAD_Y = 395f
        const val DIVISIONS = 24
        const val CELL = SIZE / DIVISIONS
        const val JOINT_COUNT = 6
        const val VERTEX_COUNT = (DIVISIONS + 1) * (DIVISIONS + 1)
        const val DEGREES_PER_RADIAN = 57.29578f
        val FACE_LEFT = floatArrayOf(260f, 413f, 260f, 260f, 347f, 260f, 413f)
        val FACE_TOP = floatArrayOf(220f, 220f, 214f, 220f, 300f, 220f, 220f)
    }
}
