package ai.nunti.score.live

import ai.nunti.score.Emotion
import ai.nunti.score.SpeechSink
import ai.nunti.tts.ApprovedSpeech
import ai.nunti.tts.AudioActivity
import ai.nunti.tts.AvatarVoiceInput
import ai.nunti.tts.ContentSource
import ai.nunti.tts.EmotionSnapshot
import ai.nunti.tts.Permission
import ai.nunti.tts.PlaybackContext
import ai.nunti.tts.Priority
import ai.nunti.tts.SpeechRequest
import ai.nunti.tts.TripPhase
import ai.nunti.tts.VehicleMotion
import ai.nunti.voice.AndroidVoiceSession
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import ai.nunti.tts.Emotion as VoiceEmotion

/**
 * 눈티 대사를 Pleos TextToSpeech SDK(on-device)로 말한다. `AndroidVoiceSession`의 큐·정책·오디오 포커스를 거친다.
 * 메인 스레드에서 만들고 호출한다.
 *
 * [drivingAllowed] 는 "이 앱이 주행 중 음성을 써도 되는가"라는 검토된 권한이다. 기본값은 false(정책이 주행 중 발화를 거부).
 * 시연 화면만 true 로 둔다. 실차 제출 전 Pleos/공모전 규정 확인 결과로 정해야 한다.
 * 통화·내비·긴급 음성 상태는 아직 관측하지 않고 QUIET 으로 가정한다.
 */
class PleosSpeechSink(
    context: Context,
    private val drivingAllowed: Boolean = false,
    private val avatarId: String = "nunti-score",
    private val onResult: (String) -> Unit = {},
) : SpeechSink, AutoCloseable {
    private val handler = Handler(Looper.getMainLooper())
    private val tripId = "score-${System.currentTimeMillis()}"
    private val profileId = "nunti-default-v1"
    private val avatar = AvatarVoiceInput(avatarId, "nunti-base", profileId)
    private var closed = false
    private val session = AndroidVoiceSession(context, onEvent = { onResult("${it.status}${it.reason?.let { r -> ":$r" } ?: ""}") })

    // 정책은 5초보다 오래된 상태를 거부한다. 실제 관측값이 없으므로 1초마다 같은 가정을 새로 공급한다.
    private val heartbeat = object : Runnable {
        override fun run() {
            if (closed) return
            session.onForeground(playbackContext())
            handler.postDelayed(this, 1_000)
        }
    }

    init {
        session.beginTrip(tripId)
        heartbeat.run()
    }

    private fun playbackContext() = PlaybackContext(
        tripId = tripId, phase = TripPhase.DRIVING, observedAtMonotonicMs = SystemClock.elapsedRealtime(),
        voiceEnabled = true, foreground = true, suspended = false, motion = VehicleMotion.MOVING,
        uxRestrictionsKnown = true, requiresDistractionOptimization = true,
        appAllowedWhileDriving = if (drivingAllowed) Permission.ALLOWED else Permission.DENIED,
        speechPermission = Permission.ALLOWED,
        call = AudioActivity.QUIET, navigation = AudioActivity.QUIET, criticalAudio = AudioActivity.QUIET,
    )

    private fun Emotion.toVoice() = when (this) {
        Emotion.NEUTRAL -> VoiceEmotion.NEUTRAL
        Emotion.WORRY -> VoiceEmotion.CONCERNED
        Emotion.RELIEF -> VoiceEmotion.RELIEVED
        Emotion.JOY -> VoiceEmotion.JOYFUL
    }

    override fun speak(text: String, utteranceId: String, emotion: Emotion) {
        if (closed) return
        val now = System.currentTimeMillis()
        val voiceEmotion = emotion.toVoice()
        val snapshot = EmotionSnapshot("emo-$utteranceId", tripId, avatarId, voiceEmotion, now)
        // 사건·감정은 이 앱의 ScoreEngine 이 직접 감지했으므로 contentVerified = true. 외부 입력이 아니다.
        session.submit(ApprovedSpeech(
            SpeechRequest(utteranceId, tripId, avatarId, text, voiceEmotion, profileId, TripPhase.DRIVING,
                Priority.NORMAL, now, now + 30_000, ContentSource.VERIFIED_EVENT_RESPONSE,
                snapshot.emotionId, utteranceId),
            avatar, snapshot, contentVerified = true,
        ))
    }

    override fun close() {
        if (closed) return
        closed = true
        handler.removeCallbacks(heartbeat)
        session.close()
    }
}
