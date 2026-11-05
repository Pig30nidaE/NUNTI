package ai.nunti.app.generated

import ai.nunti.app.routebirth.rbEqual
import ai.nunti.app.routebirth.rbRead
import ai.nunti.app.routebirth.rbSha
import ai.nunti.app.routebirth.rbUuid
import ai.nunti.app.routebirth.rbWrite
import ai.nunti.avatar.GeneratedPoint
import ai.nunti.tts.LocalVoiceCatalog
import ai.nunti.voice.LocalVoiceManifest
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

internal val generatedHash = Regex("[0-9a-f]{64}")

/** App-private connection provisioned by the local launcher, never a provider credential. */
internal class GeneratedConnection(file: File) {
    private val config = rbRead(file)
    val base = config.getString("baseUrl").also {
        require(it == "http://127.0.0.1:8767") { "INVALID_GENERATION_SERVER" }
    }
    val token = config.getString("token").also {
        require(it.length in 32..256 && it.all { c -> c.code in 33..126 }) { "INVALID_SERVER_AUTH" }
    }
}

internal data class GeneratedArtifact(val json: JSONObject, val requestId: String, val route: List<GeneratedPoint>) {
    val characterId get() = json.getString("characterId")
    val name get() = json.getString("displayName")
    val mode get() = json.getString("mode")
    val image get() = json.getJSONObject("visual").getJSONObject("asset")
    val imageSha get() = image.getString("sha256")
    val bindingId get() = json.getJSONObject("voice").getString("bindingId")
    companion object {
        fun parse(json: JSONObject, id: String, input: JSONObject): GeneratedArtifact {
            require(json.getInt("schemaVersion") == 2 && json.getString("journeyId") == rbUuid(id)) { "INVALID_CHARACTER_CONTRACT" }
            require(Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}").matches(json.getString("characterId")))
            val canonical = json.getString("inputCanonical")
            require(canonical.length <= 65536 && rbSha(canonical.toByteArray(Charsets.UTF_8)) == json.getString("inputSha256")) { "INPUT_DIGEST_MISMATCH" }
            require(rbEqual(JSONObject(canonical), input)) { "COMPANION_INPUT_MISMATCH" }
            require(json.getString("destinationName") == input.getJSONObject("destination").getString("name") &&
                json.getString("purpose") == input.getString("purpose")) { "COMPANION_DESTINATION_MISMATCH" }
            require(json.getString("displayName").length in 1..60 && generatedHash.matches(json.getString("specHash")))
            val mode = json.getString("mode")
            require(mode in listOf("OFFLINE_FIXTURE", "API")) { "UNKNOWN_GENERATION_MODE" }
            val visual = json.getJSONObject("visual")
            require(visual.getString("version") == "generated-rgba-1")
            val asset = visual.getJSONObject("asset")
            require(generatedHash.matches(asset.getString("sha256")) && asset.getString("path") == "/v2/assets/${asset.getString("sha256")}" &&
                asset.getString("mimeType") == "image/png" && asset.getInt("byteLength") in 1..8_388_608 &&
                asset.getInt("width") in 64..2048 && asset.getInt("height") in 64..2048 &&
                asset.getLong("width") * asset.getLong("height") <= 4_194_304) { "INVALID_IMAGE_METADATA" }
            val points = visual.getJSONArray("route")
            require(points.length() in 2..512)
            val route = (0 until points.length()).map { index ->
                val point = points.getJSONArray(index)
                require(point.length() == 2)
                val x = point.getDouble(0); val y = point.getDouble(1)
                require(x.isFinite() && y.isFinite() && x in 0.0..1.0 && y in 0.0..1.0)
                GeneratedPoint(x.toFloat(), y.toFloat())
            }
            require(route.distinct().size > 1)
            val manifest = json.getJSONObject("voiceManifest")
            require(manifest.getInt("schemaVersion") == 3) { "INVALID_VOICE_MANIFEST_SCHEMA" }
            val clips = manifest.getJSONArray("clips")
            require(clips.length() == 3)
            val expected = listOf("greeting", "common", "arrival").map { "${json.getString("characterId")}-$it" }.toSet()
            require((0 until clips.length()).map { clips.getJSONObject(it).getString("clipId") }.toSet() == expected)
            for (i in 0 until clips.length()) validateClip(json, clips.getJSONObject(i))
            return GeneratedArtifact(JSONObject(json.toString()), id, route)
        }

        fun validateClip(artifact: JSONObject, clip: JSONObject) {
            val voice = artifact.getJSONObject("voice")
            val source = clip.getJSONObject("source")
            require(clip.getString("characterId") == artifact.getString("characterId") &&
                clip.getString("profileId") == voice.getString("profileId") &&
                source.getString("bindingId") == voice.getString("bindingId") &&
                source.getString("specSha256") == artifact.getString("specHash")) { "VOICE_CHARACTER_BINDING_MISMATCH" }
            require(source.getString("mediaOrigin") == if (artifact.getString("mode") == "OFFLINE_FIXTURE") "OFFLINE_FIXTURE" else "PROVIDER_GENERATED") { "VOICE_ORIGIN_MISMATCH" }
            require(generatedHash.matches(clip.getString("audioSha256")))
            require(Regex("[A-Za-z0-9][A-Za-z0-9_.-]*\\.wav").matches(clip.getString("audioPath")) && !clip.getString("audioPath").contains(".."))
        }
    }
}

internal data class GeneratedMedia(val bitmap: Bitmap, val catalog: LocalVoiceCatalog)

/** Only authenticated same-origin assets can be installed. Redirects never carry the token. */
internal class GeneratedBridge(private val connection: GeneratedConnection) {
    private fun request(path: String, body: JSONObject? = null, limit: Int = 524288, mime: String? = null): ByteArray {
        require(path.startsWith("/v2/") && !path.contains("..") && !path.contains('?') && !path.contains('#'))
        val http = URL(connection.base + path).openConnection() as HttpURLConnection
        http.instanceFollowRedirects = false
        http.connectTimeout = 4000; http.readTimeout = 15000
        http.setRequestProperty("Authorization", "Bearer ${connection.token}")
        try {
            if (body != null) {
                http.requestMethod = "POST"; http.doOutput = true
                http.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                http.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = http.responseCode
            if (status !in 200..299) {
                val code = runCatching { JSONObject(http.errorStream.bufferedReader().use { it.readText().take(65536) })
                    .getJSONObject("error").getString("code") }.getOrDefault("GENERATION_SERVER_HTTP_$status")
                throw IllegalStateException(code.take(160))
            }
            if (mime != null) require(http.contentType?.substringBefore(';') in if (mime == "audio/wav")
                listOf("audio/wav", "audio/x-wav") else listOf(mime)) { "ASSET_MIME_MISMATCH" }
            return http.inputStream.use { stream ->
                val out = ByteArrayOutputStream(); val buffer = ByteArray(8192)
                while (true) {
                    val count = stream.read(buffer); if (count < 0) break
                    require(out.size() + count <= limit) { "GENERATION_RESPONSE_TOO_LARGE" }
                    out.write(buffer, 0, count)
                }
                out.toByteArray()
            }
        } finally { http.disconnect() }
    }
    private fun json(path: String, body: JSONObject? = null) = JSONObject(request(path, body).toString(Charsets.UTF_8)).getJSONObject("data")
    fun submit(input: JSONObject) = json("/v2/character-generations", input)
    fun poll(id: String) = json("/v2/jobs/${rbUuid(id)}")
    fun speech(characterId: String, input: JSONObject): JSONObject {
        require(Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}").matches(characterId))
        return json("/v2/characters/$characterId/speech", input)
    }
    private fun asset(hash: String, file: File, limit: Int, mime: String): ByteArray {
        require(generatedHash.matches(hash))
        if (file.isFile) return file.readBytes().also { require(it.size <= limit && rbSha(it) == hash) { "CACHED_ASSET_CHANGED" } }
        return request("/v2/assets/$hash", limit = limit, mime = mime).also {
            require(rbSha(it) == hash) { "DOWNLOADED_ASSET_CHANGED" }; rbWrite(file, it)
        }
    }
    fun install(artifact: GeneratedArtifact, directory: File, manifests: List<JSONObject> = emptyList()): GeneratedMedia {
        val bytes = asset(artifact.imageSha, directory.resolve("${artifact.imageSha}.png"), 8_388_608, "image/png")
        require(bytes.size == artifact.image.getInt("byteLength")) { "IMAGE_SIZE_MISMATCH" }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        require(bounds.outMimeType == "image/png" && bounds.outWidth == artifact.image.getInt("width") &&
            bounds.outHeight == artifact.image.getInt("height")) { "IMAGE_DIMENSIONS_MISMATCH" }
        val bitmap = requireNotNull(BitmapFactory.decodeByteArray(bytes, 0, bytes.size)) { "IMAGE_DECODE_FAILED" }
        require(bitmap.hasAlpha()) { "IMAGE_ALPHA_MISSING" }
        val pixels = IntArray(bitmap.width * bitmap.height)
        bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
        require(pixels.any { (it ushr 24) < 255 } && pixels.any { (it ushr 24) > 0 }) { "IMAGE_ALPHA_INVALID" }
        val merged = JSONObject(artifact.json.getJSONObject("voiceManifest").toString())
        val initial = merged.getJSONArray("clips")
        val initialSource = initial.getJSONObject(0).getJSONObject("source")
        for (manifest in manifests) {
            require(manifest.getInt("schemaVersion") == 3 && manifest.getString("providerId") == merged.getString("providerId"))
            val clips = manifest.getJSONArray("clips"); require(clips.length() == 1)
            val clip = clips.getJSONObject(0)
            GeneratedArtifact.validateClip(artifact.json, clip)
            require(rbEqual(initialSource, clip.getJSONObject("source"))) { "FOLLOWUP_VOICE_CHANGED" }
            val existing = (0 until initial.length()).map { initial.getJSONObject(it) }
                .singleOrNull { it.getString("textSha256") == clip.getString("textSha256") }
            if (existing == null) initial.put(clip)
            else require(rbEqual(existing, clip)) { "FOLLOWUP_ASSET_CHANGED" }
        }
        require(initial.length() <= 100)
        for (index in 0 until initial.length()) {
            val clip = initial.getJSONObject(index)
            GeneratedArtifact.validateClip(artifact.json, clip)
            asset(clip.getString("audioSha256"), directory.resolve(clip.getString("audioPath")), 2_000_000, "audio/wav")
        }
        val catalog = LocalVoiceManifest.parse(merged.toString(), directory, directory.parentFile!!.resolve("bindings.txt"))
        catalog.verifyAllMedia()
        return GeneratedMedia(bitmap, catalog)
    }
}

/** v2 final artifacts never mutate. Follow-up utterances have independent immutable records. */
internal class GeneratedStore(private val directory: File) {
    private val stateFile = directory.resolve("state.json")
    var state = if (stateFile.exists()) rbRead(stateFile) else JSONObject().put("records", JSONObject())
        private set
    private fun persist() = rbWrite(stateFile, state.toString().toByteArray(Charsets.UTF_8))
    private fun folder(id: String) = directory.resolve(rbUuid(id))
    fun input(value: JSONObject) {
        val id = rbUuid(value.getString("requestId")); val file = folder(id).resolve("input.json")
        require(!file.exists() || rbEqual(rbRead(file), value)) { "REQUEST_INPUT_CHANGED" }
        if (!file.exists()) rbWrite(file, value.toString().toByteArray(Charsets.UTF_8))
        if (!state.getJSONObject("records").has(id)) state.getJSONObject("records").put(id, JSONObject().put("arrived", false).put("collected", false))
        state.put("selected", id); persist()
    }
    fun input(id: String) = rbRead(folder(id).resolve("input.json"))
    fun media(id: String) = folder(id).resolve("media")
    fun put(artifact: GeneratedArtifact) {
        val file = folder(artifact.requestId).resolve("artifact.json")
        require(!file.exists() || rbEqual(rbRead(file), artifact.json)) { "SAVED_CHARACTER_CHANGED" }
        if (!file.exists()) rbWrite(file, artifact.json.toString().toByteArray(Charsets.UTF_8))
    }
    fun get(id: String): GeneratedArtifact? = folder(id).resolve("artifact.json").let {
        if (it.exists()) GeneratedArtifact.parse(rbRead(it), id, input(id)) else null
    }
    fun select(id: String) { require(state.getJSONObject("records").has(rbUuid(id))); state.put("selected", id); persist() }
    fun record(id: String) = state.getJSONObject("records").getJSONObject(rbUuid(id))
    fun arrive(id: String) { record(id).put("arrived", true); persist() }
    fun collect(id: String) { require(record(id).getBoolean("arrived")); record(id).put("collected", true); persist() }
    fun collected() = state.getJSONObject("records").keys().asSequence().filter { record(it).getBoolean("collected") }.toList()
    fun appendSpeech(id: String, jobId: String, manifest: JSONObject) {
        val file = folder(id).resolve("speech/${rbUuid(jobId)}.json")
        require(!file.exists() || rbEqual(rbRead(file), manifest)) { "SAVED_SPEECH_CHANGED" }
        if (!file.exists()) rbWrite(file, manifest.toString().toByteArray(Charsets.UTF_8))
        record(id).put("latestSpeechClipId", manifest.getJSONArray("clips").getJSONObject(0).getString("clipId"))
        record(id).put("latestSpeechJobId", jobId); persist()
    }
    fun speeches(id: String) = folder(id).resolve("speech").listFiles()?.filter { it.extension == "json" }?.sortedBy { it.name }?.map { rbRead(it) } ?: emptyList()
    fun speechInput(id: String, value: JSONObject) {
        val file = folder(id).resolve("pending-speech.json")
        rbWrite(file, value.toString().toByteArray(Charsets.UTF_8))
    }
    fun pendingSpeech(id: String) = folder(id).resolve("pending-speech.json").let { if (it.isFile) rbRead(it) else null }
    fun latestSpeechClip(id: String) = record(id).optString("latestSpeechClipId").takeIf { it.isNotEmpty() }
    fun finishSpeech(id: String) { folder(id).resolve("pending-speech.json").delete() }
}
