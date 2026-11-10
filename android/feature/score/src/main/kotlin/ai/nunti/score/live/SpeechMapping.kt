package ai.nunti.score.live

import ai.nunti.score.Emotion
import ai.nunti.tts.ApprovedSpeech
import ai.nunti.tts.AvatarVoiceInput
import ai.nunti.tts.ContentSource
import ai.nunti.tts.EmotionSnapshot
import ai.nunti.tts.Priority
import ai.nunti.tts.SpeechRequest
import ai.nunti.tts.SpeechStatus
import ai.nunti.tts.TripPhase
import ai.nunti.tts.Emotion as VoiceEmotion

/** [PleosSpeechSink] 의 순수 부분 (Android 의존 없음, JVM 단위 테스트 대상). */
internal object SpeechMapping {
    const val TTL_MS = 30_000L

    fun voiceEmotion(emotion: Emotion): VoiceEmotion = when (emotion) {
        Emotion.NEUTRAL -> VoiceEmotion.NEUTRAL
        Emotion.WORRY -> VoiceEmotion.CONCERNED
        Emotion.RELIEF -> VoiceEmotion.RELIEVED
        Emotion.JOY -> VoiceEmotion.JOYFUL
    }

    /**
     * 사건·감정은 이 앱의 ScoreEngine 이 직접 감지했으므로 contentVerified = true. 외부 입력이 아니다.
     * 시각 [nowMs] 는 epoch ms.
     */
    fun approvedSpeech(
        text: String, utteranceId: String, emotion: Emotion,
        tripId: String, avatarId: String, profileId: String, avatar: AvatarVoiceInput, nowMs: Long,
    ): ApprovedSpeech {
        val voiceEmotion = voiceEmotion(emotion)
        val snapshot = EmotionSnapshot("emo-$utteranceId", tripId, avatarId, voiceEmotion, nowMs)
        return ApprovedSpeech(
            SpeechRequest(utteranceId, tripId, avatarId, text, voiceEmotion, profileId, TripPhase.DRIVING,
                Priority.NORMAL, nowMs, nowMs + TTL_MS, ContentSource.VERIFIED_EVENT_RESPONSE,
                snapshot.emotionId, utteranceId),
            avatar, snapshot, contentVerified = true,
        )
    }

    /** 화면 표시용 "STATUS" 또는 "STATUS:REASON". */
    fun describe(status: SpeechStatus, reason: String?): String = status.name + (reason?.let { ":$it" } ?: "")

    /** 거절·실패만 로그로 남긴다 (QUEUE_FULL, DUPLICATE_TEXT, 주행 중 거부 등 이유 포함). */
    fun shouldLog(status: SpeechStatus): Boolean = status == SpeechStatus.REJECTED || status == SpeechStatus.FAILED
}
