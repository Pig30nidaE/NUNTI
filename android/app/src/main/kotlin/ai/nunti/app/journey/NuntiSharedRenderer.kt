package ai.nunti.app.journey

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import kotlin.math.exp

/** Registered frontal body mesh and rigid limb layers preserve source hands and props. */
internal class NuntiSharedRenderer {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val mesh = NuntiCompanionMesh()
    private val pose = NuntiCompanionMotion.Pose()
    private val face = NuntiFaceRig()
    private var lastTime = -1f
    private var gazeX = 0f
    private var gazeY = 0f
    private val angles = FloatArray(6)
    private val targets = FloatArray(6)

    fun draw(canvas: Canvas, image: Bitmap, time: Float, reaction: String, progress: Float,
        focusX: Float = 0f, focusY: Float = 0f, animated: Boolean = true) {
        if (!animated) {
            lastTime = -1f; angles.fill(0f); gazeX = 0f; gazeY = 0f
            canvas.drawBitmap(image, 0f, 0f, paint)
            return
        }
        val dt = if (lastTime < 0f || time < lastTime) 1f else (time - lastTime).coerceIn(0f, .1f)
        lastTime = time
        NuntiCompanionMotion.sample(time, reaction, progress, focusX, focusY, pose)
        val blend = (1f - exp(-dt * 12f)).coerceIn(0f, 1f)
        gazeX += (pose.gazeX - gazeX) * blend
        gazeY += (pose.gazeY - gazeY) * blend
        targets[0] = pose.head; targets[1] = pose.leftArm; targets[2] = pose.rightArm
        targets[3] = pose.leftLeg; targets[4] = pose.rightLeg; targets[5] = pose.lean
        for (i in angles.indices) angles[i] += (targets[i] - angles[i]) * blend
        val parts = NuntiPuppetParts.get(image)
        val articulated = parts != null && (kotlin.math.abs(angles[1]) > .05f || kotlin.math.abs(angles[2]) > .05f)
        mesh.deform(angles, rigidArms = articulated)
        val saved = canvas.save()
        canvas.translate(pose.x, pose.y)
        canvas.scale(1f + pose.breath, 1f + pose.breath, 384f, 721f)
        canvas.rotate(angles[5], 384f, 650f)
        canvas.drawBitmapMesh(if (articulated) checkNotNull(parts).body else image,
            NuntiCompanionMesh.GRID, NuntiCompanionMesh.GRID, mesh.vertices, 0, null, 0, paint)
        if (articulated) {
            val limbs = checkNotNull(parts)
            var savedArm = canvas.save()
            canvas.rotate(angles[1],limbs.leftPivot[0],limbs.leftPivot[1])
            canvas.drawBitmap(limbs.left,limbs.leftX,limbs.leftY,paint); canvas.restoreToCount(savedArm)
            savedArm = canvas.save()
            canvas.rotate(angles[2],limbs.rightPivot[0],limbs.rightPivot[1])
            canvas.drawBitmap(limbs.right,limbs.rightX,limbs.rightY,paint); canvas.restoreToCount(savedArm)
        }
        canvas.rotate(angles[0], 384f, 370f)
        face.draw(canvas, image, "shared", pose.expression, pose.expressionAmount, pose.blink, gazeX, gazeY, preserveSource = true)
        canvas.restoreToCount(saved)
    }

}
