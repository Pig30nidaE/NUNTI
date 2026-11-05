package ai.nunti.voice

import ai.nunti.tts.LocalAudioPlayer
import android.media.AudioAttributes
import android.media.MediaDataSource
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper

/** All MediaPlayer lifecycle calls and callbacks stay on the session's owning looper. */
class AndroidLocalAudioPlayer(private val attributes: AudioAttributes, private val handler: Handler) : LocalAudioPlayer {
    private var player: MediaPlayer? = null
    private var closed = false
    override fun play(wav: ByteArray, events: LocalAudioPlayer.Events) {
        check(Looper.myLooper() == handler.looper && !closed && player == null)
        val media = MediaPlayer(); player = media
        media.setAudioAttributes(attributes)
        media.setDataSource(object : MediaDataSource() {
            override fun getSize() = wav.size.toLong()
            override fun close() {}
            override fun readAt(position: Long, buffer: ByteArray, offset: Int, size: Int): Int {
                if (position < 0) return -1
                if (size == 0) return 0
                if (position >= wav.size) return -1
                val count = minOf(size, wav.size - position.toInt())
                wav.copyInto(buffer, offset, position.toInt(), position.toInt() + count)
                return count
            }
        })
        media.setOnPreparedListener {
            if (!closed && player === it) {
                try { it.start(); events.started() }
                catch (_: Exception) { events.failed("LOCAL_START_FAILED") }
            }
        }
        media.setOnCompletionListener { if (!closed && player === it) events.completed() }
        media.setOnErrorListener { current, _, _ ->
            if (!closed && player === current) events.failed("LOCAL_DECODE_FAILED")
            true
        }
        media.prepareAsync()
    }
    override fun close() {
        check(Looper.myLooper() == handler.looper)
        if (closed) return
        closed = true
        val old = player; player = null
        old?.setOnPreparedListener(null)
        old?.setOnCompletionListener(null)
        old?.setOnErrorListener(null)
        old?.release()
    }
}
