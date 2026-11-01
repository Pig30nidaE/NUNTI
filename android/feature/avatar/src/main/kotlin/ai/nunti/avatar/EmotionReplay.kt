package ai.nunti.avatar

import ai.nunti.emotion.*
import org.json.JSONArray
import org.json.JSONObject

/** Journal checkpoint for app-private storage. Replaying original receive times restores debounce,
 * pending dwell, hysteresis and dedup state as well as the displayed emotion. No Java object decoding.
 * Production storage should append atomically and follow the trip retention policy.
 */
data class EmotionJournalEntry(val receivedAt: Long, val event: DrivingEvent?)
data class EmotionJournal(val tripId: String, val avatarId: String, val startedAt: Long,
    val sessionEpochMillis: Long, val ruleDigest: String, val entries: List<EmotionJournalEntry>) {
    fun encode(): String = JSONObject().apply {
        put("format", "emotion-journal-1"); put("tripId", tripId); put("avatarId", avatarId); put("startedAt", startedAt)
        put("sessionEpochMillis", sessionEpochMillis); put("ruleDigest", ruleDigest)
        put("entries", JSONArray(entries.map { entry -> JSONObject().apply {
            put("receivedAt", entry.receivedAt)
            put("event", entry.event?.let { e -> JSONObject().apply {
                put("eventId", e.eventId); put("tripId", e.tripId); put("type", e.type.name); put("occurredAt", e.occurredAt)
                put("verified", e.verified); put("confidence", e.confidence ?: JSONObject.NULL)
                put("incidentId", e.incidentId ?: JSONObject.NULL); put("recoveryOfEventId", e.recoveryOfEventId ?: JSONObject.NULL)
            } } ?: JSONObject.NULL)
        } }))
    }.toString(2)
    fun restore(machine: EmotionMachine, expectedRuleDigest: String): EmotionState {
        require(ruleDigest == expectedRuleDigest) { "Emotion rules changed: explicit migration required" }
        return entries.fold(machine.start(tripId, avatarId, startedAt)) { state, item ->
            item.event?.let { machine.accept(state, it, item.receivedAt).state } ?: machine.tick(state, item.receivedAt)
        }
    }
    companion object {
        fun decode(text: String): EmotionJournal {
            require(text.length <= 10_000_000) { "Journal too large; enforce host retention/compaction" }
            val o = JSONObject(text); require(o.getString("format") == "emotion-journal-1")
            val array = o.getJSONArray("entries")
            require(array.length() <= 20000)
            val entries = (0 until array.length()).map { i ->
                val item = array.getJSONObject(i); val raw = item.optJSONObject("event")
                val event = raw?.let { e ->
                    fun optional(key: String) = if (e.isNull(key)) null else e.getString(key)
                    DrivingEvent(e.getString("eventId"), e.getString("tripId"), EventType.valueOf(e.getString("type")),
                        e.getLong("occurredAt"), e.getBoolean("verified"), if (e.isNull("confidence")) null else e.getDouble("confidence"),
                        optional("incidentId"), optional("recoveryOfEventId"))
                }
                EmotionJournalEntry(item.getLong("receivedAt"), event)
            }
            return EmotionJournal(o.getString("tripId"), o.getString("avatarId"), o.getLong("startedAt"),
                o.getLong("sessionEpochMillis"), o.getString("ruleDigest"), entries)
        }
    }
}
