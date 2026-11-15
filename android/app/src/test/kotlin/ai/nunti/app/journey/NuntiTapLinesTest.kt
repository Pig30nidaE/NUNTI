package ai.nunti.app.journey

import ai.nunti.app.journey.NuntiSpriteDirector.Stage
import ai.nunti.app.journey.NuntiTapLines.Moment
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class NuntiTapLinesTest {
    @Test fun drivingNeverTalks() {
        assertNull(NuntiTapLines.momentFor(Stage.DRIVING, 12.0, 90.0))
    }

    @Test fun eachScreenPicksItsOwnLines() {
        assertEquals(Moment.READY, NuntiTapLines.momentFor(Stage.PARKED, 0.0, null))
        assertEquals(Moment.REST, NuntiTapLines.momentFor(Stage.PARKED, 3.2, 81.0))
        assertEquals(Moment.GOOD, NuntiTapLines.momentFor(Stage.REPORT_GOOD, 8.0, 92.0))
        assertEquals(Moment.LOW, NuntiTapLines.momentFor(Stage.REPORT_LOW, 8.0, 61.0))
        assertEquals(Moment.NO_SCORE, NuntiTapLines.momentFor(Stage.REPORT_LOW, 8.0, null))
        assertEquals(Moment.IDLE, NuntiTapLines.momentFor(Stage.EMPTY, 0.0, null))
        assertEquals("오늘은 어디로 가볼까요?", NuntiTapLines.pick(Moment.READY, 0).text)
        // 점수가 없으면 운전 습관 이야기는 하지 않는다.
        for (i in 0..10) assertNotEquals("tap_low_3", NuntiTapLines.pick(Moment.NO_SCORE, i).id)
    }

    @Test fun tapsCycleThroughTheLines() {
        val ids = (0 until 8).map { NuntiTapLines.pick(Moment.READY, it).id }
        assertEquals(listOf("tap_ready_1", "tap_ready_2", "tap_ready_3", "tap_ready_4"), ids.take(4))
        assertEquals(ids.take(4), ids.drop(4))
    }

    // ---- 에셋 ----
    private val root = generateSequence(File("").absoluteFile) { it.parentFile }
        .map { File(it, "prototypes/avatar_generator") }.first { it.isDirectory }

    @Test fun everyLineHasItsRecordedVoiceFile() {
        val manifest = File(root, "nunti-voice/manifest.json").readText()
        assertEquals(NuntiTapLines.all.size, Regex("\"id\"\\s*:").findAll(manifest).count())
        for (line in NuntiTapLines.all) {
            val row = Regex("\\{[^{}]*\"id\"\\s*:\\s*\"${line.id}\"[^{}]*\\}").find(manifest)!!.value
            fun field(name: String) = Regex("\"$name\"\\s*:\\s*\"?([^\",]+)").find(row)!!.groupValues[1]
            assertEquals(line.id, line.text, Regex("\"text\"\\s*:\\s*\"([^\"]+)\"").find(row)!!.groupValues[1])
            assertEquals(line.id, field("seconds").toDouble(), line.seconds.toDouble(), .01)
            assertEquals(line.asset, field("path"))
            val sha = MessageDigest.getInstance("SHA-256").digest(File(root, line.asset).readBytes()).joinToString("") { "%02x".format(it) }
            assertEquals(line.id, field("sha256"), sha)
        }
    }
}
