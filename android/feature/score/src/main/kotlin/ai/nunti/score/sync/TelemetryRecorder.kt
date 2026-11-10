package ai.nunti.score.sync

import ai.nunti.score.DetectedEvent
import ai.nunti.score.ScoreReport
import ai.nunti.score.VehicleSample

/**
 * 점수 엔진이 샘플과 결과를 낼 때마다 호출한다. 한 여정(trip)의 기록을 모아 서버 요청으로 바꿔 [Outbox]에 넣는다.
 * - 샘플은 모두 기록한다. 순번이 곧 ID 다.
 * - 점수는 계산할 때마다 기록하되 [minScoreIntervalMs] 보다 촘촘하면 건너뛴다. 새 사건이 있거나 마지막이면 항상 기록한다.
 * - 첫 호출에서 여정 생성 요청을 가장 먼저 넣는다 (동의가 켜진 상태에서만 이 객체를 만들어야 한다).
 * 메인 스레드에서 [onUpdate] 를, 배경 스레드에서 [flushBuffers] 를 부를 수 있도록 동기화돼 있다.
 */
class TelemetryRecorder(
    private val outbox: Outbox,
    private val source: SourceTag,
    val tripId: String,
    private val clock: () -> Long = System::currentTimeMillis,
    private val minScoreIntervalMs: Long = 1_000,
    private val sampleBatchSize: Int = 100,
    private val scoreBatchSize: Int = 20,
) {
    private var startEpochMs = 0L
    private var firstTMs = 0L
    private var started = false
    private var recordedSamples = 0
    private var scoreCount = 0
    private var lastScoreAt: Long? = null // 아직 기록한 적 없음 (Long.MIN_VALUE 는 뺄셈이 넘쳐서 쓰지 않는다)
    private val seenEvents = HashSet<Pair<Long, DetectedEvent.Kind>>()
    private val pendingSamples = ArrayList<IndexedSample>()
    private val pendingScores = ArrayList<ScoreRecord>()

    /** 지금까지의 전체 [samples] 와 그에 대한 [report] 를 받는다. 이미 기록한 샘플은 다시 기록하지 않는다. */
    @Synchronized fun onUpdate(samples: List<VehicleSample>, report: ScoreReport, final: Boolean) {
        if (samples.isEmpty()) return
        val now = clock()
        if (!started) {
            started = true; startEpochMs = now; firstTMs = samples.first().tMs
            outbox.add("/v1/trips", TelemetryWire.tripCreate(tripId, startEpochMs))
        }
        if (samples.size < recordedSamples) return // 샘플이 줄어들면 다른 여정이다. 새 recorder 를 만들어야 한다.
        for (i in recordedSamples until samples.size) pendingSamples += IndexedSample(i, samples[i])
        recordedSamples = samples.size

        val fresh = report.events.filter { seenEvents.add(it.tMs to it.kind) }
        val last = lastScoreAt
        if (final || fresh.isNotEmpty() || last == null || now - last >= minScoreIntervalMs) {
            lastScoreAt = now
            pendingScores += ScoreRecord(
                TelemetryWire.scoreId(scoreCount++), now, (samples.last().tMs - firstTMs).coerceAtLeast(0),
                samples.size, report, final, fresh,
            )
        }
    }

    /** 모아 둔 샘플·점수를 요청으로 만들어 대기함에 넣는다. 보낼 것이 없으면 아무것도 하지 않는다. */
    @Synchronized fun flushBuffers() {
        if (!started) return
        pendingSamples.chunked(sampleBatchSize).forEach {
            outbox.add("/v1/trips/$tripId/samples", TelemetryWire.sampleBatch(tripId, source, startEpochMs, firstTMs, it))
        }
        pendingSamples.clear()
        pendingScores.chunked(scoreBatchSize).forEach {
            outbox.add("/v1/trips/$tripId/scores", TelemetryWire.scoreBatch(tripId, source, it))
        }
        pendingScores.clear()
    }

    @Synchronized fun counts() = Pair(recordedSamples, scoreCount)
}
