package ai.nunti.score.sync

import java.io.File
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * 한 번의 여정 동안 기록을 모으고 주기적으로 서버로 보낸다. 네트워크는 배경 스레드에서만 쓴다.
 * 대기함은 [outboxDir] 에 파일로 남으므로 전송에 실패하거나 앱이 꺼져도 다음 실행에서 이어서 보낸다.
 */
class TelemetrySync(
    outboxDir: File,
    config: SyncConfig,
    source: SourceTag,
    transport: HttpTransport = UrlConnectionTransport(),
    private val intervalSeconds: Long = 5,
) : AutoCloseable {
    private val outbox = FileOutbox(outboxDir)
    val recorder = TelemetryRecorder(outbox, source, "trip-" + UUID.randomUUID().toString().take(18))
    private val uploader = TelemetryUploader(outbox, transport, config)
    private val executor = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "nunti-telemetry").apply { isDaemon = true } }

    init { executor.scheduleWithFixedDelay(::tick, intervalSeconds, intervalSeconds, TimeUnit.SECONDS) }

    private fun tick() {
        try { recorder.flushBuffers(); uploader.flush() } catch (_: Exception) { /* 다음 주기에 다시 시도한다 */ }
    }

    fun status() = uploader.status()

    /** 남은 기록을 한 번 더 보내 보고 멈춘다. */
    override fun close() {
        executor.execute(::tick)
        executor.shutdown()
    }
}
