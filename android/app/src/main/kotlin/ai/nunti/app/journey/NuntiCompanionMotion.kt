package ai.nunti.app.journey

import kotlin.math.PI
import kotlin.math.sin

/** Parked-only poses in the common frontal rig. No inferred mood or per-frame random choices. */
internal object NuntiCompanionMotion {
    const val VERSION = "nunti-rig-1"
    val reactions = setOf("pat", "wave-left", "wave-right", "curious", "happy", "wink", "proud", "signature", "surprised", "nod", "sleepy", "stretch")

    class Pose {
        var head = 0f
        var leftArm = 0f
        var rightArm = 0f
        var leftLeg = 0f
        var rightLeg = 0f
        var lean = 0f
        var x = 0f
        var y = 0f
        var breath = 0f
        var gazeX = 0f
        var gazeY = 0f
        var blink = 0f
        var expression = 0
        var expressionAmount = 0f
        var action = "rest"
    }

    fun duration(reaction: String) = when (reaction) {
        "pat" -> 2.2f
        "wave-left", "wave-right", "wink", "signature" -> 2.8f
        "proud", "stretch" -> 3.6f
        "sleepy" -> 4.2f
        else -> 2.6f
    }

    fun sample(seconds: Float, reaction: String, progress: Float, focusX: Float, focusY: Float, out: Pose) {
        require(seconds.isFinite() && progress.isFinite() && focusX.isFinite() && focusY.isFinite())
        out.head = 0f; out.leftArm = 0f; out.rightArm = 0f
        out.leftLeg = 0f; out.rightLeg = 0f; out.lean = 0f; out.x = 0f; out.y = 0f
        out.breath = sin(seconds * 1.45f) * .004f
        out.gazeX = focusX.coerceIn(-1f, 1f); out.gazeY = focusY.coerceIn(-1f, 1f)
        out.blink = blink(seconds)
        out.expression = 0; out.expressionAmount = 0f; out.action = "rest"

        val phase = seconds % 53f
        if (reaction !in reactions) when {
            phase in 3f..6.8f -> {
                val amount = envelope((phase - 3f) / 3.8f)
                out.action = "look"; out.head = -5f * amount; out.gazeX -= .65f * amount
            }

            phase in 12f..16f -> {
                val amount = envelope((phase - 12f) / 4f)
                out.action = "weight-shift"; out.x = 4f * amount; out.lean = 1.5f * amount
                out.leftLeg = -4f * amount; out.rightLeg = 2f * amount; out.leftArm = -3f * amount
            }
            phase in 24f..28.5f -> gesture("stretch", (phase - 24f) / 4.5f, out)
            phase in 39f..43f -> {
                val amount = envelope((phase - 39f) / 4f)
                out.action = "look"; out.head = 4f * amount; out.gazeX += .6f * amount
            }
        }
        if (reaction in reactions) gesture(reaction, progress.coerceIn(0f, 1f), out)
        out.head = (out.head + focusX.coerceIn(-1f, 1f) * 3f).coerceIn(-10f, 10f)
        out.gazeX = out.gazeX.coerceIn(-1f, 1f)
        out.gazeY = out.gazeY.coerceIn(-1f, 1f)
    }

    private fun gesture(name: String, t: Float, out: Pose) {
        val amount = envelope(t)
        val prepare = sin(PI.toFloat() * (t / .19f).coerceIn(0f, 1f))
        val beat = sin(PI.toFloat() * 6f * ((t - .18f) / .58f).coerceIn(0f, 1f)) * amount
        out.action = if (amount > .001f) name else "rest"
        out.y += 2.5f * prepare
        when (name) {
            "pat" -> {
                out.head += 7f * amount; out.y += 3f * amount
                out.leftArm -= 5f * amount; out.rightArm += 5f * amount
                out.expression = 1; out.expressionAmount = amount * .65f
                out.blink = maxOf(out.blink, amount)
            }
            "wave-left", "wave-right", "wink", "signature" -> {
                if (name == "wave-left") out.leftArm += (31f * amount + 8f * beat)
                else out.rightArm -= (31f * amount + 8f * beat)
                out.head += (if (name == "wave-left") -4f else 4f) * amount
                out.expression = 1; out.expressionAmount = amount * .55f
            }
            "proud", "stretch" -> {
                out.leftArm += 21f * amount; out.rightArm -= 21f * amount
                out.y -= 5f * amount; out.leftLeg -= 2f * amount; out.rightLeg += 2f * amount
                out.blink = maxOf(out.blink, amount * .4f)
            }
            "curious" -> {
                out.head += 9f * amount; out.lean -= 1.6f * amount; out.gazeX += .5f * amount
                out.leftArm += 10f * amount; out.expression = 2; out.expressionAmount = amount * .65f
            }
            "happy" -> {
                out.leftArm += 15f * amount; out.rightArm -= 15f * amount
                out.head += beat * 2f; out.y -= (2f + sin(t * PI.toFloat() * 4f)) * amount
                out.expression = 1; out.expressionAmount = amount
            }
            "nod" -> { out.head += beat * 5f; out.gazeY += .25f * amount }
            "surprised" -> {
                out.leftArm -= 10f * amount; out.rightArm += 10f * amount
                out.y += 2f * amount; out.expression = 3; out.expressionAmount = amount
            }
            "sleepy" -> {
                out.head += 6f * amount; out.blink = maxOf(out.blink, amount * .92f)
                out.expression = 5; out.expressionAmount = amount
            }
        }
    }

    private fun envelope(t: Float) = smooth(t / .2f) * (1f - smooth((t - .7f) / .3f))
    private fun smooth(t: Float): Float { val x = t.coerceIn(0f, 1f); return x * x * (3f - 2f * x) }
    private fun blink(seconds: Float): Float {
        val phase = seconds % 8.7f
        return when {
            phase in 4.1f..4.38f -> sin((phase - 4.1f) / .28f * PI).toFloat().coerceAtLeast(0f)
            phase in 7.45f..7.65f -> sin((phase - 7.45f) / .2f * PI).toFloat().coerceAtLeast(0f)
            else -> 0f
        }
    }
}
