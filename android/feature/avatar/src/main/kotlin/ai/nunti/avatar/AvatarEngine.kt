package ai.nunti.avatar

import ai.nunti.navigation.*
import java.util.Properties

data class JourneyLayer(val themeId: Theme, val outfitId: String?, val accessoryIds: List<String>,
    val decorationIds: List<String>, val paletteId: String, val initialPoseId: String = "standing",
    val voiceStyleHint: String = "CALM") {
    val partIds: List<String> get() = listOfNotNull(outfitId) + accessoryIds + decorationIds
}
data class ScoreBreakdown(val routeRelevance: Double, val evidenceConfidence: Double,
    val visualConsistency: Double, val diversityBonus: Double, val constraintPenalty: Double) {
    val total get() = routeRelevance + evidenceConfidence + visualConsistency + diversityBonus - constraintPenalty
}
data class CandidateEvaluation(val journey: JourneyLayer, val evidenceFields: List<String>, val score: ScoreBreakdown,
    val violations: List<String>, val selected: Boolean, val reason: String)
data class AvatarSpec(val schemaVersion: String = "1.0", val avatarId: String, val routeId: String, val routeRevision: Long,
    val identity: IdentityLayer, val journey: JourneyLayer, val seed: Long, val generationRuleVersion: String,
    val assetVersion: String, val ruleDigest: String, val assetDigest: String, val featureFingerprint: String,
    val generationExplanation: String, val selectedEvidence: List<FeatureAudit>, val candidates: List<CandidateEvaluation>,
    val mock: Boolean)
data class GenerationResult(val avatar: AvatarSpec, val features: RouteFeatures)

class AvatarEngine(val manifest: AssetManifest = AssetManifest.load(loadProperties("assets.properties")),
    rules: Properties = loadProperties("generation.properties")) {
    private val rules = Properties().apply { putAll(rules) }
    private val extractor = RouteFeatureExtractor(FeatureRules.from(rules))
    private val validator = ConstraintValidator(manifest)
    private val ruleDigest = propertyDigest(rules)
    init {
        listOf("score.relevance", "score.confidence", "score.consistency", "score.diversity", "score.violation",
            "relevance.city", "relevance.journey", "relevance.coastal", "relevance.mountain", "relevance.highway.bonus",
            "relevance.duration.bonus").forEach { require(weight(it).isFinite() && weight(it) >= 0) }
        require(weight("score.diversity") == 0.0) { "No history input: diversity bonus must remain zero" }
    }
    private fun weight(key: String) = rules.getProperty(key).toDouble()
    fun generate(route: RouteSnapshot, seed: Long = 0, baseCharacterId: String = "nunti-v1"): GenerationResult {
        require(baseCharacterId == manifest.identity.baseCharacterId) { "Unsupported identity: $baseCharacterId" }
        val f = extractor.extract(route)
        data class Candidate(val journey: JourneyLayer, val evidence: List<String>, val relevance: Double)
        val choices = mutableListOf(Candidate(JourneyLayer(Theme.BASE, null, emptyList(), emptyList(), "plain"), emptyList(), 0.0))
        if (f.dominantRoadType == RoadType.URBAN) choices += Candidate(
            JourneyLayer(Theme.CITY, "city-vest", listOf("metro-ticket"), emptyList(), "city"), listOf("roadTypeRatios"), weight("relevance.city"))
        if (f.distanceCategory == DistanceCategory.LONG) {
            val fields = mutableListOf("distanceMeters")
            var relevance = weight("relevance.journey")
            if (f.dominantRoadType == RoadType.HIGHWAY) { fields += "roadTypeRatios"; relevance += weight("relevance.highway.bonus") }
            if (f.durationCategory == DurationCategory.EXTENDED) { fields += "estimatedDurationSeconds"; relevance += weight("relevance.duration.bonus") }
            choices += Candidate(JourneyLayer(Theme.JOURNEY, "travel-vest", listOf("travel-bag"), emptyList(), "journey"), fields, relevance)
        }
        val bag = if (f.distanceCategory == DistanceCategory.LONG) listOf("travel-bag") else emptyList()
        val terrainExtraFields = if (bag.isNotEmpty()) listOf("distanceMeters") else emptyList()
        if (TerrainTheme.COASTAL in f.verifiedTerrainThemes) choices += Candidate(
            JourneyLayer(Theme.COASTAL, "coastal-scarf", bag, listOf("wave-mark"), "coastal"), listOf("scenicTags.COASTAL") + terrainExtraFields, weight("relevance.coastal"))
        if (TerrainTheme.MOUNTAIN in f.verifiedTerrainThemes) choices += Candidate(
            JourneyLayer(Theme.MOUNTAIN, "hiking-vest", bag + "water-bottle", listOf("ridge-mark"), "mountain"), listOf("scenicTags.MOUNTAIN") + terrainExtraFields, weight("relevance.mountain"))
        val evaluated = choices.map { c ->
            val violations = validator.violations(c.journey.themeId, c.journey.partIds, c.journey.paletteId)
            val confidence = if (c.evidence.isEmpty()) 0.0 else c.evidence.map(f::confidence).average()
            CandidateEvaluation(c.journey, c.evidence.sorted(), ScoreBreakdown(c.relevance * weight("score.relevance"),
                confidence * weight("score.confidence"), if (violations.isEmpty()) weight("score.consistency") else 0.0,
                0.0, violations.size * weight("score.violation")), violations, false, "")
        }.sortedWith(compareByDescending<CandidateEvaluation> { it.score.total }.thenBy {
            // Seed only breaks exact score ties; it can never introduce an unsupported theme.
            sha256("$baseCharacterId|${f.fingerprint()}|$ruleDigest|${manifest.digest}|$seed|${it.journey.themeId}")
        })
        val winner = evaluated.firstOrNull { it.violations.isEmpty() }
            ?: error("No valid base assets; reject manifest before activation")
        val evaluations = evaluated.map { it.copy(selected = it == winner, reason = when {
            it == winner -> "HIGHEST_VALID_SCORE; exact ties use persisted seed and SHA-256"
            it.violations.isNotEmpty() -> "CONSTRAINT_REJECTED:${it.violations.joinToString()}"
            it.score.total == winner.score.total -> "DETERMINISTIC_TIE_BREAK"
            else -> "LOWER_SCORE:${it.score.total}<${winner.score.total}"
        }) }
        val selected = f.audit.filter { it.feature in winner.evidenceFields }
        val mock = route.featureEvidence.any { it.source == DataSource.MOCK }
        val explanation = (if (mock) "[MOCK 경로] " else "") + when (winner.journey.themeId) {
            Theme.BASE -> "확인 가능한 경로 근거가 부족하거나 적용할 디자인 규칙이 없어 기본 눈티를 유지했습니다."
            Theme.CITY -> "확인된 도심 도로 비율을 바탕으로 도시형 조끼와 이동 티켓 장식을 선택했습니다."
            Theme.JOURNEY -> "확인된 장거리 특성을 바탕으로 여행용 조끼와 가방 장식을 선택했습니다."
            Theme.COASTAL -> "경로와 교차하는 해안 지형 근거를 바탕으로 물결 장식과 스카프를 선택했습니다."
            Theme.MOUNTAIN -> "경로와 교차하는 산악 지형 근거를 바탕으로 능선 장식과 등산 조끼를 선택했습니다."
        } + if (bag.isNotEmpty() && winner.journey.themeId in setOf(Theme.COASTAL, Theme.MOUNTAIN)) " 확인된 장거리 특성에 따라 가방을 더했습니다." else ""
        return GenerationResult(AvatarSpec(avatarId = "avatar-${sha256("$baseCharacterId|${route.routeId}").take(20)}", routeId = route.routeId,
            routeRevision = route.routeRevision, identity = manifest.identity, journey = winner.journey, seed = seed,
            generationRuleVersion = rules.getProperty("rule.version"), assetVersion = manifest.assetVersion,
            ruleDigest = ruleDigest, assetDigest = manifest.digest, featureFingerprint = f.fingerprint(),
            generationExplanation = explanation, selectedEvidence = selected, candidates = evaluations, mock = mock), f)
    }
}

data class VoiceProfileLink(val avatarId: String, val voiceProfileId: String, val persona: String,
    val voiceStyleHint: String, val currentEmotion: String)
fun AvatarSpec.voiceProfile(emotion: String) = VoiceProfileLink(avatarId, identity.voiceProfileId, identity.persona, journey.voiceStyleHint, emotion)
