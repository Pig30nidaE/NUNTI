package ai.nunti.score

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class RecordedVoiceTest {
    @Test fun everyClipFileExistsAndIsUsedOnce() {
        val dir = File("src/main/assets/${RecordedVoice.DIR}")
        assertEquals(VoiceClip.entries.size, VoiceClip.entries.map { it.text }.toSet().size) // 한 문장에 음원 하나
        VoiceClip.entries.forEach { assertTrue("missing ${it.file}", File(dir, it.file).isFile) }
        assertEquals(VoiceClip.entries.map { it.file }.toSet(), dir.list()!!.filter { it.endsWith(".ogg") }.toSet()) // 안 쓰는 음원이 없다
    }

    @Test fun closingIsSplitIntoRecordedParts() {
        val plan = ClosingPlan(Verdict.FAIR, Highlight.BRAKES, CheckIn.ASK_HURRY)
        val parts = RecordedVoice.split(ClosingMessage.compose(plan, 0))
        assertEquals(listOf(Verdict.FAIR.variants[0], Highlight.BRAKES.variants[0], CheckIn.ASK_HURRY.variants[0]), parts)
        assertEquals(listOf(VoiceClip.VERDICT_FAIR_1, VoiceClip.SCENE_BRAKES_1, VoiceClip.CHECKIN_ASK_HURRY_1), parts.map { RecordedVoice.clipFor(it) })
    }

    @Test fun everyDemoClosingPartIsRecorded() {
        // 시연은 부품마다 첫 문장만 쓴다: 그 문장은 모두 눈티 목소리여야 한다.
        (Verdict.entries.map { it.variants[0] } + Highlight.entries.map { it.variants[0] } + CheckIn.entries.map { it.variants[0] })
            .forEach { assertTrue(it, RecordedVoice.clipFor(it) != null) }
    }

    @Test fun greetingAndFirstPauseNoticesAreRecorded() {
        listOf(EventSpeaker.GREETING, Readiness.WAITING_FOR_MOVEMENT.notices[0], Readiness.WAITING_FOR_SIGNALS.notices[0],
            PauseFollowUp.SAVED_FOR_NOW.variants[0]).forEach { assertTrue(it, RecordedVoice.clipFor(it) != null) }
    }

    @Test fun everyComposedClosingAndPauseNoticeSplitsCleanly() {
        Verdict.entries.forEach { v -> (listOf(null) + Highlight.entries).forEach { h -> CheckIn.entries.forEach { c ->
            (0 until 8).forEach { i ->
                val text = ClosingMessage.compose(ClosingPlan(v, h, c), i)
                assertEquals(text, RecordedVoice.split(text).joinToString(" "))
                assertEquals(if (h == null) 2 else 3, RecordedVoice.split(text).size)
            }
        } } }
        Readiness.entries.forEach { r -> (0 until 2).forEach { i ->
            TripLifecycle.pauseNotice(r, i)?.let { assertEquals(2, RecordedVoice.split(it).size) }
        } }
        assertEquals(listOf("모르는 문장"), RecordedVoice.split("모르는 문장"))
    }

    @Test fun eventReactionsAreRecorded() {
        DetectedEvent.Kind.entries.forEach { k -> assertTrue(k.name, RecordedVoice.clipFor(EventSpeaker.eventLine(k, 0)) != null) }
    }
}
