package ai.nunti.emotion

import ai.nunti.navigation.sha256
import java.util.Properties

enum class Emotion { NEUTRAL, RELAXED, CONCERNED, STARTLED, RELIEVED, JOYFUL }
enum class EventType { HARSH_BRAKING, SAFETY_CONCERN, STABLE_DRIVING, SAFETY_RECOVERED, POSITIVE_FEEDBACK, TRIP_ENDED, UNKNOWN }
data class DrivingEvent(val eventId: String, val tripId: String, val type: EventType, val occurredAt: Long,
    val verified: Boolean, val confidence: Double?, val incidentId: String? = null, val recoveryOfEventId: String? = null)
data class EmotionSnapshot(val emotionId: String, val tripId: String, val avatarId: String, val emotion: Emotion,
    val since: Long, val triggeredByEventId: String?, val confidence: Double, val reason: String)
data class PendingTransition(val emotion: Emotion, val event: DrivingEvent)
data class EmotionState(val snapshot: EmotionSnapshot, val startedAt: Long, val now: Long,
    val timeline: List<EmotionSnapshot>, val seenEvents: Set<String> = emptySet(), val seenIncidents: Set<String> = emptySet(),
    val lastAcceptedAt: Long = Long.MIN_VALUE, val lastAcceptedPriority: Int = -1,
    val lastTypeAt: Map<EventType, Long> = emptyMap(), val lastNegativeAt: Map<Emotion, Long> = emptyMap(),
    val stableSince: Long? = null, val lastStableAt: Long? = null, val lastVerifiedAt: Long? = null,
    val activeCause: String? = null, val pending: PendingTransition? = null, val endedAt: Long? = null)
data class Reduction(val state: EmotionState, val disposition: String)
data class TripEmotionSummary(val tripId: String, val avatarId: String, val finalEmotion: Emotion,
    val dominantEmotion: Emotion, val durationMillis: Map<Emotion, Long>, val timeline: List<EmotionSnapshot>,
    val recoveryCount: Int, val processedEventCount: Int, val endedAt: Long?)

data class EmotionRules(val confidenceMin: Double, val eventExpiry: Long, val debounce: Long, val cooldown: Long,
    val minimumDwell: Long, val stableWindow: Long, val stableGap: Long, val startledMax: Long,
    val concernedMax: Long, val reliefDwell: Long, val dataExpiry: Long) {
    init {
        require(confidenceMin.isFinite() && confidenceMin in 0.0..1.0)
        require(listOf(eventExpiry, debounce, cooldown, minimumDwell, stableWindow, stableGap,
            startledMax, concernedMax, reliefDwell, dataExpiry).all { it > 0 && it <= 3_600_000 })
        require(startledMax >= minimumDwell && concernedMax >= minimumDwell && reliefDwell >= minimumDwell)
    }
    companion object {
        fun from(p: Properties) = EmotionRules(p.getProperty("confidence.min").toDouble(),
            p.getProperty("event.expiry.ms").toLong(), p.getProperty("debounce.ms").toLong(),
            p.getProperty("cooldown.ms").toLong(), p.getProperty("minimum.dwell.ms").toLong(),
            p.getProperty("stable.window.ms").toLong(), p.getProperty("stable.gap.ms").toLong(),
            p.getProperty("startled.max.ms").toLong(), p.getProperty("concerned.max.ms").toLong(),
            p.getProperty("relief.dwell.ms").toLong(), p.getProperty("data.expiry.ms").toLong())
    }
}

/** Pure reducer. Host supplies monotonic session-relative milliseconds and persists the returned state.
 * Wall-clock wire timestamps are converted by the adapter; never use score as an emotion proxy.
 */
class EmotionMachine(val rules: EmotionRules) {
    fun start(tripId: String, avatarId: String, now: Long = 0): EmotionState {
        require(tripId.isNotBlank() && avatarId.isNotBlank() && now >= 0)
        val snapshot = snapshot(tripId, avatarId, Emotion.NEUTRAL, now, null, 0.0, "NEW_TRIP")
        return EmotionState(snapshot, now, now, listOf(snapshot))
    }
    private fun snapshot(trip: String, avatar: String, emotion: Emotion, at: Long, event: String?, confidence: Double, reason: String) =
        EmotionSnapshot("emotion-${sha256("$trip|$avatar|$at|$emotion|$event|$reason").take(24)}", trip, avatar, emotion, at, event, confidence, reason)
    private fun priority(e: Emotion) = when (e) {
        Emotion.STARTLED -> 4; Emotion.CONCERNED -> 3; Emotion.RELIEVED -> 2; Emotion.JOYFUL -> 1
        Emotion.RELAXED -> 1; Emotion.NEUTRAL -> 0
    }
    private fun target(type: EventType) = when (type) {
        EventType.HARSH_BRAKING -> Emotion.STARTLED; EventType.SAFETY_CONCERN -> Emotion.CONCERNED
        EventType.STABLE_DRIVING -> Emotion.RELAXED; EventType.SAFETY_RECOVERED -> Emotion.RELIEVED
        EventType.POSITIVE_FEEDBACK -> Emotion.JOYFUL; else -> Emotion.NEUTRAL
    }
    private fun transition(s: EmotionState, e: Emotion, at: Long, event: DrivingEvent?, reason: String): EmotionState {
        if (s.snapshot.emotion == e) return s.copy(pending = null)
        val snap = snapshot(s.snapshot.tripId, s.snapshot.avatarId, e, at, event?.eventId, event?.confidence ?: 0.0, reason)
        val negative = e in setOf(Emotion.STARTLED, Emotion.CONCERNED)
        return s.copy(snapshot = snap, timeline = s.timeline + snap, pending = null,
            lastNegativeAt = if (negative) s.lastNegativeAt + (e to at) else s.lastNegativeAt,
            activeCause = if (negative) event?.eventId else null)
    }
    fun tick(state: EmotionState, now: Long): EmotionState {
        require(now >= state.now) { "Clock must not move backwards" }
        if (state.endedAt != null) return state
        var s = state.copy(now = now)
        val pending = s.pending
        if (pending != null) {
            val due = s.snapshot.since + rules.minimumDwell
            if (now - pending.event.occurredAt > rules.eventExpiry) s = s.copy(pending = null)
            else if (now >= due) s = transition(s, pending.emotion, maxOf(due, pending.event.occurredAt), pending.event, "DWELL_COMPLETED")
        }
        val age = now - s.snapshot.since
        when (s.snapshot.emotion) {
            Emotion.STARTLED -> if (age >= rules.startledMax) s = transition(s, Emotion.NEUTRAL, s.snapshot.since + rules.startledMax, null, "STARTLE_TIMEOUT_NO_RECOVERY_CLAIM")
            Emotion.CONCERNED -> if (age >= rules.concernedMax) s = transition(s, Emotion.NEUTRAL, s.snapshot.since + rules.concernedMax, null, "CONCERN_TIMEOUT")
            Emotion.RELIEVED -> if (age >= rules.reliefDwell) s = transition(s, Emotion.RELAXED, s.snapshot.since + rules.reliefDwell, null, "VERIFIED_RECOVERY_SETTLED")
            else -> Unit
        }
        val verifiedAt = s.lastVerifiedAt
        if (verifiedAt != null && now - verifiedAt >= rules.dataExpiry && s.snapshot.emotion != Emotion.NEUTRAL) {
            s = transition(s, Emotion.NEUTRAL, maxOf(s.snapshot.since, verifiedAt + rules.dataExpiry), null, "DATA_EXPIRED")
        }
        return s
    }
    fun accept(state: EmotionState, event: DrivingEvent, now: Long): Reduction {
        var s = tick(state, now)
        fun result(reason: String) = Reduction(s, reason)
        if (s.endedAt != null) return result("TRIP_ENDED")
        if (event.tripId != s.snapshot.tripId) return result("WRONG_TRIP")
        if (event.eventId.isBlank() || event.occurredAt < s.startedAt) return result("INVALID_EVENT")
        if (event.occurredAt > now) return result("FUTURE_EVENT")
        if (now - event.occurredAt > rules.eventExpiry) return result("EXPIRED_EVENT")
        if (event.eventId in s.seenEvents) return result("DUPLICATE_EVENT")
        s = s.copy(seenEvents = s.seenEvents + event.eventId)
        if (!event.verified || event.confidence == null || !event.confidence.isFinite() || event.confidence !in rules.confidenceMin..1.0) return result("UNVERIFIED_EVENT")
        if (event.type == EventType.UNKNOWN) return result("UNKNOWN_EVENT")
        val target = target(event.type)
        val p = priority(target)
        if (event.occurredAt < s.lastAcceptedAt || (event.type != EventType.TRIP_ENDED && event.occurredAt == s.lastAcceptedAt && p <= s.lastAcceptedPriority)) return result("OUT_OF_ORDER")
        val negative = target in setOf(Emotion.STARTLED, Emotion.CONCERNED)
        if (negative && event.incidentId != null && event.incidentId in s.seenIncidents) return result("DUPLICATE_INCIDENT")
        if (event.type == EventType.TRIP_ENDED) {
            s = s.copy(endedAt = now, pending = null, lastVerifiedAt = now)
            return result("TRIP_ENDED")
        }
        val previousTypeAt = s.lastTypeAt[event.type]
        if (previousTypeAt != null && event.occurredAt - previousTypeAt < rules.debounce) return result("DEBOUNCED")
        s = s.copy(lastTypeAt = s.lastTypeAt + (event.type to event.occurredAt), lastAcceptedAt = event.occurredAt,
            lastAcceptedPriority = p, lastVerifiedAt = now,
            seenIncidents = if (negative && event.incidentId != null) s.seenIncidents + event.incidentId else s.seenIncidents)
        if (negative) {
            s = s.copy(stableSince = null, lastStableAt = null, pending = null)
            val last = s.lastNegativeAt[target]
            if (last != null && now - last < rules.cooldown) return result("COOLDOWN")
        }
        var desired = target
        if (event.type == EventType.STABLE_DRIVING) {
            val start = if (s.lastStableAt != null && event.occurredAt - s.lastStableAt <= rules.stableGap) s.stableSince ?: event.occurredAt else event.occurredAt
            s = s.copy(stableSince = start, lastStableAt = event.occurredAt)
            if (event.occurredAt - start < rules.stableWindow) return result("HYSTERESIS_PENDING")
            if (s.snapshot.emotion in setOf(Emotion.CONCERNED, Emotion.STARTLED)) desired = Emotion.RELIEVED
            else if (s.snapshot.emotion == Emotion.RELIEVED) return result("RELIEF_DWELL")
        }
        if (event.type == EventType.SAFETY_RECOVERED) {
            if (s.activeCause == null || event.recoveryOfEventId != s.activeCause) return result("UNMATCHED_RECOVERY")
        }
        // Positive feedback cannot erase an unresolved concern.
        if (event.type == EventType.POSITIVE_FEEDBACK && s.activeCause != null) return result("UNRESOLVED_CONCERN")
        if (s.snapshot.emotion == desired) return result("NO_CHANGE")
        if (now - s.snapshot.since < rules.minimumDwell && priority(desired) <= priority(s.snapshot.emotion)) {
            s = s.copy(pending = PendingTransition(desired, event))
            return result("MINIMUM_DWELL")
        }
        s = transition(s, desired, now, event, "VERIFIED_${event.type}")
        return result("TRANSITIONED")
    }
    fun summary(state: EmotionState): TripEmotionSummary {
        val end = state.endedAt ?: state.now
        val durations = Emotion.entries.associateWith { emotion -> state.timeline.mapIndexed { i, snap ->
            if (snap.emotion == emotion) ((state.timeline.getOrNull(i + 1)?.since ?: end) - snap.since).coerceAtLeast(0) else 0L
        }.sum() }
        return TripEmotionSummary(state.snapshot.tripId, state.snapshot.avatarId, state.snapshot.emotion,
            durations.entries.sortedWith(compareByDescending<Map.Entry<Emotion, Long>> { it.value }.thenBy { it.key.name }).first().key,
            durations, state.timeline, state.timeline.count { it.emotion == Emotion.RELIEVED }, state.seenEvents.size, state.endedAt)
    }
}
