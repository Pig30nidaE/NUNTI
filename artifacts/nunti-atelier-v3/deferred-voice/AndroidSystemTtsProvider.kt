package ai.nunti.voice

import ai.nunti.tts.*
import android.content.Context
import android.media.AudioAttributes
import android.os.Handler
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/** Offline fallback for devices without the Pleos TTS service. Audio focus belongs to the queue. */
class AndroidSystemTtsProvider(private val context: Context, private val handler: Handler,
    private val attributes: AudioAttributes) : TtsProvider {
    override val capabilities = ProviderCapabilities()
    override val mode = EngineMode.ON_DEVICE
    override fun source(request: SpeechRequest) = SpeechSource(mode, "android-on-device")
    private var engine: TextToSpeech? = null
    private var listener: TtsProvider.Listener? = null
    private var active: String? = null
    private var released = false

    override fun initialize(listener: TtsProvider.Listener) {
        check(!released)
        this.listener = listener
        engine = TextToSpeech(context.applicationContext) { status -> handler.post {
            if (released) return@post
            val tts = engine ?: return@post
            val voice = tts.voices?.filter { !it.isNetworkConnectionRequired && it.locale.language == "ko" }
                ?.sortedWith(compareByDescending<android.speech.tts.Voice> { it.quality }.thenBy { it.name })?.firstOrNull()
            if (status != TextToSpeech.SUCCESS || voice == null || tts.setVoice(voice) != TextToSpeech.SUCCESS) {
                listener.onError(null, "KOREAN_OFFLINE_VOICE_UNAVAILABLE")
                return@post
            }
            tts.setAudioAttributes(attributes)
            // Keep the speaker's natural timbre. Raising pitch made the old voice sound synthetic.
            tts.setSpeechRate(1f)
            tts.setPitch(1f)
            listener.onInitialized()
        } }
        engine?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) = callback(id) { listener.onStart(it) }
            override fun onDone(id: String?) = callback(id, true) { listener.onDone(it) }
            @Deprecated("Platform callback")
            override fun onError(id: String?) = callback(id, true) { listener.onError(it, "SYSTEM_TTS_ERROR") }
            override fun onStop(id: String?, interrupted: Boolean) = callback(id, true) { listener.onStop(it) }
        })
    }
    private fun callback(id: String?, terminal: Boolean = false, action: (String) -> Unit) {
        handler.post {
            if (!released && id != null && active == id) {
                if (terminal) active = null
                action(id)
            }
        }
    }
    override fun setLocale(locale: String) { require(locale == "ko-KR") }
    override fun speak(speech: PreparedSpeech) {
        check(!released && active == null)
        val id = speech.request.requestId
        active = id
        if (engine?.speak(speech.request.text, TextToSpeech.QUEUE_FLUSH, null, id) != TextToSpeech.SUCCESS) {
            active = null; listener?.onError(id, "SYSTEM_TTS_SPEAK_FAILED")
        }
    }
    override fun stop() {
        val id = active; active = null
        engine?.stop()
        if (id != null) listener?.onStop(id)
    }
    override fun release() { released = true; active = null; engine?.stop(); engine?.shutdown(); engine = null; listener = null }
}
