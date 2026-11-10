package ai.nunti.score.live

import ai.nunti.score.Emotion
import ai.nunti.score.SpeechSink
import ai.nunti.tts.AudioActivity
import ai.nunti.tts.AvatarVoiceInput
import ai.nunti.tts.Control
import ai.nunti.tts.VoiceProfile
import ai.nunti.tts.Permission
import ai.nunti.tts.PlaybackContext
import ai.nunti.tts.TripPhase
import ai.nunti.tts.VehicleMotion
import ai.nunti.voice.AndroidVoiceSession
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log

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
    /** Pleos speaker id (setSpeakerType). null = SDK default voice. Must be one of [ai.nunti.tts.PleosSpeakers.KOREAN]. */
    private val speaker: String? = null,
    private val onResult: (String) -> Unit = {},
) : SpeechSink, AutoCloseable {
    private val handler = Handler(Looper.getMainLooper())
    private val tripId = "score-${System.currentTimeMillis()}"
    private val profileId = "nunti-default-v1"
    private val avatar = AvatarVoiceInput(avatarId, "nunti-base", profileId)
    private var closed = false
    private val session = AndroidVoiceSession(context,
        profiles = listOf(VoiceProfile(profileId, preferredVoiceId = speaker,
            supportedControls = if (speaker == null) setOf(Control.LOCALE) else setOf(Control.LOCALE, Control.SPEAKER))),
        onEvent = {
        val summary = SpeechMapping.describe(it.status, it.reason)
        if (SpeechMapping.shouldLog(it.status)) Log.w(TAG, "speech ${it.requestId} $summary")
        onResult(summary)
    })

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

    override fun speak(text: String, utteranceId: String, emotion: Emotion) {
        if (closed) return
        session.submit(SpeechMapping.approvedSpeech(
            text, utteranceId, emotion, tripId, avatarId, profileId, avatar, System.currentTimeMillis()))
    }

    override fun close() {
        if (closed) return
        closed = true
        handler.removeCallbacks(heartbeat)
        session.close()
    }

    private companion object { const val TAG = "PleosSpeechSink" }
}
