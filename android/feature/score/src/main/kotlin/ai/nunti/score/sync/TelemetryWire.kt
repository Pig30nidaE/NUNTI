package ai.nunti.score.sync

import ai.nunti.score.DetectedEvent
import ai.nunti.score.ScoreReport
import ai.nunti.score.SeatState
import ai.nunti.score.VehicleSample
import java.time.Instant
import java.time.temporal.ChronoUnit
import org.json.JSONArray
import org.json.JSONObject

/** 서버 계약 v1 (contracts/v1/SampleBatch, ScoreBatch, TripCreate)의 JSON 을 만든다. 순수 JVM. */
data class SourceTag(val kind: String, val provider: String, val version: String) {
    companion object {
        /** 실제 Pleos 신호를 읽은 앱의 값. */
        val LIVE = SourceTag("ANDROID_ADAPTER", "nunti-score", "1")
        /** 시연 시나리오. 실제 주행 데이터가 아니므로 서버에서도 MOCK 으로 구분된다. */
        val DEMO = SourceTag("MOCK", "nunti-demo", "1")
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
        .put("schemaVersion", "1.0").put("tripId", tripId)
        .put("source", JSONObject().put("kind", source.kind).put("provider", source.provider).put("version", source.version))

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
                        .put("basis", it.basis.take(64)))
                }
            })
            .put("windowOverall", JSONArray().apply { report.windowOverall.forEach { put(number(it, 0.0, 100.0)) } })
            .put("newEvents", JSONArray().apply {
                r.newEvents.forEach { put(JSONObject().put("tMs", it.tMs).put("kind", it.kind.name)) }
            })
    }

    fun sampleId(index: Int) = "s-%06d".format(index)
    fun scoreId(index: Int) = "score-%06d".format(index)

    /** 계약 범위를 벗어난 값은 잘라서 보낸다 (거부당해 배치 전체가 사라지는 것보다 낫다). 유한하지 않으면 null. */
    private fun number(value: Float?, min: Double, max: Double): Any =
        value?.takeIf { it.isFinite() }?.toDouble()?.coerceIn(min, max) ?: JSONObject.NULL
}
