package ai.nunti.app.studio

import ai.nunti.tts.ApprovedSpeech
import ai.nunti.tts.AudioActivity
import ai.nunti.tts.AvatarVoiceInput
import ai.nunti.tts.ContentSource
import ai.nunti.tts.Emotion
import ai.nunti.tts.Permission
import ai.nunti.tts.PlaybackContext
import ai.nunti.tts.Priority
import ai.nunti.tts.SpeechEvent
import ai.nunti.tts.SpeechRequest
import ai.nunti.tts.TripPhase
import ai.nunti.tts.VehicleMotion
import ai.nunti.voice.AndroidVoiceSession
import android.content.Context
import android.os.SystemClock

/** The host supplies the current parked gate. The shared session owns audio focus and cancellation. */
internal class StudioConversationVoice(context: Context, onAmplitude: (String, Double) -> Unit,
    onEvent: (SpeechEvent) -> Unit) : AutoCloseable {
    private val avatar = AvatarVoiceInput("nunti-studio", "nunti-base")
    private val session = AndroidVoiceSession(context, onAmplitude = onAmplitude, onEvent = onEvent)
    private val sessionId = "studio-${SystemClock.elapsedRealtime()}"

    init { session.beginTrip(sessionId) }

    fun speak(text: String, requestId: String) {
        refreshParkedContext()
        val now = System.currentTimeMillis()
        val request = SpeechRequest(requestId, sessionId, avatar.avatarId, text, Emotion.NEUTRAL,
            avatar.voiceProfileId, TripPhase.PRE_TRIP, Priority.NORMAL, now, now + 18_000,
            ContentSource.USER_INITIATED)
        session.submit(ApprovedSpeech(request, avatar, snapshot = null, contentVerified = true))
    }

    fun refreshParkedContext() {
        session.onForeground(PlaybackContext(
            tripId = sessionId, phase = TripPhase.PRE_TRIP, observedAtMonotonicMs = SystemClock.elapsedRealtime(),
            voiceEnabled = true, foreground = true, suspended = false, motion = VehicleMotion.PARKED,
            uxRestrictionsKnown = true, requiresDistractionOptimization = false, speechPermission = Permission.ALLOWED,
            call = AudioActivity.QUIET, navigation = AudioActivity.QUIET, criticalAudio = AudioActivity.QUIET,
        ))
    }

    fun stop() = session.stop()
    override fun close() = session.close()
}
