package ai.nunti.voice

import ai.nunti.tts.CharacterVoiceBindings
import ai.nunti.tts.LocalVoiceCatalog
import ai.nunti.tts.LocalVoiceClip
import ai.nunti.tts.VoiceAssetException
import ai.nunti.tts.VoiceAssetIdentity
import ai.nunti.tts.VoiceMediaOrigin
import org.json.JSONObject
import java.io.File

/** Manifest is local experiment input, not shared wire v1 or a playback command. */
object LocalVoiceManifest {
    private fun string(value: JSONObject, key: String): String = value.get(key).let { require(it is String); it }
    private fun integer(value: JSONObject, key: String): Int = value.get(key).let { require(it is Int); it }
    private fun speed(value: JSONObject): Double = value.get("speed").let { require(it is Number); it.toDouble() }
    private fun seed(value: JSONObject): Long = value.get("seed").let {
        require(it is Int || it is Long)
        (it as Number).toLong().also { result -> require(result in 0L..0xffff_ffffL) }
    }
    private fun legacySource(clip: JSONObject, providerId: String): VoiceAssetIdentity.LegacyCatalog {
        require(string(clip, "providerId") == providerId)
        val binding = clip.getJSONObject("binding")
        for (key in listOf("providerId", "characterId", "profileId", "speakerId", "locale", "bindingId", "sourceModelRevision")) {
            require(string(clip, key) == string(binding, key))
        }
        val preset = binding.getJSONObject("preset")
        require(speed(preset) == speed(clip.getJSONObject("preset")) &&
            integer(preset, "steps") == integer(clip.getJSONObject("preset"), "steps"))
        return VoiceAssetIdentity.LegacyCatalog(string(clip, "sourceModelRevision"), string(clip, "bindingId"),
            speed(preset), integer(preset, "steps"), string(binding, "catalogSha256"))
    }
    private fun directedSource(clip: JSONObject, providerId: String): VoiceAssetIdentity.DirectedSohee {
        require(providerId == VoiceAssetIdentity.DirectedSohee.PROVIDER_ID)
        if (clip.has("providerId")) require(string(clip, "providerId") == providerId)
        require(listOf("preset", "binding", "sourceModelRevision", "bindingId").none { clip.has(it) })
        val source = clip.getJSONObject("source")
        if (string(source, "kind") != "directed-sohee-v1") throw VoiceAssetException("UNKNOWN_VOICE_ASSET_KIND")
        require(source.keys().asSequence().toSet() == setOf("kind", "sourceModelRevision", "bindingId",
            "engineFingerprint", "directionSha256", "seed"))
        return VoiceAssetIdentity.DirectedSohee(string(source, "sourceModelRevision"), string(source, "bindingId"),
            string(source, "engineFingerprint"), string(source, "directionSha256"), seed(source))
    }
    private fun designedSource(clip: JSONObject, providerId: String): VoiceAssetIdentity.DesignedVoice {
        require(providerId in VoiceAssetIdentity.DesignedVoice.PROVIDERS)
        if (clip.has("providerId")) require(string(clip, "providerId") == providerId)
        require(listOf("preset", "binding", "sourceModelRevision", "bindingId").none { clip.has(it) })
        val source = clip.getJSONObject("source")
        if (string(source, "kind") != VoiceAssetIdentity.DesignedVoice.KIND) throw VoiceAssetException("UNKNOWN_VOICE_ASSET_KIND")
        require(source.keys().asSequence().toSet() == setOf("kind", "providerId", "designModel", "synthesisModel",
            "voiceId", "bindingId", "specSha256", "settingsSha256", "mediaOrigin"))
        require(string(source, "providerId") == providerId)
        return VoiceAssetIdentity.DesignedVoice(providerId, string(source, "designModel"), string(source, "synthesisModel"),
            string(source, "voiceId"), string(source, "bindingId"), string(source, "specSha256"),
            string(source, "settingsSha256"), VoiceMediaOrigin.valueOf(string(source, "mediaOrigin")))
    }
    fun parse(json: String, audioDirectory: File, bindingFile: File): LocalVoiceCatalog {
        try {
            require(json.length <= 262_144)
            val root = JSONObject(json)
            val schemaVersion = integer(root, "schemaVersion")
            if (schemaVersion !in 1..3) throw VoiceAssetException("UNSUPPORTED_VOICE_MANIFEST_SCHEMA")
            val providerId = string(root, "providerId")
            val clips = root.getJSONArray("clips")
            require(clips.length() in 1..100)
            return LocalVoiceCatalog(providerId, (0 until clips.length()).map { index ->
                val clip = clips.getJSONObject(index)
                require(integer(clip, "sampleWidthBytes") == 2)
                val source = when (schemaVersion) {
                    1 -> legacySource(clip, providerId)
                    2 -> directedSource(clip, providerId)
                    3 -> designedSource(clip, providerId)
                    else -> error("Schema checked above")
                }
                LocalVoiceClip(string(clip, "clipId"), string(clip, "characterId"), string(clip, "profileId"),
                    string(clip, "speakerId"), string(clip, "locale"), string(clip, "text"),
                    string(clip, "textSha256"), string(clip, "audioPath"), string(clip, "audioSha256"),
                    integer(clip, "sampleRateHz"), integer(clip, "channels"), integer(clip, "durationMs"), source,
                    if (schemaVersion == 3 && clip.has("rawAudioSha256")) string(clip, "rawAudioSha256") else null)
            }, audioDirectory, CharacterVoiceBindings(bindingFile))
        } catch (e: VoiceAssetException) { throw e }
        catch (_: Exception) { throw VoiceAssetException("INVALID_VOICE_MANIFEST") }
    }
}
