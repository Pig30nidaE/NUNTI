package ai.nunti.tts

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.ByteArrayOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest

class VoiceAssetException(val reason: String) : IllegalArgumentException(reason)
private fun assetRequire(value: Boolean, reason: String) { if (!value) throw VoiceAssetException(reason) }
fun voiceSha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
    .joinToString("") { "%02x".format(it.toInt() and 255) }

/** Distinct synthesis identities share a WAV transport, not invented model controls. */
sealed interface VoiceAssetIdentity {
    data class LegacyCatalog(val revision: String, val bindingId: String, val speed: Double,
        val steps: Int, val catalogSha256: String) : VoiceAssetIdentity {
        init {
            val token = Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
            assetRequire(token.matches(revision), "INVALID_MODEL_REVISION")
            assetRequire(token.matches(bindingId) && Regex("[0-9a-f]{64}").matches(catalogSha256) &&
                speed.isFinite() && speed in 0.5..2.0 && steps in 1..100, "INVALID_VOICE_BINDING")
        }
    }

    data class DirectedSohee(val revision: String, val bindingId: String, val engineFingerprint: String,
        val directionSha256: String, val seed: Long) : VoiceAssetIdentity {
        companion object {
            const val PROVIDER_ID = "qwen3-tts-sohee-local"
            const val MODEL_REVISION = "41d3337e8b7f2843a75841595fc14e4b9a7a4b96"
        }
        init {
            assetRequire(revision == MODEL_REVISION, "UNSUPPORTED_SOHEE_MODEL_REVISION")
            assetRequire(Regex("dvb-[0-9a-f]{32}").matches(bindingId) &&
                listOf(engineFingerprint, directionSha256).all { Regex("[0-9a-f]{64}").matches(it) } &&
                seed in 0L..0xffff_ffffL, "INVALID_VOICE_BINDING")
        }
    }

    /** A retained provider voice, or an explicitly labelled recording fixture; never a preset alias. */
    data class DesignedVoice(val providerId: String, val designModel: String, val synthesisModel: String,
        val voiceId: String, val bindingId: String, val specSha256: String, val settingsSha256: String,
        val mediaOrigin: VoiceMediaOrigin) : VoiceAssetIdentity {
        companion object {
            const val KIND = "designed-voice-v1"
            const val ELEVENLABS = "elevenlabs-designed"
            const val GEMINI = "gemini-designed"
            const val FIXTURE = "nunti-offline-fixture"
            val PROVIDERS = setOf(ELEVENLABS, GEMINI, FIXTURE)
        }
        init {
            val token = Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
            assetRequire(listOf(voiceId, bindingId).all { token.matches(it) } &&
                listOf(specSha256, settingsSha256).all { Regex("[0-9a-f]{64}").matches(it) }, "INVALID_VOICE_BINDING")
            val supported = when (providerId) {
                ELEVENLABS -> designModel == "eleven_ttv_v3" && synthesisModel == "eleven_v4" &&
                    mediaOrigin == VoiceMediaOrigin.PROVIDER_GENERATED && !voiceId.startsWith("fixture-")
                GEMINI -> designModel == "gemini-3.8-flash-tts" && synthesisModel == "gemini-3.8-flash-tts" &&
                    mediaOrigin == VoiceMediaOrigin.PROVIDER_GENERATED && voiceId.startsWith("voice_")
                FIXTURE -> designModel == "offline-fixture-v1" && synthesisModel == "fixture-wav-v1" &&
                    mediaOrigin == VoiceMediaOrigin.OFFLINE_FIXTURE && voiceId.startsWith("fixture-")
                else -> false
            }
            assetRequire(supported, "DESIGNED_VOICE_SOURCE_MISMATCH")
        }
    }
}

enum class VoiceMediaOrigin { PROVIDER_GENERATED, OFFLINE_FIXTURE }

private fun VoiceAssetIdentity.fingerprintParts(): List<Any> = when (this) {
    // These parts and their order are unchanged from the persisted v1 ledger.
    is VoiceAssetIdentity.LegacyCatalog -> listOf(revision, bindingId, speed, steps, catalogSha256)
    is VoiceAssetIdentity.DirectedSohee -> listOf("directed-sohee-v1", revision, bindingId,
        engineFingerprint, directionSha256, seed)
    is VoiceAssetIdentity.DesignedVoice -> listOf(VoiceAssetIdentity.DesignedVoice.KIND, providerId,
        designModel, synthesisModel, voiceId, bindingId, specSha256, settingsSha256, mediaOrigin.name)
}

data class LocalVoiceClip(val clipId: String, val characterId: String, val profileId: String,
    val speakerId: String, val locale: String, val text: String, val textSha256: String,
    val audioPath: String, val audioSha256: String, val sampleRateHz: Int, val channels: Int,
    val durationMs: Int, val source: VoiceAssetIdentity, val rawAudioSha256: String? = null) {
    init {
        val token = Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
        assetRequire(listOf(clipId, characterId, profileId, speakerId).all { token.matches(it) }, "INVALID_VOICE_ID")
        assetRequire(locale == "ko-KR", "UNSUPPORTED_LOCALE")
        assetRequire(Regex("[A-Za-z0-9][A-Za-z0-9_.-]*\\.wav").matches(audioPath), "INVALID_AUDIO_PATH")
        assetRequire(listOf(textSha256, audioSha256).all { Regex("[0-9a-f]{64}").matches(it) }, "INVALID_ASSET_HASH")
        assetRequire(rawAudioSha256 == null || Regex("[0-9a-f]{64}").matches(rawAudioSha256), "INVALID_ASSET_HASH")
        assetRequire(text.isNotBlank() && text.length <= 2000 && voiceSha256(text.toByteArray(Charsets.UTF_8)) == textSha256,
            "MANIFEST_TEXT_MISMATCH")
        assetRequire(sampleRateHz in 8000..96000 && channels in 1..2 && durationMs in 1..30000,
            "INVALID_AUDIO_METADATA")
        if (source is VoiceAssetIdentity.DirectedSohee) {
            assetRequire(speakerId == "Sohee", "UNSUPPORTED_SOHEE_SPEAKER")
            assetRequire(text.length <= 100, "VOICE_TEXT_TOO_LONG")
            assetRequire(sampleRateHz == 24000 && channels == 1, "INVALID_SOHEE_AUDIO_METADATA")
        }
        if (source is VoiceAssetIdentity.DesignedVoice) {
            assetRequire(speakerId == source.voiceId, "DESIGNED_VOICE_SPEAKER_MISMATCH")
            assetRequire(sampleRateHz == 24000 && channels == 1, "INVALID_DESIGNED_AUDIO_METADATA")
        }
    }
    fun bindingFingerprint(providerId: String) = voiceSha256((listOf(providerId, characterId, profileId, speakerId,
        locale) + source.fingerprintParts()).joinToString("|").toByteArray(Charsets.UTF_8))
}

/** Single owning lane. Re-read and atomically replace a strict app-private binding ledger. */
class CharacterVoiceBindings(private val file: File) {
    fun bind(characterId: String, fingerprint: String, textSha256: String, assetFingerprint: String) {
        try {
            val entries = linkedMapOf<String, String>()
            if (file.exists()) {
                assetRequire(file.length() <= 1_048_576, "BINDING_STORE_CORRUPT")
                file.readLines(Charsets.UTF_8).forEach { line ->
                    val pair = line.split('=')
                    assetRequire(pair.size == 2 && Regex("(voice|asset)\\.[0-9a-f]{64}").matches(pair[0]) &&
                        Regex("[0-9a-f]{64}").matches(pair[1]) && pair[0] !in entries, "BINDING_STORE_CORRUPT")
                    entries[pair[0]] = pair[1]
                }
            }
            val voiceKey = "voice." + voiceSha256(characterId.toByteArray(Charsets.UTF_8))
            val assetKey = "asset." + voiceSha256("$characterId\n$textSha256".toByteArray(Charsets.UTF_8))
            assetRequire(entries[voiceKey] == null || entries[voiceKey] == fingerprint, "VOICE_BINDING_CHANGED")
            assetRequire(entries[assetKey] == null || entries[assetKey] == assetFingerprint, "VOICE_ASSET_CHANGED")
            if (entries[voiceKey] != null && entries[assetKey] != null) return
            val additions = listOf(voiceKey, assetKey).count { it !in entries }
            assetRequire(entries.size + additions <= 4096, "BINDING_STORE_FULL")
            entries[voiceKey] = fingerprint
            entries[assetKey] = assetFingerprint
            file.parentFile?.mkdirs()
            val temporary = File(file.parentFile, file.name + ".pending")
            FileOutputStream(temporary).use { stream ->
                stream.write(entries.toSortedMap().entries.joinToString("\n", postfix = "\n") { "${it.key}=${it.value}" }
                    .toByteArray(Charsets.UTF_8))
                stream.fd.sync()
            }
            Files.move(temporary.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
        } catch (e: IOException) { throw VoiceAssetException("BINDING_STORE_IO") }
    }
}

class LocalVoiceCatalog(val providerId: String, clips: List<LocalVoiceClip>, private val directory: File,
    private val bindings: CharacterVoiceBindings) {
    val clips = clips.toList()
    val profiles: List<VoiceProfile>
    val capabilities: ProviderCapabilities
    init {
        assetRequire(Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}").matches(providerId), "INVALID_PROVIDER_ID")
        assetRequire(clips.all { clip -> when (val source = clip.source) {
            is VoiceAssetIdentity.DirectedSohee -> providerId == VoiceAssetIdentity.DirectedSohee.PROVIDER_ID
            is VoiceAssetIdentity.DesignedVoice -> providerId == source.providerId
            is VoiceAssetIdentity.LegacyCatalog -> providerId != VoiceAssetIdentity.DirectedSohee.PROVIDER_ID &&
                providerId !in VoiceAssetIdentity.DesignedVoice.PROVIDERS
        } }, "VOICE_SOURCE_PROVIDER_MISMATCH")
        assetRequire(clips.isNotEmpty() && clips.size <= 100, "INVALID_CLIP_COUNT")
        assetRequire(clips.map { it.clipId }.distinct().size == clips.size, "DUPLICATE_CLIP_ID")
        assetRequire(clips.map { it.characterId to it.textSha256 }.distinct().size == clips.size, "AMBIGUOUS_CLIP")
        clips.groupBy { it.characterId }.values.forEach { group ->
            assetRequire(group.map { it.bindingFingerprint(providerId) }.distinct().size == 1, "VOICE_BINDING_CHANGED")
        }
        assetRequire(clips.groupBy { it.profileId }.values.all { group ->
            group.map { it.speakerId to it.locale }.distinct().size == 1
        }, "PROFILE_SPEAKER_MISMATCH")
        profiles = clips.distinctBy { it.profileId }.map { VoiceProfile(it.profileId, it.locale, it.speakerId,
            supportedControls = setOf(Control.LOCALE, Control.SPEAKER), fallbackMode = EngineMode.LOCAL_FILE) }
        capabilities = ProviderCapabilities(setOf("ko-KR"), clips.map { it.speakerId }.toSet(), setOf(Control.LOCALE, Control.SPEAKER))
    }
    fun routes(request: SpeechRequest) = clips.any { it.characterId == request.avatarId || it.profileId == request.voiceProfileId }
    /** Read every file before publishing READY; no speech request, focus, or playback is created. */
    fun verifyAllMedia() {
        // A missing later clip must not publish bindings for an incomplete media set.
        clips.forEach { readVerifiedMedia(it) }
        clips.forEach { pinVerifiedMedia(it) }
    }
    fun load(speech: PreparedSpeech): ByteArray {
        val r = speech.request
        val character = clips.filter { it.characterId == r.avatarId }
        assetRequire(character.isNotEmpty(), "UNKNOWN_VOICE_CHARACTER")
        val first = character.first()
        assetRequire(r.voiceProfileId == first.profileId && speech.voice.requestedProfileId == first.profileId &&
            speech.voice.profileId == first.profileId && !speech.voice.fallback, "VOICE_PROFILE_MISMATCH")
        assetRequire(speech.voice.speakerId == first.speakerId, "VOICE_SPEAKER_MISMATCH")
        assetRequire(speech.voice.locale == first.locale, "UNSUPPORTED_LOCALE")
        val hash = voiceSha256(r.text.toByteArray(Charsets.UTF_8))
        val clip = character.singleOrNull { it.textSha256 == hash } ?: throw VoiceAssetException("VOICE_TEXT_MISMATCH")
        val bytes = readVerifiedMedia(clip)
        pinVerifiedMedia(clip)
        return bytes
    }
    private fun pinVerifiedMedia(clip: LocalVoiceClip) {
        // Pin voice identity rather than the mutable set of approved texts; preserve v1/v2 ledger bytes.
        val rawIdentity = if (clip.source is VoiceAssetIdentity.DesignedVoice) listOf(clip.rawAudioSha256 ?: "") else emptyList()
        val assetFingerprint = voiceSha256((listOf(clip.audioSha256, clip.sampleRateHz, clip.channels, 16, clip.durationMs) + rawIdentity)
            .joinToString("|").toByteArray(Charsets.UTF_8))
        bindings.bind(clip.characterId, clip.bindingFingerprint(providerId), clip.textSha256, assetFingerprint)
    }
    private fun readVerifiedMedia(clip: LocalVoiceClip): ByteArray {
        try {
            val file = File(directory, clip.audioPath)
            assetRequire(file.canonicalFile.parentFile == directory.canonicalFile, "INVALID_AUDIO_PATH")
            assetRequire(file.isFile, "VOICE_FILE_MISSING")
            assetRequire(file.length() in 44L..16_777_216L, "VOICE_FILE_SIZE")
            val bytes = file.inputStream().use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    assetRequire(output.size() + count <= 16_777_216, "VOICE_FILE_SIZE")
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            assetRequire(bytes.size <= 16_777_216 && voiceSha256(bytes) == clip.audioSha256, "VOICE_FILE_CORRUPT")
            verifyPcmWav(bytes, clip)
            return bytes
        } catch (e: IOException) { throw VoiceAssetException("VOICE_FILE_IO") }
    }
    fun rejection(speech: PreparedSpeech): String? = try { load(speech); null }
        catch (e: VoiceAssetException) { e.reason }
}

private fun verifyPcmWav(bytes: ByteArray, clip: LocalVoiceClip) {
    fun u16(offset: Int) = (bytes[offset].toInt() and 255) or ((bytes[offset + 1].toInt() and 255) shl 8)
    fun u32(offset: Int) = u16(offset).toLong() or (u16(offset + 2).toLong() shl 16)
    fun tag(offset: Int) = String(bytes, offset, 4, Charsets.US_ASCII)
    assetRequire(bytes.size >= 44 && tag(0) == "RIFF" && tag(8) == "WAVE" && u32(4) + 8 == bytes.size.toLong(), "VOICE_FILE_FORMAT")
    var cursor = 12
    var formatSeen = false
    var dataBytes: Long? = null
    while (cursor + 8 <= bytes.size) {
        val kind = tag(cursor)
        val size = u32(cursor + 4)
        val start = cursor + 8
        assetRequire(size <= bytes.size - start, "VOICE_FILE_FORMAT")
        when (kind) {
            "fmt " -> {
                assetRequire(!formatSeen && size >= 16, "VOICE_FILE_FORMAT")
                assetRequire(u16(start) == 1 && u16(start + 2) == clip.channels && u32(start + 4) == clip.sampleRateHz.toLong() &&
                    u16(start + 14) == 16 && u16(start + 12) == clip.channels * 2 &&
                    u32(start + 8) == clip.sampleRateHz.toLong() * clip.channels * 2, "VOICE_PCM_MISMATCH")
                formatSeen = true
            }
            "data" -> {
                assetRequire(dataBytes == null && size > 0 && size % (clip.channels * 2) == 0L, "VOICE_FILE_FORMAT")
                dataBytes = size
            }
        }
        cursor = start + size.toInt() + (size % 2).toInt()
    }
    assetRequire(cursor == bytes.size && formatSeen && dataBytes != null, "VOICE_FILE_FORMAT")
    val duration = dataBytes!!.toDouble() * 1000 / (clip.sampleRateHz * clip.channels * 2)
    assetRequire(kotlin.math.abs(duration - clip.durationMs) <= 1.0 && duration <= 30000, "VOICE_DURATION_MISMATCH")
}
