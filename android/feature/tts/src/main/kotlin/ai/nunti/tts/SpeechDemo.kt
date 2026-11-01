package ai.nunti.tts

/** Four approved mock scenarios. This demonstration emits lifecycle events; Mock does not synthesize sound. */
fun main() {
    val clock = object : SpeechClock {
        override fun epochMs() = 1_800_000_000_000L
        override fun monotonicMs() = 0L
    }
    // Synchronous demo completes all utterances; timer-dependent behavior is covered by the test scheduler.
    val timer = SpeechScheduler { _, _ -> Cancellation {} }
    fun scenario(label: String, phase: TripPhase, emotion: Emotion, text: String, duplicate: Boolean = false) {
        println("\n$label | MOCK / NO AUDIO")
        val provider = MockTtsProvider()
        val queue = SpeechQueueManager(provider, MockAudioFocus(), clock, timer, sink = {
            println("${it.requestId} ${it.status} ${it.reason ?: ""} style=${it.appliedVoice?.logicalStyle ?: "-"}")
        })
        queue.beginTrip("demo-trip")
        queue.updateContext(PlaybackContext("demo-trip", phase, 0, true, true, false,
            if (phase == TripPhase.DRIVING) VehicleMotion.MOVING else VehicleMotion.PARKED,
            true, phase == TripPhase.DRIVING, 0, Permission.ALLOWED, Permission.ALLOWED,
            AudioActivity.QUIET, AudioActivity.QUIET, AudioActivity.QUIET))
        val source = when (phase) {
            TripPhase.PRE_TRIP -> ContentSource.PRE_DRIVE_GREETING
            TripPhase.POST_TRIP -> ContentSource.POST_DRIVE_REPORT
            else -> ContentSource.VERIFIED_EVENT_RESPONSE
        }
        val request = SpeechRequest("demo-1", "demo-trip", "nunti", text, emotion, "nunti-default-v1", phase,
            Priority.NORMAL, clock.epochMs(), clock.epochMs()+10_000, source, "emotion-1", "verified-demo-event")
        val approved = ApprovedSpeech(request, AvatarVoiceInput("nunti","nunti","nunti-default-v1"),
            EmotionSnapshot("emotion-1","demo-trip","nunti",emotion,clock.epochMs()),true)
        queue.submit(approved)
        println("Supplied Korean text: ${provider.spoken.single().request.text}")
        if (duplicate) queue.submit(approved)
        provider.complete(); queue.release()
    }
    scenario("A — 첫 만남",TripPhase.PRE_TRIP,Emotion.NEUTRAL,"오늘은 조금 긴 여행이네요. 함께 떠나볼까요?")
    scenario("B — 감정 변화",TripPhase.PRE_TRIP,Emotion.JOYFUL,"함께 떠나볼까요?")
    scenario("C — 허용된 주행 중 최소 음성 + 중복 차단",TripPhase.DRIVING,Emotion.RELIEVED,"휴, 이제 좀 안심돼요.",true)
    scenario("D — 전달받은 종료 코멘트",TripPhase.POST_TRIP,Emotion.RELIEVED,"중간에 조금 놀라기도 했지만, 다시 편안하게 달려서 마음이 놓였어요.")
}
