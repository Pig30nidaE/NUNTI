package ai.nunti.score.live

import ai.nunti.score.Emotion
import ai.nunti.tts.AvatarVoiceInput
import ai.nunti.tts.ContentSource
import ai.nunti.tts.Priority
import ai.nunti.tts.SpeechStatus
import ai.nunti.tts.TripPhase
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import ai.nunti.tts.Emotion as VoiceEmotion

class SpeechMappingTest {
    @Test fun emotionMapping() {
        assertEquals(VoiceEmotion.NEUTRAL, SpeechMapping.voiceEmotion(Emotion.NEUTRAL))
        assertEquals(VoiceEmotion.CONCERNED, SpeechMapping.voiceEmotion(Emotion.WORRY))
        assertEquals(VoiceEmotion.RELIEVED, SpeechMapping.voiceEmotion(Emotion.RELIEF))
        assertEquals(VoiceEmotion.JOYFUL, SpeechMapping.voiceEmotion(Emotion.JOY))
    }

    @Test fun requestConstruction() {
        val avatar = AvatarVoiceInput("av", "nunti-base", "prof")
        val a = SpeechMapping.approvedSpeech("안녕", "nunti-event-3", Emotion.WORRY, "trip", "av", "prof", avatar, 1_000)
        val r = a.request
        assertTrue(a.contentVerified)
        assertEquals("nunti-event-3", r.requestId)
        assertEquals("trip", r.tripId)
        assertEquals("안녕", r.text)
        assertEquals(VoiceEmotion.CONCERNED, r.emotion)
        assertEquals(TripPhase.DRIVING, r.tripPhase)
        assertEquals(Priority.NORMAL, r.priority)
        assertEquals(ContentSource.VERIFIED_EVENT_RESPONSE, r.contentSource)
        assertEquals(1_000, r.requestedAt)
        assertEquals(1_000 + SpeechMapping.TTL_MS, r.expiresAt)
        assertEquals("emo-nunti-event-3", r.emotionId)
        assertEquals("emo-nunti-event-3", a.snapshot?.emotionId)
        assertEquals(VoiceEmotion.CONCERNED, a.snapshot?.emotion)
    }

    @Test fun describeIncludesReason() {
        assertEquals("REJECTED:QUEUE_FULL", SpeechMapping.describe(SpeechStatus.REJECTED, "QUEUE_FULL"))
        assertEquals("QUEUED", SpeechMapping.describe(SpeechStatus.QUEUED, null))
    }

    @Test fun onlyRejectionsAndFailuresAreLogged() {
        assertTrue(SpeechMapping.shouldLog(SpeechStatus.REJECTED))
        assertTrue(SpeechMapping.shouldLog(SpeechStatus.FAILED))
        assertFalse(SpeechMapping.shouldLog(SpeechStatus.QUEUED))
        assertFalse(SpeechMapping.shouldLog(SpeechStatus.COMPLETED))
    }
}
