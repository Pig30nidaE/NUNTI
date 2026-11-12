package ai.nunti.voice

import ai.nunti.tts.*
import android.content.Context
import android.media.AudioManager
import android.media.AudioAttributes
import android.os.Handler
import android.os.Looper
import android.os.SystemClock

/** Host owns Car connection and feeds freshly observed PlaybackContext; no permissive defaults. */
class AndroidVoiceSession(context: Context, mode: EngineMode = EngineMode.ON_DEVICE,
    credentials: () -> PleosCredentials? = { null },
    profiles: List<VoiceProfile> = listOf(VoiceProfile()),
    providerFactory: ((AudioAttributes, Handler) -> TtsProvider)? = null,
    onAmplitude: ((String, Double) -> Unit)? = null,
    private val onEvent: (SpeechEvent) -> Unit = {}) {
    private val appContext = context.applicationContext
    private val handler = Handler(Looper.getMainLooper())
    private val clock = object : SpeechClock {
        override fun epochMs() = System.currentTimeMillis()
        override fun monotonicMs() = SystemClock.elapsedRealtime()
    }
    private val scheduler = SpeechScheduler { delay, action ->
        val task = Runnable(action); handler.postDelayed(task, delay)
        Cancellation { handler.removeCallbacks(task) }
    }
    private val attributes = AndroidAudioFocusController.notificationAttributes()
    private val provider = providerFactory?.invoke(attributes, handler) ?:
        PleosTtsProvider({ AndroidPleosConnection(appContext, it, attributes, handler) }, mode, credentials,
            onAmplitude = onAmplitude)
    private val focus = AndroidAudioFocusController(appContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager,
        attributes, handler)
    private val queue: SpeechQueueManager
    private val lifecycle: SpeechLifecycleManager
    init {
        check(Looper.myLooper() == Looper.getMainLooper()) { "Construct on the main thread" }
        queue = SpeechQueueManager(provider, focus, clock, scheduler,
            builder = SpeechRequestBuilder(VoiceProfileManager(profiles)), sink = onEvent)
        lifecycle = SpeechLifecycleManager(queue)
    }
    private fun run(action: () -> Unit) {
        if (Looper.myLooper() == handler.looper) action() else handler.post(action)
    }
    fun beginTrip(tripId: String) = run { queue.beginTrip(tripId) }
    fun updateContext(value: PlaybackContext) = run { queue.updateContext(value) }
    fun submit(speech: ApprovedSpeech) = run { queue.submit(speech) }
    fun submitWire(wire: WireSpeechRequest, avatar: AvatarVoiceInput, snapshot: EmotionSnapshot?, evidence: SpeechEvidence) = run {
        when (val mapped = SpeechContractBridge.tryFromWire(wire, avatar, snapshot, evidence)) {
            is SpeechMappingResult.Accepted -> queue.submit(mapped.speech)
            is SpeechMappingResult.Rejected -> runCatching {
                onEvent(SpeechEvent(mapped.requestId, mapped.tripId, SpeechStatus.REJECTED, mapped.reason))
            }
        }
    }
    fun cancel(requestId: String) = run { queue.cancel(requestId) }
    /** A user stop applies to the active utterance and everything waiting behind it. */
    fun stop() = run { queue.cancelAll("USER_CANCELLED") }
    fun onForeground(value: PlaybackContext) = run { lifecycle.onForeground(value) }
    fun onBackground() = run { lifecycle.onBackground() }
    fun onSuspend() = run { lifecycle.onSuspend() }
    fun close() = run { lifecycle.close() }
}
