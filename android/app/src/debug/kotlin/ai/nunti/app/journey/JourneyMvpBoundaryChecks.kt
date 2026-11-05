package ai.nunti.app.journey

import ai.nunti.tts.LocalVoiceCatalog
import android.util.AtomicFile
import org.json.JSONObject
import java.io.File
import java.util.UUID

/** Runs only on an explicit emulator test command, against isolated temporary state. */
object JourneyMvpBoundaryChecks {
    fun run(bundle: String, voices: LocalVoiceCatalog, directory: File): List<Map<String, Any>> {
        val checks = mutableListOf<Map<String, Any>>()
        fun check(name: String, operation: () -> Unit) {
            try { operation(); checks += mapOf("name" to name, "passed" to true) }
            catch (failure: Exception) { checks += mapOf("name" to name, "passed" to false, "error" to (failure.message ?: failure.javaClass.simpleName)) }
        }
        fun rejected(operation: () -> Unit) {
            var caught = false
            try { operation() } catch (_: IllegalArgumentException) { caught = true }
            require(caught) { "INVALID_DATA_WAS_ACCEPTED" }
        }
        fun changed(mutate: (JSONObject) -> Unit): String = JSONObject(bundle).also(mutate).toString()
        fun first(root: JSONObject) = root.getJSONArray("characters").getJSONObject(0)
        val catalog = JourneyMvpCatalog.parse(bundle, voices)
        val temporary = File(directory, "mvp-check-${UUID.randomUUID()}").also { it.mkdirs() }
        try {
            check("visual hash rejects a changed palette") {
                rejected { JourneyMvpCatalog.parse(changed { first(it).getJSONObject("visual").getJSONArray("palette").put(0, "#000000") }, voices) }
            }
            check("visual from another character is rejected") {
                rejected { JourneyMvpCatalog.parse(changed { first(it).getJSONObject("visual").put("characterId", "nunti-000000000000000000000000") }, voices) }
            }
            check("voice clips from another character are rejected") {
                rejected { JourneyMvpCatalog.parse(changed { first(it).put("clipIds", it.getJSONArray("characters").getJSONObject(1).getJSONObject("clipIds")) }, voices) }
            }
            check("voice binding cannot be changed independently") {
                rejected { JourneyMvpCatalog.parse(changed { first(it).put("bindingId", "dvb-" + "0".repeat(32)) }, voices) }
            }
            check("unsupported renderer is rejected") {
                rejected { JourneyMvpCatalog.parse(changed { it.put("rendererVersion", "unknown") }, voices) }
            }
            check("duplicate case identities are rejected") {
                rejected { JourneyMvpCatalog.parse(changed { it.getJSONArray("characters").put(first(it)) }, voices) }
            }
            val stateFile = File(temporary, "selection.json")
            val store = JourneyMvpStore(stateFile, catalog)
            val initial = store.restore()
            val saved = initial.copy(stage = JourneyStage.ARRIVED, collected = setOf(initial.characterId))
            store.save(saved)
            check("atomic state restores selected character, arrival and collection") {
                require(JourneyMvpStore(stateFile, catalog).restore() == saved)
            }
            check("same character with changed source plan cannot restore old state") {
                val altered = JourneyMvpCatalog.parse(changed { first(it).put("sourcePlanSha256", "0".repeat(64)) }, voices)
                rejected { JourneyMvpStore(stateFile, altered).restore() }
            }
            check("interrupted AtomicFile write retains the committed state") {
                val stream = AtomicFile(stateFile).startWrite()
                stream.write("{\"partial\":".toByteArray())
                stream.fd.sync(); stream.close()
                require(JourneyMvpStore(stateFile, catalog).restore() == saved)
            }
            check("corrupt saved state is rejected without overwriting it") {
                val corrupt = File(temporary, "corrupt.json").also { it.writeText("{broken") }
                val before = corrupt.readBytes()
                var caught = false
                try { JourneyMvpStore(corrupt, catalog).restore() } catch (_: Exception) { caught = true }
                require(caught && before.contentEquals(corrupt.readBytes()))
            }
        } finally { temporary.deleteRecursively() }
        return checks
    }
}
