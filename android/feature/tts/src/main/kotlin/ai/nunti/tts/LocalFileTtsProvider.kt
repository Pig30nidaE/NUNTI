package ai.nunti.tts

/** Platform player consumes the already verified bytes, never a path reopened after hashing. */
interface LocalAudioPlayer {
    interface Events {
        fun started()
        fun completed()
        fun failed(reason: String)
    }
    fun play(wav: ByteArray, events: Events)
    fun close()
}

class LocalFileTtsProvider(catalog: LocalVoiceCatalog,
    private val playerFactory: () -> LocalAudioPlayer) : TtsProvider {
    private var catalog = catalog
    override val capabilities = catalog.capabilities
    override val mode = EngineMode.LOCAL_FILE
    override fun source(request: SpeechRequest) = SpeechSource(mode, catalog.providerId)
    override fun rejection(speech: PreparedSpeech) = catalog.rejection(speech)
    private var listener: TtsProvider.Listener? = null
    private var player: LocalAudioPlayer? = null
    private var active: String? = null
    private var generation = 0L
    private var released = false
    /** Owning lane only. Extend approved texts without recreating the queue or touching active audio. */
    fun updateCatalog(expanded: LocalVoiceCatalog) {
        check(!released)
        if (expanded.providerId != catalog.providerId || expanded.capabilities != capabilities ||
            expanded.profiles != catalog.profiles) throw VoiceAssetException("VOICE_CATALOG_IDENTITY_CHANGED")
        val byId = expanded.clips.associateBy { it.clipId }
        if (catalog.clips.any { byId[it.clipId] != it }) throw VoiceAssetException("VOICE_CATALOG_NOT_APPEND_ONLY")
        catalog = expanded
    }
    override fun initialize(listener: TtsProvider.Listener) {
        check(!released)
        this.listener = listener
        listener.onInitialized()
    }
    override fun setLocale(locale: String) { require(locale in capabilities.locales) }
    override fun speak(speech: PreparedSpeech) {
        check(!released && listener != null && active == null)
        val id = speech.request.requestId
        val bytes = try { catalog.load(speech) } catch (e: VoiceAssetException) {
            listener?.onError(id, e.reason); return
        }
        val token = ++generation
        active = id
        try {
            val created = playerFactory(); player = created
            created.play(bytes, object : LocalAudioPlayer.Events {
                override fun started() { if (token == generation && active == id) listener?.onStart(id) }
                override fun completed() { if (token == generation && active == id) finish(null) }
                override fun failed(reason: String) { if (token == generation && active == id) finish(reason) }
            })
        } catch (_: Exception) { if (token == generation) finish("LOCAL_PLAYER_ERROR") }
    }
    private fun retire() {
        ++generation; active = null
        val old = player; player = null
        old?.close()
    }
    private fun finish(reason: String?) {
        val id = active ?: return
        try { retire() } catch (_: Exception) { listener?.onError(null, "LOCAL_RELEASE_FAILED"); return }
        if (reason == null) listener?.onDone(id) else listener?.onError(id, reason)
    }
    override fun stop() {
        val id = active
        retire()
        if (id != null) listener?.onStop(id)
    }
    override fun release() {
        if (released) return
        released = true
        try { retire() } finally { listener = null }
    }
}

/** Routes requests inside one queue. Selection initializes under the queue's 5s watchdog,
 * before focus/start timing. Errors never switch engines or replay a request. */
class CatalogTtsProvider(private val catalog: LocalVoiceCatalog,
    private val localFactory: () -> TtsProvider, private val pleosFactory: () -> TtsProvider) : TtsProvider {
    override val mode = EngineMode.ON_DEVICE
    override val capabilities = catalog.capabilities.copy(locales = setOf("ko-KR", "en-US", "fr-CA", "es-US", "es-MX"))
    override fun source(request: SpeechRequest) = if (catalog.routes(request))
        SpeechSource(EngineMode.LOCAL_FILE, catalog.providerId) else SpeechSource(EngineMode.ON_DEVICE, "pleos")
    override fun rejection(speech: PreparedSpeech) = if (catalog.routes(speech.request)) catalog.rejection(speech)
        else if (speech.request.voiceProfileId != null && speech.request.voiceProfileId != "nunti-default-v1") "UNKNOWN_VOICE_PROFILE"
        else if (speech.voice.speakerId != null) "UNVERIFIED_SPEAKER" else null
    private var listener: TtsProvider.Listener? = null
    private var delegate: TtsProvider? = null
    private var selectedLocal: Boolean? = null
    private var initialized = false
    private var active: String? = null
    private var generation = 0L
    private var released = false
    override fun select(speech: PreparedSpeech): Boolean {
        check(active == null && !released)
        val local = catalog.routes(speech.request)
        if (selectedLocal != local || delegate == null) {
            retire()
            delegate = if (local) localFactory() else pleosFactory()
            selectedLocal = local
        }
        return initialized
    }
    override fun initialize(listener: TtsProvider.Listener) {
        check(!released)
        this.listener = listener
        val selected = delegate
        // Foreground can warm the queue without requiring a selected utterance or emitting audio.
        if (selected == null) { listener.onInitialized(); return }
        val token = generation
        selected.initialize(object : TtsProvider.Listener {
            private fun live() = token == generation && !released
            override fun onInitialized() {
                if (!live() || initialized) return
                initialized = true; listener.onInitialized()
            }
            override fun onReady(requestId: String) { if (live() && active == requestId) listener.onReady(requestId) }
            override fun onStart(requestId: String) { if (live() && active == requestId) listener.onStart(requestId) }
            override fun onDone(requestId: String) { if (live() && active == requestId) finish(null, false) }
            override fun onStop(requestId: String) { if (live() && active == requestId) finish(null, true) }
            override fun onError(requestId: String?, code: String) {
                if (!live()) return
                if (active != null && (requestId == null || requestId == active)) finish(code, false)
                else if (requestId == null) listener.onError(null, code)
            }
        })
    }
    override fun setLocale(locale: String) { require(locale in capabilities.locales); delegate?.setLocale(locale) }
    override fun speak(speech: PreparedSpeech) {
        check(!released && active == null && initialized)
        active = speech.request.requestId
        try { checkNotNull(delegate).speak(speech) }
        catch (_: Exception) { finish("PROVIDER_EXCEPTION", false) }
    }
    private fun retire() {
        ++generation; active = null; initialized = false
        val old = delegate; delegate = null; selectedLocal = null
        old?.release()
    }
    private fun finish(reason: String?, stopped: Boolean) {
        val id = active ?: return
        try { retire() } catch (_: Exception) { listener?.onError(null, "PROVIDER_RELEASE_FAILED"); return }
        when {
            reason != null -> listener?.onError(id, reason)
            stopped -> listener?.onStop(id)
            else -> listener?.onDone(id)
        }
    }
    override fun stop() {
        val id = active
        retire()
        if (id != null) listener?.onStop(id)
    }
    override fun release() {
        if (released) return
        released = true
        try { retire() } finally { listener = null }
    }
}
