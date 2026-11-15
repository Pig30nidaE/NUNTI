package ai.nunti.app.journey

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.util.Log

/** 눈티를 눌렀을 때 대사 음원(assets)을 한 번 재생한다. 새로 누르면 앞 음성은 끊고 새 음성을 낸다. */
internal class NuntiTapVoice(private val context: Context) {
    private val audio = context.getSystemService(AudioManager::class.java)
    private val attributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
    private var player: MediaPlayer? = null
    private var focus: AudioFocusRequest? = null

    fun play(line: NuntiTapLines.Line) {
        stop()
        val media = MediaPlayer(); player = media
        media.setAudioAttributes(attributes)
        media.setOnCompletionListener { if (player === media) stop() }
        media.setOnErrorListener { _, _, _ -> if (player === media) stop(); true }
        media.setOnPreparedListener {
            if (player !== media) return@setOnPreparedListener
            // 다른 소리(길안내·음악)는 끊지 않고 잠깐 줄인다.
            val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(attributes).setOnAudioFocusChangeListener { if (it < 0 && player === media) stop() }.build()
            focus = request
            if (audio.requestAudioFocus(request) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) { stop(); return@setOnPreparedListener }
            media.start()
        }
        runCatching {
            context.assets.openFd(line.asset).use { media.setDataSource(it.fileDescriptor, it.startOffset, it.length) }
            media.prepareAsync()
        }.onFailure { Log.w("NuntiTapVoice", "tap voice unavailable: ${line.id}", it); stop() }
    }

    fun stop() {
        player?.let { runCatching { it.stop() }; it.release() }; player = null
        focus?.let { audio.abandonAudioFocusRequest(it) }; focus = null
    }
}
