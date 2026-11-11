package ai.nunti.voice

import ai.nunti.tts.*
import android.content.Context
import android.media.AudioAttributes
import android.os.Handler

/** Pleos on-device needs no server credentials. Generic Android is a visible offline fallback. */
fun nuntiOnDeviceSpeech(context: Context, attributes: AudioAttributes, handler: Handler): TtsProvider =
    InitializingFallbackTtsProvider(
        primary = { PleosTtsProvider({ AndroidPleosConnection(context.applicationContext, it, attributes, handler) }) },
        fallback = { AndroidSystemTtsProvider(context, handler, attributes) },
        scheduler = SpeechScheduler { delay, action ->
            val task = Runnable(action); handler.postDelayed(task, delay)
            Cancellation { handler.removeCallbacks(task) }
        },
    )
