package ai.nunti.app.journey

import android.content.Context
import android.util.AtomicFile
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** One Android-owned trip. Server assets are immutable; scores stay on the device. */
object JourneyRuntime {
    @Volatile private var value: String? = null
    @Volatile var isRunning = false
        internal set
    val current: JSONObject? get() = value?.let(::JSONObject)

    internal fun publish(context: Context, snapshot: JSONObject, persist: Boolean) {
        value = snapshot.toString()
        if (persist) write(File(context.filesDir, "journeys/latest.json"), snapshot)
    }

    fun latest(context: Context): JSONObject? {
        current?.let { return it }
        return runCatching {
            JSONObject(File(context.filesDir, "journeys/latest.json").readText()).apply {
                put("canFinish", false)
                if (optString("state") == "ACTIVE") {
                    put("state", "INTERRUPTED")
                    put("line", "앱이 중단되어 여정 기록을 멈췄어요. 마지막 저장 기록입니다.")
                }
            }
        }.getOrNull()
    }

    internal fun write(file: File, data: JSONObject) {
        file.parentFile?.mkdirs()
        val atomic = AtomicFile(file)
        val stream = atomic.startWrite()
        try { stream.write(data.toString().toByteArray()); atomic.finishWrite(stream) }
        catch (error: Exception) { atomic.failWrite(stream); throw error }
    }
}

/** Local authenticated transport; neither bridge callers nor assets choose a host or path. */
internal class JourneyAssets(private val context: Context) {
    private val base = "http://127.0.0.1:8768"
    private val config = JSONObject(File(context.filesDir, "avatar-studio-connection.json").readText())
    private val token = config.getString("token")
    init { require(config.getString("baseUrl") == base && token.length in 32..256) }

    private fun get(path: String, limit: Int): ByteArray {
        val connection = URL(base + path).openConnection() as HttpURLConnection
        try {
            connection.connectTimeout = 4000; connection.readTimeout = 10000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Authorization", "Bearer $token")
            check(connection.responseCode in 200..299) { "자산을 불러오지 못했어요 (${connection.responseCode})" }
            return connection.inputStream.use { stream ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    check(output.size() + count <= limit) { "자산이 너무 큽니다" }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
        } finally { connection.disconnect() }
    }

    private fun json(path: String) = JSONObject(String(get(path, 2_000_000))).getJSONObject("data")
    private fun asset(record: JSONObject, extension: String): File {
        val sha = record.getString("sha256")
        require(sha.matches(Regex("[0-9a-f]{64}")) && record.getString("path") == "/v3/assets/$sha")
        val file = File(context.filesDir, "journeys/assets/$sha.$extension")
        fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        if (file.isFile && hash(file.readBytes()) == sha) return file
        val bytes = get("/v3/assets/$sha", 20_000_000)
        check(hash(bytes) == sha) { "자산 검증에 실패했어요" }
        file.parentFile?.mkdirs()
        val atomic = AtomicFile(file); val output = atomic.startWrite()
        try { output.write(bytes); atomic.finishWrite(output) }
        catch (error: Exception) { atomic.failWrite(output); throw error }
        return file
    }

    fun image(sha: String): File = asset(JSONObject().put("sha256", sha).put("path", "/v3/assets/$sha"), "png")

    fun rigEyes(textureSha: String, manifestSha: String): List<File> {
        val record = JSONObject().put("sha256", manifestSha).put("path", "/v3/assets/$manifestSha")
        val rig = JSONObject(asset(record, "json").readText())
        require(rig.getString("version") == NuntiCompanionMotion.VERSION && rig.getString("kind") == "REGISTERED_TEXTURE_MESH")
        require(rig.getString("textureSha256") == textureSha)
        val parts = rig.getJSONObject("parts")
        return listOf("leftEye", "rightEye").map { name -> asset(parts.getJSONObject(name), "png") }
    }

    fun prepare(characterId: String, source: String): File {
        require(characterId.matches(Regex("nunti-[0-9a-f-]{36}")))
        require(source == "LIVE" || source == "DEMO")
        val artifact = json("/v3/avatars/$characterId")
        check(artifact.getString("characterId") == characterId)
        val image = asset(artifact.getJSONObject("visual"), "png")
        artifact.optJSONObject("design")?.optJSONObject("animationRig")?.let { rig ->
            rigEyes(artifact.getJSONObject("visual").getString("sha256"), rig.getJSONObject("manifest").getString("sha256"))
        }
        val voices = JSONObject()
        artifact.optJSONObject("voice")?.optJSONObject("audio")?.let {
            voices.put("GREETING", asset(it, "wav").absolutePath)
        }
        val sessionId = java.util.UUID.randomUUID().toString()
        val metadata = JSONObject()
            .put("sessionId", sessionId).put("characterId", characterId)
            .put("displayName", artifact.getString("displayName"))
            .put("destination", artifact.getJSONObject("destination").getString("name"))
            .put("purpose", artifact.optString("purpose"))
            .put("route", artifact.optJSONObject("route"))
            .put("faceRig", artifact.optJSONObject("design")?.optJSONObject("wardrobe")?.optString("faceRig") ?: "none")
            .put("routePlanId", artifact.optJSONObject("route")?.optString("apiPlanId")?.ifBlank { null })
            .put("staticOnly", artifact.optJSONObject("design")?.optBoolean("staticOnly", false) == true ||
                artifact.optString("mediaOrigin") == "LOCAL_LAYERS")
            .put("imageFile", image.absolutePath).put("voices", voices).put("source", source)
            .put("startedAtEpochMs", System.currentTimeMillis())
        val file = File(context.filesDir, "journeys/$sessionId-input.json")
        JourneyRuntime.write(file, metadata)
        return file
    }
}

/** Offline skins feed the existing Journey service using the same bundled final PNG as Studio. */
internal fun prepareBundledSkinJourney(context: Context, selection: String, source: String): File {
    require(source == "LIVE" || source == "DEMO")
    val input = JSONObject(selection)
    val id = input.getString("characterId")
    val skin = input.getString("skinId")
    require(id.matches(Regex("nunti-skin-[0-9a-f]{32}")) && skin in setOf("default", "sea", "city", "mountain"))
    val version = input.optString("skinVersion", "skin-v2.0")
    require(version in setOf("skin-v2.0", "skin-v2.1", "skin-v2.2"))
    val name = input.getString("displayName")
    val destination = input.getString("destination")
    val purpose = input.optString("purpose")
    require(name.length in 1..60 && destination.length in 1..60 && purpose.length <= 120)
    val routePlan = input.optString("routePlanId").takeIf { it.matches(Regex("[a-f0-9]{64}")) }
    val directory = if (skin == "default" || version == "skin-v2.0") "skin-v2" else "skin-v2/atelier"
    val bytes = context.assets.open("$directory/$skin/final.png").use { it.readBytes() }
    val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    val image = File(context.filesDir, "journeys/assets/$hash.png")
    if (!image.isFile || !image.readBytes().contentEquals(bytes)) {
        image.parentFile?.mkdirs()
        val atomic = AtomicFile(image)
        val stream = atomic.startWrite()
        try { stream.write(bytes); atomic.finishWrite(stream) }
        catch (error: Exception) { atomic.failWrite(stream); throw error }
    }
    val sessionId = java.util.UUID.randomUUID().toString()
    val metadata = JSONObject().put("sessionId", sessionId).put("characterId", id)
        .put("displayName", name).put("destination", destination).put("purpose", purpose)
        .put("routePlanId", routePlan).put("staticOnly", true).put("imageFile", image.absolutePath)
        .put("route", input.optJSONObject("route")).put("faceRig", if(version == "skin-v2.2" && skin != "default") skin else "none")
        .put("voices", JSONObject()).put("source", source).put("startedAtEpochMs", System.currentTimeMillis())
    val file = File(context.filesDir, "journeys/$sessionId-input.json")
    JourneyRuntime.write(file, metadata)
    return file
}
