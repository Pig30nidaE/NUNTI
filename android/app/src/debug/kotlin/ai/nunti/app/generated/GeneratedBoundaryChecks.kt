package ai.nunti.app.generated

import ai.nunti.app.routebirth.rbEqual
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Runs the actual Android JSON parser and immutable store, never a provider request. */
internal object GeneratedBoundaryChecks {
    fun run(value: GeneratedArtifact, input: JSONObject, store: GeneratedStore, scratch: File): JSONArray {
        val passed = JSONArray()
        fun reject(name: String, change: (JSONObject) -> Unit) {
            val copy = JSONObject(value.json.toString()); change(copy)
            check(runCatching { GeneratedArtifact.parse(copy, value.requestId, input) }.isFailure) { "BOUNDARY_ACCEPTED_$name" }
            passed.put(name)
        }
        reject("INPUT_JOIN") { it.put("inputSha256", "0".repeat(64)) }
        reject("DESTINATION_JOIN") { it.put("destinationName", "different") }
        reject("UNKNOWN_SCHEMA") { it.put("schemaVersion", 1) }
        reject("CROSS_ORIGIN_IMAGE") { it.getJSONObject("visual").getJSONObject("asset").put("path", "https://example.invalid/x.png") }
        reject("IMAGE_DECODE_BUDGET") { it.getJSONObject("visual").getJSONObject("asset").put("width", 100000) }
        reject("VOICE_CHARACTER_JOIN") { it.getJSONObject("voiceManifest").getJSONArray("clips").getJSONObject(0).put("characterId", "other") }
        reject("VOICE_SPEC_JOIN") { it.getJSONObject("voiceManifest").getJSONArray("clips").getJSONObject(0).getJSONObject("source").put("specSha256", "0".repeat(64)) }
        reject("VOICE_ORIGIN_JOIN") { it.getJSONObject("voiceManifest").getJSONArray("clips").getJSONObject(0).getJSONObject("source")
            .put("mediaOrigin", if (value.mode == "API") "OFFLINE_FIXTURE" else "PROVIDER_GENERATED") }
        reject("AUDIO_PATH") { it.getJSONObject("voiceManifest").getJSONArray("clips").getJSONObject(0).put("audioPath", "../x.wav") }
        val before = store.get(value.requestId)!!.json
        val changed = JSONObject(value.json.toString()).put("displayName", value.name + "x")
        val parsed = GeneratedArtifact.parse(changed, value.requestId, input)
        check(runCatching { store.put(parsed) }.isFailure) { "BOUNDARY_ACCEPTED_IMMUTABLE_CHARACTER" }
        check(rbEqual(before, store.get(value.requestId)!!.json))
        passed.put("IMMUTABLE_CHARACTER")
        check(!scratch.resolve("unexpected-generated-write").exists())
        return passed
    }
}
