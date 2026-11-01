package ai.nunti.tts

enum class Permission { UNKNOWN, ALLOWED, DENIED }
enum class VehicleMotion { UNKNOWN, PARKED, STOPPED, MOVING }
enum class AudioActivity { UNKNOWN, QUIET, BUSY }
data class PlaybackContext(val tripId: String? = null, val phase: TripPhase? = null,
    val observedAtMonotonicMs: Long = Long.MIN_VALUE, val voiceEnabled: Boolean = false,
    val foreground: Boolean = false, val suspended: Boolean = true,
    val motion: VehicleMotion = VehicleMotion.UNKNOWN, val uxRestrictionsKnown: Boolean = false,
    val requiresDistractionOptimization: Boolean = true, val activeRestrictions: Int = 0,
    val appAllowedWhileDriving: Permission = Permission.UNKNOWN,
    val speechPermission: Permission = Permission.UNKNOWN,
    val call: AudioActivity = AudioActivity.UNKNOWN, val navigation: AudioActivity = AudioActivity.UNKNOWN,
    val criticalAudio: AudioActivity = AudioActivity.UNKNOWN)

class SpeechPlaybackPolicy(val maxStateAgeMs: Long = 5_000, val drivingGapMs: Long = 15_000,
    val repeatWindowMs: Long = 60_000, val maxDrivingCharacters: Int = 80) {
    fun isDriving(c: PlaybackContext) = c.phase in setOf(TripPhase.DRIVING, TripPhase.STOPPED) ||
        c.motion != VehicleMotion.PARKED || c.requiresDistractionOptimization
    /** Null means eligible to request focus. UX bits alone do not imply TTS authorization. */
    fun rejection(r: SpeechRequest, c: PlaybackContext, epoch: Long, mono: Long,
        lastStart: Long?, lastSameText: Long?, alreadyActive: Boolean = false): String? {
        if (epoch >= r.expiresAt) return "EXPIRED"
        if (c.tripId != r.tripId || c.phase != r.tripPhase) return "TRIP_PHASE_MISMATCH"
        if (c.observedAtMonotonicMs > mono || c.observedAtMonotonicMs < mono - maxStateAgeMs) return "STALE_PLATFORM_STATE"
        if (!c.voiceEnabled) return "VOICE_DISABLED"
        if (!c.foreground || c.suspended) return "INACTIVE"
        if (!c.uxRestrictionsKnown || c.motion == VehicleMotion.UNKNOWN) return "UNKNOWN_PLATFORM_STATE"
        if (c.speechPermission != Permission.ALLOWED) return "SPEECH_NOT_ALLOWED"
        if (c.call != AudioActivity.QUIET || c.navigation != AudioActivity.QUIET || c.criticalAudio != AudioActivity.QUIET) return "OTHER_AUDIO"
        if (isDriving(c)) {
            if (c.appAllowedWhileDriving != Permission.ALLOWED) return "DRIVING_NOT_ALLOWED"
            if (r.contentSource !in setOf(ContentSource.VERIFIED_EVENT_RESPONSE, ContentSource.USER_INITIATED)) return "DRIVING_SOURCE"
            if (r.priority == Priority.LOW) return "LOW_PRIORITY_DRIVING"
            if (r.text.codePointCount(0, r.text.length) > maxDrivingCharacters) return "DRIVING_TEXT_TOO_LONG"
            if (!alreadyActive && lastStart != null && mono - lastStart < drivingGapMs) return "COOLDOWN"
        }
        if (!alreadyActive && lastSameText != null && mono - lastSameText < repeatWindowMs) return "REPEATED_TEXT"
        return null
    }
}
