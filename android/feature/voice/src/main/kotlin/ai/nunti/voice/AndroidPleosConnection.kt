package ai.nunti.voice

import ai.nunti.tts.*
import ai.pleos.playground.tts.TextToSpeech
import ai.pleos.playground.tts.constant.ErrorType
import ai.pleos.playground.tts.constant.Mode
import ai.pleos.playground.tts.listener.EventListener
import ai.pleos.playground.tts.listener.OnInitializeListener
import ai.pleos.playground.tts.listener.OnServerConnectionListener
import android.content.Context
import android.media.AudioAttributes
import android.os.Handler
import android.os.Looper
import java.util.Locale

/** Compiled against official ai.pleos.playground:TextToSpeech:3.3.1. */
class AndroidPleosConnection(context: Context, mode: EngineMode,
    private val attributes: AudioAttributes, private val handler: Handler) : PleosConnection {
    private val sdk = TextToSpeech(context.applicationContext, Mode.valueOf(mode.name))
    private val listeners = mutableMapOf<PleosConnection.Events, EventListener>()
    private var closed = false
    private fun post(action: () -> Unit) { handler.post { if (!closed) action() } }
    private fun lane() { check(Looper.myLooper() == handler.looper) }
    override fun initialize(success: () -> Unit, failure: (String) -> Unit) {
        lane()
        sdk.initialize(object : OnInitializeListener {
            override fun onSuccess() = post {
                try { sdk.setAudioAttributes(attributes); success() }
                catch (_: Exception) { failure("AUDIO_ATTRIBUTES_FAILED") }
            }
            override fun onFailure(errorType: ErrorType) = post { failure(errorType.name) }
        })
    }
    override fun addListener(events: PleosConnection.Events) {
        lane(); if (events in listeners) return
        val listener = object : EventListener {
            override fun onReady() = post { events.ready() }
            override fun onStart() = post { events.start() }
            override fun onDone() = post { events.done() }
            override fun onStop() = post { events.stopped() }
            override fun onError(errorType: ErrorType) = post { events.error(errorType.name) }
            override fun onUpdatedRms(rms: Double) = post { events.rms(rms) }
        }
        listeners[events] = listener
        sdk.addEventListener(listener)
    }
    override fun removeListener(events: PleosConnection.Events) {
        lane(); listeners.remove(events)?.let { sdk.removeEventListener(it) }
    }
    override fun registerApp(credentials: PleosCredentials, connected: () -> Unit, failed: (String) -> Unit) {
        lane()
        sdk.registerApp(credentials.clientId, credentials.clientSecret, object : OnServerConnectionListener {
            override fun onConnected() = post(connected)
            override fun onFailed(errorType: ErrorType) = post { failed(errorType.name) }
        })
    }
    override fun setLocale(locale: String) { lane(); sdk.setLocale(Locale.forLanguageTag(locale)) }
    override fun speak(text: String) { lane(); sdk.speak(text, true) }
    override fun stop() { lane(); sdk.stop() }
    override fun release() {
        lane(); if (closed) return
        closed = true
        try { listeners.values.toList().forEach { sdk.removeEventListener(it) } }
        finally { listeners.clear(); sdk.release() }
    }
}
