package ai.nunti.tts

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files

private class VoiceTime : SpeechClock, SpeechScheduler {
    var wall = 1_800_000_000_000L
    var mono = 0L
    private data class Task(val at: Long, val action: () -> Unit, var cancelled: Boolean = false)
    private val tasks = mutableListOf<Task>()
    override fun epochMs() = wall
    override fun monotonicMs() = mono
    override fun after(delayMs: Long, action: () -> Unit): Cancellation {
        val task = Task(mono + delayMs, action); tasks += task
        return Cancellation { task.cancelled = true }
    }
    fun advance(ms: Long) {
        val end = mono + ms
        while (true) {
            val task = tasks.filter { !it.cancelled && it.at <= end }.minByOrNull { it.at } ?: break
            tasks.remove(task); wall += task.at - mono; mono = task.at; task.action()
        }
        wall += end - mono; mono = end
    }
}
private class VoicePlayer : LocalAudioPlayer {
    var events: LocalAudioPlayer.Events? = null
    var bytes: ByteArray? = null
    var closed = false
    override fun play(wav: ByteArray, events: LocalAudioPlayer.Events) {
        bytes = wav; this.events = events; events.started()
    }
    override fun close() { closed = true }
}
private fun wav(value: Int, sampleRateHz: Int = 16000): ByteArray {
    val frames = sampleRateHz / 100
    val buffer = ByteBuffer.allocate(44 + frames * 2).order(ByteOrder.LITTLE_ENDIAN)
    buffer.put("RIFF".toByteArray()).putInt(36 + frames * 2).put("WAVEfmt ".toByteArray()).putInt(16)
        .putShort(1).putShort(1).putInt(sampleRateHz).putInt(sampleRateHz * 2).putShort(2).putShort(16)
        .put("data".toByteArray()).putInt(frames * 2)
    repeat(frames) { buffer.putShort(value.toShort()) }
    return buffer.array()
}
private class VoiceFixture : AutoCloseable {
    val dir = Files.createTempDirectory("nunti-voice-test").toFile()
    val ledger = File(dir, "bindings.txt")
    val time = VoiceTime()
    val players = mutableListOf<VoicePlayer>()
    val events = mutableListOf<SpeechEvent>()
    val focus = MockAudioFocus()
    var defaultCalls = 0
    val common = "안녕하세요. 오늘의 여행도 함께할게요."
    val clips = (1..3).map { index -> clip("c$index", "p$index", "s$index", common, index) } +
        clip("c1", "p1", "s1", "다음 문장입니다.", 4)
    fun clip(character: String, profile: String, speaker: String, text: String, seed: Int): LocalVoiceClip {
        val bytes = wav(seed); val file = "sample-$seed.wav"; File(dir, file).writeBytes(bytes)
        return LocalVoiceClip("clip-$seed", character, profile, speaker, "ko-KR", text,
            voiceSha256(text.toByteArray()), file, voiceSha256(bytes), 16000, 1, 10,
            VoiceAssetIdentity.LegacyCatalog("model-v1", "binding-$character", 1.0, 16, "a".repeat(64)))
    }
    fun directed(seed: Long = 0xffff_ffffL): LocalVoiceClip {
        val bytes = wav(5, 24000)
        File(dir, "directed.wav").writeBytes(bytes)
        return LocalVoiceClip("directed", "directed-character", "directed-profile", "Sohee", "ko-KR", common,
            voiceSha256(common.toByteArray()), "directed.wav", voiceSha256(bytes), 24000, 1, 10,
            VoiceAssetIdentity.DirectedSohee(VoiceAssetIdentity.DirectedSohee.MODEL_REVISION,
                "dvb-" + "a".repeat(32), "b".repeat(64), "c".repeat(64), seed))
    }
    fun directedCatalog(values: List<LocalVoiceClip>) = LocalVoiceCatalog(VoiceAssetIdentity.DirectedSohee.PROVIDER_ID,
        values, dir, CharacterVoiceBindings(ledger))
    fun designed(providerId: String = VoiceAssetIdentity.DesignedVoice.FIXTURE): LocalVoiceClip {
        val voiceId = when (providerId) {
            VoiceAssetIdentity.DesignedVoice.FIXTURE -> "fixture-" + "a".repeat(24)
            VoiceAssetIdentity.DesignedVoice.GEMINI -> "voice_" + "a".repeat(24)
            else -> "a".repeat(20)
        }
        val source = when (providerId) {
            VoiceAssetIdentity.DesignedVoice.FIXTURE -> VoiceAssetIdentity.DesignedVoice(providerId,
                "offline-fixture-v1", "fixture-wav-v1", voiceId, "design-binding-1", "b".repeat(64), "c".repeat(64),
                VoiceMediaOrigin.OFFLINE_FIXTURE)
            VoiceAssetIdentity.DesignedVoice.GEMINI -> VoiceAssetIdentity.DesignedVoice(providerId,
                "gemini-3.8-flash-tts", "gemini-3.8-flash-tts", voiceId, "design-binding-1", "b".repeat(64), "c".repeat(64),
                VoiceMediaOrigin.PROVIDER_GENERATED)
            else -> VoiceAssetIdentity.DesignedVoice(providerId, "eleven_ttv_v3", "eleven_v4", voiceId,
                "design-binding-1", "b".repeat(64), "c".repeat(64), VoiceMediaOrigin.PROVIDER_GENERATED)
        }
        val bytes = wav(7, 24000)
        File(dir, "designed.wav").writeBytes(bytes)
        return LocalVoiceClip("designed", "designed-character", "designed-profile", voiceId, "ko-KR", common,
            voiceSha256(common.toByteArray()), "designed.wav", voiceSha256(bytes), 24000, 1, 10, source, "d".repeat(64))
    }
    fun designedCatalog(values: List<LocalVoiceClip>): LocalVoiceCatalog {
        val source = values.first().source as VoiceAssetIdentity.DesignedVoice
        return LocalVoiceCatalog(source.providerId, values, dir, CharacterVoiceBindings(ledger))
    }
    fun prepared(clip: LocalVoiceClip, catalog: LocalVoiceCatalog): PreparedSpeech {
        val input = input().let { it.copy(request = it.request.copy(avatarId = clip.characterId,
            voiceProfileId = clip.profileId, text = clip.text), avatar = AvatarVoiceInput(clip.characterId, clip.characterId, clip.profileId)) }
        return SpeechRequestBuilder(VoiceProfileManager(catalog.profiles)).build(input, catalog.capabilities, time.wall)
    }
    fun catalog(values: List<LocalVoiceClip> = clips) = LocalVoiceCatalog("experimental-local", values, dir, CharacterVoiceBindings(ledger))
    val catalog = catalog()
    fun player() = VoicePlayer().also { players += it }
    val provider = CatalogTtsProvider(catalog, { LocalFileTtsProvider(catalog, ::player) }, {
        defaultCalls++; MockTtsProvider()
    })
    val q = SpeechQueueManager(provider, focus, time, time,
        builder = SpeechRequestBuilder(VoiceProfileManager(catalog.profiles + VoiceProfile())), sink = events::add)
    var context = PlaybackContext("trip", TripPhase.POST_TRIP, 0, true, true, false, VehicleMotion.PARKED,
        true, false, 0, Permission.DENIED, Permission.ALLOWED, AudioActivity.QUIET, AudioActivity.QUIET, AudioActivity.QUIET)
    init { q.beginTrip("trip"); q.updateContext(context) }
    fun input(index: Int = 0, id: String = "r1", ttl: Long = 10000): ApprovedSpeech {
        val c = clips[index]
        return ApprovedSpeech(SpeechRequest(id, "trip", c.characterId, c.text, Emotion.NEUTRAL, c.profileId,
            TripPhase.POST_TRIP, Priority.NORMAL, time.wall, time.wall + ttl, ContentSource.USER_INITIATED),
            AvatarVoiceInput(c.characterId, c.characterId, c.profileId), null, true)
    }
    fun prepared(index: Int = 0) = SpeechRequestBuilder(VoiceProfileManager(catalog.profiles)).build(input(index), catalog.capabilities, time.wall)
    override fun close() { q.release(); dir.deleteRecursively() }
}

fun runLocalVoiceTests() {
    var count = 0
    fun test(name: String, action: (VoiceFixture) -> Unit) {
        VoiceFixture().use(action); count++; println("PASS local $name")
    }
    fun fails(reason: String, action: () -> Unit) {
        val error = runCatching(action).exceptionOrNull()
        check(error is VoiceAssetException && error.reason == reason) { "expected $reason, got $error" }
    }
    test("three characters select distinct verified WAV bytes") { f ->
        f.clips.take(3).forEachIndexed { i, clip -> check(f.catalog.load(f.prepared(i)).contentEquals(File(f.dir, clip.audioPath).readBytes())) }
    }
    test("initialization does not play; playback shares queue and focus") { f ->
        f.q.initialize(); check(f.players.isEmpty())
        f.q.submit(f.input()); check(f.players.size == 1 && f.focus.held)
        check(f.events.last().providerId == "experimental-local" && f.events.last().mode == EngineMode.LOCAL_FILE)
        f.players.single().events!!.completed(); check(!f.focus.held && f.events.last().status == SpeechStatus.COMPLETED)
    }
    test("unknown profile cannot reach Pleos default fallback") { f ->
        val input = f.input().let { it.copy(request = it.request.copy(avatarId = "unknown", voiceProfileId = "missing"),
            avatar = AvatarVoiceInput("unknown", "unknown", "missing")) }
        check(f.q.submit(input) == SpeechStatus.REJECTED)
        check(f.events.last().reason == "UNKNOWN_VOICE_PROFILE" && f.defaultCalls == 0 && f.players.isEmpty())
    }
    test("cross character profile and wrong speaker rejected") { f ->
        val p = f.prepared()
        fails("VOICE_PROFILE_MISMATCH") { f.catalog.load(p.copy(request = p.request.copy(avatarId = "c2"))) }
        fails("VOICE_SPEAKER_MISMATCH") { f.catalog.load(p.copy(voice = p.voice.copy(speakerId = "s2"))) }
    }
    test("exact UTF8 text including whitespace is required") { f ->
        val p = f.prepared(); fails("VOICE_TEXT_MISMATCH") { f.catalog.load(p.copy(request = p.request.copy(text = p.request.text + " "))) }
    }
    test("missing file rejects without binding or player") { f ->
        File(f.dir, f.clips[0].audioPath).delete(); f.q.submit(f.input())
        check(f.events.last().reason == "VOICE_FILE_MISSING" && f.players.isEmpty() && !f.ledger.exists())
    }
    test("corrupt file rejects without binding") { f ->
        File(f.dir, f.clips[0].audioPath).appendBytes(byteArrayOf(1)); f.q.submit(f.input())
        check(f.events.last().reason == "VOICE_FILE_CORRUPT" && !f.ledger.exists())
    }
    test("PCM metadata and duration are checked after hash") { f ->
        fails("VOICE_PCM_MISMATCH") { f.catalog(listOf(f.clips[0].copy(channels = 2))).load(f.prepared()) }
        fails("VOICE_DURATION_MISMATCH") { f.catalog(listOf(f.clips[0].copy(durationMs = 50))).load(f.prepared()) }
    }
    test("invalid RIFF rejected even with matching file hash") { f ->
        val bytes = wav(1); bytes[4] = 0
        File(f.dir, f.clips[0].audioPath).writeBytes(bytes)
        fails("VOICE_FILE_FORMAT") { f.catalog(listOf(f.clips[0].copy(audioSha256 = voiceSha256(bytes)))).load(f.prepared()) }
    }
    test("duplicate keys and traversal refused at catalog boundary") { f ->
        fails("AMBIGUOUS_CLIP") { f.catalog(f.clips + f.clips[0].copy(clipId = "duplicate")) }
        fails("INVALID_AUDIO_PATH") { f.clips[0].copy(audioPath = "../escape.wav") }
    }
    test("same voice binding survives restart and new approved text") { f ->
        f.catalog(listOf(f.clips[0])).load(f.prepared())
        val voiceBefore = f.ledger.readLines().single { it.startsWith("voice.") }
        f.catalog().load(f.prepared(3))
        check(f.ledger.readLines().single { it.startsWith("voice.") } == voiceBefore)
        check(f.ledger.readLines().count { it.startsWith("asset.") } == 2)
        val expanded = f.ledger.readText()
        f.catalog().load(f.prepared()); check(f.ledger.readText() == expanded)
    }
    test("same character and original text cannot replace collected WAV bytes") { f ->
        f.catalog.load(f.prepared())
        val before = f.ledger.readText()
        val replacement = wav(92); File(f.dir, f.clips[0].audioPath).writeBytes(replacement)
        val changed = f.clips[0].copy(audioSha256 = voiceSha256(replacement))
        fails("VOICE_ASSET_CHANGED") { f.catalog(listOf(changed)).load(f.prepared()) }
        check(f.ledger.readText() == before)
    }
    test("changed preset or speaker rejected across restart") { f ->
        f.catalog.load(f.prepared())
        val oldSource = f.clips[0].source as VoiceAssetIdentity.LegacyCatalog
        fails("VOICE_BINDING_CHANGED") { f.catalog(listOf(f.clips[0].copy(source = oldSource.copy(speed = 1.1)))).load(f.prepared()) }
        val changed = f.clips[0].copy(speakerId = "s9")
        fails("VOICE_BINDING_CHANGED") { f.catalog(listOf(changed)).load(f.prepared().let { it.copy(voice = it.voice.copy(speakerId = "s9")) }) }
    }
    test("profile reused by another journey selects only its own asset") { f ->
        val second = f.clip("new-character", "p1", "s1", f.common, 5)
        val catalog = f.catalog(listOf(f.clips[0], second))
        val p = f.prepared().let { it.copy(request = it.request.copy(avatarId = second.characterId)) }
        check(catalog.load(p).contentEquals(File(f.dir, second.audioPath).readBytes()))
        fails("UNKNOWN_VOICE_CHARACTER") { catalog.load(p.copy(request = p.request.copy(avatarId = "absent"))) }
    }
    test("corrupt persisted binding fails closed") { f ->
        f.ledger.writeText("broken\n"); f.q.submit(f.input())
        check(f.events.last().reason == "BINDING_STORE_CORRUPT" && f.players.isEmpty())
    }
    test("vehicle denial and unknown audio never start player") { f ->
        f.q.updateContext(f.context.copy(speechPermission = Permission.DENIED)); f.q.submit(f.input())
        check(f.events.last().reason == "SPEECH_NOT_ALLOWED")
        f.q.updateContext(f.context.copy(call = AudioActivity.UNKNOWN)); f.q.submit(f.input(id = "r2"))
        check(f.events.last().reason == "OTHER_AUDIO" && f.players.isEmpty())
    }
    test("focus denied never starts local audio") { f ->
        f.focus.granted = false; f.q.submit(f.input()); check(f.players.isEmpty() && f.events.last().reason == "FOCUS_DENIED")
    }
    test("cancel invalidates late callbacks while next request plays") { f ->
        f.q.submit(f.input()); val old = f.players.single(); f.q.cancel("r1")
        f.q.submit(f.input(3, "r2")); val before = f.events.size
        old.events!!.started(); old.events!!.completed(); old.events!!.failed("LATE")
        check(old.closed && f.events.size == before && f.q.activeRequestId == "r2")
    }
    test("background and focus loss release player without replay") { f ->
        f.q.submit(f.input()); val lifecycle = SpeechLifecycleManager(f.q)
        lifecycle.onBackground(); lifecycle.onForeground(f.context)
        check(f.players.single().closed && f.q.activeRequestId == null && !f.focus.held)
        f.q.submit(f.input(3, "r2")); f.focus.lose(); check(f.players.last().closed && f.q.pendingCount == 0)
    }
    test("same text stays deduplicated across character change") { f ->
        f.q.submit(f.input()); f.players.single().events!!.completed(); f.q.submit(f.input(1, "r2"))
        check(f.events.last().reason == "REPEATED_TEXT" && f.players.size == 1)
    }
    test("expired local playback and suspend never restart") { f ->
        f.q.submit(f.input(ttl = 200)); f.time.advance(200)
        check(f.players.single().closed && f.events.last().reason == "EXPIRED")
        SpeechLifecycleManager(f.q).onSuspend(); f.q.submit(f.input(3, "r2"))
        check(f.events.last().reason == "PROVIDER_UNAVAILABLE")
    }
    test("actual playing bytes remain verified if source file changes") { f ->
        f.q.submit(f.input()); val bytes = f.players.single().bytes!!.copyOf()
        File(f.dir, f.clips[0].audioPath).writeBytes(wav(90))
        check(f.players.single().bytes!!.contentEquals(bytes))
    }
    test("file deleted while pending fails explicitly without fallback") { f ->
        f.q.submit(f.input()); f.q.submit(f.input(3, "r2"))
        File(f.dir, f.clips[3].audioPath).delete(); f.players.single().events!!.completed()
        check(f.events.last().reason == "VOICE_FILE_MISSING" && f.players.size == 1 && f.defaultCalls == 0 && !f.focus.held)
    }
    test("moving policy cancels active local player and does not replay on park") { f ->
        f.q.submit(f.input())
        f.q.updateContext(f.context.copy(motion = VehicleMotion.MOVING, speechPermission = Permission.DENIED))
        check(f.players.single().closed && f.events.last().reason == "SPEECH_NOT_ALLOWED")
        f.q.updateContext(f.context); check(f.players.size == 1 && f.q.activeRequestId == null)
    }
    test("legacy default still selects only the legacy provider") { f ->
        val input = f.input().let { it.copy(request = it.request.copy(avatarId = "legacy", voiceProfileId = "nunti-default-v1"),
            avatar = AvatarVoiceInput("legacy", "nunti", "nunti-default-v1")) }
        f.q.submit(input); check(f.defaultCalls == 1 && f.players.isEmpty() && f.events.last().status == SpeechStatus.STARTED)
        f.q.cancel("r1"); check(!f.focus.held)
    }
    test("legacy source retains the historical fingerprint bytes") { f ->
        check(f.clips[0].bindingFingerprint("experimental-local") == "dd61014d0bb19240afc8207939f6a44161a6dd87726ff41be0c280f5cac566a3")
    }
    test("historical ledger is unchanged when legacy audio loads after migration") { f ->
        val clip = f.clips[0]
        val voiceKey = "voice." + voiceSha256(clip.characterId.toByteArray())
        val assetKey = "asset." + voiceSha256("${clip.characterId}\n${clip.textSha256}".toByteArray())
        val oldAsset = voiceSha256(listOf(clip.audioSha256, 16000, 1, 16, 10).joinToString("|").toByteArray())
        f.ledger.writeText(listOf("$voiceKey=dd61014d0bb19240afc8207939f6a44161a6dd87726ff41be0c280f5cac566a3", "$assetKey=$oldAsset")
            .sorted().joinToString("\n", postfix = "\n"))
        val before = f.ledger.readText()
        f.catalog.load(f.prepared())
        check(f.ledger.readText() == before)
    }
    test("directed Sohee uses actual source identity and verified PCM") { f ->
        val clip = f.directed()
        val catalog = f.directedCatalog(listOf(clip))
        check(catalog.load(f.prepared(clip, catalog)).contentEquals(File(f.dir, clip.audioPath).readBytes()))
        val before = f.ledger.readText()
        val restarted = f.directedCatalog(listOf(clip))
        restarted.load(f.prepared(clip, restarted))
        check(f.ledger.readText() == before)
    }
    test("directed engine direction seed and binding are pinned across restart") { f ->
        val clip = f.directed()
        val source = clip.source as VoiceAssetIdentity.DirectedSohee
        val catalog = f.directedCatalog(listOf(clip))
        catalog.load(f.prepared(clip, catalog))
        val before = f.ledger.readText()
        listOf(source.copy(engineFingerprint = "d".repeat(64)), source.copy(directionSha256 = "d".repeat(64)),
            source.copy(seed = 0), source.copy(bindingId = "dvb-" + "d".repeat(32))).forEach { changed ->
            val updated = f.directedCatalog(listOf(clip.copy(source = changed)))
            fails("VOICE_BINDING_CHANGED") { updated.load(f.prepared(clip, updated)) }
            check(f.ledger.readText() == before)
        }
    }
    test("directed collection accepts new text without changing its voice ledger") { f ->
        val first = f.directed()
        val initial = f.directedCatalog(listOf(first))
        initial.load(f.prepared(first, initial))
        val voiceBefore = f.ledger.readLines().single { it.startsWith("voice.") }
        val text = "새로운 여행의 기억을 함께 모아보자."
        val bytes = wav(6, 24000)
        File(f.dir, "directed-next.wav").writeBytes(bytes)
        val next = first.copy(clipId = "directed-next", text = text, textSha256 = voiceSha256(text.toByteArray()),
            audioPath = "directed-next.wav", audioSha256 = voiceSha256(bytes))
        val expanded = f.directedCatalog(listOf(first, next))
        expanded.load(f.prepared(next, expanded))
        check(f.ledger.readLines().single { it.startsWith("voice.") } == voiceBefore)
        check(f.ledger.readLines().count { it.startsWith("asset.") } == 2)
        val changed = next.copy(source = (next.source as VoiceAssetIdentity.DirectedSohee).copy(seed = 0))
        fails("VOICE_BINDING_CHANGED") { f.directedCatalog(listOf(first, changed)) }
    }
    test("directed identity refuses fake revisions malformed hashes and seeds outside uint32") { f ->
        val source = f.directed().source as VoiceAssetIdentity.DirectedSohee
        fails("UNSUPPORTED_SOHEE_MODEL_REVISION") { source.copy(revision = "fake-model") }
        fails("INVALID_VOICE_BINDING") { source.copy(bindingId = "dvb-fake") }
        fails("INVALID_VOICE_BINDING") { source.copy(engineFingerprint = "b".repeat(63)) }
        fails("INVALID_VOICE_BINDING") { source.copy(directionSha256 = "c".repeat(63)) }
        fails("INVALID_VOICE_BINDING") { source.copy(seed = -1) }
        fails("INVALID_VOICE_BINDING") { source.copy(seed = 0x1_0000_0000L) }
        check(source.copy(seed = 0).seed == 0L && source.seed == 0xffff_ffffL)
    }
    test("directed identity cannot masquerade as legacy provider or unknown speaker") { f ->
        val clip = f.directed()
        fails("VOICE_SOURCE_PROVIDER_MISMATCH") { f.catalog(listOf(clip)) }
        fails("VOICE_SOURCE_PROVIDER_MISMATCH") { f.directedCatalog(listOf(f.clips[0])) }
        fails("UNSUPPORTED_SOHEE_SPEAKER") { clip.copy(speakerId = "F3") }
        fails("INVALID_SOHEE_AUDIO_METADATA") { clip.copy(sampleRateHz = 44100) }
        val text = "가".repeat(101)
        fails("VOICE_TEXT_TOO_LONG") { clip.copy(text = text, textSha256 = voiceSha256(text.toByteArray())) }
    }
    test("router gives cold initialization 5 seconds before start timeout") { f ->
        var init: TtsProvider.Listener? = null
        var spoken = false
        val delayed = object : TtsProvider {
            override val capabilities = ProviderCapabilities()
            override val mode = EngineMode.ON_DEVICE
            override fun initialize(listener: TtsProvider.Listener) { init = listener }
            override fun setLocale(locale: String) {}
            override fun speak(speech: PreparedSpeech) { spoken = true; init!!.onStart(speech.request.requestId) }
            override fun stop() {}
            override fun release() {}
        }
        val router = CatalogTtsProvider(f.catalog, { LocalFileTtsProvider(f.catalog, f::player) }, { delayed })
        val q = SpeechQueueManager(router, f.focus, f.time, f.time, sink = f.events::add)
        q.beginTrip("trip"); q.updateContext(f.context)
        val input = f.input().let { it.copy(request = it.request.copy(avatarId = "legacy", voiceProfileId = "nunti-default-v1"),
            avatar = AvatarVoiceInput("legacy", "nunti", "nunti-default-v1")) }
        q.submit(input); f.time.advance(4000)
        check(!spoken && !f.focus.held && f.events.none { it.reason == "START_TIMEOUT" })
        init!!.onInitialized(); check(spoken && f.focus.held)
        q.release()
    }
    test("three designed providers load only verified normalized WAV bytes") { f ->
        VoiceAssetIdentity.DesignedVoice.PROVIDERS.forEach { provider ->
            val clip = f.designed(provider).copy(characterId = "character-$provider")
            val catalog = f.designedCatalog(listOf(clip))
            check(catalog.load(f.prepared(clip, catalog)).contentEquals(File(f.dir, clip.audioPath).readBytes()))
        }
    }
    test("designed voice keeps binding across restart and later approved text") { f ->
        val first = f.designed()
        val initial = f.designedCatalog(listOf(first))
        initial.load(f.prepared(first, initial))
        val voiceBefore = f.ledger.readLines().single { it.startsWith("voice.") }
        val text = "다음에도 이 목소리로 여정을 기억할게."
        val bytes = wav(8, 24000)
        File(f.dir, "designed-next.wav").writeBytes(bytes)
        val next = first.copy(clipId = "designed-next", text = text, textSha256 = voiceSha256(text.toByteArray()),
            audioPath = "designed-next.wav", audioSha256 = voiceSha256(bytes), rawAudioSha256 = "e".repeat(64))
        val restarted = f.designedCatalog(listOf(first, next))
        restarted.load(f.prepared(next, restarted))
        check(f.ledger.readLines().single { it.startsWith("voice.") } == voiceBefore)
        check(f.ledger.readLines().count { it.startsWith("asset.") } == 2)
        val before = f.ledger.readText()
        restarted.load(f.prepared(first, restarted))
        check(f.ledger.readText() == before)
    }
    test("designed identity changes are rejected without changing the ledger") { f ->
        val clip = f.designed()
        val source = clip.source as VoiceAssetIdentity.DesignedVoice
        val initial = f.designedCatalog(listOf(clip))
        initial.load(f.prepared(clip, initial))
        val before = f.ledger.readText()
        listOf(source.copy(voiceId = "fixture-" + "f".repeat(24)), source.copy(bindingId = "changed-binding"),
            source.copy(specSha256 = "e".repeat(64)), source.copy(settingsSha256 = "e".repeat(64))).forEach { changed ->
            val updated = clip.copy(source = changed, speakerId = changed.voiceId)
            val catalog = f.designedCatalog(listOf(updated))
            fails("VOICE_BINDING_CHANGED") { catalog.load(f.prepared(updated, catalog)) }
            check(f.ledger.readText() == before)
            val text = "새 대사에도 다른 음색을 끼워 넣을 수 없어."
            fails("VOICE_BINDING_CHANGED") { f.designedCatalog(listOf(clip, updated.copy(clipId = "changed",
                text = text, textSha256 = voiceSha256(text.toByteArray())))) }
        }
    }
    test("designed and directed source fingerprint field order is pinned") { f ->
        check(f.designed().bindingFingerprint(VoiceAssetIdentity.DesignedVoice.FIXTURE) ==
            "97f00e9c71d9f4107401f6a065bde3e771040cd3ab44c18d556ab662104f3225")
        check(f.directed().bindingFingerprint(VoiceAssetIdentity.DirectedSohee.PROVIDER_ID) ==
            "f994b7584e8daa8085d2c72325889c6d76b3aff796d31f5c48aa8b824ac55ea5")
    }
    test("raw provider metadata is optional but immutable for an existing clip") { f ->
        val clip = f.designed().copy(rawAudioSha256 = null)
        val catalog = f.designedCatalog(listOf(clip))
        catalog.load(f.prepared(clip, catalog))
        val before = f.ledger.readText()
        val withRaw = clip.copy(rawAudioSha256 = "e".repeat(64))
        val updated = f.designedCatalog(listOf(withRaw))
        fails("VOICE_ASSET_CHANGED") { updated.load(f.prepared(withRaw, updated)) }
        check(f.ledger.readText() == before)
        fails("INVALID_ASSET_HASH") { clip.copy(rawAudioSha256 = "not-a-hash") }
    }
    test("designed source cannot claim another provider or a preset speaker") { f ->
        val clip = f.designed()
        fails("VOICE_SOURCE_PROVIDER_MISMATCH") { f.catalog(listOf(clip)) }
        fails("VOICE_SOURCE_PROVIDER_MISMATCH") { LocalVoiceCatalog(VoiceAssetIdentity.DesignedVoice.ELEVENLABS,
            listOf(clip), f.dir, CharacterVoiceBindings(f.ledger)) }
        fails("VOICE_SOURCE_PROVIDER_MISMATCH") { LocalVoiceCatalog(VoiceAssetIdentity.DesignedVoice.FIXTURE,
            listOf(f.clips.first()), f.dir, CharacterVoiceBindings(f.ledger)) }
        fails("DESIGNED_VOICE_SPEAKER_MISMATCH") { clip.copy(speakerId = "Sohee") }
        fails("DESIGNED_VOICE_SPEAKER_MISMATCH") { clip.copy(speakerId = "Anna") }
    }
    test("fixture media cannot masquerade as provider generated and model mismatches fail") { f ->
        val fixture = f.designed().source as VoiceAssetIdentity.DesignedVoice
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { fixture.copy(mediaOrigin = VoiceMediaOrigin.PROVIDER_GENERATED) }
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { fixture.copy(designModel = "eleven_ttv_v3") }
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { fixture.copy(voiceId = "not-a-fixture") }
        val eleven = f.designed(VoiceAssetIdentity.DesignedVoice.ELEVENLABS).source as VoiceAssetIdentity.DesignedVoice
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { eleven.copy(mediaOrigin = VoiceMediaOrigin.OFFLINE_FIXTURE) }
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { eleven.copy(voiceId = fixture.voiceId) }
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { eleven.copy(synthesisModel = "eleven_flash_v2_5") }
        val gemini = f.designed(VoiceAssetIdentity.DesignedVoice.GEMINI).source as VoiceAssetIdentity.DesignedVoice
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { gemini.copy(voiceId = "no-google-voice-prefix") }
        fails("DESIGNED_VOICE_SOURCE_MISMATCH") { gemini.copy(designModel = "gemini-3.8-flash") }
        fails("INVALID_VOICE_BINDING") { fixture.copy(specSha256 = "bad") }
        fails("INVALID_VOICE_BINDING") { fixture.copy(bindingId = "bad|binding") }
    }
    test("designed PCM requires 24k mono sixteen bit and maximum thirty seconds") { f ->
        val clip = f.designed()
        fails("INVALID_DESIGNED_AUDIO_METADATA") { clip.copy(sampleRateHz = 44100) }
        fails("INVALID_DESIGNED_AUDIO_METADATA") { clip.copy(channels = 2) }
        fails("INVALID_AUDIO_METADATA") { clip.copy(durationMs = 30001) }
        val bytes = wav(7, 24000)
        bytes[34] = 8
        File(f.dir, clip.audioPath).writeBytes(bytes)
        val changed = clip.copy(audioSha256 = voiceSha256(bytes))
        val catalog = f.designedCatalog(listOf(changed))
        fails("VOICE_PCM_MISMATCH") { catalog.load(f.prepared(changed, catalog)) }
        check(!f.ledger.exists())
    }
    test("designed queue uses existing cancellation and never selects a default provider") { f ->
        val first = f.designed()
        val text = "도착했어. 오늘의 길을 기억하자."
        val second = first.copy(clipId = "designed-next", text = text, textSha256 = voiceSha256(text.toByteArray()),
            audioPath = "designed-next.wav")
        File(f.dir, second.audioPath).writeBytes(File(f.dir, first.audioPath).readBytes())
        val catalog = f.designedCatalog(listOf(first, second))
        var fallbackCalls = 0
        val provider = CatalogTtsProvider(catalog, { LocalFileTtsProvider(catalog, f::player) }, {
            fallbackCalls++; MockTtsProvider()
        })
        val queue = SpeechQueueManager(provider, f.focus, f.time, f.time,
            builder = SpeechRequestBuilder(VoiceProfileManager(catalog.profiles)), sink = f.events::add)
        fun input(clip: LocalVoiceClip, id: String) = f.input(id = id).let {
            it.copy(request = it.request.copy(avatarId = clip.characterId, voiceProfileId = clip.profileId, text = clip.text),
                avatar = AvatarVoiceInput(clip.characterId, clip.characterId, clip.profileId))
        }
        queue.beginTrip("trip"); queue.updateContext(f.context)
        queue.submit(input(first, "designed-active")); queue.submit(input(second, "designed-pending"))
        check(queue.pendingCount == 1 && f.players.size == 1)
        queue.cancelAll("USER_CANCELLED")
        check(queue.activeRequestId == null && queue.pendingCount == 0 && f.players.single().closed && !f.focus.held)
        val before = f.events.size
        f.players.single().events!!.completed()
        check(f.events.size == before && fallbackCalls == 0)
        queue.release()
    }
    test("all media verification reads every file and does not create playback") { f ->
        f.catalog.verifyAllMedia()
        check(f.players.isEmpty() && f.events.isEmpty() && !f.focus.held)
        check(f.ledger.readLines().count { it.startsWith("voice.") } == 3)
        check(f.ledger.readLines().count { it.startsWith("asset.") } == 4)
        val before = f.ledger.readText()
        f.catalog.verifyAllMedia()
        check(f.ledger.readText() == before)
    }
    test("all media verification refuses a missing later file before publishing bindings") { f ->
        File(f.dir, f.clips.last().audioPath).delete()
        fails("VOICE_FILE_MISSING") { f.catalog.verifyAllMedia() }
        check(!f.ledger.exists() && f.players.isEmpty())
    }
    test("all media verification catches corrupt bytes PCM and duration") { f ->
        val last = f.clips.last()
        val path = File(f.dir, last.audioPath)
        val original = path.readBytes()
        path.writeBytes(original + byteArrayOf(1))
        fails("VOICE_FILE_CORRUPT") { f.catalog.verifyAllMedia() }
        path.writeBytes(original)
        fails("VOICE_PCM_MISMATCH") { f.catalog(f.clips.dropLast(1) + last.copy(sampleRateHz = 24000)).verifyAllMedia() }
        fails("VOICE_DURATION_MISMATCH") { f.catalog(f.clips.dropLast(1) + last.copy(durationMs = 99)).verifyAllMedia() }
        check(!f.ledger.exists())
    }
    test("all media verification checks retained designed binding and playback rechecks files") { f ->
        val clip = f.designed()
        val catalog = f.designedCatalog(listOf(clip)); catalog.verifyAllMedia()
        val before = f.ledger.readText()
        val source = clip.source as VoiceAssetIdentity.DesignedVoice
        val changed = clip.copy(source = source.copy(settingsSha256 = "e".repeat(64)))
        fails("VOICE_BINDING_CHANGED") { f.designedCatalog(listOf(changed)).verifyAllMedia() }
        check(f.ledger.readText() == before)
        File(f.dir, clip.audioPath).appendBytes(byteArrayOf(1))
        fails("VOICE_FILE_CORRUPT") { catalog.load(f.prepared(clip, catalog)) }
    }
    test("provider catalog append keeps active audio pending cancellation and late callback isolation") { f ->
        val first = f.designed()
        val text = "계속 같은 목소리로 함께할게."
        val next = first.copy(clipId = "designed-next", text = text, textSha256 = voiceSha256(text.toByteArray()),
            audioPath = "designed-next.wav")
        File(f.dir, next.audioPath).writeBytes(File(f.dir, first.audioPath).readBytes())
        val initial = f.designedCatalog(listOf(first))
        val provider = LocalFileTtsProvider(initial, f::player)
        val queue = SpeechQueueManager(provider, f.focus, f.time, f.time,
            builder = SpeechRequestBuilder(VoiceProfileManager(initial.profiles)), sink = f.events::add)
        fun input(clip: LocalVoiceClip, id: String) = f.input(id = id).let {
            it.copy(request = it.request.copy(avatarId = clip.characterId, voiceProfileId = clip.profileId, text = clip.text),
                avatar = AvatarVoiceInput(clip.characterId, clip.characterId, clip.profileId))
        }
        queue.beginTrip("trip"); queue.updateContext(f.context)
        queue.submit(input(first, "active")); val player = f.players.single(); val playing = player.bytes!!.copyOf()
        val expanded = f.designedCatalog(listOf(first, next)); expanded.verifyAllMedia()
        provider.updateCatalog(expanded)
        check(queue.activeRequestId == "active" && !player.closed && f.focus.held && player.bytes!!.contentEquals(playing))
        queue.submit(input(next, "pending"))
        check(queue.pendingCount == 1 && f.players.size == 1)
        queue.cancelAll("USER_CANCELLED")
        check(queue.activeRequestId == null && queue.pendingCount == 0 && player.closed && !f.focus.held)
        val before = f.events.size
        player.events!!.started(); player.events!!.completed(); player.events!!.failed("LATE")
        check(f.events.size == before && f.players.size == 1)
        queue.release()
    }
    test("provider append preserves completed-text repetition history in the same queue") { f ->
        val first = f.designed()
        val initial = f.designedCatalog(listOf(first))
        val provider = LocalFileTtsProvider(initial, f::player)
        val queue = SpeechQueueManager(provider, f.focus, f.time, f.time,
            builder = SpeechRequestBuilder(VoiceProfileManager(initial.profiles)), sink = f.events::add)
        val input = f.input().let { it.copy(request = it.request.copy(avatarId = first.characterId,
            voiceProfileId = first.profileId, text = first.text), avatar = AvatarVoiceInput(first.characterId, "test", first.profileId)) }
        queue.beginTrip("trip"); queue.updateContext(f.context); queue.submit(input)
        f.players.single().events!!.completed()
        val text = "새 대사도 같은 여행에 속해."
        val next = first.copy(clipId = "next", text = text, textSha256 = voiceSha256(text.toByteArray()))
        provider.updateCatalog(f.designedCatalog(listOf(first, next)))
        queue.submit(input.copy(request = input.request.copy(requestId = "repeat-after-append")))
        check(f.events.last().status == SpeechStatus.REJECTED && f.events.last().reason == "REPEATED_TEXT" && f.players.size == 1)
        queue.release()
    }
    test("provider append rejects removed or changed clips including raw hash without swapping catalogs") { f ->
        val first = f.designed()
        val initial = f.designedCatalog(listOf(first))
        val provider = LocalFileTtsProvider(initial, f::player)
        val text = "새 대사만 남기면 기존 대사가 삭제돼."
        val next = first.copy(clipId = "next", text = text, textSha256 = voiceSha256(text.toByteArray()))
        fails("VOICE_CATALOG_NOT_APPEND_ONLY") { provider.updateCatalog(f.designedCatalog(listOf(next))) }
        fails("VOICE_CATALOG_NOT_APPEND_ONLY") { provider.updateCatalog(f.designedCatalog(listOf(first.copy(rawAudioSha256 = "e".repeat(64))))) }
        val changed = first.copy(audioSha256 = "f".repeat(64))
        fails("VOICE_CATALOG_NOT_APPEND_ONLY") { provider.updateCatalog(f.designedCatalog(listOf(changed))) }
        check(provider.rejection(f.prepared(first, initial)) == null)
        val other = f.designed(VoiceAssetIdentity.DesignedVoice.ELEVENLABS)
        fails("VOICE_CATALOG_IDENTITY_CHANGED") { provider.updateCatalog(f.designedCatalog(listOf(other))) }
        val profile = first.copy(profileId = "changed-profile")
        fails("VOICE_CATALOG_IDENTITY_CHANGED") { provider.updateCatalog(f.designedCatalog(listOf(profile))) }
        provider.release()
    }
    println("$count local voice tests passed")
}
