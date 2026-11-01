package ai.nunti.avatar

import ai.nunti.navigation.*
import ai.nunti.emotion.*
import org.json.JSONObject
import org.json.JSONArray
import java.time.Instant

/** Explicit host trust registration. An arbitrary provider label never establishes GIS verification. */
data class SourceRegistry(val providers: Map<Pair<String, String>, DataSource>, val allowMock: Boolean = false) {
    fun classify(source: JSONObject?): DataSource {
        if (source == null) return DataSource.UNKNOWN
        val kind = source.optString("kind")
        if (kind == "MOCK") return if (allowMock) DataSource.MOCK else DataSource.UNKNOWN
        return providers[kind to source.optString("provider")] ?: DataSource.UNKNOWN
    }
}

class V1WireAdapter(private val registry: SourceRegistry) {
    private fun optionalString(o: JSONObject, key: String): String? = if (o.isNull(key)) null else o.getString(key)
    private fun number(o: JSONObject, key: String): Double? = if (o.isNull(key)) null else {
        val value = o.get(key)
        require(value is Number) { "$key must be a JSON number" }
        value.toDouble().also { require(it.isFinite()) { "$key must be finite" } }
    }
    private fun tags(o: JSONObject, key: String): Set<String> = o.optJSONArray(key)?.let { a -> (0 until a.length()).map { a.getString(it) }.toSet() } ?: emptySet()
    private fun instant(value: String) = Instant.parse(value).toEpochMilli()
    private fun requireVersion(o: JSONObject) { require(o.getString("schemaVersion") == "1.0") { "Unsupported schema" } }

    /** Evidence is snapshot-scoped by the v1 agreement. Producers MUST reverify it after route/value changes.
     * This adapter binds the atomic snapshot to revision+value locally; it cannot detect a dishonest producer.
     */
    fun route(json: String, nowEpochMillis: Long): RouteSnapshot {
        val o = JSONObject(json); requireVersion(o)
        val id = o.getString("routeId"); val revisionNumber = number(o, "routeRevision") ?: error("Missing routeRevision")
        require(revisionNumber >= 1 && revisionNumber <= Int.MAX_VALUE && revisionNumber % 1.0 == 0.0)
        val revision = revisionNumber.toLong()
        require(id.isNotBlank())
        val duration = number(o, "estimatedDurationSeconds")
        require(duration == null || duration % 1.0 == 0.0) { "Duration must be integer seconds" }
        val collected = instant(o.getString("collectedAt"))
        val ratioJson = o.optJSONObject("roadTypeRatios")
        val ratios = ratioJson?.let { r ->
            val values = RoadType.entries.associateWith { type -> number(r, type.name.lowercase()) ?: 0.0 }
            val total = values.values.sum()
            // The SERVER schema permits partial coverage. The remainder is explicitly UNKNOWN.
            if (total <= 1.0 && values.values.all { it.isFinite() && it >= 0 }) values + (RoadType.UNKNOWN to (values.getValue(RoadType.UNKNOWN) + 1.0 - total)) else values
        }
        var route = RouteSnapshot(id, revision, optionalString(o, "routeOption") ?: "UNKNOWN", number(o, "distanceMeters"),
            duration, ratios, tags(o, "regionTags"), tags(o, "scenicTags").mapNotNull {
                when (it) { "COASTAL" -> TerrainTheme.COASTAL; "MOUNTAIN" -> TerrainTheme.MOUNTAIN; else -> null }
            }.toSet())
        val raw = mapOf("distanceMeters" to route.distanceMeters, "estimatedDurationSeconds" to route.estimatedDurationSeconds,
            "roadTypeRatios" to route.roadTypeRatios, "regionTags" to route.regionTags, "scenicTags" to route.scenicTags) +
            route.scenicTags.associate { "scenicTags.${it.name}" to it.name } + route.regionTags.associate { "regionTags.$it" to it }
        val evidences = o.optJSONObject("featureEvidence") ?: JSONObject()
        val mapped = raw.mapNotNull { (field, value) ->
            val e = evidences.optJSONObject(field) ?: return@mapNotNull null
            val source = registry.classify(e.optJSONObject("source"))
            val observed = runCatching { instant(e.getString("observedAt")) }.getOrNull()
            val until = optionalString(e, "validUntil")?.let { runCatching { instant(it) }.getOrDefault(Long.MIN_VALUE) }
            val valid = e.optString("validity") == "VALID" && observed != null && observed <= collected && collected <= nowEpochMillis &&
                (until == null || nowEpochMillis <= until) && source != DataSource.UNKNOWN
            FeatureEvidence(field, id, revision, canonical(value), source, e.optJSONObject("source")?.optString("provider") ?: "",
                valid && e.optString("verificationStatus") == "VERIFIED", number(e, "confidence") ?: 0.0)
        }
        route = route.copy(featureEvidence = mapped)
        return route
    }

    fun event(json: String, sessionEpochMillis: Long): DrivingEvent {
        val o = JSONObject(json); requireVersion(o)
        val source = registry.classify(o.optJSONObject("source"))
        val type = when (o.getString("eventType")) {
            "HARD_BRAKING", "HARSH_BRAKING" -> EventType.HARSH_BRAKING
            "SAFETY_CONCERN", "UNSAFE_DISTANCE" -> EventType.SAFETY_CONCERN
            "STABLE_DRIVING" -> EventType.STABLE_DRIVING
            "SAFETY_RECOVERED", "SAFE_DISTANCE_RECOVERED" -> EventType.SAFETY_RECOVERED
            "POSITIVE_FEEDBACK" -> EventType.POSITIVE_FEEDBACK
            "TRIP_ENDED" -> EventType.TRIP_ENDED
            else -> EventType.UNKNOWN
        }
        return DrivingEvent(o.getString("eventId"), o.getString("tripId"), type, instant(o.getString("occurredAt")) - sessionEpochMillis,
            source != DataSource.UNKNOWN && o.getString("verificationStatus") == "VERIFIED", number(o, "confidence"),
            optionalString(o, "correlationId"), optionalString(o, "recoveryOfEventId"))
    }

    fun avatar(spec: AvatarSpec): String = JSONObject().apply {
        put("schemaVersion", "1.0"); put("avatarId", spec.avatarId); put("baseCharacterId", spec.identity.baseCharacterId)
        put("routeId", spec.routeId); put("routeRevision", spec.routeRevision); put("generationSeed", spec.seed.toString())
        put("ruleVersion", spec.generationRuleVersion); put("assetVersion", spec.assetVersion); put("paletteId", spec.journey.paletteId)
        put("outfitId", spec.journey.outfitId ?: "outfit-none"); put("accessoryIds", JSONArray(spec.journey.accessoryIds + spec.journey.decorationIds))
        put("themeId", spec.journey.themeId.name.lowercase()); put("voiceProfileId", spec.identity.voiceProfileId)
        put("generationExplanation", spec.generationExplanation)
    }.toString(2)

    fun emotion(snapshot: EmotionSnapshot, sessionEpochMillis: Long): String = JSONObject().apply {
        put("schemaVersion", "1.0"); put("emotionId", snapshot.emotionId); put("tripId", snapshot.tripId); put("avatarId", snapshot.avatarId)
        put("emotion", snapshot.emotion.name); put("intensity", when (snapshot.emotion) { Emotion.NEUTRAL -> 0.0; Emotion.STARTLED -> 0.7; else -> 0.4 })
        put("triggeredByEventId", snapshot.triggeredByEventId ?: JSONObject.NULL)
        put("occurredAt", Instant.ofEpochMilli(sessionEpochMillis + snapshot.since).toString()); put("confidence", snapshot.confidence)
    }.toString(2)

    fun voiceProfile(spec: AvatarSpec): String = JSONObject().apply {
        put("schemaVersion", "1.0"); put("voiceProfileId", spec.identity.voiceProfileId); put("locale", "ko-KR")
        put("persona", "COMPANION"); put("speakingStyle", spec.journey.voiceStyleHint)
        put("preferredVoiceId", JSONObject.NULL); put("supportedControls", JSONArray())
    }.toString(2)
}

/** Local replay record; the server's compact AvatarSpec alone intentionally does not carry every audit field. */
object AvatarReplay {
    fun save(routeJson: String, generated: AvatarSpec, evaluatedAtEpochMillis: Long): String = JSONObject().apply {
        put("format", "avatar-replay-1"); put("route", JSONObject(routeJson)); put("seed", generated.seed.toString())
        put("ruleDigest", generated.ruleDigest); put("assetDigest", generated.assetDigest)
        put("evaluatedAtEpochMillis", evaluatedAtEpochMillis)
    }.toString(2)
    fun restore(saved: String, adapter: V1WireAdapter, engine: AvatarEngine): GenerationResult {
        val o = JSONObject(saved); require(o.getString("format") == "avatar-replay-1")
        // Replay uses original evaluation time; a NEW generation must re-evaluate evidence expiry at current time.
        val result = engine.generate(adapter.route(o.getJSONObject("route").toString(), o.getLong("evaluatedAtEpochMillis")), o.getString("seed").toLong())
        require(result.avatar.ruleDigest == o.getString("ruleDigest") && result.avatar.assetDigest == o.getString("assetDigest")) {
            "Version mismatch: retain the previous assets/rules or explicitly regenerate; never silently migrate"
        }
        return result
    }
}
