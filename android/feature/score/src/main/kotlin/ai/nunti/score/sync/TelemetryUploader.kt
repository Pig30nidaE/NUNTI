package ai.nunti.score.sync

import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

/** 서버 주소와 인증 토큰. 비밀값이라 소스·저장소에 넣지 않고 기기의 앱 전용 파일에서 읽는다. */
data class SyncConfig(val baseUrl: String, val token: String) {
    override fun toString() = "SyncConfig(baseUrl=$baseUrl, token=REDACTED)"

    companion object {
        fun parse(text: String): SyncConfig? = try {
            val json = JSONObject(text)
            val url = json.getString("baseUrl").trim().trimEnd('/')
            val token = json.getString("token").trim()
            if ((url.startsWith("http://") || url.startsWith("https://")) && token.isNotEmpty()) SyncConfig(url, token) else null
        } catch (_: Exception) { null }

        fun load(file: File): SyncConfig? = if (file.isFile) parse(file.readText()) else null
    }
}

fun interface HttpTransport {
    /** [method](POST·PUT)로 JSON 을 보내고 응답 코드를 돌려준다. 연결 실패는 [IOException]. */
    fun send(method: String, url: String, token: String, json: String): Int
}

class UrlConnectionTransport(private val timeoutMs: Int = 5_000) : HttpTransport {
    override fun send(method: String, url: String, token: String, json: String): Int {
        val connection = URL(url).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = timeoutMs
            connection.readTimeout = timeoutMs
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.outputStream.use { it.write(json.toByteArray(Charsets.UTF_8)) }
            val code = connection.responseCode
            (if (code in 200..299) connection.inputStream else connection.errorStream)?.use { it.readBytes() }
            return code
        } finally {
            connection.disconnect()
        }
    }
}

/** 대기함의 요청을 순서대로 보낸다. 실패하면 멈추고 다음 시도까지 점점 오래 기다린다. */
class TelemetryUploader(
    private val outbox: Outbox,
    private val transport: HttpTransport,
    private val config: SyncConfig,
    private val clock: () -> Long = System::currentTimeMillis,
    private val baseBackoffMs: Long = 2_000,
    private val maxBackoffMs: Long = 60_000,
) {
    enum class Outcome { SENT, DROP, BLOCKED, RETRY }

    data class Status(val pending: Int, val sent: Int, val dropped: Int, val blocked: Boolean, val lastError: String?)

    private var sent = 0
    private var dropped = 0
    private var blocked = false
    private var lastError: String? = null
    private var failures = 0
    private var nextAttemptAt = 0L

    @Synchronized fun status() = Status(outbox.size(), sent, dropped, blocked, lastError)

    /** 보낼 수 있는 만큼 보낸다. 백오프 중이면 아무것도 하지 않는다. */
    @Synchronized fun flush(): Status {
        if (clock() < nextAttemptAt) return status()
        while (true) {
            val item = outbox.peek() ?: break
            val outcome = try {
                classify(transport.send(item.method, config.baseUrl + item.path, config.token, item.body))
            } catch (e: IOException) {
                lastError = "network: ${e.javaClass.simpleName}"
                Outcome.RETRY
            }
            when (outcome) {
                // 성공해도 거부 기록(rejected)은 지우지 않는다: 뒤 요청이 성공하면 앞에서 버린 배치가 화면에서 사라지기 때문.
                Outcome.SENT -> { outbox.remove(item.id); sent++; failures = 0; blocked = false; if (lastError?.startsWith("rejected") != true) lastError = null }
                Outcome.DROP -> { outbox.remove(item.id); dropped++; lastError = "rejected: ${item.path.substringAfterLast('/')} ×$dropped" }
                Outcome.BLOCKED -> { blocked = true; backOff(); break }
                Outcome.RETRY -> { backOff(); break }
            }
        }
        return status()
    }

    private fun backOff() {
        failures++
        nextAttemptAt = clock() + minOf(maxBackoffMs, baseBackoffMs shl minOf(failures - 1, 10))
    }

    companion object {
        /**
         * 2xx 는 성공(중복 응답도 2xx). 401·403 은 토큰·동의 설정 문제라 대기함을 지우지 않고 멈춘다.
         * 408·429·5xx 는 재시도. 그 밖의 4xx(검증 실패·충돌)는 다시 보내도 같은 결과이므로 버린다.
         */
        fun classify(code: Int): Outcome = when (code) {
            in 200..299 -> Outcome.SENT
            401, 403 -> Outcome.BLOCKED
            408, 429, in 500..599 -> Outcome.RETRY
            else -> Outcome.DROP
        }
    }
}
