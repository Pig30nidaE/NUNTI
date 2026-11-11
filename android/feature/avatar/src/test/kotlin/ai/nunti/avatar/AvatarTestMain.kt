package ai.nunti.avatar

import ai.nunti.navigation.*
import ai.nunti.emotion.*
import java.io.File
import org.json.JSONObject
import kotlin.random.Random
import kotlin.system.measureNanoTime

private var tests = 0
private val results = mutableListOf<String>()
private fun test(name: String, block: () -> Unit) {
    try { block(); tests++; results += "PASS $name" } catch (e: Throwable) { throw AssertionError("FAIL $name", e) }
}
private fun same(expected: Any?, actual: Any?) { check(expected == actual) { "Expected $expected, got $actual" } }
private fun fails(block: () -> Unit) { check(runCatching(block).isFailure) { "Expected rejection" } }

fun main(args: Array<String>) {
    val out = File(args.firstOrNull() ?: "build/reports").apply { mkdirs() }
    val engine = AvatarEngine()
    val routes = MockRoutes.representative()
    val adapter = V1WireAdapter(SourceRegistry(emptyMap(), allowMock = true))
    val city = routes[0]; val coast = routes[2]
    test("representative city/long/coast/mountain differentiation") {
        same(listOf(Theme.CITY, Theme.JOURNEY, Theme.COASTAL, Theme.MOUNTAIN), routes.map { engine.generate(it).avatar.journey.themeId })
    }
    test("same input same full AvatarSpec") { same(engine.generate(coast, 42), engine.generate(coast, 42)) }
    test("engine snapshots mutable rule configuration") {
        val config = loadProperties("generation.properties")
        val frozen = AvatarEngine(rules = config)
        val before = frozen.generate(coast)
        config.setProperty("relevance.coastal", "0")
        same(before, frozen.generate(coast))
    }
    test("map/evidence iteration ordering does not affect output") {
        same(engine.generate(city), engine.generate(city.copy(roadTypeRatios = city.roadTypeRatios!!.entries.reversed().associate { it.toPair() }, featureEvidence = city.featureEvidence.reversed())))
    }
    test("identity fixed across routes and seeds") {
        val identities = routes.flatMap { r -> (0L..10L).map { engine.generate(r, it).avatar.identity } }.toSet()
        same(setOf(IdentityLayer()), identities)
    }
    test("seed cannot override evidence and unique winner") { same(1, (0L..100L).map { engine.generate(coast, it).avatar.journey }.toSet().size) }
    test("coast requires verified evidence") { same(Theme.JOURNEY, engine.generate(coast.copy(featureEvidence = coast.featureEvidence.filter { it.field != "scenicTags" })).avatar.journey.themeId) }
    test("destination name never implies terrain") { same(Theme.BASE, engine.generate(RouteSnapshot("name", 1, destinationName = "해안 산악 서울")).avatar.journey.themeId) }
    test("HIGHWAY option never implies road ratio") { same(RoadType.UNKNOWN, engine.generate(RouteSnapshot("option", 1, "HIGHWAY")).features.dominantRoadType) }
    test("missing ratios/destination/terrain succeeds") {
        val result = engine.generate(MockRoutes.route("missing", 5000.0, null, null))
        same(Theme.BASE, result.avatar.journey.themeId); same("UNKNOWN", result.features.routeComplexity)
    }
    test("negative/NaN/infinite/huge distance becomes UNKNOWN") {
        listOf(-1.0, Double.NaN, Double.POSITIVE_INFINITY, 2_000_001.0).forEach { d ->
            same(DistanceCategory.UNKNOWN, engine.generate(MockRoutes.route("invalid", d, 10.0, null)).features.distanceCategory)
        }
    }
    test("invalid ratio sums and values are not normalized into evidence") {
        listOf(mapOf(RoadType.URBAN to 1.1), mapOf(RoadType.URBAN to -.1, RoadType.HIGHWAY to 1.1), mapOf(RoadType.URBAN to .6), mapOf(RoadType.URBAN to Double.NaN)).forEach {
            same(RoadType.UNKNOWN, engine.generate(MockRoutes.route("ratios", 1.0, 1.0, it)).features.dominantRoadType)
        }
    }
    test("stale revision evidence cannot be reused") { same(Theme.BASE, engine.generate(city.copy(routeRevision = 2)).avatar.journey.themeId) }
    test("same evidence cannot be applied to altered values") { same(DistanceCategory.UNKNOWN, engine.generate(city.copy(distanceMeters = 999999.0)).features.distanceCategory) }
    test("revision preserves avatarId; different route avoids storage collision") {
        same(engine.generate(city).avatar.avatarId, engine.generate(city.copy(routeRevision = 2)).avatar.avatarId)
        check(engine.generate(city).avatar.avatarId != engine.generate(coast).avatar.avatarId)
    }
    test("unknown schema falls back safely") { same(Theme.BASE, engine.generate(city.copy(schemaVersion = "9")).avatar.journey.themeId) }
    test("untrusted/user-declared geography is not verified") {
        val r = coast.copy(featureEvidence = coast.featureEvidence.map { it.copy(source = DataSource.USER_DECLARED) })
        same(Theme.BASE, engine.generate(r).avatar.journey.themeId)
    }
    test("low/NaN confidence evidence rejected") {
        listOf(.7, Double.NaN, 1.1).forEach { confidence ->
            same(Theme.BASE, engine.generate(city.copy(featureEvidence = city.featureEvidence.map { it.copy(confidence = confidence) })).avatar.journey.themeId)
        }
    }
    test("threshold boundary behavior is explicit") {
        listOf(20000.0 to DistanceCategory.SHORT, 20000.1 to DistanceCategory.MEDIUM, 150000.0 to DistanceCategory.LONG).forEach { (d, expected) ->
            same(expected, engine.generate(MockRoutes.route("boundary", d, null, null)).features.distanceCategory)
        }
    }
    test("no-data confidence is zero, not average of present data") { same(0.0, engine.generate(RouteSnapshot("empty", 1)).features.routeDataConfidence) }
    test("conflicting terrain candidates retain scores and tie explanation") {
        val both = MockRoutes.route("both", 50000.0, null, null, setOf(TerrainTheme.COASTAL, TerrainTheme.MOUNTAIN))
        val result = engine.generate(both, 7).avatar
        same(1, result.candidates.count { it.selected }); check(result.candidates.any { it.reason == "DETERMINISTIC_TIE_BREAK" })
        same(result, engine.generate(both, 7).avatar)
    }
    test("every selected non-base theme has verified evidence and explanation") {
        routes.map { engine.generate(it).avatar }.forEach { a ->
            check(a.selectedEvidence.isNotEmpty() && a.selectedEvidence.all { it.verified }); check(a.generationExplanation.startsWith("[MOCK 경로]"))
        }
    }
    test("part slot/theme/exclusion/face/anchor/contrast constraints") {
        val validator = ConstraintValidator(engine.manifest)
        check(validator.violations(Theme.CITY, listOf("city-vest", "travel-vest", "metro-ticket", "travel-bag"), "city").any { it.startsWith("SLOT_COLLISION") })
        check(validator.violations(Theme.CITY, listOf("travel-bag"), "city").any { it.startsWith("THEME") })
        val bad = engine.manifest.parts.getValue("city-vest").copy(bounds = Bounds(110.0, 110.0, 20.0, 20.0), anchor = "eye")
        val invalid = engine.manifest.copy(parts = engine.manifest.parts + (bad.id to bad), palettes = engine.manifest.palettes + ("city" to Palette("city", "#FFFFFF", "#FFFFFF")))
        val errors = ConstraintValidator(invalid).violations(Theme.CITY, listOf(bad.id), "city")
        check("FACE_OCCLUSION:${bad.id}" in errors && "ANCHOR:${bad.id}" in errors && "LOW_CONTRAST" in errors)
    }
    test("missing resource candidate falls back before rendering") {
        val missing = engine.manifest.copy(parts = engine.manifest.parts - "city-vest")
        same(Theme.BASE, AvatarEngine(missing).generate(city).avatar.journey.themeId)
    }
    test("unsupported identity rejected") { fails { engine.generate(city, baseCharacterId = "different-character") } }

    val machine = EmotionMachine(EmotionRules.from(loadProperties("emotion.properties")))
    fun fresh() = machine.start("trip-test", "avatar-test")
    fun event(id: String, type: EventType, at: Long, recovery: String? = null, incident: String? = null) = DrivingEvent(id, "trip-test", type, at, true, .95, incident, recovery)
    fun stable(): EmotionState {
        var s = fresh()
        for (at in listOf(0L, 1500L, 3000L)) s = machine.accept(s, event("stable-$at", EventType.STABLE_DRIVING, at), at).state
        return s
    }
    test("no data stays neutral") { same(Emotion.NEUTRAL, machine.tick(fresh(), 90000).snapshot.emotion) }
    test("stable hysteresis requires sustained observations") {
        same(Emotion.NEUTRAL, machine.accept(fresh(), event("stable", EventType.STABLE_DRIVING, 0), 0).state.snapshot.emotion)
        same(Emotion.RELAXED, stable().snapshot.emotion)
    }
    test("hysteresis gap resets evidence window") {
        var s = machine.accept(fresh(), event("s1", EventType.STABLE_DRIVING, 0), 0).state
        s = machine.accept(s, event("s2", EventType.STABLE_DRIVING, 4000), 4000).state
        same(Emotion.NEUTRAL, s.snapshot.emotion)
    }
    test("calm startled relieved calm demo") {
        var s = stable()
        s = machine.accept(s, event("brake", EventType.HARSH_BRAKING, 6000), 6000).state
        same(Emotion.STARTLED, s.snapshot.emotion)
        s = machine.accept(s, event("recovery", EventType.SAFETY_RECOVERED, 9000, "brake"), 9000).state
        same(Emotion.RELIEVED, s.snapshot.emotion)
        s = machine.tick(s, 12000); same(Emotion.RELAXED, s.snapshot.emotion)
        same(listOf(Emotion.NEUTRAL, Emotion.RELAXED, Emotion.STARTLED, Emotion.RELIEVED, Emotion.RELAXED), s.timeline.map { it.emotion })
        val summary = machine.summary(s); same(1, summary.recoveryCount); same(12000L, summary.durationMillis.values.sum())
    }
    test("interactive demo uses actual reducer timeline") {
        same(listOf(Emotion.NEUTRAL, Emotion.RELAXED, Emotion.STARTLED, Emotion.RELIEVED, Emotion.RELAXED),
            MockEmotionTimeline.run("demo-avatar").map { it.snapshot.emotion })
    }
    test("unverified event and nonfinite confidence do not cause negative emotion") {
        listOf(event("u", EventType.HARSH_BRAKING, 0).copy(verified = false), event("nan", EventType.HARSH_BRAKING, 0).copy(confidence = Double.NaN)).forEach {
            same(Emotion.NEUTRAL, machine.accept(fresh(), it, 0).state.snapshot.emotion)
        }
    }
    test("duplicate event and correlated incident suppressed") {
        val e = event("brake", EventType.HARSH_BRAKING, 1000, incident = "incident")
        val s = machine.accept(fresh(), e, 1000).state
        same(Disposition.DUPLICATE_EVENT, machine.accept(s, e, 2000).disposition)
        same(Disposition.DUPLICATE_INCIDENT, machine.accept(s, e.copy(eventId = "other", occurredAt = 3000), 3000).disposition)
        same(Emotion.RELIEVED, machine.accept(s, event("recovered", EventType.SAFETY_RECOVERED, 3000, "brake", "incident"), 3000).state.snapshot.emotion)
    }
    test("out of order/future/expired/cross-trip rejected") {
        val s = machine.accept(fresh(), event("b", EventType.HARSH_BRAKING, 3000), 3000).state
        same(Disposition.OUT_OF_ORDER, machine.accept(s, event("late", EventType.SAFETY_CONCERN, 2000), 4000).disposition)
        same(Disposition.FUTURE_EVENT, machine.accept(s, event("future", EventType.HARSH_BRAKING, 5000), 4000).disposition)
        same(Disposition.EXPIRED_EVENT, machine.accept(s, event("old", EventType.HARSH_BRAKING, 1000), 17000).disposition)
        same(Disposition.WRONG_TRIP, machine.accept(s, event("other", EventType.HARSH_BRAKING, 4000).copy(tripId = "different"), 4000).disposition)
    }
    test("same timestamp higher priority hazard supersedes concern") {
        val s = machine.accept(fresh(), event("concern", EventType.SAFETY_CONCERN, 1000), 1000).state
        same(Emotion.STARTLED, machine.accept(s, event("brake", EventType.HARSH_BRAKING, 1000), 1000).state.snapshot.emotion)
    }
    test("startle times out without asserting recovery") {
        val s = machine.accept(fresh(), event("b", EventType.HARSH_BRAKING, 1000), 1000).state
        val done = machine.tick(s, 7000); same(Emotion.NEUTRAL, done.snapshot.emotion)
        same(0, machine.summary(done).recoveryCount)
    }
    test("minimum dwell queues valid recovery") {
        val s = machine.accept(fresh(), event("b", EventType.HARSH_BRAKING, 1000), 1000).state
        val pending = machine.accept(s, event("r", EventType.SAFETY_RECOVERED, 1500, "b"), 1500)
        same(Disposition.MINIMUM_DWELL, pending.disposition); same(Emotion.RELIEVED, machine.tick(pending.state, 3000).snapshot.emotion)
    }
    test("cooldown limits recurrent startle after recovery") {
        var s = machine.accept(fresh(), event("b", EventType.HARSH_BRAKING, 1000), 1000).state
        s = machine.accept(s, event("r", EventType.SAFETY_RECOVERED, 3000, "b"), 3000).state
        same(Disposition.COOLDOWN, machine.accept(s, event("b2", EventType.HARSH_BRAKING, 5000), 5000).disposition)
    }
    test("debounce suppresses rapid new event ids") {
        val s = machine.accept(fresh(), event("c", EventType.SAFETY_CONCERN, 1000), 1000).state
        same(Disposition.DEBOUNCED, machine.accept(s, event("c2", EventType.SAFETY_CONCERN, 1200), 1200).disposition)
    }
    test("unmatched recovery and positive feedback cannot erase concern") {
        val s = machine.accept(fresh(), event("c", EventType.SAFETY_CONCERN, 1000), 1000).state
        same(Disposition.UNMATCHED_RECOVERY, machine.accept(s, event("r", EventType.SAFETY_RECOVERED, 4000, "not-c"), 4000).disposition)
        same(Disposition.UNRESOLVED_CONCERN, machine.accept(s, event("p", EventType.POSITIVE_FEEDBACK, 5000), 5000).disposition)
    }
    test("stale calm returns to neutral; clock reversal rejected") {
        same(Emotion.NEUTRAL, machine.tick(stable(), 33000).snapshot.emotion)
        fails { machine.tick(stable(), 2000) }
    }
    test("trip end freezes state; next trip fully resets") {
        val end = machine.accept(stable(), event("end", EventType.TRIP_ENDED, 7000), 7000).state
        same(end, machine.tick(end, 99000))
        same(Disposition.TRIP_ENDED, machine.accept(end, event("late", EventType.HARSH_BRAKING, 8000), 8000).disposition)
        val new = machine.start("next", "avatar-test", 8000); same(emptySet<String>(), new.seenEvents); same(Emotion.NEUTRAL, new.snapshot.emotion)
    }
    test("trip end at same timestamp as hazard still closes trip") {
        val s = machine.accept(fresh(), event("b", EventType.HARSH_BRAKING, 1000), 1000).state
        same(1000L, machine.accept(s, event("end", EventType.TRIP_ENDED, 1000), 1000).state.endedAt)
    }
    test("emotion app-restart journal restores pending recovery and dedup") {
        val entries = listOf(EmotionJournalEntry(1000, event("b", EventType.HARSH_BRAKING, 1000)),
            EmotionJournalEntry(1500, event("r", EventType.SAFETY_RECOVERED, 1500, "b")))
        val digest = propertyDigest(loadProperties("emotion.properties"))
        val journal = EmotionJournal("trip-test", "avatar-test", 0, MockRoutes.EPOCH, digest, entries)
        val file = File(out, "emotion-journal.json").apply { writeText(journal.encode()) }
        val replay = EmotionJournal.decode(file.readText()).restore(machine, digest)
        same(Disposition.DUPLICATE_EVENT, machine.accept(replay, entries.last().event!!, 2000).disposition)
        same(Emotion.RELIEVED, machine.tick(replay, 3000).snapshot.emotion)
        same(journal.restore(machine, digest), replay)
        fails { journal.restore(machine, "changed") }
    }

    val parked = PlatformDisplayPolicy(0, true, true, false, parkedConfirmed = true)
    val spec = engine.generate(city).avatar
    val renderer = CharacterRenderer(CanvasPartProvider(engine.manifest))
    test("unknown/blocked/stale platform policy hides entire avatar") {
        listOf(null, parked.copy(platformAllowsAvatarScreen = false), parked.copy(restrictionsKnown = false)).forEach {
            val state = RenderPolicy.resolve(TripPhase.PRE_DRIVE, Emotion.JOYFUL, it, 0)
            check(!state.visible); check(renderer.scene(spec, state).primitives.isEmpty())
        }
        check(!RenderPolicy.resolve(TripPhase.PRE_DRIVE, Emotion.NEUTRAL, parked, 5001).visible)
    }
    test("driving requires explicit host approval, freezes expression and semantics") {
        check(!RenderPolicy.resolve(TripPhase.DRIVING, Emotion.STARTLED, parked, 0).visible)
        val policy = parked.copy(requiresDistractionOptimization = true, hostIsApprovedForDistractionOptimization = true, permitsStaticAvatarWhileDriving = true)
        val state = RenderPolicy.resolve(TripPhase.DRIVING, Emotion.STARTLED, policy, 0)
        same(Emotion.NEUTRAL, state.emotion); check(!state.animationsAllowed && !state.interactionsAllowed)
        same("눈티", renderer.scene(spec, state).accessibilityLabel)
    }
    test("parked pre/post expressions render; all expression states preserve body") {
        val scenes = Emotion.entries.map { e -> renderer.scene(spec, RenderPolicy.resolve(TripPhase.POST_DRIVE, e, parked, 0)) }
        same(1, scenes.map { it.primitives.filter { p -> p.layer in setOf("body", "face", "signature") } }.toSet().size)
        same(6, scenes.map { it.primitives }.toSet().size)
    }
    test("missing renderer assets fall back to safe base and face") {
        val broken = CharacterRenderer(CanvasPartProvider(engine.manifest.copy(parts = emptyMap())))
        val scene = broken.scene(spec, RenderPolicy.resolve(TripPhase.PRE_DRIVE, Emotion.NEUTRAL, parked, 0))
        check(scene.warnings.isNotEmpty()); check(scene.primitives.any { it.layer == "body" }); check(scene.primitives.none { it.layer == "city-vest" })
    }
    test("renderer supports portrait/landscape scaling without coordinate drift") {
        val scene = renderer.scene(spec, RenderPolicy.resolve(TripPhase.PRE_DRIVE, Emotion.NEUTRAL, parked, 0))
        check(scene.toSvg(160, 480).contains("viewBox=\"0 0 320 320\"")); check(scene.toSvg(1024, 240).contains("width=\"1024\""))
    }
    test("wire route evidence and numeric unknown remainder") {
        val json = JSONObject(MockRoutes.wire(city)).put("roadTypeRatios", JSONObject().put("urban", .8)).toString()
        same(RoadType.URBAN, engine.generate(adapter.route(json, MockRoutes.EPOCH)).features.dominantRoadType)
        check(kotlin.math.abs(.2 - adapter.route(json, MockRoutes.EPOCH).roadTypeRatios!!.getValue(RoadType.UNKNOWN)) < 1e-9)
    }
    test("production registry does not trust mock sources") {
        val production = V1WireAdapter(SourceRegistry(emptyMap()))
        same(Theme.BASE, engine.generate(production.route(MockRoutes.wire(city), MockRoutes.EPOCH)).avatar.journey.themeId)
    }
    test("expired wire evidence is UNKNOWN") {
        val json = JSONObject(MockRoutes.wire(city)); val evidence = json.getJSONObject("featureEvidence")
        evidence.keys().forEach { evidence.getJSONObject(it).put("validUntil", "2020-01-01T00:00:00Z") }
        same(Theme.BASE, engine.generate(adapter.route(json.toString(), MockRoutes.EPOCH)).avatar.journey.themeId)
    }
    test("tag-specific evidence cannot verify unrelated terrain") {
        val json = JSONObject(MockRoutes.wire(coast))
        json.put("scenicTags", org.json.JSONArray(listOf("COASTAL", "MOUNTAIN")))
        val evidence = json.getJSONObject("featureEvidence")
        val coastalProof = evidence.remove("scenicTags")
        evidence.put("scenicTags.COASTAL", coastalProof)
        val result = engine.generate(adapter.route(json.toString(), MockRoutes.EPOCH))
        same(setOf(TerrainTheme.COASTAL), result.features.verifiedTerrainThemes)
        same(Theme.COASTAL, result.avatar.journey.themeId)
        check(result.avatar.candidates.none { it.journey.themeId == Theme.MOUNTAIN })
    }
    test("wire numeric strings, fractional revision/duration, and unknown versions reject") {
        listOf("1", 1.5, 2147483648L, 0).forEach { invalid ->
            fails { adapter.route(JSONObject(MockRoutes.wire(city)).put("routeRevision", invalid).toString(), MockRoutes.EPOCH) }
        }
        fails { adapter.route(JSONObject(MockRoutes.wire(city)).put("estimatedDurationSeconds", 1.5).toString(), MockRoutes.EPOCH) }
        fails { adapter.route(JSONObject(MockRoutes.wire(city)).put("distanceMeters", "8000").toString(), MockRoutes.EPOCH) }
        fails { adapter.route(JSONObject(MockRoutes.wire(city)).put("schemaVersion", "2.0").toString(), MockRoutes.EPOCH) }
    }
    test("actual disk save and app-restart generation restore") {
        val wire = MockRoutes.wire(coast); val original = engine.generate(adapter.route(wire, MockRoutes.EPOCH), 1234)
        val file = File(out, "avatar-replay.json").apply { writeText(AvatarReplay.save(wire, original.avatar, MockRoutes.EPOCH)) }
        same(original, AvatarReplay.restore(file.readText(), V1WireAdapter(SourceRegistry(emptyMap(), true)), AvatarEngine()))
        val changed = loadProperties("generation.properties").apply { setProperty("distance.long.min", "160000") }
        fails { AvatarReplay.restore(file.readText(), adapter, AvatarEngine(rules = changed)) }
    }
    test("voice profile identity remains fixed across themes/emotions") {
        same(1, routes.map { engine.generate(it).avatar.voiceProfile("STARTLED").voiceProfileId }.toSet().size)
        same("CALM", spec.voiceProfile("JOYFUL").voiceStyleHint)
    }
    val contract = args.getOrNull(1)?.let(::File)
    if (contract != null && File(contract, "examples/RouteSnapshot.valid.json").exists()) {
        test("SERVER RouteSnapshot/DrivingEvent fixtures consumed") {
            val r = adapter.route(File(contract, "examples/RouteSnapshot.valid.json").readText(), MockRoutes.EPOCH + 86400000)
            same(Theme.CITY, engine.generate(r).avatar.journey.themeId)
            val e = adapter.event(File(contract, "examples/DrivingEvent.valid.json").readText(), MockRoutes.EPOCH)
            same(EventType.HARSH_BRAKING, e.type); check(e.verified)
        }
        val coastalFixture = File(contract.parentFile.parentFile, "backend/nunti/mock_data/03-coastal.json")
        if (coastalFixture.exists()) test("SERVER coastal fixture tag proof maps to coastal candidate") {
            val json = JSONObject(coastalFixture.readText()).getJSONObject("contracts").getJSONObject("RouteSnapshot").toString()
            same(Theme.COASTAL, engine.generate(adapter.route(json, MockRoutes.EPOCH + 86400000)).avatar.journey.themeId)
        }
    }
    val rng = Random(73)
    var deterministic = 0; var conflicts = 0; var grounded = 0; var fallbackSuccess = 0
    val timings = mutableListOf<Long>()
    test("1000 seeded fixtures: reproduction constraints grounding deletion robustness") {
        repeat(1000) { n ->
            val roads = listOf(RoadType.URBAN, RoadType.HIGHWAY, RoadType.RURAL)[rng.nextInt(3)]
            val terrain = when (rng.nextInt(4)) { 0 -> setOf(TerrainTheme.COASTAL); 1 -> setOf(TerrainTheme.MOUNTAIN); else -> emptySet() }
            val r = MockRoutes.route("batch-$n", rng.nextDouble(0.0, 700000.0), rng.nextDouble(0.0, 20000.0), mapOf(roads to .8, RoadType.UNKNOWN to .2), terrain)
            lateinit var a: AvatarSpec
            timings += measureNanoTime { a = engine.generate(r, n.toLong()).avatar }
            if (a == engine.generate(r, n.toLong()).avatar) deterministic++
            if (ConstraintValidator(engine.manifest).violations(a.journey.themeId, a.journey.partIds, a.journey.paletteId).isNotEmpty()) conflicts++
            if (a.journey.themeId == Theme.BASE || a.selectedEvidence.all { it.verified } && a.selectedEvidence.isNotEmpty()) grounded++
            if (engine.generate(r.copy(featureEvidence = emptyList())).avatar.journey.themeId == Theme.BASE) fallbackSuccess++
        }
        same(1000, deterministic); same(0, conflicts); same(1000, grounded); same(1000, fallbackSuccess)
    }
    routes.forEach { r ->
        val a = engine.generate(r, 42).avatar
        File(out, "${r.routeId}.AvatarSpec.json").writeText(adapter.avatar(a))
        File(out, "${r.routeId}.RouteSnapshot.json").writeText(MockRoutes.wire(r))
    }
    File(out, "VoiceProfile.json").writeText(adapter.voiceProfile(spec))
    File(out, "EmotionSnapshot.json").writeText(adapter.emotion(stable().snapshot, MockRoutes.EPOCH))
    generateVisualDemo(engine, routes, renderer, parked, out)
    val sorted = timings.sorted()
    val metrics = JSONObject().put("testsPassed", tests).put("fixtureCount", 1000).put("deterministicMatches", deterministic)
        .put("constraintConflicts", conflicts).put("groundedOutputs", grounded).put("missingEvidenceFallbackSuccesses", fallbackSuccess)
        .put("generationMedianMicros", sorted[499] / 1000.0).put("generationP95Micros", sorted[949] / 1000.0)
        .put("timingScope", "local JVM synthetic fixtures; includes audit/hash; not AAOS benchmark")
    File(out, "metrics.json").writeText(metrics.toString(2))
    File(out, "tests.txt").writeText(results.joinToString("\n") + "\n")
    println(results.joinToString("\n")); println(metrics.toString(2)); println("Artifacts: ${out.absolutePath}")
}
