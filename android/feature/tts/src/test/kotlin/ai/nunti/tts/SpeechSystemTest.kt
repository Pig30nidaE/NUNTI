package ai.nunti.tts

private class Time : SpeechClock, SpeechScheduler {
    var wall = 1_800_000_000_000L
    var mono = 0L
    private data class Task(val at: Long, val action: () -> Unit, var cancelled: Boolean = false)
    private val tasks = mutableListOf<Task>()
    override fun epochMs() = wall
    override fun monotonicMs() = mono
    override fun after(delayMs: Long, action: () -> Unit): Cancellation {
        val t = Task(mono + delayMs, action); tasks += t
        return Cancellation { t.cancelled = true }
    }
    fun advance(ms: Long, moveWall: Boolean = true) {
        val end = mono + ms
        while (true) {
            val next = tasks.filter { !it.cancelled && it.at <= end }.minByOrNull { it.at } ?: break
            tasks.remove(next); if (moveWall) wall += next.at - mono; mono = next.at; next.action()
        }
        if (moveWall) wall += end - mono; mono = end
        tasks.removeAll { it.cancelled }
    }
}
private class Fixture(val provider: MockTtsProvider = MockTtsProvider(), capacity: Int = 8, maxIds: Int = 4096) {
    val time = Time(); val focus = MockAudioFocus(); val events = mutableListOf<SpeechEvent>()
    val q = SpeechQueueManager(provider, focus, time, time, capacity = capacity, maxRequestIds = maxIds, sink = events::add)
    var context = parked()
    init { q.beginTrip("trip"); q.updateContext(context) }
    fun parked() = PlaybackContext("trip", TripPhase.PRE_TRIP, time.mono, true, true, false,
        VehicleMotion.PARKED, true, false, 0, Permission.UNKNOWN, Permission.ALLOWED,
        AudioActivity.QUIET, AudioActivity.QUIET, AudioActivity.QUIET)
    fun driving(allowed: Boolean = true) {
        context = parked().copy(phase = TripPhase.DRIVING, motion = VehicleMotion.MOVING,
            requiresDistractionOptimization = true,
            appAllowedWhileDriving = if (allowed) Permission.ALLOWED else Permission.UNKNOWN)
        q.updateContext(context)
    }
    fun input(id: String = "r1", text: String = "안녕하세요. 함께 떠나볼까요?", emotion: Emotion = Emotion.NEUTRAL,
        priority: Priority = Priority.NORMAL, ttl: Long = 10_000): ApprovedSpeech {
        val phase = context.phase!!
        val purpose = when (phase) {
            TripPhase.PRE_TRIP -> ContentSource.PRE_DRIVE_GREETING
            TripPhase.POST_TRIP -> ContentSource.POST_DRIVE_REPORT
            else -> ContentSource.VERIFIED_EVENT_RESPONSE
        }
        val snapshot = EmotionSnapshot("emotion-1", "trip", "avatar", emotion, time.wall)
        return ApprovedSpeech(SpeechRequest(id, "trip", "avatar", text, emotion, "nunti-default-v1", phase,
            priority, time.wall, time.wall + ttl, purpose, snapshot.emotionId, "event-1"),
            AvatarVoiceInput("avatar", "nunti", "nunti-default-v1"), snapshot, true)
    }
    fun lastReason() = events.last().reason
}
private class FakeConnection : PleosConnection {
    var success: (() -> Unit)? = null; var failure: ((String) -> Unit)? = null
    var connected: (() -> Unit)? = null; var connectFailure: ((String) -> Unit)? = null
    var callback: PleosConnection.Events? = null
    var adds = 0; var removes = 0; var stops = 0; var releases = 0
    var speakers = mutableListOf<String>(); var throwSpeaker = false
    var words = mutableListOf<String>(); var locales = mutableListOf<String>()
    var throwStop = false; var throwRemove = false
    override fun initialize(success: () -> Unit, failure: (String) -> Unit) { this.success = success; this.failure = failure }
    override fun addListener(events: PleosConnection.Events) { adds++; callback = events }
    override fun removeListener(events: PleosConnection.Events) { check(callback === events); removes++; if (throwRemove) error("remove") }
    override fun registerApp(credentials: PleosCredentials, connected: () -> Unit, failed: (String) -> Unit) {
        this.connected = connected; connectFailure = failed
    }
    override fun setLocale(locale: String) { locales += locale }
    override fun setSpeaker(speakerId: String) { if (throwSpeaker) error("speaker"); speakers += speakerId }
    override fun speak(text: String) { words += text }
    override fun stop() { stops++; if (throwStop) error("stop") }
    override fun release() { releases++ }
}
private class Listener : TtsProvider.Listener {
    val events = mutableListOf<String>()
    override fun onInitialized() { events += "initialized" }
    override fun onStart(requestId: String) { events += "start:$requestId" }
    override fun onDone(requestId: String) { events += "done:$requestId" }
    override fun onStop(requestId: String) { events += "stop:$requestId" }
    override fun onError(requestId: String?, code: String) { events += "error:$requestId:$code" }
}
private var count = 0
private val failures = mutableListOf<String>()
private fun test(name: String, body: () -> Unit) {
    try { body(); count++; println("PASS $name") }
    catch (e: Throwable) { failures += name; System.err.println("FAIL $name: $e"); e.printStackTrace() }
}
private fun expectFailure(code: String, action: () -> Unit) {
    val e = runCatching(action).exceptionOrNull(); check(e is IllegalArgumentException && e.message == code) { "Expected $code, got $e" }
}
fun main() {
    test("Korean greeting starts and completes with focus cleanup") {
        val f=Fixture(); check(f.q.submit(f.input()) == SpeechStatus.QUEUED)
        check(f.provider.spoken.single().request.text == "안녕하세요. 함께 떠나볼까요?"); check(f.focus.held)
        f.provider.complete(); check(f.events.last().status == SpeechStatus.COMPLETED); check(!f.focus.held)
    }
    test("empty whitespace is rejected") { val f=Fixture(); f.q.submit(f.input(text=" \n")); check(f.lastReason()=="EMPTY_TEXT") }
    test("long text is rejected") { val f=Fixture(); f.q.submit(f.input(text="가".repeat(2001))); check(f.lastReason()=="TEXT_TOO_LONG") }
    test("unknown locale fails without silently changing language") {
        val profiles=VoiceProfileManager(listOf(VoiceProfile(locale="xx-XX")))
        expectFailure("UNSUPPORTED_LOCALE") { profiles.resolve("nunti-default-v1",Emotion.NEUTRAL,ProviderCapabilities()) }
    }
    test("missing and invalid profile fall back") {
        val p=VoiceProfileManager(); listOf(null,"absent").forEach { check(p.resolve(it,Emotion.NEUTRAL,ProviderCapabilities()).fallback) }
    }
    test("unsupported voice controls are recorded but not applied") {
        val p=VoiceProfileManager(listOf(VoiceProfile(preferredVoiceId="unverified",supportedControls=Control.entries.toSet())))
        val v=p.resolve("nunti-default-v1",Emotion.JOYFUL,ProviderCapabilities());check(v.speakerId==null)
        check(v.appliedControls==setOf(Control.LOCALE));check(v.ignoredControls.containsAll(setOf(Control.PITCH,Control.RATE,Control.EMOTION,Control.SPEAKER)))
    }
    test("all six emotions preserve speaker and supplied text") {
        Emotion.entries.forEach { e -> val f=Fixture();val i=f.input(emotion=e);f.q.submit(i)
            check(f.provider.spoken.single().request.text==i.request.text);check(f.provider.spoken.single().voice.speakerId==null)
            check(f.provider.spoken.single().voice.logicalStyle==EmotionVoiceMapper().style(e)) }
    }
    test("persona route hint does not change voice identity") {
        val f=Fixture(); val i=f.input(); f.q.submit(i.copy(avatar=i.avatar.copy(persona="adventurous",voiceStyleHint="excited")))
        check(f.provider.spoken.single().voice.profileId=="nunti-default-v1")
    }
    test("emotion mismatch is rejected") { val f=Fixture(); val i=f.input(); f.q.submit(i.copy(snapshot=i.snapshot!!.copy(emotion=Emotion.STARTLED)));check(f.lastReason()=="EMOTION_MISMATCH") }
    test("missing emotion snapshot is rejected") { val f=Fixture(); f.q.submit(f.input(emotion=Emotion.JOYFUL).copy(snapshot=null));check(f.lastReason()=="MISSING_EMOTION") }
    test("rapid emotion changes do not mutate an active utterance") {
        val f=Fixture();f.q.submit(f.input(emotion=Emotion.RELAXED));f.q.submit(f.input("r2",emotion=Emotion.STARTLED))
        check(f.provider.spoken.single().request.emotion==Emotion.RELAXED);check(f.lastReason()=="DUPLICATE_TEXT")
    }
    test("unverified content is rejected") { val f=Fixture();f.q.submit(f.input().copy(contentVerified=false));check(f.lastReason()=="UNVERIFIED_CONTENT") }
    test("missing verified event reference is rejected") { val f=Fixture();f.driving();val i=f.input();f.q.submit(i.copy(request=i.request.copy(sourceEventId=null)));check(f.lastReason()=="MISSING_EVENT_EVIDENCE") }
    test("request ID remains deduplicated after completion") { val f=Fixture();val i=f.input();f.q.submit(i);f.provider.complete();f.q.submit(i);check(f.lastReason()=="DUPLICATE_ID") }
    test("duplicate text is rejected while pending or active") { val f=Fixture();f.q.submit(f.input());f.q.submit(f.input("r2"));check(f.lastReason()=="DUPLICATE_TEXT") }
    test("same text repeat window survives completion") { val f=Fixture();f.q.submit(f.input());f.provider.complete();f.q.submit(f.input("r2"));check(f.lastReason()=="REPEATED_TEXT") }
    test("bounded request ledger rejects flood without evicting dedup IDs") { val f=Fixture(maxIds=1);f.q.submit(f.input());f.q.submit(f.input("r2","다음"));check(f.lastReason()=="REQUEST_LIMIT") }
    test("unconfirmed driving permission blocks output") { val f=Fixture();f.driving(false);f.q.submit(f.input());check(f.lastReason()=="DRIVING_NOT_ALLOWED") }
    test("confirmed driving permission allows short verified response") { val f=Fixture();f.driving();f.q.submit(f.input(text="휴, 이제 좀 안심돼요."));check(f.provider.spoken.size==1) }
    test("low priority driving response is suppressed") { val f=Fixture();f.driving();f.q.submit(f.input(priority=Priority.LOW));check(f.lastReason()=="LOW_PRIORITY_DRIVING") }
    test("long driving response is suppressed") { val f=Fixture();f.driving();f.q.submit(f.input(text="가".repeat(81)));check(f.lastReason()=="DRIVING_TEXT_TOO_LONG") }
    test("driving cooldown prevents unrelated event bursts") { val f=Fixture();f.driving();f.q.submit(f.input());f.provider.complete();f.q.submit(f.input("r2","다른 멘트"));check(f.lastReason()=="COOLDOWN") }
    test("unknown vehicle state blocks pre-trip bypass") { val f=Fixture();f.q.updateContext(f.context.copy(motion=VehicleMotion.UNKNOWN));f.q.submit(f.input());check(f.lastReason()=="UNKNOWN_PLATFORM_STATE") }
    test("moving vehicle cannot use pre-trip greeting") { val f=Fixture();f.q.updateContext(f.context.copy(motion=VehicleMotion.MOVING,appAllowedWhileDriving=Permission.ALLOWED));f.q.submit(f.input());check(f.lastReason()=="DRIVING_SOURCE") }
    test("STOPPED is not proof of parking") {
        val f=Fixture();f.context=f.context.copy(phase=TripPhase.STOPPED,motion=VehicleMotion.STOPPED);f.q.updateContext(f.context)
        f.q.submit(f.input());check(f.lastReason()=="DRIVING_NOT_ALLOWED")
    }
    test("navigation or call or critical sound blocks output") {
        val variants=listOf<(PlaybackContext)->PlaybackContext>({it.copy(navigation=AudioActivity.BUSY)}, {it.copy(call=AudioActivity.BUSY)}, {it.copy(criticalAudio=AudioActivity.BUSY)})
        variants.forEach { val f=Fixture();f.q.updateContext(it(f.context));f.q.submit(f.input());check(f.lastReason()=="OTHER_AUDIO") }
    }
    test("platform permission revoked during playback stops it") { val f=Fixture();f.q.submit(f.input());f.q.updateContext(f.context.copy(speechPermission=Permission.DENIED));check(f.provider.active==null);check(!f.focus.held) }
    test("permission release requires a new request") {
        val f=Fixture();f.q.updateContext(f.context.copy(speechPermission=Permission.DENIED));f.q.submit(f.input());f.q.updateContext(f.context)
        check(f.provider.spoken.isEmpty());f.q.submit(f.input("new"));check(f.provider.spoken.size==1)
    }
    test("stale platform state watchdog stops playback") { val f=Fixture();f.q.submit(f.input());f.time.advance(5100);check(f.provider.active==null);check(f.lastReason()=="STALE_PLATFORM_STATE") }
    test("focus denial never calls speak") { val f=Fixture();f.focus.granted=false;f.q.submit(f.input());check(f.provider.spoken.isEmpty());check(f.lastReason()=="FOCUS_DENIED") }
    test("focus loss clears active and pending requests") { val f=Fixture();f.q.submit(f.input());f.q.submit(f.input("r2","다음 말"));f.focus.lose();check(f.q.pendingCount==0);check(f.provider.active==null) }
    test("expiry cancels synthesis before delayed start") { val f=Fixture(MockTtsProvider(autoStart=false));f.q.submit(f.input(ttl=200));f.time.advance(200);f.provider.start();check(f.events.none{it.status==SpeechStatus.STARTED});check(f.lastReason()=="EXPIRED") }
    test("monotonic deadline resists backward wall clock change") { val f=Fixture(MockTtsProvider(autoStart=false));f.q.submit(f.input(ttl=200));f.time.wall-=5000;f.time.advance(200,false);check(f.lastReason()=="EXPIRED") }
    test("start timeout cancels a stalled engine") { val f=Fixture(MockTtsProvider(autoStart=false));f.q.submit(f.input());f.time.advance(3000);check(f.lastReason()=="START_TIMEOUT");check(!f.focus.held) }
    test("expired pending request is never spoken later") { val f=Fixture();f.q.submit(f.input());f.q.submit(f.input("r2","다음 말",ttl=100));f.time.advance(100);f.provider.complete();check(f.provider.spoken.size==1) }
    test("higher priority request preempts lower priority") { val f=Fixture();f.q.submit(f.input(priority=Priority.LOW));f.q.submit(f.input("r2","중요한 말",priority=Priority.HIGH));check(f.provider.active?.request?.requestId=="r2");check(f.events.any{it.reason=="PREEMPTED"}) }
    test("bounded queue evicts lower priority pending request") {
        val f=Fixture(capacity=1);f.q.submit(f.input(priority=Priority.HIGH));f.q.submit(f.input("r2","낮은 말",priority=Priority.LOW))
        f.q.submit(f.input("r3","보통 말"));check(f.q.pendingCount==1);check(f.events.any{it.requestId=="r2"&&it.reason=="EVICTED"})
        f.provider.complete();check(f.provider.active?.request?.requestId=="r3")
    }
    test("full queue rejects equal priority") { val f=Fixture(capacity=1);f.q.submit(f.input());f.q.submit(f.input("r2","둘"));f.q.submit(f.input("r3","셋"));check(f.lastReason()=="QUEUE_FULL") }
    test("new trip clears previous requests and context") { val f=Fixture();f.q.submit(f.input());f.q.beginTrip("next");check(f.provider.active==null);f.q.submit(f.input("r2"));check(f.lastReason()=="WRONG_TRIP") }
    test("beginning same trip does not reset deduplication") { val f=Fixture();val i=f.input();f.q.submit(i);f.provider.complete();f.q.beginTrip("trip");f.q.submit(i);check(f.lastReason()=="DUPLICATE_ID") }
    test("cancelled request releases focus") { val f=Fixture();f.q.submit(f.input());f.q.cancel("r1");check(f.provider.active==null);check(!f.focus.held);check(f.lastReason()=="USER_CANCELLED") }
    test("background clears without automatic replay on resume") { val f=Fixture();val l=SpeechLifecycleManager(f.q);f.q.submit(f.input());l.onBackground();l.onForeground(f.context);check(f.provider.active==null);check(f.q.pendingCount==0) }
    test("suspend clears focus and queue") { val f=Fixture();f.q.submit(f.input());SpeechLifecycleManager(f.q).onSuspend();check(!f.focus.held);check(f.provider.active==null) }
    test("release is idempotent and rejects later requests") { val f=Fixture();f.q.submit(f.input());f.q.release();f.q.release();f.q.submit(f.input("r2"));check(f.provider.released);check(f.lastReason()=="PROVIDER_UNAVAILABLE") }
    test("server mode network failure is terminal") { val f=Fixture(MockTtsProvider(EngineMode.SERVER,connected=false));f.q.submit(f.input());check(f.events.any{it.status==SpeechStatus.FAILED&&it.reason=="NETWORK_ERROR"});check(!f.focus.held) }
    test("hybrid fallback simulation works offline") { val f=Fixture(MockTtsProvider(EngineMode.HYBRID,connected=false));f.q.submit(f.input());check(f.provider.spoken.size==1) }
    test("on-device simulation works offline") { val f=Fixture(MockTtsProvider(connected=false));f.q.submit(f.input());check(f.provider.spoken.size==1) }
    test("initialization failure does not retain queued work") { val f=Fixture(MockTtsProvider(failInitialization=true));f.q.submit(f.input());check(f.q.pendingCount==0);check(!f.focus.held);check(f.provider.released) }
    test("restarted session refuses historical request replay") {
        val f=Fixture();val old=f.input();f.time.advance(1)
        val q=SpeechQueueManager(MockTtsProvider(),MockAudioFocus(),f.time,f.time,sink=f.events::add);q.beginTrip("trip");q.updateContext(f.context)
        q.submit(old);check(f.lastReason()=="BEFORE_SESSION")
    }
    test("final report text remains byte-for-byte identical") {
        val f=Fixture();f.context=f.context.copy(phase=TripPhase.POST_TRIP);f.q.updateContext(f.context)
        val text="중간에 조금 놀라기도 했지만,\n다시 편안하게 달려서 마음이 놓였어요. "
        f.q.submit(f.input(text=text));check(f.provider.spoken.single().request.text==text)
    }
    test("wire provenance and purpose stay separate") {
        val f=Fixture();val i=f.input();val w=WireSpeechRequest("1.0","r","trip","avatar",i.request.text,"nunti-default-v1","NEUTRAL","PRE_TRIP","NORMAL", "2027-01-15T08:00:00Z","2027-01-15T08:00:10Z","TEMPLATE",emotionId="emotion-1")
        val a=SpeechContractBridge.fromWire(w,i.avatar,i.snapshot,SpeechEvidence(approvedText=true));check(a.contentVerified);check(a.request.contentSource==ContentSource.PRE_DRIVE_GREETING)
        expectFailure("MOCK_DISABLED") { SpeechContractBridge.fromWire(w.copy(contentSource="MOCK"),i.avatar,i.snapshot,SpeechEvidence()) }
    }
    test("event enum alone never proves verification") {
        val f=Fixture(); val i=f.input();val w=WireSpeechRequest("1.0","r","trip","avatar","괜찮아요.","nunti-default-v1","NEUTRAL","DRIVING","NORMAL","2027-01-15T08:00:00Z","2027-01-15T08:00:10Z","TEMPLATE","VERIFIED_EVENT_RESPONSE","ev","emotion-1")
        check(!SpeechContractBridge.fromWire(w,i.avatar,i.snapshot,SpeechEvidence(approvedText=true)).contentVerified)
    }
    test("Pleos initialization and listener are registered once") {
        val sdk=FakeConnection();val p=PleosTtsProvider({sdk});val l=Listener();p.initialize(l);p.initialize(l);sdk.success!!();sdk.success!!()
        check(sdk.adds==1);check(l.events==listOf("initialized"));p.release();p.release();check(sdk.removes==1);check(sdk.releases==1)
    }
    test("Pleos applies a verified speaker before speaking and falls back for unknown ids") {
        fun profile(id: String) = VoiceProfileManager(listOf(VoiceProfile("nunti-default-v1", preferredVoiceId = id,
            supportedControls = setOf(Control.LOCALE, Control.SPEAKER))))
        val f=Fixture(); val sdk=FakeConnection(); val p=PleosTtsProvider({sdk}); val l=Listener(); p.initialize(l); sdk.success!!()
        val known=SpeechRequestBuilder(profile("haeun")).build(f.input(),p.capabilities,f.time.wall)
        check(known.voice.speakerId=="haeun"); p.speak(known)
        check(sdk.speakers==listOf("haeun")); check(sdk.words==listOf(known.request.text))
        val unknown=SpeechRequestBuilder(profile("not-a-speaker")).build(f.input("r2"),p.capabilities,f.time.wall)
        check(unknown.voice.speakerId==null)
    }
    test("Pleos speaker failure is reported and nothing is spoken") {
        val f=Fixture(); val sdk=FakeConnection(); val p=PleosTtsProvider({sdk}); val l=Listener(); p.initialize(l); sdk.success!!(); sdk.throwSpeaker=true
        val known=SpeechRequestBuilder(VoiceProfileManager(listOf(VoiceProfile("nunti-default-v1", preferredVoiceId = "haeun",
            supportedControls = setOf(Control.LOCALE, Control.SPEAKER))))).build(f.input(),p.capabilities,f.time.wall)
        p.speak(known); check(sdk.words.isEmpty()); check(l.events.last().endsWith("SDK_SPEAKER_EXCEPTION"))
    }
    test("Pleos stale callbacks cannot finish next utterance") {
        val sessions=mutableListOf<FakeConnection>();val p=PleosTtsProvider({FakeConnection().also{sessions+=it}});val l=Listener();val f=Fixture()
        p.initialize(l);sessions[0].success!!();p.speak(SpeechRequestBuilder().build(f.input(),p.capabilities,f.time.wall))
        val old=sessions[0].callback!!;old.start();p.stop();p.speak(SpeechRequestBuilder().build(f.input("r2","다음 말"),p.capabilities,f.time.wall))
        sessions[1].success!!();old.done();old.error("NETWORK_ERROR");check(l.events.none{it=="done:r2"||it.contains("NETWORK_ERROR")})
        sessions[1].callback!!.done();check(l.events.last()=="done:r2");check(sessions[0].removes==1)
    }
    test("Pleos server waits for registration connection") {
        val sdk=FakeConnection();val p=PleosTtsProvider({sdk},EngineMode.SERVER,{PleosCredentials("id","secret")});val l=Listener()
        p.initialize(l);sdk.success!!();check(l.events.isEmpty());sdk.connected!!();check(l.events==listOf("initialized"))
    }
    test("Pleos registration failure reports actual error") {
        val sdk=FakeConnection();val p=PleosTtsProvider({sdk},EngineMode.HYBRID,{PleosCredentials("id","secret")});val l=Listener()
        p.initialize(l);sdk.success!!();sdk.connectFailure!!("UNAUTHENTICATED");check(l.events.last()=="error:null:UNAUTHENTICATED");check(sdk.releases==1)
    }
    test("Pleos missing credentials does not pretend hybrid is connected") {
        val sdk=FakeConnection();val p=PleosTtsProvider({sdk},EngineMode.HYBRID);val l=Listener();p.initialize(l);sdk.success!!();check(l.events.last()=="error:null:MISSING_CREDENTIALS")
    }
    test("Pleos initialization failure and late success are isolated") {
        val sdk=FakeConnection();val p=PleosTtsProvider({sdk});val l=Listener();p.initialize(l);sdk.failure!!("PERMISSION_DENIED");sdk.success!!()
        check(l.events==listOf("error:null:PERMISSION_DENIED"));check(sdk.adds==0)
    }
    test("Pleos release ignores late initialization callback") { val sdk=FakeConnection();val p=PleosTtsProvider({sdk});val l=Listener();p.initialize(l);p.release();sdk.success!!();check(l.events.isEmpty());check(sdk.adds==0) }
    test("Pleos cleanup still releases when listener removal throws") {
        val sdk=FakeConnection();val p=PleosTtsProvider({sdk});p.initialize(Listener());sdk.success!!();sdk.throwRemove=true;p.release();check(sdk.releases==1)
    }
    test("queue initialization timeout releases hung SDK") {
        val time=Time();val sdk=FakeConnection();val p=PleosTtsProvider({sdk});val q=SpeechQueueManager(p,MockAudioFocus(),time,time)
        q.initialize();time.advance(5000);check(sdk.releases==1);sdk.success!!();check(sdk.adds==0)
    }
    test("observer exception does not interrupt cleanup") {
        val t=Time();val p=MockTtsProvider();val focus=MockAudioFocus();val q=SpeechQueueManager(p,focus,t,t,sink={error("observer")})
        val f=Fixture();q.beginTrip("trip");q.updateContext(f.context);q.submit(f.input());p.complete();check(!focus.held)
    }
    println("${count} tests passed; ${failures.size} failed")
    check(failures.isEmpty()) { failures.joinToString() }
    runLocalVoiceTests()
}
