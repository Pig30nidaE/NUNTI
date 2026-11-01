package ai.nunti.tts

/** Descriptive only: no unverified acoustic control is sent to the SDK. */
class EmotionVoiceMapper {
    fun style(emotion: Emotion): String = when (emotion) {
        Emotion.NEUTRAL -> "natural"
        Emotion.RELAXED -> "calm"
        Emotion.CONCERNED -> "brief-concern"
        Emotion.STARTLED -> "brief-surprise"
        Emotion.RELIEVED -> "relief"
        Emotion.JOYFUL -> "warm-joy"
    }
}
class VoiceProfileManager(profiles: List<VoiceProfile> = listOf(VoiceProfile())) {
    private val fallback = VoiceProfile()
    private val profiles = profiles.associateBy { it.voiceProfileId }
    // Fixed default speaker across route/persona changes. Approved speaker selection is a product-wide setting.
    fun resolve(id: String?, emotion: Emotion, capabilities: ProviderCapabilities): AppliedVoiceProfile {
        val profile = profiles[id] ?: fallback
        require(profile.locale in capabilities.locales) { "UNSUPPORTED_LOCALE" }
        val speaker = profile.preferredVoiceId?.takeIf {
            Control.SPEAKER in capabilities.controls && it in capabilities.verifiedSpeakerIds
        }
        val applied = setOf(Control.LOCALE) + if (speaker != null) setOf(Control.SPEAKER) else emptySet()
        return AppliedVoiceProfile(id, profile.voiceProfileId, profile.locale, speaker,
            EmotionVoiceMapper().style(emotion), applied,
            profile.supportedControls - applied + if (profile.preferredVoiceId != null && speaker == null)
                setOf(Control.SPEAKER) else emptySet(), id != profile.voiceProfileId)
    }
}
class SpeechRequestBuilder(private val profiles: VoiceProfileManager = VoiceProfileManager()) {
    fun build(input: ApprovedSpeech, capabilities: ProviderCapabilities, now: Long): PreparedSpeech {
        val r = input.request
        require(listOf(r.requestId, r.tripId, r.avatarId).all { it.matches(Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")) }) { "INVALID_ID" }
        require(r.text.isNotBlank()) { "EMPTY_TEXT" }
        require(r.text.codePointCount(0, r.text.length) <= 2000) { "TEXT_TOO_LONG" }
        require(!r.text.any { it.isISOControl() && it !in "\n\t\r" }) { "INVALID_TEXT" }
        require(input.contentVerified) { "UNVERIFIED_CONTENT" }
        require(r.expiresAt > now && r.expiresAt > r.requestedAt) { "EXPIRED" }
        require(r.requestedAt >= 0 && r.requestedAt <= now && r.expiresAt - r.requestedAt <= 120_000) { "INVALID_TTL" }
        require(input.avatar.avatarId == r.avatarId) { "AVATAR_MISMATCH" }
        require(input.avatar.voiceProfileId == r.voiceProfileId) { "PROFILE_MISMATCH" }
        if (r.contentSource == ContentSource.VERIFIED_EVENT_RESPONSE) {
            require(!r.sourceEventId.isNullOrBlank()) { "MISSING_EVENT_EVIDENCE" }
        }
        input.snapshot?.let {
            require(it.tripId == r.tripId && it.avatarId == r.avatarId && it.emotion == r.emotion &&
                it.emotionId == r.emotionId && it.occurredAt <= r.requestedAt) { "EMOTION_MISMATCH" }
        } ?: require(r.emotion == Emotion.NEUTRAL && r.emotionId == null) { "MISSING_EMOTION" }
        val validPhase = when (r.contentSource) {
            ContentSource.PRE_DRIVE_GREETING -> r.tripPhase == TripPhase.PRE_TRIP
            ContentSource.POST_DRIVE_REPORT -> r.tripPhase == TripPhase.POST_TRIP
            ContentSource.VERIFIED_EVENT_RESPONSE -> r.tripPhase in setOf(TripPhase.DRIVING, TripPhase.STOPPED)
            ContentSource.USER_INITIATED -> true
        }
        require(validPhase) { "SOURCE_PHASE_MISMATCH" }
        // Preserve the exact supplied text, including finalText. No score/event interpretation or rewriting.
        return PreparedSpeech(r, profiles.resolve(r.voiceProfileId, r.emotion, capabilities))
    }
}
