package ai.nunti.score.sync

import java.io.File

/** 서버로 보낼 요청 하나 (POST). 같은 요청을 다시 보내도 서버가 중복으로 처리하므로 재전송은 안전하다. */
data class OutboxItem(val id: String, val path: String, val body: String)

/** 보낼 요청을 순서대로 쌓아 두는 대기함. 순서가 중요하다: 여정 생성이 항상 샘플·점수보다 앞선다. */
interface Outbox {
    fun add(path: String, body: String)
    fun peek(): OutboxItem?
    fun remove(id: String)
    fun size(): Int
}

class MemoryOutbox : Outbox {
    private val items = ArrayDeque<OutboxItem>()
    private var counter = 0L
    @Synchronized override fun add(path: String, body: String) { items.addLast(OutboxItem("${counter++}", path, body)) }
    @Synchronized override fun peek() = items.firstOrNull()
    @Synchronized override fun remove(id: String) { items.removeAll { it.id == id } }
    @Synchronized override fun size() = items.size
}

/** 앱을 다시 켜도 남아 있도록 요청마다 파일 하나로 저장한다. 파일명 순서가 곧 전송 순서다. */
class FileOutbox(private val dir: File) : Outbox {
    private var counter: Long

    init {
        dir.mkdirs()
        counter = (files().maxOfOrNull { it.nameWithoutExtension.toLongOrNull() ?: -1L } ?: -1L) + 1
    }

    private fun files(): List<File> =
        dir.listFiles { f -> f.isFile && f.extension == "json" && f.nameWithoutExtension.toLongOrNull() != null }
            ?.sortedBy { it.nameWithoutExtension.toLong() } ?: emptyList()

    @Synchronized override fun add(path: String, body: String) {
        val name = "%019d".format(counter++)
        val temp = File(dir, "$name.tmp")
        temp.writeText(org.json.JSONObject().put("path", path).put("body", body).toString())
        check(temp.renameTo(File(dir, "$name.json"))) { "outbox write failed" }
    }

    @Synchronized override fun peek(): OutboxItem? {
        val file = files().firstOrNull() ?: return null
        return try {
            val json = org.json.JSONObject(file.readText())
            OutboxItem(file.nameWithoutExtension, json.getString("path"), json.getString("body"))
        } catch (_: Exception) {
            file.delete() // 읽을 수 없는 파일이 뒤의 요청을 막지 않게 한다
            peek()
        }
    }

    @Synchronized override fun remove(id: String) { File(dir, "$id.json").delete() }
    @Synchronized override fun size() = files().size
}
