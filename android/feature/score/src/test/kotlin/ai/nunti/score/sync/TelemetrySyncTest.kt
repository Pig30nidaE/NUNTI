package ai.nunti.score.sync

import ai.nunti.score.AreaResult
import ai.nunti.score.Area
import ai.nunti.score.DetectedEvent
import ai.nunti.score.Gear
import ai.nunti.score.Item
import ai.nunti.score.ItemResult
import ai.nunti.score.ScoreReport
import ai.nunti.score.SeatState
import ai.nunti.score.VehicleSample
import java.io.File
import java.io.IOException
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun report(total: Float? = 96.5f, events: List<DetectedEvent> = emptyList()) = ScoreReport(
    total = total, coverage = 0.9f,
    areas = listOf(AreaResult(Area.CONTROL, 100f, 35f), AreaResult(Area.EFFICIENCY, null, null)),
    items = listOf(ItemResult(Item.ACCEL_DECEL, 100f, "유효 4초", emptyList()), ItemResult(Item.EFFICIENCY, null, "수신 없음", emptyList())),
    windowOverall = listOf(100f, null), events = events,
)

private fun samples(n: Int, from: Int = 0) = (from until from + n).map { VehicleSample(tMs = 5_000L + it * 1000L, speedKmh = 50f + it) }

class TelemetryWireTest {
    @Test fun notReceivedStaysNullNeverZero() {
        val s = VehicleSample(tMs = 1000, speedKmh = null, brakePressed = null, gear = null, driverSeat = SeatState(true, null))
        val json = JSONObject(TelemetryWire.sampleBatch("trip-1", SourceTag.DEMO, 0, 1000, listOf(IndexedSample(0, s)))).getJSONArray("samples").getJSONObject(0)
        assertTrue(json.isNull("speedKmh")); assertTrue(json.isNull("brakePressed")); assertTrue(json.isNull("gear"))
        assertTrue(json.isNull("doorOpen")); assertTrue(json.isNull("passengerSeat"))
        assertEquals(true, json.getJSONObject("driverSeat").getBoolean("occupied"))
        assertTrue(json.getJSONObject("driverSeat").isNull("buckled"))
    }

    @Test fun sampleIdIsTheIndexAndTimesAreRelative() {
        val s = VehicleSample(tMs = 9_000, speedKmh = 60f, gear = Gear.D)
        val json = JSONObject(TelemetryWire.sampleBatch("trip-1", SourceTag.LIVE, 1_000L, 5_000, listOf(IndexedSample(12, s)))).getJSONArray("samples").getJSONObject(0)
        assertEquals("s-000012", json.getString("sampleId"))
        assertEquals(4_000L, json.getLong("tMs"))
        assertEquals("1970-01-01T00:00:05Z", json.getString("occurredAt"))
        assertEquals("D", json.getString("gear"))
    }

    @Test fun outOfRangeAndNonFiniteValuesAreClampedOrNull() {
        val s = VehicleSample(tMs = 0, speedKmh = -3f, leadDistanceM = Float.NaN, speedLimitKmh = 999)
        val json = JSONObject(TelemetryWire.sampleBatch("t", SourceTag.DEMO, 0, 0, listOf(IndexedSample(0, s)))).getJSONArray("samples").getJSONObject(0)
        assertEquals(0.0, json.getDouble("speedKmh"), 0.0)
        assertTrue(json.isNull("leadDistanceM"))
        assertEquals(300, json.getInt("speedLimitKmh"))
    }

    @Test fun scoreKeepsUnevaluableAsNullAndClampsTotal() {
        val record = ScoreRecord("score-000000", 0, 3000, 4, report(total = 100.00001f), false,
            listOf(DetectedEvent(2000, DetectedEvent.Kind.HARD_BRAKE)))
        val json = JSONObject(TelemetryWire.scoreBatch("t", SourceTag.LIVE, listOf(record))).getJSONArray("scores").getJSONObject(0)
        assertEquals(100.0, json.getDouble("total"), 0.0)
        assertTrue(json.getJSONArray("areas").getJSONObject(1).isNull("score"))
        assertTrue(json.getJSONArray("windowOverall").isNull(1))
        assertEquals("HARD_BRAKE", json.getJSONArray("newEvents").getJSONObject(0).getString("kind"))
        assertEquals(TelemetryWire.ENGINE_VERSION, json.getString("engineVersion"))
    }

    @Test fun tripCreateAlwaysCarriesExplicitConsent() {
        assertEquals(true, JSONObject(TelemetryWire.tripCreate("trip-1", 0)).getBoolean("syncConsent"))
    }
}

class OutboxTest {
    @Test fun fileOutboxKeepsOrderAndSurvivesRestart() {
        val dir = Files.createTempDirectory("outbox").toFile()
        val a = FileOutbox(dir)
        a.add("/p1", "{\"n\":1}"); a.add("/p2", "{\"n\":2}")
        val b = FileOutbox(dir) // 앱을 다시 켠 것과 같다
        assertEquals(2, b.size())
        assertEquals("/p1", b.peek()!!.path)
        b.remove(b.peek()!!.id)
        b.add("/p3", "{}")
        assertEquals(listOf("/p2", "/p3"), generateSequence { b.peek()?.also { b.remove(it.id) } }.map { it.path }.toList())
        dir.deleteRecursively()
    }

    @Test fun unreadableFileDoesNotBlockTheQueue() {
        val dir = Files.createTempDirectory("outbox").toFile()
        val outbox = FileOutbox(dir)
        outbox.add("/first", "{}"); outbox.add("/second", "{}")
        File(dir, "%019d.json".format(0)).writeText("not json") // 가장 앞 파일을 망가뜨린다
        assertEquals("/second", outbox.peek()!!.path)
        assertEquals(1, outbox.size())
        dir.deleteRecursively()
    }
}

class UploaderTest {
    private class Fake(val results: MutableList<Any>) : HttpTransport {
        val urls = mutableListOf<String>()
        override fun post(url: String, token: String, json: String): Int {
            urls += url
            val next = if (results.isEmpty()) 200 else results.removeAt(0)
            if (next is IOException) throw next
            return next as Int
        }
    }

    private val config = SyncConfig("http://host", "t".repeat(32))

    @Test fun classifyMatchesTheServerContract() {
        assertEquals(TelemetryUploader.Outcome.SENT, TelemetryUploader.classify(200))
        assertEquals(TelemetryUploader.Outcome.BLOCKED, TelemetryUploader.classify(401))
        assertEquals(TelemetryUploader.Outcome.BLOCKED, TelemetryUploader.classify(403))
        assertEquals(TelemetryUploader.Outcome.RETRY, TelemetryUploader.classify(503))
        assertEquals(TelemetryUploader.Outcome.RETRY, TelemetryUploader.classify(429))
        assertEquals(TelemetryUploader.Outcome.DROP, TelemetryUploader.classify(409))
        assertEquals(TelemetryUploader.Outcome.DROP, TelemetryUploader.classify(422))
    }

    @Test fun sendsInOrderAndEmptiesTheQueue() {
        val outbox = MemoryOutbox().apply { add("/v1/trips", "{}"); add("/v1/trips/t/samples", "{}") }
        val transport = Fake(mutableListOf())
        val status = TelemetryUploader(outbox, transport, config).flush()
        assertEquals(listOf("http://host/v1/trips", "http://host/v1/trips/t/samples"), transport.urls)
        assertEquals(0, status.pending); assertEquals(2, status.sent)
    }

    @Test fun networkFailureKeepsTheItemAndBacksOff() {
        var now = 0L
        val outbox = MemoryOutbox().apply { add("/a", "{}") }
        val transport = Fake(mutableListOf(IOException("down")))
        val uploader = TelemetryUploader(outbox, transport, config, clock = { now }, baseBackoffMs = 2000)
        assertEquals(1, uploader.flush().pending)
        assertEquals(1, transport.urls.size)
        now = 1000; uploader.flush() // 백오프 중이라 시도하지 않는다
        assertEquals(1, transport.urls.size)
        now = 2500
        val status = uploader.flush()
        assertEquals(2, transport.urls.size); assertEquals(0, status.pending); assertEquals(1, status.sent)
    }

    @Test fun rejectedItemIsDroppedSoItDoesNotBlockTheRest() {
        val outbox = MemoryOutbox().apply { add("/bad", "{}"); add("/good", "{}") }
        val status = TelemetryUploader(outbox, Fake(mutableListOf(422)), config).flush()
        assertEquals(0, status.pending); assertEquals(1, status.dropped); assertEquals(1, status.sent)
    }

    @Test fun unauthorizedKeepsEverythingAndReportsBlocked() {
        val outbox = MemoryOutbox().apply { add("/a", "{}"); add("/b", "{}") }
        val status = TelemetryUploader(outbox, Fake(mutableListOf(401)), config).flush()
        assertEquals(2, status.pending); assertTrue(status.blocked)
    }

    @Test fun configParsingRejectsBadInputAndHidesTheToken() {
        assertNull(SyncConfig.parse("{}")); assertNull(SyncConfig.parse("""{"baseUrl":"ftp://x","token":"t"}"""))
        assertNull(SyncConfig.parse("""{"baseUrl":"http://x","token":" "}"""))
        val ok = SyncConfig.parse("""{"baseUrl":"http://127.0.0.1:8000/","token":"secret"}""")!!
        assertEquals("http://127.0.0.1:8000", ok.baseUrl)
        assertFalse(ok.toString().contains("secret"))
    }
}

class RecorderTest {
    private fun recorder(outbox: Outbox, now: () -> Long) = TelemetryRecorder(outbox, SourceTag.DEMO, "trip-t", now)

    @Test fun tripCreateComesFirstAndSamplesAreNeverDuplicated() {
        val outbox = MemoryOutbox(); var now = 10_000L
        val r = recorder(outbox) { now }
        r.onUpdate(samples(3), report(), false)
        now += 2000; r.onUpdate(samples(5), report(), false) // 앞의 3개를 포함한 전체 목록
        r.flushBuffers()
        val items = generateSequence { outbox.peek()?.also { outbox.remove(it.id) } }.toList()
        assertEquals("/v1/trips", items.first().path)
        val ids = items.filter { it.path.endsWith("/samples") }.flatMap { item ->
            val arr = JSONObject(item.body).getJSONArray("samples"); (0 until arr.length()).map { arr.getJSONObject(it).getString("sampleId") }
        }
        assertEquals((0 until 5).map { "s-%06d".format(it) }, ids)
    }

    @Test fun scoresAreThrottledButEventsAndFinalAlwaysCount() {
        val outbox = MemoryOutbox(); var now = 0L
        val r = recorder(outbox) { now }
        r.onUpdate(samples(1), report(), false)                 // 기록
        now = 300; r.onUpdate(samples(2), report(), false)      // 너무 촘촘해서 건너뜀
        now = 400
        val brake = DetectedEvent(2000, DetectedEvent.Kind.HARD_BRAKE)
        r.onUpdate(samples(3), report(events = listOf(brake)), false) // 새 사건: 항상 기록
        now = 500; r.onUpdate(samples(4), report(events = listOf(brake)), false) // 건너뜀, 같은 사건은 다시 싣지 않음
        now = 600; r.onUpdate(samples(5), report(events = listOf(brake)), true)  // 마지막: 항상 기록
        assertEquals(3, r.counts().second)
        r.flushBuffers()
        val scores = generateSequence { outbox.peek()?.also { outbox.remove(it.id) } }.first { it.path.endsWith("/scores") }
        val arr = JSONObject(scores.body).getJSONArray("scores")
        assertEquals(listOf(0, 1, 0), (0 until arr.length()).map { arr.getJSONObject(it).getJSONArray("newEvents").length() })
        assertTrue(arr.getJSONObject(2).getBoolean("final"))
    }

    @Test fun largeBuffersAreSplitIntoBatchesWithinTheServerLimit() {
        val outbox = MemoryOutbox(); var now = 0L
        val r = recorder(outbox) { now }
        r.onUpdate(samples(250), report(), false)
        r.flushBuffers()
        val sizes = generateSequence { outbox.peek()?.also { outbox.remove(it.id) } }.filter { it.path.endsWith("/samples") }
            .map { JSONObject(it.body).getJSONArray("samples").length() }.toList()
        assertEquals(listOf(100, 100, 50), sizes)
    }

    @Test fun nothingIsRecordedWithoutSamples() {
        val outbox = MemoryOutbox()
        val r = recorder(outbox) { 0 }
        r.onUpdate(emptyList(), report(), false); r.flushBuffers()
        assertEquals(0, outbox.size())
    }
}
