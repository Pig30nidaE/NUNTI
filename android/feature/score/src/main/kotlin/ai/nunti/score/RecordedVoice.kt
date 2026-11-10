package ai.nunti.score

import ai.nunti.score.DetectedEvent.Kind

/**
 * 눈티 목소리로 미리 녹음한 대사 하나. 음원은 assets/[RecordedVoice.DIR]/[file] 이다.
 * 음원은 prototypes/fish_voice/build_clips.py 가 mp3/ 에서 만든다. 새로 녹음하면 스크립트 KEYS 와 여기에 한 항목씩 더한다.
 * 문장은 앱 상수에서 직접 가져오므로 문구를 고치면 같이 따라간다 (그 음원은 다시 녹음해야 한다).
 */
enum class VoiceClip(val text: String) {
    BRAKE_1(EventSpeaker.eventLine(Kind.HARD_BRAKE, 0)),
    BRAKE_2(EventSpeaker.eventLine(Kind.HARD_BRAKE, 1)),
    BRAKE_3(EventSpeaker.eventLine(Kind.HARD_BRAKE, 2)),
    ACCEL_1(EventSpeaker.eventLine(Kind.HARD_ACCEL, 0)),
    ACCEL_2(EventSpeaker.eventLine(Kind.HARD_ACCEL, 1)),
    CURVE_1(EventSpeaker.eventLine(Kind.CURVE_TOO_FAST, 0)),
    CURVE_2(EventSpeaker.eventLine(Kind.CURVE_TOO_FAST, 1)),
    RELIEF(Emotion.RELIEF.line),
    VERDICT_UNKNOWN_1(Verdict.UNKNOWN.variants[0]),
    VERDICT_GREAT_1(Verdict.GREAT.variants[0]),
    VERDICT_GOOD_1(Verdict.GOOD.variants[0]),
    VERDICT_FAIR_1(Verdict.FAIR.variants[0]),
    VERDICT_LOW_1(Verdict.LOW.variants[0]),
    SCENE_RECOVERED_1(Highlight.RECOVERED.variants[0]),
    SCENE_BRAKES_1(Highlight.BRAKES.variants[0]),
    ;

    /** BRAKE_1 → brake-1.ogg (build_clips.py 의 ID 와 같다). */
    val file: String get() = name.lowercase().replace('_', '-') + ".ogg"
}

/** 녹음 대사 찾기와, 이어 붙인 문장을 부품으로 나누기 (순수 Kotlin). */
object RecordedVoice {
    const val DIR = "score-voice"

    private val byText: Map<String, VoiceClip> = VoiceClip.entries.associateBy { it.text }

    /** 이어 붙여 말하는 문장(마무리 멘트·일시저장 안내)의 부품. 긴 것부터 맞춰 본다. */
    private val parts: List<String> by lazy {
        (Verdict.entries.flatMap { it.variants.toList() } + Highlight.entries.flatMap { it.variants.toList() } +
            CheckIn.entries.flatMap { it.variants.toList() } + Readiness.entries.flatMap { it.notices.toList() } +
            PauseFollowUp.entries.flatMap { it.variants.toList() }).distinct().sortedByDescending { it.length }
    }

    /**
     * 말할 문장을 부품 단위로 나눈다. 아는 부품으로 끝까지 나눠지지 않으면 문장 전체를 한 덩어리로 돌려준다.
     * 각 덩어리는 녹음이 있으면 음원으로, 없으면 Pleos TTS 로 말한다.
     */
    fun split(text: String): List<String> {
        val out = mutableListOf<String>()
        var rest = text.trim()
        while (rest.isNotEmpty()) {
            val part = parts.firstOrNull { rest.startsWith(it) } ?: return listOf(text)
            out += part
            rest = rest.removePrefix(part).trimStart()
        }
        return out
    }

    fun clipFor(text: String): VoiceClip? = byText[text]
}
