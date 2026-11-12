package ai.nunti.app.journey

import kotlin.math.cos
import kotlin.math.sin

/** Bind-space weights are fixed per rig version; frames apply five joint matrices without allocation. */
internal class NuntiCompanionMesh {
    val vertices = FloatArray((GRID + 1) * (GRID + 1) * 2)
    private val bind = FloatArray(vertices.size)
    private val weights = Array(5) { FloatArray(vertices.size / 2) }
    private val cosine = FloatArray(5)
    private val sine = FloatArray(5)
    private val pivotX = floatArrayOf(384f, 287f, 488f, 329f, 437f)
    private val pivotY = floatArrayOf(370f, 414f, 414f, 590f, 590f)

    init {
        var index = 0
        for (row in 0..GRID) for (col in 0..GRID) {
            val x = col * 768f / GRID; val y = row * 768f / GRID
            bind[index * 2] = x; bind[index * 2 + 1] = y
            weights[0][index] = 1f - smooth((y - 354f) / 51f)
            val sleeve = smooth((y - 395f) / 48f) * (1f - smooth((y - 564f) / 32f))
            // Below the shoulder, keep the coat pocket and crossbody bag on the torso.
            val armEdge = 275f - smooth((y - 440f) / 55f) * 45f
            weights[1][index] = sleeve * (1f - smooth((x - armEdge + 20f) / 40f))
            weights[2][index] = sleeve * (1f - smooth((768f - x - armEdge + 20f) / 40f))
            val leg = smooth((y - 565f) / 65f)
            weights[3][index] = leg * (1f - smooth((x - 373f) / 22f))
            weights[4][index] = leg * smooth((x - 373f) / 22f)
            index++
        }
        bind.copyInto(vertices)
    }

    fun deform(angles: FloatArray, rigidArms: Boolean = false) {
        require(angles.size >= 5)
        for (joint in 0..4) {
            require(angles[joint].isFinite())
            val radians = if (rigidArms && joint in 1..2) 0f else angles[joint] * .017453293f
            cosine[joint] = cos(radians) - 1f; sine[joint] = sin(radians)
        }
        for (index in weights[0].indices) {
            val i = index * 2; val x = bind[i]; val y = bind[i + 1]
            var px = x; var py = y
            for (joint in 0..4) {
                val weight = weights[joint][index]
                if (weight <= 0f) continue
                val dx = x - pivotX[joint]; val dy = y - pivotY[joint]
                px += (dx * cosine[joint] - dy * sine[joint]) * weight
                py += (dx * sine[joint] + dy * cosine[joint]) * weight
            }
            vertices[i] = px; vertices[i + 1] = py
        }
    }

    private fun smooth(t: Float): Float { val x = t.coerceIn(0f, 1f); return x * x * (3f - 2f * x) }
    companion object { const val GRID = 40 }
}
