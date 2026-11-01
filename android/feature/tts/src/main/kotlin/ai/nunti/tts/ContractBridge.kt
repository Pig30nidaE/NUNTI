package ai.nunti.tts

import java.time.Instant

/** DTO projection of SERVER v1. Deserialization/authentication stay at the host boundary. */
data class WireSpeechRequest(val schemaVersion: String, val requestId: String, val tripId: String,
    val avatarId: String, val text: String, val voiceProfileId: String, val emotion: String,
    val tripPhase: String, val priority: String, val requestedAt: String, val expiresAt: String,
    val contentSource: String, val speechPurpose: String? = null,
    val sourceEventId: String? = null, val emotionId: String? = null)
data class SpeechEvidence(val approvedText: Boolean = false, val verifiedEventIds: Set<String> = emptySet(),
    val userInitiated: Boolean = false, val allowMock: Boolean = false)
sealed interface SpeechMappingResult {
    data class Accepted(val speech: ApprovedSpeech) : SpeechMappingResult
    data class Rejected(val requestId: String, val tripId: String, val reason: String) : SpeechMappingResult
}
data class WireVoiceProfile(val schemaVersion: String, val voiceProfileId: String, val locale: String,
    val persona: String, val speakingStyle: String, val preferredVoiceId: String?, val supportedControls: List<String>)
object SpeechContractBridge {
    fun fromVoiceProfile(w: WireVoiceProfile): VoiceProfile {
        require(w.schemaVersion == "1.0") { "UNSUPPORTED_SCHEMA" }
        return VoiceProfile(w.voiceProfileId, w.locale, w.preferredVoiceId, w.speakingStyle,
            w.supportedControls.mapNotNull { name -> Control.entries.firstOrNull { it.name == name } }.toSet())
    }
    /** Unknown tokens, malformed timestamps or versions cannot crash the playback host. */
    fun tryFromWire(w: WireSpeechRequest, avatar: AvatarVoiceInput, snapshot: EmotionSnapshot?,
        evidence: SpeechEvidence): SpeechMappingResult = try {
        SpeechMappingResult.Accepted(fromWire(w, avatar, snapshot, evidence))
    } catch (_: IllegalArgumentException) {
        SpeechMappingResult.Rejected(w.requestId, w.tripId, "INVALID_WIRE_REQUEST")
    } catch (_: java.time.DateTimeException) {
        SpeechMappingResult.Rejected(w.requestId, w.tripId, "INVALID_TIMESTAMP")
    } catch (_: ArithmeticException) {
        SpeechMappingResult.Rejected(w.requestId, w.tripId, "INVALID_TIMESTAMP")
    }

    fun fromWire(w: WireSpeechRequest, avatar: AvatarVoiceInput, snapshot: EmotionSnapshot?,
        evidence: SpeechEvidence): ApprovedSpeech {
        require(w.schemaVersion == "1.0") { "UNSUPPORTED_SCHEMA" }
        require(w.contentSource in setOf("MOCK", "TEMPLATE", "EXTERNAL_REPORT")) { "UNKNOWN_CONTENT_SOURCE" }
        require(w.contentSource != "MOCK" || evidence.allowMock) { "MOCK_DISABLED" }
        val phase = TripPhase.valueOf(w.tripPhase)
        val purpose = w.speechPurpose?.let { ContentSource.valueOf(it) } ?: when {
            w.contentSource == "TEMPLATE" && phase == TripPhase.PRE_TRIP -> ContentSource.PRE_DRIVE_GREETING
            w.contentSource == "EXTERNAL_REPORT" && phase == TripPhase.POST_TRIP -> ContentSource.POST_DRIVE_REPORT
            else -> throw IllegalArgumentException("MISSING_PURPOSE")
        }
        val trusted = evidence.approvedText && when (purpose) {
            ContentSource.VERIFIED_EVENT_RESPONSE -> w.sourceEventId != null && w.sourceEventId in evidence.verifiedEventIds
            ContentSource.USER_INITIATED -> evidence.userInitiated
            ContentSource.POST_DRIVE_REPORT -> w.contentSource == "EXTERNAL_REPORT" || (w.contentSource == "MOCK" && evidence.allowMock)
            ContentSource.PRE_DRIVE_GREETING -> w.contentSource == "TEMPLATE" || (w.contentSource == "MOCK" && evidence.allowMock)
        }
        return ApprovedSpeech(SpeechRequest(w.requestId, w.tripId, w.avatarId, w.text,
            Emotion.valueOf(w.emotion), w.voiceProfileId, phase, Priority.valueOf(w.priority),
            Instant.parse(w.requestedAt).toEpochMilli(), Instant.parse(w.expiresAt).toEpochMilli(),
            purpose, w.emotionId, w.sourceEventId), avatar, snapshot, trusted)
    }
}
