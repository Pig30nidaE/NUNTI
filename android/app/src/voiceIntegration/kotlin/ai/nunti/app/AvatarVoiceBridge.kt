package ai.nunti.app

import ai.nunti.avatar.AvatarSpec
import ai.nunti.avatar.TripPhase
import ai.nunti.emotion.EmotionSnapshot
import ai.nunti.tts.AvatarVoiceInput

/** DTO projection only. TTS owns approvals, speech generation, SDK calls, queue and audio policy. */
fun AvatarSpec.toVoiceInput() = AvatarVoiceInput(avatarId, identity.baseCharacterId, identity.voiceProfileId,
    persona = "COMPANION", voiceStyleHint = journey.voiceStyleHint)
fun EmotionSnapshot.toVoiceEmotion(sessionEpochMillis: Long) = ai.nunti.tts.EmotionSnapshot(
    emotionId, tripId, avatarId, ai.nunti.tts.Emotion.valueOf(emotion.name), sessionEpochMillis + since)
fun TripPhase.toVoicePhase(): ai.nunti.tts.TripPhase = when (this) {
    TripPhase.PRE_DRIVE -> ai.nunti.tts.TripPhase.PRE_TRIP
    TripPhase.DRIVING -> ai.nunti.tts.TripPhase.DRIVING
    TripPhase.POST_DRIVE -> ai.nunti.tts.TripPhase.POST_TRIP
}
