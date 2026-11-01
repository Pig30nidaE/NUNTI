package ai.nunti.tts

interface TtsProvider {
    val capabilities: ProviderCapabilities
    val mode: EngineMode
    interface Listener {
        fun onInitialized()
        fun onReady(requestId: String) {}
        fun onStart(requestId: String)
        fun onDone(requestId: String)
        fun onStop(requestId: String)
        fun onError(requestId: String?, code: String)
    }
    fun initialize(listener: Listener)
    fun setLocale(locale: String)
    fun speak(speech: PreparedSpeech)
    /** Must prevent stale callbacks from being attributed to the next request. */
    fun stop()
    fun release()
}
interface AudioFocusController {
    fun request(onLoss: () -> Unit): Boolean
    fun abandon()
}
/** Deterministic simulation; deliberately produces no sound. */
class MockTtsProvider(override val mode: EngineMode = EngineMode.ON_DEVICE,
    var failInitialization: Boolean = false, var connected: Boolean = true,
    var autoStart: Boolean = true) : TtsProvider {
    override val capabilities = ProviderCapabilities()
    private var listener: TtsProvider.Listener? = null
    var active: PreparedSpeech? = null; private set
    var initialized = false; private set
    var released = false; private set
    var appliedLocale = "ko-KR"; private set
    val spoken = mutableListOf<PreparedSpeech>()
    override fun initialize(listener: TtsProvider.Listener) {
        check(!released) { "RELEASED" }
        if (initialized) return
        this.listener = listener
        if (failInitialization) listener.onError(null, "INITIALIZATION_FAILED")
        else { initialized = true; listener.onInitialized() }
    }
    override fun setLocale(locale: String) {
        require(locale in capabilities.locales) { "UNSUPPORTED_LOCALE" }
        appliedLocale = locale
    }
    override fun speak(speech: PreparedSpeech) {
        check(initialized && !released && active == null)
        active = speech
        if (!connected && mode == EngineMode.SERVER) { fail("NETWORK_ERROR"); return }
        spoken += speech
        listener?.onReady(speech.request.requestId)
        if (autoStart) start()
    }
    fun start() { active?.let { listener?.onStart(it.request.requestId) } }
    fun complete() { val id = active?.request?.requestId ?: return; active = null; listener?.onDone(id) }
    fun fail(code: String) { val id = active?.request?.requestId; active = null; listener?.onError(id, code) }
    override fun stop() { val id = active?.request?.requestId ?: return; active = null; listener?.onStop(id) }
    override fun release() { stop(); listener = null; initialized = false; released = true }
}
class MockAudioFocus(var granted: Boolean = true) : AudioFocusController {
    private var loss: (() -> Unit)? = null
    var held = false; private set
    override fun request(onLoss: () -> Unit): Boolean { loss = onLoss; held = granted; return held }
    override fun abandon() { held = false; loss = null }
    fun lose() { val callback = loss; held = false; callback?.invoke() }
}
