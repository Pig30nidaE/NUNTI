package ai.nunti.score.journey

import ai.nunti.score.DrivingEvent
import ai.nunti.score.Emotion
import ai.nunti.score.ScoreEngine
import ai.nunti.score.ScoreReport
import ai.nunti.score.VehicleSample

enum class JourneySource { LIVE, DEMO }

/** Consumers acknowledge key, rather than replaying feedback on every snapshot. */
data class JourneyFeedback(val key: String, val kind: Emotion, val text: String)

data class JourneySnapshot(
    val report: ScoreReport,
    val emotion: Emotion,
    val sampleCount: Int,
    val elapsedMs: Long,
    val finished: Boolean,
    val currentSample: VehicleSample?,
    val feedback: JourneyFeedback?,
)

/**
 * One character accompanies one journey. Sample timestamps are monotonic elapsed milliseconds
 * from that journey's start, including interruptions; they are never compressed on resume.
 * All methods are synchronized so service callbacks cannot race finish(). No Android dependency.
 */
class JourneySession(
    val sessionId: String,
    val characterId: String,
    val routePlanId: String?,
    val source: JourneySource,
    val startedAtEpochMs: Long,
    private val engine: ScoreEngine = ScoreEngine(),
) {
    private val samples = mutableListOf<VehicleSample>()
    private val events = linkedSetOf<DrivingEvent>()
    private var actualSampleCount = 0
    private var currentSample: VehicleSample? = null
    private var finished = false
    private var feedbackSequence = 0L
    private var feedback: JourneyFeedback? = null
    private var lastSpokenEmotion = Emotion.NEUTRAL
    private var lastFeedbackMs: Long? = null
    private var state = JourneySnapshot(engine.evaluate(emptyList(), emptyList()), Emotion.NEUTRAL, 0, 0, false, null, null)

    init {
        require(sessionId.isNotBlank() && characterId.isNotBlank())
        require(routePlanId == null || routePlanId.isNotBlank())
        require(startedAtEpochMs >= 0)
    }

    /** Finished sessions ignore late input and return the same final snapshot. Exact retries are idempotent. */
    @Synchronized
    fun add(sample: VehicleSample, events: List<DrivingEvent> = emptyList()): JourneySnapshot {
        if (finished) return state
        require(sample.tMs >= 0 && sample.tMs >= state.elapsedMs) { "Sample time must not go backwards" }
        require(events.all { it.tMs in 0..sample.tMs }) { "Events must belong to the observed journey interval" }
        val last = samples.lastOrNull()
        if (last?.tMs == sample.tMs) {
            require(last == sample || currentSample == null) { "Conflicting samples at the same timestamp" }
            if (last != sample) samples[samples.lastIndex] = sample
            if (currentSample == null) actualSampleCount++
        } else {
            samples += sample
            actualSampleCount++
        }
        currentSample = sample
        this.events += events
        return refresh()
    }

    /** Insert an unknown boundary. Neither pause duration nor a restart becomes fabricated driving. */
    @Synchronized
    fun interrupt(elapsedMs: Long): JourneySnapshot {
        if (finished) return state
        require(elapsedMs >= state.elapsedMs) { "Interruption time must not go backwards" }
        val unknown = VehicleSample(elapsedMs)
        if (samples.lastOrNull()?.tMs == elapsedMs) samples[samples.lastIndex] = unknown else samples += unknown
        currentSample = null
        return refresh()
    }

    @Synchronized
    fun snapshot(): JourneySnapshot = state

    /** Final feedback has one stable key, even when finish is retried or there was no usable signal. */
    @Synchronized
    fun finish(): JourneySnapshot {
        if (finished) return state
        finished = true
        return refresh(finalFeedback = true)
    }

    private fun refresh(finalFeedback: Boolean = false): JourneySnapshot {
        val report = engine.evaluate(samples, events.toList())
        val elapsed = samples.lastOrNull()?.tMs ?: 0L
        val emotion = if (report.total == null || (!finished && currentSample == null)) Emotion.NEUTRAL
            else engine.emotion(report, finished)
        val cooldownPassed = lastFeedbackMs?.let { elapsed - it >= FEEDBACK_COOLDOWN_MS } ?: true
        if (finalFeedback || (emotion != lastSpokenEmotion && cooldownPassed && currentSample != null)) {
            val text = if (finalFeedback && report.total == null) "이번 여정은 수신한 정보가 부족해 점수를 매기지 않았어요."
                else emotion.line
            feedback = JourneyFeedback("$sessionId:${++feedbackSequence}", emotion, text)
            lastSpokenEmotion = emotion
            lastFeedbackMs = elapsed
        }
        state = JourneySnapshot(report, emotion, actualSampleCount, elapsed, finished, currentSample, feedback)
        return state
    }

    private companion object { const val FEEDBACK_COOLDOWN_MS = 30_000L }
}
