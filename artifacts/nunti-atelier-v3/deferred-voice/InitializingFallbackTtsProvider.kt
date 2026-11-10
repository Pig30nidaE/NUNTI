package ai.nunti.tts

/** Switch only before speech starts. Never repeat a partly spoken line on another engine. */
class InitializingFallbackTtsProvider(private val primary: () -> TtsProvider,
    private val fallback: () -> TtsProvider, private val scheduler: SpeechScheduler) : TtsProvider {
    override val capabilities = ProviderCapabilities()
    override val mode = EngineMode.ON_DEVICE
    private var delegate: TtsProvider? = null
    private var listener: TtsProvider.Listener? = null
    private var timer: Cancellation? = null
    private var generation = 0L
    private var released = false
    private var ready = false
    override fun source(request: SpeechRequest) = delegate?.source(request) ?: SpeechSource(mode, "pleos")
    override fun initialize(listener: TtsProvider.Listener) {
        check(!released)
        this.listener = listener
        connect(false)
    }
    private fun connect(usingFallback: Boolean) {
        val token = ++generation
        timer?.cancel()
        val old = delegate; delegate = null
        runCatching { old?.release() }
        fun failed(id: String?, reason: String) {
            if (released || token != generation) return
            timer?.cancel()
            if (!ready && !usingFallback) connect(true) else listener?.onError(id, reason)
        }
        if (!usingFallback) timer = scheduler.after(2000) { failed(null, "PLEOS_INIT_TIMEOUT") }
        try {
            val provider = if (usingFallback) fallback() else primary()
            delegate = provider
            provider.initialize(object : TtsProvider.Listener {
                private fun live() = !released && token == generation
                override fun onInitialized() { if (live()) { timer?.cancel(); ready = true; listener?.onInitialized() } }
                override fun onStart(requestId: String) { if (live()) listener?.onStart(requestId) }
                override fun onDone(requestId: String) { if (live()) listener?.onDone(requestId) }
                override fun onStop(requestId: String) { if (live()) listener?.onStop(requestId) }
                override fun onError(requestId: String?, code: String) = failed(requestId, code)
            })
        } catch (_: Exception) { failed(null, "TTS_INITIALIZATION_FAILED") }
    }
    override fun setLocale(locale: String) { delegate?.setLocale(locale) }
    override fun speak(speech: PreparedSpeech) { check(ready && !released); checkNotNull(delegate).speak(speech) }
    override fun stop() { delegate?.stop() }
    override fun release() { released = true; ++generation; timer?.cancel(); delegate?.release(); delegate = null; listener = null }
}
