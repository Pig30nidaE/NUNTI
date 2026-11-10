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
    /** 이 시각(elapsedRealtime)까지는 "주행 후(정차)" 상태로 공급한다. 주행 후 보고를 말하는 동안만 쓴다. */
    @Volatile private var postTripUntil = 0L
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

    private fun playbackContext(): PlaybackContext {
        val now = SystemClock.elapsedRealtime()
        val parked = now < postTripUntil
        return PlaybackContext(
        tripId = tripId, phase = if (parked) TripPhase.POST_TRIP else TripPhase.DRIVING, observedAtMonotonicMs = now,
        voiceEnabled = true, foreground = true, suspended = false,
        motion = if (parked) VehicleMotion.PARKED else VehicleMotion.MOVING,
        uxRestrictionsKnown = true, requiresDistractionOptimization = !parked,
        appAllowedWhileDriving = if (drivingAllowed) Permission.ALLOWED else Permission.DENIED,
        speechPermission = Permission.ALLOWED,
        call = AudioActivity.QUIET, navigation = AudioActivity.QUIET, criticalAudio = AudioActivity.QUIET,
        )
    }

    override fun speak(text: String, utteranceId: String, emotion: Emotion) {
        if (closed) return
        session.submit(SpeechMapping.approvedSpeech(
            text, utteranceId, emotion, tripId, avatarId, profileId, avatar, System.currentTimeMillis()))
    }

    /**
     * 주행 후 보고(마무리 멘트·일시저장 안내). 차가 멈춘 것이 확인된 때만 부른다 — 호출한 쪽이 정차를 보증한다.
     * 주행 중 대사의 15초 간격 정책을 받지 않고, 같은 문장 반복(60초)만 막힌다.
     */
    fun speakTripReport(text: String, utteranceId: String, emotion: Emotion) {
        if (closed) return
        postTripUntil = SystemClock.elapsedRealtime() + REPORT_WINDOW_MS
        session.onForeground(playbackContext()) // 곧바로 주행 후 상태를 반영한다 (다음 1초 박자를 기다리지 않는다)
        session.submit(SpeechMapping.tripReportSpeech(
            text, utteranceId, emotion, tripId, avatarId, profileId, avatar, System.currentTimeMillis()))
    }

    override fun close() {
        if (closed) return
        closed = true
        handler.removeCallbacks(heartbeat)
        session.close()
    }

    private companion object {
        const val TAG = "PleosSpeechSink"
        const val REPORT_WINDOW_MS = 20_000L // 문장을 말하는 동안 주행 후 상태를 유지한다
    }
}
