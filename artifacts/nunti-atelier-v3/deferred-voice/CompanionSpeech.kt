package ai.nunti.app.journey

import ai.nunti.app.studio.StudioCarGate
import ai.nunti.tts.*
import ai.nunti.voice.AndroidLocalAudioPlayer
import ai.nunti.voice.AndroidVoiceSession
import ai.nunti.voice.nuntiOnDeviceSpeech
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioManager
import android.os.Handler
import android.os.SystemClock
import java.io.File
import java.security.MessageDigest

/** One queue, focus owner and cancellation policy for previews and foreground journeys. */
internal class CompanionSpeech(private val context: Context, private val tripId: String,
    private val characterId: String, private val gate: () -> StudioCarGate?,
    private val enabled: () -> Boolean, private val active: () -> Boolean,
    clips: Map<String, File> = emptyMap(), private val onEvent: (SpeechEvent) -> Unit) : AutoCloseable {
    private val manager = context.getSystemService(AudioManager::class.java)
    private var phase = TripPhase.PRE_TRIP
    private var sequence = 0L
    private val voice = AndroidVoiceSession(context, providerFactory = { attributes, handler ->
        JourneySpeechProvider(context, attributes, handler, clips)
    }, onEvent = onEvent)

    init { voice.beginTrip(tripId) }

    fun refresh() {
        val vehicle = gate()?.speechState()
        val automotive = context.packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)
        val mode = manager.mode
        val usages = runCatching { manager.activePlaybackConfigurations.map { it.audioAttributes.usage } }.getOrDefault(emptyList())
        voice.updateContext(PlaybackContext(tripId = tripId, phase = phase,
            observedAtMonotonicMs = SystemClock.elapsedRealtime(), voiceEnabled = enabled(),
            // A user-started foreground service owns the ongoing journey, even over navigation.
            foreground = active(), suspended = !active(),
            motion = vehicle?.motion ?: if (!automotive) VehicleMotion.PARKED else VehicleMotion.UNKNOWN,
            uxRestrictionsKnown = vehicle?.known ?: !automotive,
            requiresDistractionOptimization = vehicle?.restricted ?: automotive,
            activeRestrictions = vehicle?.restrictions ?: 0,
            appAllowedWhileDriving = Permission.ALLOWED, speechPermission = Permission.ALLOWED,
            call = if (mode == AudioManager.MODE_IN_CALL || mode == AudioManager.MODE_IN_COMMUNICATION || mode == AudioManager.MODE_RINGTONE) AudioActivity.BUSY else AudioActivity.QUIET,
            navigation = if (AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE in usages) AudioActivity.BUSY else AudioActivity.QUIET,
            criticalAudio = if (AudioAttributes.USAGE_ALARM in usages) AudioActivity.BUSY else AudioActivity.QUIET))
    }

    fun say(kind: String, text: String, phase: TripPhase, source: ContentSource,
        emotion: Emotion = Emotion.NEUTRAL, evidence: String? = null): String {
        this.phase = phase
        refresh()
        val now = System.currentTimeMillis()
        val id = "speech-${++sequence}-$kind"
        val emotionId = if (emotion != Emotion.NEUTRAL) "emotion-$sequence" else null
        val request = SpeechRequest(id, tripId, characterId, text, emotion, "nunti-default-v1", phase,
            Priority.NORMAL, now, now + 20_000, source, emotionId, evidence)
        voice.submit(ApprovedSpeech(request, AvatarVoiceInput(characterId, "nunti", "nunti-default-v1"),
            emotionId?.let { EmotionSnapshot(it, tripId, characterId, emotion, now) }, contentVerified = true))
        return id
    }
    fun stop() = voice.stop()
    override fun close() = voice.close()
}

/** Existing immutable journey recordings and synthesized text share the same queue. */
private class JourneySpeechProvider(private val context: Context, private val attributes: AudioAttributes,
    private val handler: Handler, private val clips: Map<String, File>) : TtsProvider {
    override val mode = EngineMode.ON_DEVICE
    override val capabilities = ProviderCapabilities()
    private var delegate: TtsProvider? = null
    private var selected: String? = null
    private fun kind(request: SpeechRequest) = request.requestId.substringAfterLast('-')
    override fun source(request: SpeechRequest) = if (clips.containsKey(kind(request)))
        SpeechSource(EngineMode.LOCAL_FILE, "nunti-recorded") else delegate?.source(request) ?: SpeechSource(mode, "pleos")
    override fun select(speech: PreparedSpeech): Boolean {
        val key = kind(speech.request)
        if (selected == key && delegate != null) return true
        delegate?.release()
        selected = key
        delegate = clips[key]?.let { RecordedLineProvider(it, context, attributes, handler) }
            ?: nuntiOnDeviceSpeech(context, attributes, handler)
        return false
    }
    override fun initialize(listener: TtsProvider.Listener) {
        // Queue initialization can precede provider selection; it has no output.
        delegate?.initialize(listener) ?: listener.onInitialized()
    }
    override fun setLocale(locale: String) { delegate?.setLocale(locale) }
    override fun speak(speech: PreparedSpeech) = checkNotNull(delegate).speak(speech)
    override fun stop() { delegate?.stop() }
    override fun release() { delegate?.release(); delegate = null; selected = null }
}

private class RecordedLineProvider(private val file: File, private val context: Context,
    private val attributes: AudioAttributes, private val handler: Handler) : TtsProvider {
    override val mode = EngineMode.LOCAL_FILE
    override val capabilities = ProviderCapabilities()
    private var listener: TtsProvider.Listener? = null
    private var player: AndroidLocalAudioPlayer? = null
    private var id: String? = null
    private var bytes: ByteArray? = null
    override fun initialize(listener: TtsProvider.Listener) {
        this.listener = listener
        val verified = runCatching {
            require(file.canonicalFile.parentFile == File(context.filesDir, "journeys/assets").canonicalFile)
            require(file.name.matches(Regex("[a-f0-9]{64}\\.wav")) && file.length() in 44..4_000_000)
            val data = file.readBytes()
            val sha = MessageDigest.getInstance("SHA-256").digest(data).joinToString("") { "%02x".format(it) }
            require(sha == file.nameWithoutExtension)
            data
        }
        verified.onSuccess { bytes = it; listener.onInitialized() }
            .onFailure { listener.onError(null, "RECORDING_UNAVAILABLE") }
    }
    override fun setLocale(locale: String) { require(locale == "ko-KR") }
    override fun speak(speech: PreparedSpeech) {
        val current = speech.request.requestId
        id = current
        val audio = AndroidLocalAudioPlayer(attributes, handler); player = audio
        audio.play(checkNotNull(bytes), object : LocalAudioPlayer.Events {
            override fun started() { if (id == current) listener?.onStart(current) }
            override fun completed() { if (id == current) { stopPlayer(); listener?.onDone(current) } }
            override fun failed(reason: String) { if (id == current) { stopPlayer(); listener?.onError(current, reason) } }
        })
    }
    private fun stopPlayer() { id = null; player?.close(); player = null }
    override fun stop() { val current = id; stopPlayer(); if (current != null) listener?.onStop(current) }
    override fun release() { stopPlayer(); listener = null; bytes = null }
}
