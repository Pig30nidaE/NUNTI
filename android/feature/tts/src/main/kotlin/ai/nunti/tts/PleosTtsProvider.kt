package ai.nunti.tts

/** Seam implemented by the real 3.3.1 SDK wrapper; fake implementations only belong in tests. */
interface PleosConnection {
    interface Events {
        fun ready(); fun start(); fun done(); fun stopped(); fun error(code: String)
        fun rms(value: Double) {}
    }
    fun initialize(success: () -> Unit, failure: (String) -> Unit)
    fun addListener(events: Events)
    fun removeListener(events: Events)
    fun registerApp(credentials: PleosCredentials, connected: () -> Unit, failed: (String) -> Unit)
    fun setLocale(locale: String)
    fun speak(text: String)
    fun stop()
    fun release()
}
class PleosCredentials(val clientId: String, val clientSecret: String) {
    init { require(clientId.isNotBlank() && clientSecret.isNotBlank()) }
    override fun toString() = "PleosCredentials(REDACTED)"
}

/** Uses a new SDK connection after each terminal utterance to isolate callbacks lacking request IDs. */
class PleosTtsProvider(private val factory: (EngineMode) -> PleosConnection,
    override val mode: EngineMode = EngineMode.ON_DEVICE,
    private val credentials: (() -> PleosCredentials?) = { null }) : TtsProvider {
    override val capabilities = ProviderCapabilities(locales = setOf("ko-KR", "en-US", "fr-CA", "es-US", "es-MX"))
    private var listener: TtsProvider.Listener? = null
    private var generation = 0L
    private var connection: PleosConnection? = null
    private var events: PleosConnection.Events? = null
    private var connectionReady = false
    private var initialized = false
    private var initializing = false
    private var released = false
    private var broken = false
    private var locale = "ko-KR"
    private var active: PreparedSpeech? = null
    private var dispatched = false
    override fun initialize(listener: TtsProvider.Listener) {
        check(!released && !broken) { "RELEASED" }
        if (initialized || initializing) return
        this.listener = listener; initializing = true
        connect()
    }
    override fun setLocale(locale: String) {
        require(locale in capabilities.locales) { "UNSUPPORTED_LOCALE" }
        this.locale = locale
    }
    override fun speak(speech: PreparedSpeech) {
        check(initialized && !released && !broken && active == null) { "NOT_READY" }
        require(speech.voice.speakerId == null) { "UNVERIFIED_SPEAKER" }
        active = speech; locale = speech.voice.locale; dispatched = false
        if (connection == null) connect() else dispatch()
    }
    private fun connect() {
        val token = ++generation
        var setupStarted = false
        try {
            val sdk = factory(mode); connection = sdk
            sdk.initialize(success = {
                if (token == generation && !released && !setupStarted) {
                    setupStarted = true
                    try {
                        val callback = object : PleosConnection.Events {
                            override fun ready() { if (live(token)) active?.let { listener?.onReady(it.request.requestId) } }
                            override fun start() { if (live(token)) active?.let { listener?.onStart(it.request.requestId) } }
                            override fun done() { if (live(token)) terminal(null, false) }
                            override fun stopped() { if (live(token)) terminal(null, true) }
                            override fun error(code: String) { if (live(token)) fail(code) }
                        }
                        events = callback; sdk.addListener(callback); sdk.setLocale(locale)
                        if (mode == EngineMode.ON_DEVICE) connected(token)
                        else {
                            val auth = credentials()
                            if (auth == null) fail("MISSING_CREDENTIALS")
                            else sdk.registerApp(auth, { connected(token) }, { if (live(token)) fail(it) })
                        }
                    } catch (_: Exception) { if (live(token)) fail("SDK_SETUP_EXCEPTION") }
                }
            }, failure = { if (live(token)) fail(it) })
        } catch (_: Exception) { if (live(token)) fail("SDK_INITIALIZATION_EXCEPTION") }
    }
    private fun connected(token: Long) {
        if (!live(token)) return
        connectionReady = true
        if (!initialized) { initialized = true; initializing = false; listener?.onInitialized() }
        dispatch()
    }
    private fun dispatch() {
        val speech = active ?: return
        if (!connectionReady || dispatched || released) return
        dispatched = true
        try { connection!!.setLocale(locale); connection!!.speak(speech.request.text) }
        catch (_: Exception) { fail("SDK_SPEAK_EXCEPTION") }
    }
    private fun live(token: Long) = token == generation && !released
    private fun terminal(error: String?, stopped: Boolean) {
        val id = active?.request?.requestId ?: return
        active = null
        val clean = retire(stop = error != null)
        if (!clean) { broken = true; listener?.onError(id, "SDK_CLEANUP_FAILED"); listener?.onError(null, "SDK_CLEANUP_FAILED") }
        else if (error != null) listener?.onError(id, error)
        else if (stopped) listener?.onStop(id) else listener?.onDone(id)
    }
    private fun fail(code: String) {
        if (active != null) terminal(code, false)
        else {
            initializing = false; initialized = false; retire(true)
            listener?.onError(null, code)
        }
    }
    private fun retire(stop: Boolean): Boolean {
        ++generation // Invalidate callbacks before stop/remove/release, including synchronous callbacks.
        val sdk = connection; val callback = events
        connection = null; events = null; connectionReady = false; dispatched = false
        var clean = true
        if (sdk != null) {
            if (stop) try { sdk.stop() } catch (_: Exception) { clean = false }
            if (callback != null) try { sdk.removeListener(callback) } catch (_: Exception) { clean = false }
            try { sdk.release() } catch (_: Exception) { clean = false }
        }
        return clean
    }
    override fun stop() {
        val id = active?.request?.requestId; active = null
        if (!retire(true)) { broken = true; error("SDK_STOP_FAILED") }
        if (id != null) listener?.onStop(id)
    }
    override fun release() {
        if (released) return
        released = true; val id = active?.request?.requestId; active = null
        retire(true); initialized = false; initializing = false
        if (id != null) listener?.onStop(id)
        listener = null
    }
}
