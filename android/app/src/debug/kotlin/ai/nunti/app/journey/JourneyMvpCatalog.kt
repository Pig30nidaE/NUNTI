package ai.nunti.app.journey

import ai.nunti.avatar.*
import ai.nunti.tts.LocalVoiceCatalog
import ai.nunti.tts.VoiceAssetIdentity
import ai.nunti.tts.voiceSha256
import android.util.AtomicFile
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

data class JourneyCase(val caseId: String, val label: String, val summary: String,
    val characterId: String, val journeyId: String, val displayName: String,
    val visual: JourneyVisualSpec, val identity: String, val clipIds: Map<String, String>)

/** Parse the worker boundary before exposing any selectable character or playback. */
class JourneyMvpCatalog(val bundleId: String, val characters: List<JourneyCase>) {
    companion object {
        fun parse(text: String, voices: LocalVoiceCatalog): JourneyMvpCatalog {
            require(text.length <= 1_000_000) { "BUNDLE_TOO_LARGE" }
            val root = JSONObject(text)
            require(root.getInt("schemaVersion") == 1 && root.getString("rendererVersion") == "journey-keepsake-canvas-1") { "UNSUPPORTED_BUNDLE" }
            val entries = root.getJSONArray("characters")
            require(entries.length() in 1..32) { "INVALID_CASE_COUNT" }
            val characters = (0 until entries.length()).map { index ->
                val item = entries.getJSONObject(index)
                val characterId = item.getString("characterId")
                require(Regex("nunti-[0-9a-f]{24}").matches(characterId)) { "INVALID_CHARACTER_ID" }
                val visual = item.getJSONObject("visual")
                require(visual.keys().asSequence().toSet() == setOf("characterId", "seed", "bodyFamily", "shapeId", "palette", "widthMultiplier", "heightMultiplier", "motif", "routePattern", "purpose")) { "INVALID_VISUAL_FIELDS" }
                require(visual.getString("characterId") == characterId) { "VISUAL_CHARACTER_MISMATCH" }
                require(hash(canonical(visual)) == item.getString("visualSha256")) { "VISUAL_HASH_MISMATCH" }
                val palette = visual.getJSONArray("palette")
                val spec = JourneyVisualSpec(characterId, visual.getString("seed"),
                    JourneyBody.valueOf(visual.getString("bodyFamily").uppercase()), visual.getString("shapeId"),
                    (0 until palette.length()).map { palette.getString(it) },
                    visual.getDouble("widthMultiplier").toFloat(), visual.getDouble("heightMultiplier").toFloat(),
                    JourneyMotif.valueOf(visual.getString("motif").uppercase()),
                    JourneyPattern.valueOf(visual.getString("routePattern").uppercase()),
                    JourneyPurpose.valueOf(visual.getString("purpose").uppercase()))
                val clipObject = item.getJSONObject("clipIds")
                val categories = setOf("greeting", "arrival", "common")
                require(clipObject.keys().asSequence().toSet() == categories) { "INVALID_CLIP_CATEGORIES" }
                val clipIds = categories.associateWith { clipObject.getString(it) }
                val clipFingerprints = clipIds.toSortedMap().map { (category, id) ->
                    val clip = voices.clips.single { it.clipId == id }
                    val source = clip.source
                    require(source is VoiceAssetIdentity.DirectedSohee) { "UNSUPPORTED_VOICE_SOURCE" }
                    require(id == "$characterId-$category" && clip.characterId == characterId &&
                        clip.profileId == item.getString("voiceProfileId") && source.bindingId == item.getString("bindingId") &&
                        source.directionSha256 == item.getString("directionSha256")) { "VISUAL_VOICE_MISMATCH" }
                    listOf(id, clip.textSha256, clip.audioSha256, clip.bindingFingerprint(voices.providerId)).joinToString("|")
                }
                val pinFields = listOf("visualSha256", "recipeSha256", "sourcePlanSha256", "directionSha256")
                require(pinFields.all { Regex("[0-9a-f]{64}").matches(item.getString(it)) }) { "INVALID_SOURCE_HASH" }
                val identity = hash((listOf(characterId, item.getString("journeyId"), item.getString("bindingId"),
                    item.getString("voiceProfileId")) + pinFields.map { item.getString(it) } + clipFingerprints).joinToString("\n"))
                fun bounded(key: String, limit: Int): String = item.getString(key).also {
                    require(it.isNotBlank() && it.length <= limit) { "INVALID_CASE_TEXT" }
                }
                JourneyCase(bounded("caseId", 120), bounded("label", 60), bounded("summary", 240),
                    characterId, bounded("journeyId", 120), bounded("displayName", 40), spec, identity, clipIds)
            }
            require(characters.map { it.characterId }.distinct().size == characters.size &&
                characters.map { it.journeyId }.distinct().size == characters.size &&
                characters.map { it.caseId }.distinct().size == characters.size) { "DUPLICATE_CASE_IDENTITY" }
            require(voices.clips.map { it.clipId }.toSet() == characters.flatMap { it.clipIds.values }.toSet()) { "BUNDLE_VOICE_SET_MISMATCH" }
            return JourneyMvpCatalog(root.getString("bundleId"), characters)
        }
        private fun hash(text: String) = voiceSha256(text.toByteArray(Charsets.UTF_8))
        private fun canonical(value: Any): String = when (value) {
            is JSONObject -> value.keys().asSequence().toList().sorted().joinToString(",", "{", "}") { JSONObject.quote(it) + ":" + canonical(value.get(it)) }
            is JSONArray -> (0 until value.length()).joinToString(",", "[", "]") { canonical(value.get(it)) }
            is String -> JSONObject.quote(value)
            // Visual numeric fields are ratios. Android JSONObject re-encodes 1.0 as 1.
            is Number -> value.toDouble().toString()
            is Boolean -> value.toString()
            else -> error("INVALID_CANONICAL_VALUE")
        }
    }
}

enum class JourneyStage { PREVIEW, ARRIVED }
data class JourneySelection(val characterId: String, val stage: JourneyStage, val collected: Set<String>)

/** One host writer; an atomic document pins visual + voice + source and never restores speech. */
class JourneyMvpStore(file: File, private val catalog: JourneyMvpCatalog) {
    private val atomic = AtomicFile(file)
    private val pins = linkedMapOf<String, String>()
    fun restore(): JourneySelection {
        if (!atomic.baseFile.exists() && !File(atomic.baseFile.path + ".bak").exists()) {
            val initial = JourneySelection(catalog.characters.first().characterId, JourneyStage.PREVIEW, emptySet())
            save(initial); return initial
        }
        val text = atomic.openRead().use { it.readBytes().toString(Charsets.UTF_8) }
        require(text.length <= 100_000) { "SAVED_STATE_TOO_LARGE" }
        val root = JSONObject(text)
        require(root.getInt("schemaVersion") == 1) { "UNSUPPORTED_SAVED_STATE" }
        val saved = root.getJSONObject("pins")
        saved.keys().forEach { id ->
            require(catalog.characters.singleOrNull { it.characterId == id }?.identity == saved.getString(id)) { "SAVED_CHARACTER_CHANGED" }
            pins[id] = saved.getString(id)
        }
        val selected = root.getString("selected")
        require(selected in pins) { "SAVED_SELECTION_UNBOUND" }
        val collected = root.getJSONArray("collected").let { list -> (0 until list.length()).map { list.getString(it) }.toSet() }
        require(collected.all { it in pins }) { "SAVED_COLLECTION_UNBOUND" }
        return JourneySelection(selected, JourneyStage.valueOf(root.getString("stage")), collected)
    }
    fun save(value: JourneySelection) {
        val selected = catalog.characters.single { it.characterId == value.characterId }
        require(pins[selected.characterId] == null || pins[selected.characterId] == selected.identity) { "SAVED_CHARACTER_CHANGED" }
        val nextPins = LinkedHashMap(pins).apply { put(selected.characterId, selected.identity) }
        require(value.collected.all { it in nextPins }) { "UNBOUND_COLLECTION" }
        val payload = JSONObject().put("schemaVersion", 1).put("selected", value.characterId)
            .put("stage", value.stage.name).put("pins", JSONObject(nextPins.toMap()))
            .put("collected", JSONArray(value.collected.sorted())).toString().toByteArray(Charsets.UTF_8)
        val stream = atomic.startWrite()
        try { stream.write(payload); stream.fd.sync(); atomic.finishWrite(stream) }
        catch (error: Exception) { atomic.failWrite(stream); throw error }
        pins.clear(); pins.putAll(nextPins)
    }
}
