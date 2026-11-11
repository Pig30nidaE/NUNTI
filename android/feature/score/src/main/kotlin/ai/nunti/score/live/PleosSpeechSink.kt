package ai.nunti.score.live

import ai.nunti.score.Emotion
import ai.nunti.score.RecordedVoice
import ai.nunti.score.SpeechSink
import ai.nunti.score.VoiceClip
import ai.nunti.tts.AudioActivity
import ai.nunti.tts.AvatarVoiceInput
import ai.nunti.tts.Control
import ai.nunti.tts.VoiceProfile
import ai.nunti.tts.Permission
import ai.nunti.tts.PlaybackContext
import ai.nunti.tts.TripPhase
import ai.nunti.tts.VehicleMotion
import ai.nunti.tts.SpeechStatus
import ai.nunti.voice.AndroidAudioFocusController
import ai.nunti.voice.AndroidVoiceSession
import android.content.Context
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
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
 *
 * 눈티 목소리로 녹음한 문장([RecordedVoice])은 그 음원을 재생하고, 녹음이 없는 문장만 Pleos TTS 로 말한다.
 * 이어 붙인 문장(마무리 멘트 등)은 부품마다 따로 고르므로, 일부만 녹음돼 있으면 두 목소리가 섞인다.
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
    private val appContext = context.applicationContext
    private val audio = appContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val attributes = AndroidAudioFocusController.notificationAttributes()
    /** 순서대로 말하는 중인 Pleos 부품: 요청 id → 끝나면 다음 부품으로. */
    private val pendingTts = HashMap<String, () -> Unit>()
    private var player: MediaPlayer? = null
    private var focus: AudioFocusRequest? = null
    private var sequence = 0
    private var busy = false
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
        if (it.status in TERMINAL) handler.post { pendingTts.remove(it.requestId)?.invoke() }
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
        if (RecordedVoice.clipFor(text) == null) {
            session.submit(SpeechMapping.approvedSpeech(
                text, utteranceId, emotion, tripId, avatarId, profileId, avatar, System.currentTimeMillis()))
            return
        }
        // 정책 큐를 거치지 않으므로 주행 중 허용 여부와 겹침은 여기서 지킨다 (간격은 EventSpeaker 가 지킨다).
        if (!drivingAllowed || busy) return
        playParts(listOf(text), utteranceId, emotion, report = false)
    }

    /**
     * 주행 후 보고(마무리 멘트·일시저장 안내). 차가 멈춘 것이 확인된 때만 부른다 — 호출한 쪽이 정차를 보증한다.
     * 주행 중 대사의 15초 간격 정책을 받지 않고, 같은 문장 반복(60초)만 막힌다.
     */
    fun speakTripReport(text: String, utteranceId: String, emotion: Emotion) {
        if (closed) return
        postTripUntil = SystemClock.elapsedRealtime() + REPORT_WINDOW_MS
        session.onForeground(playbackContext()) // 곧바로 주행 후 상태를 반영한다 (다음 1초 박자를 기다리지 않는다)
        val parts = RecordedVoice.split(text)
        if (parts.none { RecordedVoice.clipFor(it) != null }) {
            session.submit(SpeechMapping.tripReportSpeech(
                text, utteranceId, emotion, tripId, avatarId, profileId, avatar, System.currentTimeMillis()))
            return
        }
        playParts(parts, utteranceId, emotion, report = true) // 보고는 말하던 반응을 끊고 시작한다
    }

    private fun playParts(parts: List<String>, utteranceId: String, emotion: Emotion, report: Boolean) {
        stopClip()
        busy = true
        val seq = ++sequence
        fun step(i: Int) {
            if (closed || seq != sequence) return
            if (i >= parts.size) { busy = false; return }
            val next: () -> Unit = { handler.post { step(i + 1) } }
            val text = parts[i]
            val clip = RecordedVoice.clipFor(text)
            if (clip != null) { playClip(clip, next); return }
            val id = "$utteranceId-$i"
            pendingTts[id] = { next() }
            val now = System.currentTimeMillis()
            session.submit(if (report) SpeechMapping.tripReportSpeech(text, id, emotion, tripId, avatarId, profileId, avatar, now)
                else SpeechMapping.approvedSpeech(text, id, emotion, tripId, avatarId, profileId, avatar, now))
        }
        step(0)
    }

    private fun playClip(clip: VoiceClip, next: () -> Unit) {
        val file = clip.file
        val mp = MediaPlayer()
        val done = {
            if (player === mp) stopClip()
            next()
        }
        try {
            appContext.assets.openFd("${RecordedVoice.DIR}/$file").use { mp.setDataSource(it.fileDescriptor, it.startOffset, it.length) }
            mp.setAudioAttributes(attributes)
            mp.setOnCompletionListener { done() }
            mp.setOnErrorListener { _, what, extra -> Log.w(TAG, "clip $file error $what/$extra"); done(); true }
            mp.prepare()
        } catch (e: Exception) {
            Log.w(TAG, "clip $file failed", e)
            mp.release(); next(); return
        }
        val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK).setAudioAttributes(attributes)
            .setOnAudioFocusChangeListener({ change ->
                if (change == AudioManager.AUDIOFOCUS_LOSS || change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) if (player === mp) done()
            }, handler).build()
        if (audio.requestAudioFocus(request) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            mp.release(); onResult("CLIP_NO_FOCUS:$file"); next(); return
        }
        player = mp; focus = request
        mp.start()
        onResult("CLIP:$file")
    }

    private fun stopClip() {
        val mp = player; player = null
        if (mp != null) try { mp.stop() } catch (_: Exception) { } finally { mp.release() }
        focus?.let { audio.abandonAudioFocusRequest(it) }; focus = null
    }

    override fun close() {
        if (closed) return
        closed = true
        handler.removeCallbacks(heartbeat)
        sequence++; pendingTts.clear(); stopClip()
        session.close()
    }

    private companion object {
        const val TAG = "PleosSpeechSink"
        const val REPORT_WINDOW_MS = 20_000L // 문장을 말하는 동안 주행 후 상태를 유지한다
        val TERMINAL = setOf(SpeechStatus.COMPLETED, SpeechStatus.CANCELLED, SpeechStatus.REJECTED, SpeechStatus.FAILED)
    }
}
