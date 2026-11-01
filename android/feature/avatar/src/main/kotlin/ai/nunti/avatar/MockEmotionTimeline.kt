package ai.nunti.avatar

import ai.nunti.emotion.*

/** Replays actual reducer inputs; UI never maps a score to an expression. */
object MockEmotionTimeline {
    fun run(avatarId: String): List<EmotionState> {
        val machine = EmotionMachine(EmotionRules.from(loadProperties("emotion.properties")))
        var state = machine.start("mock-emotion-trip", avatarId)
        val frames = mutableListOf(state)
        fun event(id: String, type: EventType, at: Long, recovery: String? = null) {
            state = machine.accept(state, DrivingEvent(id, "mock-emotion-trip", type, at, true, .95,
                recoveryOfEventId = recovery), at).state
        }
        event("stable-0", EventType.STABLE_DRIVING, 0)
        event("stable-1500", EventType.STABLE_DRIVING, 1500)
        event("stable-3000", EventType.STABLE_DRIVING, 3000); frames += state
        event("braking", EventType.HARSH_BRAKING, 6000); frames += state
        event("recovered", EventType.SAFETY_RECOVERED, 9000, "braking"); frames += state
        state = machine.tick(state, 12000); frames += state
        return frames
    }
}
