package ai.nunti.emotion

/** 아바타가 보일 수 있는 감정. [priority] 가 클수록 먼저 표시된다 (같은 시각의 이벤트 충돌과 최소 유지 시간에 쓰인다). */
enum class Emotion(val priority: Int, val negative: Boolean = false) {
    NEUTRAL(0),
    RELAXED(1),
    CONCERNED(3, negative = true),
    STARTLED(4, negative = true),
    RELIEVED(2),
    JOYFUL(1),
}

/** 감정을 바꾸는 이유. 감정 ID 의 해시 입력이자 저장 형식이므로 이름(name)을 바꾸면 기존 기록과 ID 가 달라진다. */
enum class TransitionReason {
    NEW_TRIP,
    VERIFIED_HARSH_BRAKING,
    VERIFIED_SAFETY_CONCERN,
    VERIFIED_STABLE_DRIVING,
    VERIFIED_SAFETY_RECOVERED,
    VERIFIED_POSITIVE_FEEDBACK,
    DWELL_COMPLETED,
    STARTLE_TIMEOUT_NO_RECOVERY_CLAIM,
    CONCERN_TIMEOUT,
    VERIFIED_RECOVERY_SETTLED,
    DATA_EXPIRED,
    MOCK_PREVIEW,
    MOCK_RUNTIME_PROBE,
}

/**
 * 주행 이벤트의 종류와, 그 이벤트가 가리키는 감정 ([target]) · 실제로 전환될 때의 이유 ([transitionReason]).
 * 새 이벤트를 추가하려면 여기 한 줄과 필요한 경우 [TransitionReason] 만 바꾸면 된다.
 * 주행 종료와 알 수 없음은 감정을 바꾸지 않으므로 [transitionReason] 이 없다.
 */
enum class EventType(val target: Emotion, val transitionReason: TransitionReason? = null) {
    HARSH_BRAKING(Emotion.STARTLED, TransitionReason.VERIFIED_HARSH_BRAKING),
    SAFETY_CONCERN(Emotion.CONCERNED, TransitionReason.VERIFIED_SAFETY_CONCERN),
    STABLE_DRIVING(Emotion.RELAXED, TransitionReason.VERIFIED_STABLE_DRIVING),
    SAFETY_RECOVERED(Emotion.RELIEVED, TransitionReason.VERIFIED_SAFETY_RECOVERED),
    POSITIVE_FEEDBACK(Emotion.JOYFUL, TransitionReason.VERIFIED_POSITIVE_FEEDBACK),
    TRIP_ENDED(Emotion.NEUTRAL),
    UNKNOWN(Emotion.NEUTRAL),
}

/** [EmotionMachine.accept] 가 이벤트 하나를 어떻게 처리했는지. 이름(name)이 저장·시험·로그에 그대로 쓰인다. */
enum class Disposition {
    /** 감정이 바뀌었다. */
    TRANSITIONED,
    /** 이미 같은 감정이라 바뀐 것이 없다. */
    NO_CHANGE,
    /** 최소 유지 시간이 지나지 않아 전환을 대기열에 넣었다. */
    MINIMUM_DWELL,
    /** 안정 주행이 아직 충분히 이어지지 않았다 (히스테리시스). */
    HYSTERESIS_PENDING,
    /** 이미 안도 상태라 다시 안도로 바꾸지 않는다. */
    RELIEF_DWELL,
    /** 여정이 끝났다. */
    TRIP_ENDED,
    WRONG_TRIP,
    INVALID_EVENT,
    FUTURE_EVENT,
    EXPIRED_EVENT,
    DUPLICATE_EVENT,
    DUPLICATE_INCIDENT,
    /** 확인되지 않았거나 신뢰도가 기준 미만이다. */
    UNVERIFIED_EVENT,
    UNKNOWN_EVENT,
    OUT_OF_ORDER,
    /** 같은 종류가 너무 빨리 반복되었다. */
    DEBOUNCED,
    /** 같은 부정 감정이 쿨다운 안에 반복되었다. */
    COOLDOWN,
    /** 해결 대상이 되는 걱정·놀람 원인과 맞지 않는 회복이다. */
    UNMATCHED_RECOVERY,
    /** 해결되지 않은 걱정이 있어 긍정 피드백을 받지 않는다. */
    UNRESOLVED_CONCERN,
}

data class DrivingEvent(val eventId: String, val tripId: String, val type: EventType, val occurredAt: Long,
    val verified: Boolean, val confidence: Double?, val incidentId: String? = null, val recoveryOfEventId: String? = null)
data class EmotionSnapshot(val emotionId: String, val tripId: String, val avatarId: String, val emotion: Emotion,
    val since: Long, val triggeredByEventId: String?, val confidence: Double, val reason: TransitionReason)
data class PendingTransition(val emotion: Emotion, val event: DrivingEvent)
data class EmotionState(val snapshot: EmotionSnapshot, val startedAt: Long, val now: Long,
    val timeline: List<EmotionSnapshot>, val seenEvents: Set<String> = emptySet(), val seenIncidents: Set<String> = emptySet(),
    val lastAcceptedAt: Long = Long.MIN_VALUE, val lastAcceptedPriority: Int = -1,
    val lastTypeAt: Map<EventType, Long> = emptyMap(), val lastNegativeAt: Map<Emotion, Long> = emptyMap(),
    val stableSince: Long? = null, val lastStableAt: Long? = null, val lastVerifiedAt: Long? = null,
    val activeCause: String? = null, val pending: PendingTransition? = null, val endedAt: Long? = null)
data class Reduction(val state: EmotionState, val disposition: Disposition)
data class TripEmotionSummary(val tripId: String, val avatarId: String, val finalEmotion: Emotion,
    val dominantEmotion: Emotion, val durationMillis: Map<Emotion, Long>, val timeline: List<EmotionSnapshot>,
    val recoveryCount: Int, val processedEventCount: Int, val endedAt: Long?)
