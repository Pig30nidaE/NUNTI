package ai.nunti.navigation

import java.security.MessageDigest
import java.util.Properties

enum class RoadType { URBAN, HIGHWAY, RURAL, UNKNOWN }
enum class DistanceCategory { SHORT, MEDIUM, LONG, UNKNOWN }
enum class DurationCategory { BRIEF, MODERATE, EXTENDED, UNKNOWN }
enum class TerrainTheme { COASTAL, MOUNTAIN, UNKNOWN }
enum class DataSource { NAVI_HELPER, VERIFIED_GIS, USER_DECLARED, MOCK, UNKNOWN }

/** Internal boundary model; SERVER owns the wire contract. No SDK availability is implied. */
data class RouteSnapshot(
    val routeId: String,
    val routeRevision: Long,
    val routeOption: String = "UNKNOWN",
    val distanceMeters: Double? = null,
    val estimatedDurationSeconds: Double? = null,
    val roadTypeRatios: Map<RoadType, Double>? = null,
    val regionTags: Set<String> = emptySet(),
    val scenicTags: Set<TerrainTheme> = emptySet(),
    val featureEvidence: List<FeatureEvidence> = emptyList(),
    val destinationName: String? = null,
    val schemaVersion: String = "1.0",
)

data class FeatureEvidence(
    val field: String,
    val routeId: String,
    val routeRevision: Long,
    val valueCanonical: String,
    val source: DataSource,
    val sourceRef: String,
    val verified: Boolean,
    val confidence: Double,
)

fun canonical(value: Any?): String = when (value) {
    null -> "UNKNOWN"
    is Map<*, *> -> value.entries.sortedBy { it.key.toString() }.joinToString(";") { "${it.key}=${it.value}" }
    is Set<*> -> value.map { it.toString() }.sorted().joinToString(";")
    else -> value.toString()
}

fun sha256(text: String): String = MessageDigest.getInstance("SHA-256")
    .digest(text.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

data class FeatureAudit(
    val feature: String,
    val raw: String,
    val value: String,
    val rule: String,
    val source: DataSource,
    val sourceRef: String?,
    val verified: Boolean,
    val confidence: Double,
    val reason: String,
)

data class RouteFeatures(
    val distanceCategory: DistanceCategory,
    val durationCategory: DurationCategory,
    val dominantRoadType: RoadType,
    val verifiedTerrainThemes: Set<TerrainTheme>,
    val verifiedRegionTags: Set<String>,
    val routeComplexity: String = "UNKNOWN",
    val routeDataConfidence: Double,
    val audit: List<FeatureAudit>,
    val warnings: List<String>,
) {
    fun confidence(feature: String): Double = audit.firstOrNull { it.feature == feature }?.confidence ?: 0.0
    fun fingerprint(): String = sha256(audit.sortedBy { it.feature }.joinToString("|") {
        "${it.feature}:${it.value}:${it.verified}:${it.confidence}"
    })
}

/** Initial experimental thresholds, not validated driving classifications. */
data class FeatureRules(
    val shortDistanceMax: Double,
    val longDistanceMin: Double,
    val briefDurationMax: Double,
    val extendedDurationMin: Double,
    val maxDistance: Double,
    val maxDuration: Double,
    val dominantRatio: Double,
    val ratioSumTolerance: Double,
    val minimumConfidence: Double,
) {
    init {
        require(listOf(shortDistanceMax, longDistanceMin, briefDurationMax, extendedDurationMin,
            maxDistance, maxDuration, dominantRatio, ratioSumTolerance, minimumConfidence).all { it.isFinite() })
        require(shortDistanceMax > 0 && longDistanceMin > shortDistanceMax && maxDistance > longDistanceMin)
        require(briefDurationMax > 0 && extendedDurationMin > briefDurationMax && maxDuration > extendedDurationMin)
        require(dominantRatio > 0.5 && dominantRatio <= 1 && ratioSumTolerance in 0.0..0.1)
        require(minimumConfidence in 0.0..1.0)
    }
    companion object {
        fun from(p: Properties) = FeatureRules(
            p.getProperty("distance.short.max").toDouble(), p.getProperty("distance.long.min").toDouble(),
            p.getProperty("duration.brief.max").toDouble(), p.getProperty("duration.extended.min").toDouble(),
            p.getProperty("distance.valid.max").toDouble(), p.getProperty("duration.valid.max").toDouble(),
            p.getProperty("road.dominant.min").toDouble(), p.getProperty("road.sum.tolerance").toDouble(),
            p.getProperty("evidence.confidence.min").toDouble(),
        )
    }
}

class RouteFeatureExtractor(private val rules: FeatureRules) {
    fun extract(route: RouteSnapshot): RouteFeatures {
        val audit = mutableListOf<FeatureAudit>()
        val warnings = mutableListOf<String>()
        val validEnvelope = route.routeId.isNotBlank() && route.routeRevision >= 0 && route.schemaVersion == "1.0"
        if (!validEnvelope) warnings += "INVALID_ROUTE_ENVELOPE"
        fun record(field: String, raw: Any?, valid: Boolean, value: String, rule: String, geographic: Boolean = false): Boolean {
            val evidence = route.featureEvidence.filter {
                ((it.field == field && it.valueCanonical == canonical(raw)) ||
                    (field.startsWith("scenicTags.") && it.field == "scenicTags" && it.valueCanonical == canonical(route.scenicTags)) ||
                    (field.startsWith("regionTags.") && it.field == "regionTags" && it.valueCanonical == canonical(route.regionTags))) &&
                    it.routeId == route.routeId && it.routeRevision == route.routeRevision && it.verified && it.sourceRef.isNotBlank() &&
                    it.confidence.isFinite() && it.confidence in rules.minimumConfidence..1.0 &&
                    it.source in if (geographic) setOf(DataSource.VERIFIED_GIS, DataSource.MOCK)
                    else setOf(DataSource.NAVI_HELPER, DataSource.VERIFIED_GIS, DataSource.MOCK)
            }.sortedWith(compareByDescending<FeatureEvidence> { it.confidence }.thenBy { it.source.name }.thenBy { it.sourceRef }).firstOrNull()
            val accepted = validEnvelope && valid && evidence != null
            val reason = when {
                !validEnvelope -> "INVALID_ROUTE_ENVELOPE"
                !valid -> "MISSING_OR_INVALID_VALUE"
                evidence == null -> "NO_MATCHING_VERIFIED_EVIDENCE"
                else -> "VERIFIED"
            }
            if (!accepted) warnings += "$field:$reason"
            audit += FeatureAudit(field, canonical(raw), if (accepted) value else "UNKNOWN", rule,
                if (accepted) evidence!!.source else DataSource.UNKNOWN,
                if (accepted) evidence!!.sourceRef else null, accepted, if (accepted) evidence!!.confidence else 0.0, reason)
            return accepted
        }
        val distance = route.distanceMeters
        val dc = when {
            distance == null -> DistanceCategory.UNKNOWN
            distance <= rules.shortDistanceMax -> DistanceCategory.SHORT
            distance >= rules.longDistanceMin -> DistanceCategory.LONG
            else -> DistanceCategory.MEDIUM
        }
        val distanceOk = record("distanceMeters", distance, distance != null && distance.isFinite() && distance in 0.0..rules.maxDistance,
            dc.name, "short<=${rules.shortDistanceMax};long>=${rules.longDistanceMin};otherwise=MEDIUM")
        val duration = route.estimatedDurationSeconds
        val tc = when {
            duration == null -> DurationCategory.UNKNOWN
            duration <= rules.briefDurationMax -> DurationCategory.BRIEF
            duration >= rules.extendedDurationMin -> DurationCategory.EXTENDED
            else -> DurationCategory.MODERATE
        }
        val timeOk = record("estimatedDurationSeconds", duration, duration != null && duration.isFinite() && duration in 0.0..rules.maxDuration,
            tc.name, "brief<=${rules.briefDurationMax};extended>=${rules.extendedDurationMin};otherwise=MODERATE")
        val ratios = route.roadTypeRatios
        val ratiosValid = !ratios.isNullOrEmpty() && ratios.values.all { it.isFinite() && it in 0.0..1.0 } &&
            kotlin.math.abs(ratios.values.sum() - 1.0) <= rules.ratioSumTolerance
        val dominant = if (ratiosValid) ratios!!.entries.sortedBy { it.key.name }
            .firstOrNull { it.key != RoadType.UNKNOWN && it.value >= rules.dominantRatio }?.key ?: RoadType.UNKNOWN else RoadType.UNKNOWN
        val roadOk = record("roadTypeRatios", ratios, ratiosValid, dominant.name, "dominant>=${rules.dominantRatio};option ignored")
        val terrain = (route.scenicTags - TerrainTheme.UNKNOWN).sortedBy { it.name }.filter {
            record("scenicTags.${it.name}", it.name, true, it.name, "verified route intersection per tag", true)
        }.toSet()
        val regions = route.regionTags.filter { it.isNotBlank() }.sorted().filter {
            record("regionTags.$it", it, true, it, "verified route region per tag;never destination name", true)
        }.toSet()
        fun aggregate(field: String, raw: Any, values: Set<*>) {
            val proofs = audit.filter { it.feature.startsWith("$field.") && it.verified }
            audit += FeatureAudit(field, canonical(raw), if (values.isEmpty()) "UNKNOWN" else canonical(values), "only individually verified tags",
                if (proofs.any { it.source == DataSource.MOCK }) DataSource.MOCK else proofs.firstOrNull()?.source ?: DataSource.UNKNOWN,
                proofs.mapNotNull { it.sourceRef }.distinct().sorted().joinToString(","), proofs.isNotEmpty(),
                proofs.minOfOrNull { it.confidence } ?: 0.0, if (proofs.isEmpty()) "NO_MATCHING_VERIFIED_EVIDENCE" else "VERIFIED")
        }
        aggregate("scenicTags", route.scenicTags, terrain)
        aggregate("regionTags", route.regionTags, regions)
        audit += FeatureAudit("routeComplexity", "UNKNOWN", "UNKNOWN", "no geometry/turn evidence available", DataSource.UNKNOWN, null, false, 0.0, "UNSUPPORTED")
        return RouteFeatures(if (distanceOk) dc else DistanceCategory.UNKNOWN, if (timeOk) tc else DurationCategory.UNKNOWN,
            if (roadOk) dominant else RoadType.UNKNOWN, terrain.toSortedSet(),
            regions, routeDataConfidence = audit.filter { it.feature in setOf("distanceMeters", "estimatedDurationSeconds", "roadTypeRatios", "scenicTags", "regionTags") }.sumOf { it.confidence } / 5,
            audit = audit.toList(), warnings = warnings.sorted())
    }
}
