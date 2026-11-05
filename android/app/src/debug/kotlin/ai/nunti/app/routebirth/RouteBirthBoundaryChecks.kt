package ai.nunti.app.routebirth

import android.util.AtomicFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.nio.file.Files

/** Explicit emulator QA only; isolated storage, never edits user artifacts or voice files. */
internal object RouteBirthBoundaryChecks {
    fun run(artifact: BornArtifact, input: JSONObject, cache: File): JSONArray {
        val results = JSONArray()
        fun test(name: String, block: () -> Unit) { block(); results.put(name) }
        fun rejected(block: () -> Unit) { var denied = false; try { block() } catch (_: IllegalArgumentException) { denied = true }; check(denied) }
        test("valid artifact and actual submitted input") { BornArtifact.parse(artifact.json, artifact.requestId, input) }
        test("wrong input under same request id rejected") {
            val wrong = JSONObject(input.toString()).also { it.getJSONObject("destination").put("name", "다른 목적지") }
            rejected { BornArtifact.parse(artifact.json, artifact.requestId, wrong) }
        }
        test("canonical input digest change rejected") {
            val wrong = JSONObject(artifact.json.toString()).put("inputSha256", "0".repeat(64))
            rejected { BornArtifact.parse(wrong, artifact.requestId, input) }
        }
        test("destination field mismatch rejected") {
            val wrong = JSONObject(artifact.json.toString()).put("destinationName", "다른 목적지")
            rejected { BornArtifact.parse(wrong, artifact.requestId, input) }
        }
        test("malformed supplied outline rejected") {
            val wrong = JSONObject(artifact.json.toString()).also { it.getJSONObject("visual").getJSONArray("outline").getJSONArray(0).put(0, 2.0) }
            rejected { BornArtifact.parse(wrong, artifact.requestId, input) }
        }
        val temporary = Files.createTempDirectory(cache.toPath(), "route-boundary-").toFile()
        try {
            val store = BornStore(temporary.resolve("store")); store.input(input)
            val pending = JSONObject(artifact.json.toString()).also { it.remove("voiceManifest") }
            store.put(BornArtifact.parse(pending, artifact.requestId, input))
            test("pending voice identity cannot change at READY") {
                val wrong = JSONObject(artifact.json.toString()).also { it.getJSONObject("voice").put("bindingId", "changed") }
                rejected { store.put(BornArtifact.parse(wrong, artifact.requestId, input)) }
            }
            store.put(artifact)
            test("committed name cannot change") {
                val wrong = JSONObject(artifact.json.toString()).put("displayName", "바뀐 이름")
                rejected { store.put(BornArtifact.parse(wrong, artifact.requestId, input)) }
            }
            test("retry preserves arrived and collection state") {
                store.arrive(artifact.requestId); store.collect(artifact.requestId); store.input(input)
                check(store.record(artifact.requestId).getBoolean("arrived") && store.collected() == listOf(artifact.requestId))
            }
            test("AtomicFile interrupted write keeps committed bytes") {
                val file = temporary.resolve("atomic"); rbWrite(file, "committed".toByteArray())
                val atomic = AtomicFile(file); val stream = atomic.startWrite(); stream.write("partial".toByteArray()); atomic.failWrite(stream)
                check(atomic.openRead().use { it.readBytes() }.toString(Charsets.UTF_8) == "committed")
            }
        } finally { temporary.deleteRecursively() }
        return results
    }
}
