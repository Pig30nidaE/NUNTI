package ai.nunti.app.routebirth

import ai.nunti.avatar.RouteBornFace
import ai.nunti.avatar.RouteBornPoint
import ai.nunti.avatar.RouteBornSpec
import ai.nunti.tts.LocalVoiceCatalog
import ai.nunti.voice.LocalVoiceManifest
import ai.nunti.tts.VoiceAssetIdentity
import android.util.AtomicFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.UUID

internal fun rbSha(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
internal fun rbWrite(file: File, bytes: ByteArray) {
    file.parentFile!!.mkdirs()
    val atomic = AtomicFile(file)
    val stream = atomic.startWrite()
    try { stream.write(bytes); atomic.finishWrite(stream) } catch (e: Exception) { atomic.failWrite(stream); throw e }
}
internal fun rbRead(file: File) = JSONObject(AtomicFile(file).openRead().bufferedReader().use { it.readText() })
internal fun rbEqual(a: Any?, b: Any?): Boolean = when {
    a is JSONObject && b is JSONObject -> {
        val keys = a.keys().asSequence().toSet()
        keys == b.keys().asSequence().toSet() && keys.all { rbEqual(a.get(it), b.get(it)) }
    }
    a is JSONArray && b is JSONArray -> a.length() == b.length() && (0 until a.length()).all { rbEqual(a.get(it), b.get(it)) }
    a is Number && b is Number -> a.toDouble().isFinite() && a.toDouble() == b.toDouble()
    else -> a == b
}
internal fun rbUuid(value: String): String { require(UUID.fromString(value).toString() == value); return value }

internal data class BornArtifact(val json: JSONObject, val spec: RouteBornSpec, val requestId: String) {
    val characterId get() = json.getString("characterId")
    val name get() = json.getString("displayName")
    val visualSha get() = rbSha(json.getJSONObject("visual").toString().toByteArray())
    val ready get() = json.has("voiceManifest")
    companion object {
        fun parse(value: JSONObject, requestId: String, input: JSONObject): BornArtifact {
            require(value.getInt("schemaVersion") == 1 && value.getString("journeyId") == rbUuid(requestId))
            val id = value.getString("characterId")
            require(id.matches(Regex("route-[0-9a-f]{24}")))
            val canonicalInput = value.getString("inputCanonical")
            require(canonicalInput.length <= 65536 && rbSha(canonicalInput.toByteArray()) == value.getString("inputSha256")) { "INPUT_DIGEST_MISMATCH" }
            require(rbEqual(JSONObject(canonicalInput), input)) { "COMPANION_INPUT_MISMATCH" }
            require(value.getString("destinationName") == input.getJSONObject("destination").getString("name") &&
                value.getString("purpose") == input.getString("purpose")) { "COMPANION_DESTINATION_MISMATCH" }
            require(value.getString("displayName").length in 1..60)
            val visual = value.getJSONObject("visual")
            require(visual.getString("version") == "route-born-1")
            fun points(key: String): List<RouteBornPoint> {
                val values = visual.getJSONArray(key); require(values.length() == 72)
                return (0 until values.length()).map { i -> values.getJSONArray(i).let { p ->
                    require(p.length() == 2); RouteBornPoint(p.getDouble(0).toFloat(), p.getDouble(1).toFloat())
                } }
            }
            val colors = visual.getJSONArray("palette"); require(colors.length() == 3)
            val face = visual.getJSONObject("face")
            val spec = RouteBornSpec(id, points("outline"), points("route"), (0..2).map { colors.getString(it) },
                RouteBornFace(face.getDouble("cx").toFloat(), face.getDouble("cy").toFloat(), face.getDouble("scale").toFloat(), face.getDouble("eyeSpacing").toFloat()))
            return BornArtifact(value, spec, requestId)
        }
    }
}

/** Only the loopback PC bridge is reachable. No arbitrary host or asset URL from generated data. */
internal class BornBridge {
    private val base = "http://127.0.0.1:8766"
    private fun request(path: String, body: JSONObject? = null, limit: Int = 524288): ByteArray {
        val connection = URL(base + path).openConnection() as HttpURLConnection
        connection.connectTimeout = 4000; connection.readTimeout = 15000
        try {
            if (body != null) {
                connection.requestMethod = "POST"; connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            require(status in 200..299) { "PC_WORKER_HTTP_$status" }
            return connection.inputStream.use { source ->
                val out = java.io.ByteArrayOutputStream(); val buffer = ByteArray(8192)
                while (true) { val count = source.read(buffer); if (count < 0) break
                    require(out.size() + count <= limit) { "WORKER_RESPONSE_TOO_LARGE" }; out.write(buffer, 0, count) }
                out.toByteArray()
            }
        } finally { connection.disconnect() }
    }
    fun submit(input: JSONObject) = JSONObject(request("/v1/journeys", input).toString(Charsets.UTF_8))
    fun poll(id: String) = JSONObject(request("/v1/journeys/${rbUuid(id)}").toString(Charsets.UTF_8))
    fun install(artifact: BornArtifact, directory: File): LocalVoiceCatalog {
        val manifest = artifact.json.getJSONObject("voiceManifest")
        val voice = artifact.json.getJSONObject("voice")
        val clips = manifest.getJSONArray("clips"); require(clips.length() == 3)
        val expectedIds = listOf("greeting", "arrival", "common").map { "${artifact.characterId}-$it" }.toSet()
        require((0 until clips.length()).map { clips.getJSONObject(it).getString("clipId") }.toSet() == expectedIds)
        for (i in 0 until clips.length()) {
            val clip = clips.getJSONObject(i)
            require(clip.getString("characterId") == artifact.characterId && clip.getString("profileId") == voice.getString("profileId"))
            val source = clip.getJSONObject("source")
            require(source.getString("bindingId") == voice.getString("bindingId"))
            require(source.getString("directionSha256") == rbSha(voice.getString("direction").toByteArray()))
            val name = clip.getString("audioPath")
            require(name.matches(Regex("[A-Za-z0-9._-]+\\.wav")) && !name.contains(".."))
            val destination = directory.resolve(name)
            if (destination.exists()) require(rbSha(destination.readBytes()) == clip.getString("audioSha256")) { "CACHED_AUDIO_CHANGED" }
            else {
                val bytes = request("/v1/journeys/${artifact.requestId}/audio/$name", limit = 2000000)
                require(rbSha(bytes) == clip.getString("audioSha256")) { "DOWNLOADED_AUDIO_CHANGED" }
                rbWrite(destination, bytes)
            }
        }
        return LocalVoiceManifest.parse(manifest.toString(), directory, directory.parentFile!!.resolve("voice-bindings.txt"))
    }
}

internal class BornStore(private val directory: File) {
    private val stateFile = directory.resolve("state.json")
    var state: JSONObject = if (stateFile.exists()) rbRead(stateFile) else JSONObject().put("records", JSONObject())
        private set
    init { require(state.getJSONObject("records").keys().asSequence().all { rbUuid(it) == it }) }
    private fun persist() = rbWrite(stateFile, state.toString().toByteArray())
    fun input(request: JSONObject) {
        val id = rbUuid(request.getString("requestId"))
        val file = directory.resolve("$id/input.json")
        require(!file.exists() || rbEqual(rbRead(file), request)) { "REQUEST_INPUT_CHANGED" }
        if (!file.exists()) rbWrite(file, request.toString().toByteArray())
        if (!state.getJSONObject("records").has(id)) state.getJSONObject("records").put(id, JSONObject().put("arrived", false).put("collected", false))
        state.put("selected", id); persist()
    }
    fun input(id: String) = rbRead(directory.resolve("${rbUuid(id)}/input.json"))
    fun audio(id: String) = directory.resolve("${rbUuid(id)}/voice")
    fun put(artifact: BornArtifact) {
        val file = directory.resolve("${artifact.requestId}/artifact.json")
        if (file.exists()) {
            val old = BornArtifact.parse(rbRead(file), artifact.requestId, input(artifact.requestId))
            val oldBase = JSONObject(old.json.toString()).also { it.remove("voiceManifest") }
            val nextBase = JSONObject(artifact.json.toString()).also { it.remove("voiceManifest") }
            require(rbEqual(oldBase, nextBase)) { "SAVED_COMPANION_CHANGED" }
            require(!old.ready || rbEqual(old.json, artifact.json)) { "SAVED_VOICE_CHANGED" }
        }
        rbWrite(file, artifact.json.toString().toByteArray())
    }
    fun get(id: String): BornArtifact? = directory.resolve("${rbUuid(id)}/artifact.json").let { if (it.exists()) BornArtifact.parse(rbRead(it), id, input(id)) else null }
    fun select(id: String) { require(state.getJSONObject("records").has(rbUuid(id))); state.put("selected", id); persist() }
    fun record(id: String) = state.getJSONObject("records").getJSONObject(rbUuid(id))
    fun arrive(id: String) { record(id).put("arrived", true); persist() }
    fun collect(id: String) { require(record(id).getBoolean("arrived")); record(id).put("collected", true); persist() }
    fun collected() = state.getJSONObject("records").keys().asSequence().filter { record(it).getBoolean("collected") }.toList()
}
