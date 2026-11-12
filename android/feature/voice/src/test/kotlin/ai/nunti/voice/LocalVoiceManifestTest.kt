package ai.nunti.voice

import ai.nunti.tts.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files

/** Exercises the production JSON parser and catalog, not a projection of JSON into properties. */
fun main(args: Array<String>) {
    val repository = File(args[0])
    val temporary = Files.createTempDirectory("nunti-manifest-parser").toFile()
    var count = 0
    fun test(name: String, body: () -> Unit) { body(); count++; println("PASS manifest $name") }
    fun fails(reason: String, body: () -> Unit) {
        val result = runCatching(body).exceptionOrNull()
        check(result is VoiceAssetException && result.reason == reason) { "Expected $reason, got $result" }
    }
    val text = "안녕, 오늘의 길을 함께 기억하자."
    val buffer = ByteBuffer.allocate(524).order(ByteOrder.LITTLE_ENDIAN)
    buffer.put("RIFF".toByteArray()).putInt(516).put("WAVEfmt ".toByteArray()).putInt(16)
        .putShort(1).putShort(1).putInt(24000).putInt(48000).putShort(2).putShort(16)
        .put("data".toByteArray()).putInt(480)
    repeat(240) { buffer.putShort(100) }
    val audio = buffer.array()
    File(temporary, "fixture.wav").writeBytes(audio)
    fun manifest(provider: String = VoiceAssetIdentity.DesignedVoice.FIXTURE): JSONObject {
        val isFixture = provider == VoiceAssetIdentity.DesignedVoice.FIXTURE
        val isGemini = provider == VoiceAssetIdentity.DesignedVoice.GEMINI
        val voiceId = when { isFixture -> "fixture-" + "a".repeat(24); isGemini -> "voice_test_voice"; else -> "elevenTestVoiceId1234" }
        val source = JSONObject().put("kind", "designed-voice-v1").put("providerId", provider)
            .put("designModel", when { isFixture -> "offline-fixture-v1"; isGemini -> "gemini-3.8-flash-tts"; else -> "eleven_ttv_v3" })
            .put("synthesisModel", when { isFixture -> "fixture-wav-v1"; isGemini -> "gemini-3.8-flash-tts"; else -> "eleven_v4" })
            .put("voiceId", voiceId).put("bindingId", "designed-binding-1").put("specSha256", "b".repeat(64))
            .put("settingsSha256", "c".repeat(64)).put("mediaOrigin", if (isFixture) "OFFLINE_FIXTURE" else "PROVIDER_GENERATED")
        val clip = JSONObject().put("clipId", "first").put("characterId", "test-character").put("profileId", "test-profile")
            .put("speakerId", voiceId).put("locale", "ko-KR").put("text", text).put("textSha256", voiceSha256(text.toByteArray()))
            .put("audioPath", "fixture.wav").put("audioSha256", voiceSha256(audio)).put("rawAudioSha256", "d".repeat(64))
            .put("sampleRateHz", 24000).put("channels", 1).put("sampleWidthBytes", 2).put("durationMs", 10).put("source", source)
        return JSONObject().put("schemaVersion", 3).put("providerId", provider).put("clips", JSONArray().put(clip))
    }
    fun clip(value: JSONObject) = value.getJSONArray("clips").getJSONObject(0)
    fun source(value: JSONObject) = clip(value).getJSONObject("source")
    fun parse(value: JSONObject, ledger: String = "${count}-binding.txt") =
        LocalVoiceManifest.parse(value.toString(), temporary, File(temporary, ledger))
    fun load(catalog: LocalVoiceCatalog, selected: LocalVoiceClip = catalog.clips.first()) {
        val request = SpeechRequest(selected.clipId, "test-trip", selected.characterId, selected.text, Emotion.NEUTRAL,
            selected.profileId, TripPhase.POST_TRIP, Priority.NORMAL, 100, 10000, ContentSource.USER_INITIATED)
        val approved = ApprovedSpeech(request, AvatarVoiceInput(selected.characterId, "test", selected.profileId), null, true)
        val prepared = SpeechRequestBuilder(VoiceProfileManager(catalog.profiles)).build(approved, catalog.capabilities, 100)
        check(voiceSha256(catalog.load(prepared)) == selected.audioSha256)
    }
    try {
        test("schema 3 accepts honest fixture and supported retained provider identities") {
            VoiceAssetIdentity.DesignedVoice.PROVIDERS.forEach { provider ->
                val catalog = parse(manifest(provider), "$provider-ledger.txt")
                val source = catalog.clips.single().source as VoiceAssetIdentity.DesignedVoice
                check(source.providerId == catalog.providerId && catalog.clips.single().speakerId == source.voiceId)
                check(catalog.clips.single().rawAudioSha256 == "d".repeat(64))
                catalog.verifyAllMedia()
                load(catalog)
            }
        }
        test("optional raw original hash can be absent") {
            val value = manifest(); clip(value).remove("rawAudioSha256")
            val catalog = parse(value); check(catalog.clips.single().rawAudioSha256 == null); load(catalog)
        }
        test("unknown schema fails before interpreting clips") {
            fails("UNSUPPORTED_VOICE_MANIFEST_SCHEMA") { parse(manifest().put("schemaVersion", 4)) }
        }
        test("schema kind cannot be changed to an old or unknown source") {
            listOf("directed-sohee-v1", "legacy-catalog-v1", "designed-voice-v2").forEach { kind ->
                val value = manifest(); source(value).put("kind", kind)
                fails("UNKNOWN_VOICE_ASSET_KIND") { parse(value) }
            }
        }
        test("old schema cannot interpret designed metadata") {
            fails("INVALID_VOICE_MANIFEST") { parse(manifest().put("schemaVersion", 2)) }
        }
        test("root source and optional clip providers must match") {
            val rootChanged = manifest().put("providerId", VoiceAssetIdentity.DesignedVoice.ELEVENLABS)
            fails("INVALID_VOICE_MANIFEST") { parse(rootChanged) }
            val clipChanged = manifest(); clip(clipChanged).put("providerId", "other-provider")
            fails("INVALID_VOICE_MANIFEST") { parse(clipChanged) }
        }
        test("source missing extra and non-string fields fail") {
            listOf("voiceId", "specSha256", "settingsSha256", "mediaOrigin").forEach { key ->
                val missing = manifest(); source(missing).remove(key)
                fails("INVALID_VOICE_MANIFEST") { parse(missing) }
                val coerced = manifest(); source(coerced).put(key, 123)
                fails("INVALID_VOICE_MANIFEST") { parse(coerced) }
            }
            val extra = manifest(); source(extra).put("seed", 1)
            fails("INVALID_VOICE_MANIFEST") { parse(extra) }
        }
        test("designed clip cannot carry legacy binding aliases") {
            listOf("binding", "bindingId", "sourceModelRevision", "preset").forEach { key ->
                val value = manifest(); clip(value).put(key, "legacy")
                fails("INVALID_VOICE_MANIFEST") { parse(value) }
            }
        }
        test("fixture cannot claim provider-generated origin") {
            val value = manifest(); source(value).put("mediaOrigin", "PROVIDER_GENERATED")
            fails("DESIGNED_VOICE_SOURCE_MISMATCH") { parse(value) }
        }
        test("real provider cannot claim fixture origin or unsupported model") {
            val value = manifest(VoiceAssetIdentity.DesignedVoice.ELEVENLABS)
            source(value).put("mediaOrigin", "OFFLINE_FIXTURE")
            fails("DESIGNED_VOICE_SOURCE_MISMATCH") { parse(value) }
            val model = manifest(VoiceAssetIdentity.DesignedVoice.GEMINI)
            source(model).put("synthesisModel", "gemini-3.8-flash")
            fails("DESIGNED_VOICE_SOURCE_MISMATCH") { parse(model) }
        }
        test("speaker metadata cannot silently name Anna or Sohee") {
            listOf("Anna", "Sohee").forEach { speaker ->
                val value = manifest(); clip(value).put("speakerId", speaker)
                fails("DESIGNED_VOICE_SPEAKER_MISMATCH") { parse(value) }
            }
        }
        test("raw original hash is strict and normalized audio bytes are independently checked") {
            val invalid = manifest(); clip(invalid).put("rawAudioSha256", "not-a-hash")
            fails("INVALID_ASSET_HASH") { parse(invalid) }
            val corrupt = manifest(); clip(corrupt).put("audioSha256", "0".repeat(64))
            fails("VOICE_FILE_CORRUPT") { load(parse(corrupt)) }
        }
        test("integer PCM constraints are checked without string coercion") {
            val width = manifest(); clip(width).put("sampleWidthBytes", 1)
            fails("INVALID_VOICE_MANIFEST") { parse(width) }
            val rate = manifest(); clip(rate).put("sampleRateHz", 44100)
            fails("INVALID_DESIGNED_AUDIO_METADATA") { parse(rate) }
            val stringRate = manifest(); clip(stringRate).put("sampleRateHz", "24000")
            fails("INVALID_VOICE_MANIFEST") { parse(stringRate) }
            val stereo = manifest(); clip(stereo).put("channels", 2)
            fails("INVALID_DESIGNED_AUDIO_METADATA") { parse(stereo) }
            val long = manifest(); clip(long).put("durationMs", 30001)
            fails("INVALID_AUDIO_METADATA") { parse(long) }
        }
        test("same voice survives JSON append and process-style parser restart") {
            val value = manifest(); val initial = parse(value, "append-ledger.txt"); load(initial)
            val ledger = File(temporary, "append-ledger.txt")
            val before = ledger.readLines().single { it.startsWith("voice.") }
            val next = JSONObject(clip(value).toString()).put("clipId", "second").put("text", "도착했어. 오늘도 고마워.")
            next.put("textSha256", voiceSha256(next.getString("text").toByteArray())).put("rawAudioSha256", "e".repeat(64))
            value.getJSONArray("clips").put(next)
            val restarted = parse(value, "append-ledger.txt"); load(restarted, restarted.clips.last())
            check(ledger.readLines().single { it.startsWith("voice.") } == before)
            check(ledger.readLines().count { it.startsWith("asset.") } == 2)
            source(value).put("settingsSha256", "e".repeat(64))
            fails("VOICE_BINDING_CHANGED") { parse(value, "append-ledger.txt") }
        }
        listOf("journey-voice", "journey-dynamic").forEach { directory ->
            val path = File(repository, "android/app/src/debug/assets/$directory/manifest.json")
            if (path.isFile) test("existing $directory manifest parses and all original WAVs load") {
                val catalog = LocalVoiceManifest.parse(path.readText(), path.parentFile, File(temporary, "$directory-ledger.txt"))
                catalog.clips.forEach { load(catalog, it) }
                println("  ${catalog.clips.size} preserved WAVs verified with production JSON parser")
            }
        }
        if (args.size > 1) {
            test("supplied schema 3 catalog parses and every WAV loads") {
                val manifest = File(args[1]); val directory = if (args.size > 2) File(args[2]) else manifest.parentFile
                val catalog = LocalVoiceManifest.parse(manifest.readText(), directory, File(temporary, "external-ledger.txt"))
                check(catalog.clips.all { it.source is VoiceAssetIdentity.DesignedVoice })
                catalog.verifyAllMedia()
                catalog.clips.forEach { load(catalog, it) }
                println("  ${catalog.clips.size} designed catalog WAVs verified")
            }
        }
        println("$count production JSON manifest tests passed; no model/provider call or speaker playback")
    } finally { temporary.deleteRecursively() }
}
