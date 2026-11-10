package ai.nunti.app.transformation

/** Pure timing and terminal-state policy. No vehicle state is synthesized here. */
enum class TransformationStyle { LIGHT_TRAIL, QUIET_COLOR }

data class TransformationFrame(
    val elapsedMs: Long,
    val road: Float,
    val scarf: Float,
    val pocket: Float,
    val expression: Float,
    val settle: Float,
    val trailOpacity: Float,
) {
    val complete: Boolean get() = elapsedMs >= TransformationTimeline.DURATION_MS
    val coreAlpha: Float get() = 1f
    val phase: String get() = when {
        complete -> "FINAL"
        elapsedMs >= 3400 -> "SETTLE"
        elapsedMs >= 2700 -> "EXPRESSION"
        elapsedMs >= 1700 -> "DESTINATION"
        elapsedMs >= 1300 -> "COLOR"
        elapsedMs >= 450 -> "ROUTE"
        else -> "BASE"
    }
}

object TransformationTimeline {
    const val DURATION_MS = 4000L

    fun at(elapsedMs: Long): TransformationFrame {
        val time = elapsedMs.coerceIn(0, DURATION_MS)
        return TransformationFrame(time,
            progress(time, 450, 1300), progress(time, 1300, 1900),
            progress(time, 1700, 2500), progress(time, 2850, 3050),
            progress(time, 3400, DURATION_MS),
            progress(time, 450, 550) * (1 - progress(time, 1200, 1300)))
    }

    private fun progress(time: Long, start: Long, end: Long): Float =
        easing(((time - start).toDouble() / (end - start)).coerceIn(0.0, 1.0)).toFloat()

    /** CSS/Compose cubic-bezier(.4, 0, .2, 1), solving x before evaluating y. */
    private fun easing(x: Double): Double {
        if (x <= 0.0 || x >= 1.0) return x
        var low = 0.0
        var high = 1.0
        repeat(24) {
            val t = (low + high) * .5
            val curveX = 3 * (1 - t) * (1 - t) * t * .4 + 3 * (1 - t) * t * t * .2 + t * t * t
            if (curveX < x) low = t else high = t
        }
        val t = (low + high) * .5
        return 3 * (1 - t) * t * t + t * t * t
    }
}

enum class PlaybackStatus { LOADING, BASE, RUNNING, SETTLED, FAILED }
enum class StopReason { NONE, COMPLETED, SKIPPED, REDUCED_MOTION, RESTRICTED, BACKGROUNDED, LOAD_FAILURE, CAPTURE }

data class TransformationState(
    val status: PlaybackStatus = PlaybackStatus.LOADING,
    val elapsedMs: Long = 0,
    val assetsReady: Boolean = false,
    val stopReason: StopReason = StopReason.NONE,
) {
    val running: Boolean get() = status == PlaybackStatus.RUNNING
    val finalVisible: Boolean get() = assetsReady && status == PlaybackStatus.SETTLED && elapsedMs >= TransformationTimeline.DURATION_MS
}

/** Only play() can enter RUNNING. Permission recovery and asset completion never resume. */
class TransformationPlayback {
    var state = TransformationState()
        private set
    private var startedAt = 0L

    fun loading() { state = TransformationState() }

    fun ready() {
        state = if (state.status == PlaybackStatus.LOADING) TransformationState(PlaybackStatus.BASE, assetsReady = true)
        else state.copy(assetsReady = true,
            elapsedMs = if (state.status == PlaybackStatus.SETTLED) TransformationTimeline.DURATION_MS else state.elapsedMs)
    }

    fun failed() { state = TransformationState(PlaybackStatus.FAILED, stopReason = StopReason.LOAD_FAILURE) }

    fun play(nowMs: Long, allowed: Boolean, reducedMotion: Boolean): Boolean {
        if (!allowed || !state.assetsReady) return false
        if (reducedMotion) { stop(StopReason.REDUCED_MOTION); return false }
        startedAt = nowMs
        state = TransformationState(PlaybackStatus.RUNNING, assetsReady = true)
        return true
    }

    fun advance(nowMs: Long, allowed: Boolean, foreground: Boolean, reducedMotion: Boolean) {
        if (!state.running) return
        when {
            !foreground -> stop(StopReason.BACKGROUNDED)
            !allowed -> stop(StopReason.RESTRICTED)
            reducedMotion -> stop(StopReason.REDUCED_MOTION)
            else -> {
                val elapsed = (nowMs - startedAt).coerceIn(state.elapsedMs, TransformationTimeline.DURATION_MS)
                state = state.copy(elapsedMs = elapsed)
                if (elapsed == TransformationTimeline.DURATION_MS) stop(StopReason.COMPLETED)
            }
        }
    }

    fun stop(reason: StopReason) {
        require(reason != StopReason.NONE)
        state = state.copy(status = PlaybackStatus.SETTLED,
            elapsedMs = if (state.assetsReady) TransformationTimeline.DURATION_MS else 0,
            stopReason = reason)
    }

    /** Frozen review frames are debug-only and require the same actual parked permission. */
    fun seek(elapsedMs: Long, allowed: Boolean): Boolean {
        if (!allowed || !state.assetsReady) return false
        state = state.copy(status = PlaybackStatus.SETTLED,
            elapsedMs = elapsedMs.coerceIn(0, TransformationTimeline.DURATION_MS), stopReason = StopReason.CAPTURE)
        return true
    }
}
