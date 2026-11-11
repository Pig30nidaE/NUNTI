package ai.nunti.score.sync

import ai.nunti.score.DetectedEvent
import ai.nunti.score.ScoreReport
import ai.nunti.score.SeatState
import ai.nunti.score.VehicleSample
import java.time.Instant
import java.time.temporal.ChronoUnit
import org.json.JSONArray
import org.json.JSONObject

/** 서버 계약 v1 (contracts/v1/SampleBatch, ScoreBatch, EventBatch, TripReport, TripCreate)의 JSON 을 만든다. 순수 JVM. */
enum class SourceKind { MOCK, ANDROID_ADAPTER, EXTERNAL_MODULE, USER_INPUT }

data class SourceTag(val kind: SourceKind, val provider: String, val version: String) {
    /** 실제 차량 신호에서 감지한 사건만 VERIFIED 로 보낸다. 시연 데이터의 사건은 UNVERIFIED 다. */
    val verified: Boolean get() = kind == SourceKind.ANDROID_ADAPTER

    companion object {
        /** 실제 Pleos 신호를 읽은 앱의 값. */
        val LIVE = SourceTag(SourceKind.ANDROID_ADAPTER, "nunti-score", "1")
        /** 시연 시나리오. 실제 주행 데이터가 아니므로 서버에서도 MOCK 으로 구분된다. */
        val DEMO = SourceTag(SourceKind.MOCK, "nunti-demo", "1")
    }
}

/** 샘플 순번(index)이 곧 서버의 sampleId 다. 같은 순번은 항상 같은 내용이어야 재전송이 중복으로 처리된다. */
data class IndexedSample(val index: Int, val sample: VehicleSample)

/** 점수 엔진이 한 번 계산한 결과와 그 시점의 맥락. [newEvents] 는 직전 기록 이후 새로 감지된 사건만이다. */
data class ScoreRecord(
    val scoreId: String,
    val computedAtEpochMs: Long,
    val tMs: Long,
    val sampleCount: Int,
    val report: ScoreReport,
    val final: Boolean,
    val newEvents: List<DetectedEvent>,
)

/** 감지 사건 하나. [offsetMs] 는 여정 첫 샘플 기준 시각이고 [eventId] 는 그 시각과 종류로 정해져 재전송이 중복으로 처리된다. */
data class EventRecord(val eventId: String, val offsetMs: Long, val event: DetectedEvent)

/** 여정이 확정될 때 한 번 보내는 최종 결과. [evidenceEventIds] 는 /events 로 먼저 보낸 사건들이다. */
data class TripReportRecord(
    val report: ScoreReport,
    val finalText: String,
    val totalSeconds: Double,
    val evidenceEventIds: List<String>,
    val generatedAtEpochMs: Long,
)

object TelemetryWire {
    /** 점수 규칙 판본. 임계값은 아직 초안이라 규칙을 바꾸면 이 값도 올려야 서버 기록을 구분할 수 있다. */
    const val ENGINE_VERSION = "score-engine-draft-1"

    fun iso(epochMs: Long): String = Instant.ofEpochMilli(epochMs).truncatedTo(ChronoUnit.MILLIS).toString()

    fun tripCreate(tripId: String, startedAtEpochMs: Long): String = JSONObject()
        .put("schemaVersion", "1.0").put("tripId", tripId)
        .put("startedAt", iso(startedAtEpochMs)).put("syncConsent", true).toString()

    fun sampleBatch(tripId: String, source: SourceTag, startEpochMs: Long, firstTMs: Long, samples: List<IndexedSample>): String =
        batch(tripId, source).put("samples", JSONArray().apply {
            samples.forEach { put(sample(it, startEpochMs, firstTMs)) }
        }).toString()

    fun scoreBatch(tripId: String, source: SourceTag, scores: List<ScoreRecord>): String =
        batch(tripId, source).put("scores", JSONArray().apply { scores.forEach { put(score(it)) } }).toString()

    private fun batch(tripId: String, source: SourceTag) = JSONObject()
        .put("schemaVersion", "1.0").put("tripId", tripId).put("source", sourceJson(source))

    private fun sourceJson(source: SourceTag) =
        JSONObject().put("kind", source.kind.name).put("provider", source.provider).put("version", source.version)

    /** 수신하지 못한 신호는 null 그대로 보낸다 (0이나 정상값으로 바꾸지 않는다). */
    private fun sample(item: IndexedSample, startEpochMs: Long, firstTMs: Long): JSONObject {
        val s = item.sample
        val offset = (s.tMs - firstTMs).coerceAtLeast(0)
        return JSONObject()
            .put("sampleId", sampleId(item.index)).put("tMs", offset).put("occurredAt", iso(startEpochMs + offset))
            .put("speedKmh", number(s.speedKmh, 0.0, 400.0))
            .put("brakePressed", s.brakePressed ?: JSONObject.NULL)
            .put("gear", s.gear?.name ?: JSONObject.NULL)
            .put("turnSignal", s.turnSignal?.name ?: JSONObject.NULL)
            .put("driverSeat", seat(s.driverSeat)).put("passengerSeat", seat(s.passengerSeat))
            .put("doorOpen", s.doorOpen ?: JSONObject.NULL)
            .put("headlightOn", s.headlightOn ?: JSONObject.NULL)
            .put("isNight", s.isNight ?: JSONObject.NULL)
            .put("leadDistanceM", number(s.leadDistanceM, 0.0, 1000.0))
            .put("speedLimitKmh", s.speedLimitKmh?.coerceIn(0, 300) ?: JSONObject.NULL)
            .put("roadType", s.roadType.name)
            .put("steeringDeg", number(s.steeringDeg, -1080.0, 1080.0))
    }

    private fun seat(seat: SeatState?): Any = seat?.let {
        JSONObject().put("occupied", it.occupied ?: JSONObject.NULL).put("buckled", it.buckled ?: JSONObject.NULL)
    } ?: JSONObject.NULL

    private fun score(r: ScoreRecord): JSONObject {
        val report = r.report
        return JSONObject()
            .put("scoreId", r.scoreId).put("computedAt", iso(r.computedAtEpochMs)).put("tMs", r.tMs)
            .put("sampleCount", r.sampleCount).put("total", number(report.total, 0.0, 100.0))
            .put("coverage", number(report.coverage, 0.0, 1.0)).put("final", r.final)
            .put("engineVersion", ENGINE_VERSION)
            .put("areas", JSONArray().apply {
                report.areas.forEach {
                    put(JSONObject().put("area", it.area.name).put("score", number(it.score, 0.0, 100.0))
                        .put("points", number(it.points, 0.0, 100.0)))
                }
            })
            .put("items", JSONArray().apply {
                report.items.forEach {
                    put(JSONObject().put("item", it.item.name).put("score", number(it.score, 0.0, 100.0))
                        .put("basis", it.basis.text.take(64)))
                }
            })
            .put("windowOverall", JSONArray().apply { report.windowOverall.forEach { put(number(it, 0.0, 100.0)) } })
            .put("newEvents", JSONArray().apply {
                r.newEvents.forEach { put(JSONObject().put("tMs", it.tMs).put("kind", it.kind.name)) }
            })
    }

    fun eventBatch(tripId: String, source: SourceTag, startEpochMs: Long, events: List<EventRecord>): String = JSONObject()
        .put("schemaVersion", "1.0")
        .put("events", JSONArray().apply {
            events.forEach {
                put(JSONObject()
                    .put("schemaVersion", "1.0").put("eventId", it.eventId).put("tripId", tripId)
                    .put("eventType", it.event.kind.name).put("occurredAt", iso(startEpochMs + it.offsetMs))
                    .put("severity", severity(it.event.kind)).put("confidence", JSONObject.NULL)
                    .put("verificationStatus", if (source.verified) "VERIFIED" else "UNVERIFIED")
                    .put("source", sourceJson(source)))
            }
        }).toString()

    /** 사건 종류별 심각도. */
    fun severity(kind: DetectedEvent.Kind) = when (kind) {
        DetectedEvent.Kind.HARD_BRAKE, DetectedEvent.Kind.CURVE_TOO_FAST -> "HIGH"
        DetectedEvent.Kind.HARD_ACCEL, DetectedEvent.Kind.HARD_DECEL, DetectedEvent.Kind.REVERSE_TOO_FAST,
        DetectedEvent.Kind.PARK_WHILE_MOVING -> "MEDIUM"
    }

    fun tripReport(tripId: String, r: TripReportRecord): String {
        val report = r.report
        val total = r.totalSeconds.coerceAtLeast(0.0)
        val evaluated = report.movingSeconds.toDouble().coerceIn(0.0, total)
        return JSONObject()
            .put("schemaVersion", "1.0").put("tripId", tripId)
            .put("overallScore", number(report.total, 0.0, 100.0))
            .put("dataCoverage", JSONObject()
                .put("status", coverageStatus(report))
                .put("evaluatedSeconds", evaluated).put("totalSeconds", total)
                .put("ratio", number(report.coverage, 0.0, 1.0))
                .put("unavailableSignals", JSONArray(report.notConnected.map { it.name })))
            .put("finalText", r.finalText.trim().take(2000).ifEmpty { "-" })
            .put("evidenceEventIds", JSONArray(r.evidenceEventIds.takeLast(MAX_EVIDENCE)))
            .put("generatedAt", iso(r.generatedAtEpochMs))
            .toString()
    }

    /** 평가 범위(배점 비율)로 나눈다. 0.5 는 [ai.nunti.score.TripLifecycle.MIN_COVERAGE] 와 같은 기준이다. */
    fun coverageStatus(report: ScoreReport) = when {
        report.total == null -> "UNAVAILABLE"
        report.coverage >= 0.9f -> "SUFFICIENT"
        report.coverage >= ai.nunti.score.TripLifecycle.MIN_COVERAGE -> "PARTIAL"
        else -> "INSUFFICIENT"
    }

    fun eventId(offsetMs: Long, kind: DetectedEvent.Kind) = "ev-%09d-%s".format(offsetMs, kind.name)

    private const val MAX_EVIDENCE = 500

    fun sampleId(index: Int) = "s-%06d".format(index)
    fun scoreId(index: Int) = "score-%06d".format(index)

    /** 계약 범위를 벗어난 값은 잘라서 보낸다 (거부당해 배치 전체가 사라지는 것보다 낫다). 유한하지 않으면 null. */
    private fun number(value: Float?, min: Double, max: Double): Any =
        value?.takeIf { it.isFinite() }?.toDouble()?.coerceIn(min, max) ?: JSONObject.NULL
}
