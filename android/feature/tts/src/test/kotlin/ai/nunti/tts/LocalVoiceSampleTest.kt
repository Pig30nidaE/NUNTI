package ai.nunti.tts

import java.io.File
import java.nio.file.Files
import java.util.Base64
import java.util.Properties

/** Runs the real catalog loader against the shipped experimental PCM assets. No speaker playback. */
fun main(args: Array<String>) {
    val properties = Properties().apply { File(args[0]).inputStream().use { load(it) } }
    fun value(key: String) = String(Base64.getDecoder().decode(properties.getProperty(key)), Charsets.UTF_8)
    val clips = (0 until value("count").toInt()).map { i ->
        fun field(name: String) = value("clip.$i.$name")
        val source = when (field("sourceKind")) {
            "legacy-catalog-v1" -> VoiceAssetIdentity.LegacyCatalog(field("sourceModelRevision"), field("bindingId"),
                field("speed").toDouble(), field("steps").toInt(), field("catalogSha256"))
            "directed-sohee-v1" -> VoiceAssetIdentity.DirectedSohee(field("sourceModelRevision"), field("bindingId"),
                field("engineFingerprint"), field("directionSha256"), field("seed").toLong())
            "designed-voice-v1" -> VoiceAssetIdentity.DesignedVoice(field("sourceProviderId"), field("designModel"),
                field("synthesisModel"), field("voiceId"), field("bindingId"), field("specSha256"),
                field("settingsSha256"), VoiceMediaOrigin.valueOf(field("mediaOrigin")))
            else -> error("Unknown projected voice asset kind")
        }
        LocalVoiceClip(field("clipId"), field("characterId"), field("profileId"), field("speakerId"), field("locale"),
            field("text"), field("textSha256"), field("audioPath"), field("audioSha256"), field("sampleRateHz").toInt(),
            field("channels").toInt(), field("durationMs").toInt(), source,
            if (source is VoiceAssetIdentity.DesignedVoice) field("rawAudioSha256").ifEmpty { null } else null)
    }
    val temp = Files.createTempDirectory("nunti-real-voice").toFile()
    try {
        val catalog = LocalVoiceCatalog(value("providerId"), clips, File(args[1]), CharacterVoiceBindings(File(temp, "binding.txt")))
        val builder = SpeechRequestBuilder(VoiceProfileManager(catalog.profiles))
        clips.forEach { clip ->
            val request = SpeechRequest(clip.clipId, "test-trip", clip.characterId, clip.text, Emotion.NEUTRAL, clip.profileId,
                TripPhase.POST_TRIP, Priority.NORMAL, 100, 10000, ContentSource.USER_INITIATED)
            val input = ApprovedSpeech(request, AvatarVoiceInput(clip.characterId, clip.characterId, clip.profileId), null, true)
            val prepared = builder.build(input, catalog.capabilities, 100)
            val bytes = catalog.load(prepared)
            check(voiceSha256(bytes) == clip.audioSha256 && prepared.voice.speakerId == clip.speakerId)
            println("PASS real ${clip.clipId} speaker=${clip.speakerId} profile=${clip.profileId} bytes=${bytes.size}")
        }
        if (value("schemaVersion") == "1") check(clips.size == 6 && clips.map { it.speakerId }.distinct().size == 3)
        else if (value("schemaVersion") == "2") check(clips.all { it.source is VoiceAssetIdentity.DirectedSohee })
        else check(value("schemaVersion") == "3" && clips.all { it.source is VoiceAssetIdentity.DesignedVoice })
        println("${clips.size} actual WAV catalog checks passed; acoustic listening NOT tested")
    } finally { temp.deleteRecursively() }
}
