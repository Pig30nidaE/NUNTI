package ai.nunti.score.live

/** Each SDK registration captures its epoch. A released service cannot write into a later session. */
internal class SignalSessionGate {
    private var epoch = 0L
    private var running = false

    @Synchronized
    fun begin(reset: () -> Unit): Long? {
        if (running) return null
        epoch++
        reset()
        running = true
        return epoch
    }

    @Synchronized
    fun end(reset: () -> Unit): Boolean {
        if (!running) return false
        running = false
        epoch++
        reset()
        return true
    }

    @Synchronized
    fun accept(expectedEpoch: Long, update: () -> Unit): Boolean {
        if (!running || epoch != expectedEpoch) return false
        update()
        return true
    }

    @Synchronized
    fun current(): Long? = epoch.takeIf { running }

    @Synchronized
    fun <T> read(read: () -> T): T = read()
}

/** One open door is known unsafe; all closed requires a reading for every configured door. */
internal fun aggregateDoorState(readings: Map<String, Boolean>, expectedDoors: Set<String>): Boolean? = when {
    readings.filterKeys { it in expectedDoors }.values.any { it } -> true
    expectedDoors.isNotEmpty() && expectedDoors.all { readings[it] == false } -> false
    else -> null
}
