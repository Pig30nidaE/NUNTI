package ai.nunti.emotion

import ai.nunti.navigation.sha256

/**
 * 주행 이벤트를 받아 아바타의 감정을 정하는 순수 reducer.
 * 호스트가 단조 증가하는 세션 상대 시간(ms)을 넣고, 돌려받은 상태를 저장한다. 벽시계 시간은 어댑터에서 변환한다.
 * 점수를 감정의 대용으로 쓰지 않는다.
 *
 * 이벤트 하나는 [accept] 의 단계를 순서대로 통과하며, 어느 단계에서든 [Disposition] 과 함께 멈춘다.
 * 단계의 순서가 결과를 바꾼다 (예: 중복 방지 목록은 신뢰도 검사 전에 기록된다). 순서를 바꾸면 안 된다.
 * 규칙(이벤트→감정, 우선순위)은 [EventType] 과 [Emotion] 에 있다.
 */
class EmotionMachine(val rules: EmotionRules) {

    fun start(tripId: String, avatarId: String, now: Long = 0): EmotionState {
        require(tripId.isNotBlank() && avatarId.isNotBlank() && now >= 0)
        val first = snapshot(tripId, avatarId, Emotion.NEUTRAL, now, null, 0.0, TransitionReason.NEW_TRIP)
        return EmotionState(first, now, now, listOf(first))
    }

    // ---- 시간이 흐를 때 ----

    /** 이벤트 없이 시간만 흐를 때: 대기 중인 전환, 감정 유지 시간 만료, 오래된 데이터를 처리한다. */
    fun tick(state: EmotionState, now: Long): EmotionState {
        require(now >= state.now) { "Clock must not move backwards" }
        if (state.endedAt != null) return state
        return state.copy(now = now)
            .let { applyPendingTransition(it, now) }
            .let { expireTimedEmotion(it, now) }
            .let { expireStaleData(it, now) }
    }

    /** 최소 유지 시간 때문에 미뤄 둔 전환을 시간이 되면 적용하고, 이벤트가 너무 오래되면 버린다. */
    private fun applyPendingTransition(s: EmotionState, now: Long): EmotionState {
        val pending = s.pending ?: return s
        val due = s.snapshot.since + rules.minimumDwell
        return when {
            now - pending.event.occurredAt > rules.eventExpiry -> s.copy(pending = null)
            now >= due -> transition(s, pending.emotion, maxOf(due, pending.event.occurredAt), pending.event, TransitionReason.DWELL_COMPLETED)
            else -> s
        }
    }

    /** 놀람·걱정은 회복 없이 중립으로, 안도는 편안으로 시간이 되면 돌아간다. */
    private fun expireTimedEmotion(s: EmotionState, now: Long): EmotionState {
        val age = now - s.snapshot.since
        val since = s.snapshot.since
        return when (s.snapshot.emotion) {
            Emotion.STARTLED -> if (age >= rules.startledMax)
                transition(s, Emotion.NEUTRAL, since + rules.startledMax, null, TransitionReason.STARTLE_TIMEOUT_NO_RECOVERY_CLAIM) else s
            Emotion.CONCERNED -> if (age >= rules.concernedMax)
                transition(s, Emotion.NEUTRAL, since + rules.concernedMax, null, TransitionReason.CONCERN_TIMEOUT) else s
            Emotion.RELIEVED -> if (age >= rules.reliefDwell)
                transition(s, Emotion.RELAXED, since + rules.reliefDwell, null, TransitionReason.VERIFIED_RECOVERY_SETTLED) else s
            else -> s
        }
    }

    /** 확인된 이벤트가 오래 없으면 중립으로 돌아간다. */
    private fun expireStaleData(s: EmotionState, now: Long): EmotionState {
        val verifiedAt = s.lastVerifiedAt ?: return s
        if (now - verifiedAt < rules.dataExpiry || s.snapshot.emotion == Emotion.NEUTRAL) return s
        return transition(s, Emotion.NEUTRAL, maxOf(s.snapshot.since, verifiedAt + rules.dataExpiry), null, TransitionReason.DATA_EXPIRED)
    }

    // ---- 이벤트가 올 때 ----

    /** 단계가 이어지는 중([Next]) 인지, 결과를 내고 멈췄는지([Stop]). [desired] 는 지금까지 정해진 목표 감정. */
    private sealed interface Stage {
        data class Next(val state: EmotionState, val desired: Emotion) : Stage
        data class Stop(val reduction: Reduction) : Stage
    }

    private fun Stage.Next.stop(disposition: Disposition): Stage = Stage.Stop(Reduction(state, disposition))
    private inline fun Stage.then(step: (Stage.Next) -> Stage): Stage = if (this is Stage.Next) step(this) else this

    fun accept(state: EmotionState, event: DrivingEvent, now: Long): Reduction =
        when (val outcome = Stage.Next(tick(state, now), event.type.target)
            .then { admit(it, event, now) }
            .then { requireTrusted(it, event) }
            .then { requireOrder(it, event) }
            .then { closeTrip(it, event, now) }
            .then { debounce(it, event) }
            .then { record(it, event, now) }
            .then { applyCooldown(it, event, now) }
            .then { settleStableDriving(it, event) }
            .then { requireMatchingRecovery(it, event) }
            .then { requireNoOpenConcern(it, event) }
            .then { decide(it, event, now) }) {
            is Stage.Stop -> outcome.reduction
            is Stage.Next -> error("accept() must end with a decision")
        }

    /** 여정·시간·중복 검사. 통과하면 이 이벤트 ID 를 "본 것"으로 기록한다 (이후 검사에서 거부돼도 기록은 남는다). */
    private fun admit(f: Stage.Next, e: DrivingEvent, now: Long): Stage {
        val s = f.state
        val rejection = when {
            s.endedAt != null -> Disposition.TRIP_ENDED
            e.tripId != s.snapshot.tripId -> Disposition.WRONG_TRIP
            e.eventId.isBlank() || e.occurredAt < s.startedAt -> Disposition.INVALID_EVENT
            e.occurredAt > now -> Disposition.FUTURE_EVENT
            now - e.occurredAt > rules.eventExpiry -> Disposition.EXPIRED_EVENT
            e.eventId in s.seenEvents -> Disposition.DUPLICATE_EVENT
            else -> null
        }
        return if (rejection != null) f.stop(rejection) else f.copy(state = s.copy(seenEvents = s.seenEvents + e.eventId))
    }

    /** 확인된 이벤트, 충분한 신뢰도, 알려진 종류만 받는다. */
    private fun requireTrusted(f: Stage.Next, e: DrivingEvent): Stage {
        val confidence = e.confidence
        val trusted = e.verified && confidence != null && confidence.isFinite() && confidence in rules.confidenceMin..1.0
        return when {
            !trusted -> f.stop(Disposition.UNVERIFIED_EVENT)
            e.type == EventType.UNKNOWN -> f.stop(Disposition.UNKNOWN_EVENT)
            else -> f
        }
    }

    /** 이미 처리한 것보다 오래된 이벤트와, 같은 사건(incident)의 부정 이벤트 반복을 거부한다. */
    private fun requireOrder(f: Stage.Next, e: DrivingEvent): Stage {
        val s = f.state
        val target = e.type.target
        val outOfOrder = e.occurredAt < s.lastAcceptedAt ||
            (e.type != EventType.TRIP_ENDED && e.occurredAt == s.lastAcceptedAt && target.priority <= s.lastAcceptedPriority)
        if (outOfOrder) return f.stop(Disposition.OUT_OF_ORDER)
        val repeatsIncident = target.negative && e.incidentId != null && e.incidentId in s.seenIncidents
        return if (repeatsIncident) f.stop(Disposition.DUPLICATE_INCIDENT) else f
    }

    private fun closeTrip(f: Stage.Next, e: DrivingEvent, now: Long): Stage {
        if (e.type != EventType.TRIP_ENDED) return f
        return f.copy(state = f.state.copy(endedAt = now, pending = null, lastVerifiedAt = now)).stop(Disposition.TRIP_ENDED)
    }

    private fun debounce(f: Stage.Next, e: DrivingEvent): Stage {
        val previous = f.state.lastTypeAt[e.type]
        return if (previous != null && e.occurredAt - previous < rules.debounce) f.stop(Disposition.DEBOUNCED) else f
    }

    /** 받아들인 이벤트의 시각·종류·우선순위를 기록한다. */
    private fun record(f: Stage.Next, e: DrivingEvent, now: Long): Stage {
        val s = f.state
        val newIncident = if (e.type.target.negative && e.incidentId != null) s.seenIncidents + e.incidentId else s.seenIncidents
        return f.copy(state = s.copy(lastTypeAt = s.lastTypeAt + (e.type to e.occurredAt), lastAcceptedAt = e.occurredAt,
            lastAcceptedPriority = e.type.target.priority, lastVerifiedAt = now, seenIncidents = newIncident))
    }

    /** 부정 이벤트는 안정 주행 누적을 끊고 대기 전환을 취소하며, 같은 부정 감정의 쿨다운을 적용한다. */
    private fun applyCooldown(f: Stage.Next, e: DrivingEvent, now: Long): Stage {
        val target = e.type.target
        if (!target.negative) return f
        val cleared = f.copy(state = f.state.copy(stableSince = null, lastStableAt = null, pending = null))
        val last = cleared.state.lastNegativeAt[target]
        return if (last != null && now - last < rules.cooldown) cleared.stop(Disposition.COOLDOWN) else cleared
    }

    /** 안정 주행은 일정 시간 이어져야 반영한다. 걱정·놀람 뒤라면 목표 감정이 안도로 바뀐다. */
    private fun settleStableDriving(f: Stage.Next, e: DrivingEvent): Stage {
        if (e.type != EventType.STABLE_DRIVING) return f
        val s = f.state
        val continues = s.lastStableAt != null && e.occurredAt - s.lastStableAt <= rules.stableGap
        val start = if (continues) s.stableSince ?: e.occurredAt else e.occurredAt
        val updated = f.copy(state = s.copy(stableSince = start, lastStableAt = e.occurredAt))
        if (e.occurredAt - start < rules.stableWindow) return updated.stop(Disposition.HYSTERESIS_PENDING)
        return when (s.snapshot.emotion) {
            Emotion.CONCERNED, Emotion.STARTLED -> updated.copy(desired = Emotion.RELIEVED)
            Emotion.RELIEVED -> updated.stop(Disposition.RELIEF_DWELL)
            else -> updated
        }
    }

    /** 회복은 지금 걱정·놀람의 원인 이벤트를 가리킬 때만 받는다. */
    private fun requireMatchingRecovery(f: Stage.Next, e: DrivingEvent): Stage {
        if (e.type != EventType.SAFETY_RECOVERED) return f
        val cause = f.state.activeCause
        return if (cause == null || e.recoveryOfEventId != cause) f.stop(Disposition.UNMATCHED_RECOVERY) else f
    }

    /** 해결되지 않은 걱정·놀람이 있으면 긍정 피드백으로 지우지 않는다. */
    private fun requireNoOpenConcern(f: Stage.Next, e: DrivingEvent): Stage =
        if (e.type == EventType.POSITIVE_FEEDBACK && f.state.activeCause != null) f.stop(Disposition.UNRESOLVED_CONCERN) else f

    /** 마지막 단계: 바꿀 것이 없으면 NO_CHANGE, 최소 유지 시간 안이면 대기, 아니면 전환한다. */
    private fun decide(f: Stage.Next, e: DrivingEvent, now: Long): Stage {
        val s = f.state
        val current = s.snapshot.emotion
        if (current == f.desired) return f.stop(Disposition.NO_CHANGE)
        if (now - s.snapshot.since < rules.minimumDwell && f.desired.priority <= current.priority) {
            return f.copy(state = s.copy(pending = PendingTransition(f.desired, e))).stop(Disposition.MINIMUM_DWELL)
        }
        val reason = checkNotNull(e.type.transitionReason) { "${e.type} cannot change the emotion" }
        return Stage.Stop(Reduction(transition(s, f.desired, now, e, reason), Disposition.TRANSITIONED))
    }

    // ---- 공통 ----

    private fun transition(s: EmotionState, to: Emotion, at: Long, event: DrivingEvent?, reason: TransitionReason): EmotionState {
        if (s.snapshot.emotion == to) return s.copy(pending = null)
        val next = snapshot(s.snapshot.tripId, s.snapshot.avatarId, to, at, event?.eventId, event?.confidence ?: 0.0, reason)
        return s.copy(snapshot = next, timeline = s.timeline + next, pending = null,
            lastNegativeAt = if (to.negative) s.lastNegativeAt + (to to at) else s.lastNegativeAt,
            activeCause = if (to.negative) event?.eventId else null)
    }

    /** 감정 ID 는 (여정, 아바타, 시각, 감정, 원인 이벤트, 이유)의 해시다. 이유의 이름이 바뀌면 ID 가 바뀐다. */
    private fun snapshot(trip: String, avatar: String, emotion: Emotion, at: Long, event: String?, confidence: Double, reason: TransitionReason) =
        EmotionSnapshot("emotion-${sha256("$trip|$avatar|$at|$emotion|$event|$reason").take(24)}", trip, avatar, emotion, at, event, confidence, reason)

    fun summary(state: EmotionState): TripEmotionSummary {
        val end = state.endedAt ?: state.now
        val durations = Emotion.entries.associateWith { emotion ->
            state.timeline.mapIndexed { i, snap ->
                if (snap.emotion == emotion) ((state.timeline.getOrNull(i + 1)?.since ?: end) - snap.since).coerceAtLeast(0) else 0L
            }.sum()
        }
        val dominant = durations.entries.sortedWith(compareByDescending<Map.Entry<Emotion, Long>> { it.value }.thenBy { it.key.name }).first().key
        return TripEmotionSummary(state.snapshot.tripId, state.snapshot.avatarId, state.snapshot.emotion, dominant, durations,
            state.timeline, state.timeline.count { it.emotion == Emotion.RELIEVED }, state.seenEvents.size, state.endedAt)
    }
}
