package ai.nunti.score

fun interface SpeechSink { fun speak(text: String, utteranceId: String, emotion: Emotion) }

/**
 * 새로 감지된 사건과 감정 변화를 짧은 대사로 바꿔 [SpeechSink]에 넘긴다 (순수 Kotlin).
 * - 이미 말한 사건은 다시 말하지 않는다 (tMs + 종류로 식별).
 * - 같은 시간에 사건이 여럿이면 가장 최근 하나만 말한다.
 * - tts 모듈 정책의 초안 값(최소 간격 15초, 80자)을 따른다. 쿨다운 중의 사건은 버린다 (나중에 몰아 말하지 않음).
 * - 첫 호출은 기준선이다: 이미 있던 사건은 말하지 않는다.
 */
class EventSpeaker(
    private val sink: SpeechSink,
    private val cooldownMs: Long = 15_000,
    private val maxChars: Int = 80,
) {
    private val seen = HashSet<Pair<Long, DetectedEvent.Kind>>()
    private var primed = false
    private var lastEmotion = Emotion.NEUTRAL
    private var lastSpokenAt = Long.MIN_VALUE
    private var counter = 0
    private val spokenByKind = HashMap<DetectedEvent.Kind, Int>() // 종류별로 말한 횟수 = 다음 대사 변형 번호

    /** [nowMs] 는 단조 시계. 반환값은 말한 대사 (없으면 null). */
    fun onUpdate(report: ScoreReport, emotion: Emotion, nowMs: Long): String? {
        val fresh = report.events.filter { seen.add(it.tMs to it.kind) }
        val prevEmotion = lastEmotion
        lastEmotion = emotion
        if (!primed) { primed = true; return null }
        val kind = fresh.lastOrNull()?.kind
        val line = kind?.let { eventLine(it, spokenByKind[it] ?: 0) } ?: emotionLine(prevEmotion, emotion) ?: return null
        if (lastSpokenAt != Long.MIN_VALUE && nowMs - lastSpokenAt < cooldownMs) return null
        if (line.codePointCount(0, line.length) > maxChars) return null
        lastSpokenAt = nowMs
        if (kind != null) spokenByKind[kind] = (spokenByKind[kind] ?: 0) + 1 // 쿨다운·길이로 버려진 대사는 번호를 쓰지 않는다
        sink.speak(line, "nunti-event-${counter++}", emotion)
        return line
    }

    fun reset() { seen.clear(); primed = false; lastEmotion = Emotion.NEUTRAL; lastSpokenAt = Long.MIN_VALUE; spokenByKind.clear() }

    companion object {
        /** 사건 종류별 대사. 같은 종류가 이어지면 순서대로 번갈아 쓴다. 각 대사는 80자 이하여야 한다. */
        val lines: Map<DetectedEvent.Kind, List<String>> = mapOf(
            DetectedEvent.Kind.HARD_BRAKE to listOf(
                "앗, 급제동이었어요. 앞차와 거리를 조금 더 둬요.",
                "방금 꽤 세게 멈췄어요. 차간 거리를 넉넉히 둬요.",
            ),
            DetectedEvent.Kind.HARD_ACCEL to listOf(
                "출발이 조금 급했어요. 천천히 밟아 봐요.",
                "가속이 빨랐어요. 페달을 부드럽게 눌러 봐요.",
            ),
            DetectedEvent.Kind.HARD_DECEL to listOf(
                "속도가 갑자기 줄었어요. 미리 여유 있게 줄여요.",
                "감속이 갑작스러웠어요. 조금 일찍 발을 떼 봐요.",
            ),
        )

        /** [variant] 를 종류별 대사 수로 나눈 나머지를 쓴다 (결정적 순환). */
        fun eventLine(kind: DetectedEvent.Kind, variant: Int = 0): String {
            val options = lines.getValue(kind)
            return options[Math.floorMod(variant, options.size)]
        }

        fun emotionLine(from: Emotion, to: Emotion): String? = when {
            from == to -> null
            to == Emotion.RELIEF -> Emotion.RELIEF.line
            to == Emotion.JOY -> Emotion.JOY.line
            else -> null // 걱정은 사건 대사가 이미 전한다. 중립 복귀는 말하지 않는다.
        }
    }
}
