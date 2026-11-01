package ai.nunti.voice

import ai.nunti.tts.AudioFocusController
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Handler

/** Speech stops on duck because the verified TTS API has no volume/pause control. */
class AndroidAudioFocusController(private val manager: AudioManager,
    val attributes: AudioAttributes, private val handler: Handler) : AudioFocusController {
    private var request: AudioFocusRequest? = null
    private var generation = 0L
    override fun request(onLoss: () -> Unit): Boolean {
        abandon()
        val token = ++generation
        val candidate = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
            .setAudioAttributes(attributes)
            .setAcceptsDelayedFocusGain(false)
            .setWillPauseWhenDucked(true)
            .setOnAudioFocusChangeListener({ change ->
                if (token == generation && change != AudioManager.AUDIOFOCUS_GAIN) {
                    abandon(); onLoss()
                }
            }, handler).build()
        request = candidate
        return try {
            val granted = manager.requestAudioFocus(candidate) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
            if (!granted) abandon()
            granted
        } catch (_: Exception) { abandon(); false }
    }
    override fun abandon() {
        ++generation
        val old = request; request = null
        if (old != null) try { manager.abandonAudioFocusRequest(old) } catch (_: Exception) { }
    }
    companion object {
        /** Companion reactions are notifications, never emergency/safety/navigation guidance. */
        fun notificationAttributes(): AudioAttributes = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_NOTIFICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
    }
}
