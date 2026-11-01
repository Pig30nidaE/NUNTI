package ai.nunti.tts

/** Single serial lane required. AndroidVoiceSession marshals every callback to the main looper. */
class SpeechQueueManager(private val provider: TtsProvider, private val focus: AudioFocusController,
    private val clock: SpeechClock, private val scheduler: SpeechScheduler,
    private val builder: SpeechRequestBuilder = SpeechRequestBuilder(),
    private val policy: SpeechPlaybackPolicy = SpeechPlaybackPolicy(),
    private val capacity: Int = 8, private val maxRequestIds: Int = 4096,
    private val sink: (SpeechEvent) -> Unit = {}) : TtsProvider.Listener {
    private data class Entry(val speech: PreparedSpeech, val submitted: Long, val deadline: Long,
        val sequence: Long, var dispatched: Long? = null, var started: Boolean = false)
    private val owner = Thread.currentThread()
    private val sessionEpoch = clock.epochMs()
    private val pending = mutableListOf<Entry>()
    private val seen = mutableSetOf<String>()
    private val spoken = linkedMapOf<String, Long>()
    private var current: Entry? = null
    private var context = PlaybackContext()
    private var tripId: String? = null
    private var sequence = 0L
    private var lastStart: Long? = null
    private var ready = false
    private var initializing = false
    private var initAt = 0L
    private var closed = false
    private var failed = false
    private var timer: Cancellation? = null
    val pendingCount get() = pending.size
    val activeRequestId get() = current?.speech?.request?.requestId
    init { require(capacity > 0 && maxRequestIds > 0) }
    private fun lane() { check(Thread.currentThread() == owner) { "Use the owning serial executor" } }
    fun initialize() {
        lane(); if (closed || ready || initializing || failed) return
        initializing = true; initAt = clock.monotonicMs()
        try { provider.initialize(this) } catch (_: Exception) { onError(null, "INITIALIZATION_EXCEPTION") }
        arm()
    }
    fun beginTrip(id: String) {
        lane(); check(!closed); require(id.isNotBlank())
        if (id == tripId) return
        cancelAll("NEW_TRIP"); tripId = id; seen.clear(); context = PlaybackContext()
    }
    fun updateContext(value: PlaybackContext) { lane(); if (closed) return; context = value; tick() }
    fun submit(input: ApprovedSpeech): SpeechStatus {
        lane()
        val r = input.request
        fun reject(reason: String): SpeechStatus { emit(r, SpeechStatus.REJECTED, reason); return SpeechStatus.REJECTED }
        if (closed || failed) return reject("PROVIDER_UNAVAILABLE")
        if (r.tripId != tripId) return reject("WRONG_TRIP")
        if (r.requestId in seen) return reject("DUPLICATE_ID")
        if (seen.size >= maxRequestIds) return reject("REQUEST_LIMIT")
        seen += r.requestId
        if (r.requestedAt < sessionEpoch) return reject("BEFORE_SESSION")
        val speech = try { builder.build(input, provider.capabilities, clock.epochMs()) }
            catch (e: IllegalArgumentException) { return reject(e.message ?: "INVALID_REQUEST") }
        val key = key(r.text)
        if (pending.any { key(it.speech.request.text) == key } || current?.let { key(it.speech.request.text) == key } == true)
            return reject("DUPLICATE_TEXT")
        val why = reason(speech.request)
        if (why != null) return reject(why)
        if (pending.size >= capacity) {
            val worst = pending.minWithOrNull(compareBy<Entry> { it.speech.request.priority.ordinal }.thenByDescending { it.sequence })!!
            if (worst.speech.request.priority >= r.priority) return reject("QUEUE_FULL")
            pending.remove(worst); emit(worst.speech.request, SpeechStatus.CANCELLED, "EVICTED")
        }
        val mono = clock.monotonicMs()
        pending += Entry(speech, mono, mono + (r.expiresAt - clock.epochMs()), sequence++)
        emit(r, SpeechStatus.QUEUED, voice = speech.voice)
        if (current?.speech?.request?.priority?.let { it < r.priority } == true) cancelCurrent("PREEMPTED")
        if (!ready) initialize()
        pump(); arm()
        return SpeechStatus.QUEUED
    }
    fun cancel(requestId: String) {
        lane()
        pending.filter { it.speech.request.requestId == requestId }.toList().forEach {
            pending.remove(it); emit(it.speech.request, SpeechStatus.CANCELLED, "USER_CANCELLED")
        }
        if (activeRequestId == requestId) cancelCurrent("USER_CANCELLED")
        pump(); arm()
    }
    fun cancelAll(reason: String) {
        lane()
        val removed = pending.toList(); pending.clear()
        removed.forEach { emit(it.speech.request, SpeechStatus.CANCELLED, reason) }
        cancelCurrent(reason); timer?.cancel(); timer = null
    }
    fun release() {
        lane(); if (closed) return
        closed = true; cancelAll("RELEASED"); ready = false; initializing = false
        try { provider.release() } catch (_: Exception) { /* Output already cancelled; no retry. */ }
        focus.abandon()
    }
    private fun reason(r: SpeechRequest, active: Boolean = false) = policy.rejection(r, context,
        clock.epochMs(), clock.monotonicMs(), lastStart, spoken[key(r.text)], active)
    private fun key(text: String) = text.trim().replace(Regex("\\s+"), " ")
    private fun tick() {
        if (closed) return
        val mono = clock.monotonicMs()
        if (initializing && mono - initAt >= 5_000) { onError(null, "INITIALIZATION_TIMEOUT"); return }
        pending.toList().forEach {
            val why = if (mono >= it.deadline) "EXPIRED" else reason(it.speech.request)
            if (why != null) { pending.remove(it); emit(it.speech.request, SpeechStatus.CANCELLED, why) }
        }
        current?.let {
            val why = when {
                mono >= it.deadline -> "EXPIRED"
                !it.started && mono - (it.dispatched ?: mono) >= 3_000 -> "START_TIMEOUT"
                mono - (it.dispatched ?: mono) >= 30_000 -> "PLAYBACK_TIMEOUT"
                else -> reason(it.speech.request, active = true)
            }
            if (why != null) cancelCurrent(why)
        }
        pump(); arm()
    }
    private fun pump() {
        if (closed || failed || !ready || current != null) return
        while (pending.isNotEmpty() && current == null) {
            val entry = pending.maxWithOrNull(compareBy<Entry> { it.speech.request.priority.ordinal }.thenBy { -it.sequence })!!
            pending.remove(entry)
            val why = if (clock.monotonicMs() >= entry.deadline) "EXPIRED" else reason(entry.speech.request)
            if (why != null) { emit(entry.speech.request, SpeechStatus.CANCELLED, why); continue }
            current = entry
            val granted = try { focus.request { onFocusLoss() } } catch (_: Exception) { false }
            if (!granted || current !== entry) {
                if (current === entry) { current = null; emit(entry.speech.request, SpeechStatus.CANCELLED, "FOCUS_DENIED") }
                focus.abandon(); continue
            }
            entry.dispatched = clock.monotonicMs()
            try { provider.setLocale(entry.speech.voice.locale); provider.speak(entry.speech) }
            catch (_: Exception) { onError(entry.speech.request.requestId, "PROVIDER_EXCEPTION") }
        }
    }
    fun onFocusLoss() { lane(); cancelAll("FOCUS_LOST") }
    private fun cancelCurrent(reason: String) {
        val e = current ?: return
        current = null
        try { provider.stop() } catch (_: Exception) {
            failed = true; ready = false
            try { provider.release() } catch (_: Exception) { }
        }
        focus.abandon(); emit(e.speech.request, SpeechStatus.CANCELLED, reason, e.speech.voice)
        if (failed) {
            pending.toList().forEach { emit(it.speech.request, SpeechStatus.FAILED, "STOP_FAILED") }
            pending.clear()
        }
    }
    private fun arm() {
        timer?.cancel(); timer = null
        if (!closed && !failed && (initializing || current != null || pending.isNotEmpty())) {
            val deadlines = pending.map { it.deadline } + listOfNotNull(current?.deadline)
            val delay = minOf(100L, ((deadlines.minOrNull() ?: (clock.monotonicMs() + 100)) - clock.monotonicMs()).coerceAtLeast(1))
            timer = scheduler.after(delay) { lane(); tick() }
        }
    }
    override fun onInitialized() { lane(); if (closed || failed) return; ready = true; initializing = false; pump(); arm() }
    override fun onReady(requestId: String) { lane() /* Per-utterance readiness is not initialization. */ }
    override fun onStart(requestId: String) {
        lane(); val e = current?.takeIf { it.speech.request.requestId == requestId } ?: return
        if (e.started) return
        val why = if (clock.monotonicMs() >= e.deadline) "EXPIRED" else reason(e.speech.request)
        if (why != null) { cancelCurrent(why); pump(); arm(); return }
        e.started = true; lastStart = clock.monotonicMs(); spoken[key(e.speech.request.text)] = lastStart!!
        while (spoken.size > 256) spoken.remove(spoken.keys.first())
        emit(e.speech.request, SpeechStatus.STARTED, voice = e.speech.voice,
            latency = clock.monotonicMs() - e.submitted)
    }
    override fun onDone(requestId: String) { finish(requestId, SpeechStatus.COMPLETED, null) }
    override fun onStop(requestId: String) { finish(requestId, SpeechStatus.CANCELLED, "PROVIDER_STOPPED") }
    override fun onError(requestId: String?, code: String) {
        lane(); if (closed) return
        if (requestId == null) {
            failed = true; ready = false; initializing = false
            cancelAll(code)
            try { provider.release() } catch (_: Exception) { }
        } else finish(requestId, SpeechStatus.FAILED, code)
    }
    private fun finish(id: String, status: SpeechStatus, reason: String?) {
        lane(); val e = current?.takeIf { it.speech.request.requestId == id } ?: return
        current = null; focus.abandon(); emit(e.speech.request, status, reason, e.speech.voice); pump(); arm()
    }
    private fun emit(r: SpeechRequest, status: SpeechStatus, reason: String? = null,
        voice: AppliedVoiceProfile? = null, latency: Long? = null) {
        // Observers cannot break focus cleanup or playback. Never log text or credentials here.
        try { sink(SpeechEvent(r.requestId, r.tripId, status, reason, voice, provider.mode, latency)) }
        catch (_: Exception) { }
    }
}

class SpeechLifecycleManager(private val queue: SpeechQueueManager) {
    fun onForeground(context: PlaybackContext) { queue.updateContext(context); queue.initialize() }
    fun onBackground() { queue.cancelAll("BACKGROUND"); queue.updateContext(PlaybackContext()) }
    /** Suspend disposes the session. Construct a fresh session after resume; never auto-replay. */
    fun onSuspend() = queue.release()
    fun close() = queue.release()
}
