package ai.nunti.avatar

import ai.nunti.navigation.*
import org.json.JSONArray
import org.json.JSONObject

/** Verified means internally consistent synthetic data, never real-world route verification. */
object MockRoutes {
    const val EPOCH = 1793498400000L // 2026-11-01T02:00:00Z
    fun route(id: String, distance: Double?, duration: Double?, ratios: Map<RoadType, Double>?,
        terrain: Set<TerrainTheme> = emptySet()): RouteSnapshot {
        val r = RouteSnapshot(id, 1, "RECOMMENDED", distance, duration, ratios, scenicTags = terrain)
        val fields = mapOf("distanceMeters" to distance, "estimatedDurationSeconds" to duration,
            "roadTypeRatios" to ratios, "scenicTags" to terrain)
        return r.copy(featureEvidence = fields.filter { it.value != null }.map { (field, value) ->
            FeatureEvidence(field, id, 1, canonical(value), DataSource.MOCK, "avatar-fixture-v1", true, 0.95)
        })
    }
    fun representative(): List<RouteSnapshot> = listOf(
        route("mock-seoul-city", 8_000.0, 1500.0, mapOf(RoadType.URBAN to .85, RoadType.HIGHWAY to .1, RoadType.UNKNOWN to .05)),
        route("mock-long-journey", 320_000.0, 15000.0, mapOf(RoadType.HIGHWAY to .88, RoadType.RURAL to .12)),
        route("mock-verified-coast", 180_000.0, 10000.0, mapOf(RoadType.RURAL to .75, RoadType.HIGHWAY to .25), setOf(TerrainTheme.COASTAL)),
        route("mock-verified-mountain", 75_000.0, 5400.0, mapOf(RoadType.RURAL to .9, RoadType.UNKNOWN to .1), setOf(TerrainTheme.MOUNTAIN)),
    )
    fun wire(route: RouteSnapshot): String = JSONObject().apply {
        put("schemaVersion", "1.0"); put("routeId", route.routeId); put("routeRevision", route.routeRevision)
        put("collectedAt", java.time.Instant.ofEpochMilli(EPOCH).toString()); put("source", source())
        put("routeOption", route.routeOption); put("distanceMeters", route.distanceMeters ?: JSONObject.NULL)
        put("estimatedDurationSeconds", route.estimatedDurationSeconds?.toLong() ?: JSONObject.NULL)
        put("roadTypeRatios", route.roadTypeRatios?.let { JSONObject(it.mapKeys { entry -> entry.key.name.lowercase() }) } ?: JSONObject.NULL)
        put("regionTags", JSONArray(route.regionTags)); put("scenicTags", JSONArray(route.scenicTags.map { it.name }))
        put("featureEvidence", JSONObject().apply {
            route.featureEvidence.forEach { e -> put(e.field, JSONObject().apply {
                put("source", source()); put("verificationStatus", if (e.verified) "VERIFIED" else "UNVERIFIED")
                put("confidence", e.confidence); put("validity", "VALID"); put("observedAt", java.time.Instant.ofEpochMilli(EPOCH).toString())
            }) }
        })
    }.toString(2)
    private fun source() = JSONObject().put("kind", "MOCK").put("provider", "avatar-fixture-v1").put("version", "1")
}
