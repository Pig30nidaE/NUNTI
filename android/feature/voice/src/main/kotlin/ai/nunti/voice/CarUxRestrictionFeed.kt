package ai.nunti.voice

import android.car.drivingstate.CarUxRestrictions
import android.car.drivingstate.CarUxRestrictionsManager

/** Host supplies the connected manager and combines these bits with reviewed feature permission. */
class CarUxRestrictionFeed(private val manager: CarUxRestrictionsManager,
    private val onChanged: (CarUxRestrictions?) -> Unit) : AutoCloseable {
    private var started = false
    private val listener = CarUxRestrictionsManager.OnUxRestrictionsChangedListener {
        if (started) onChanged(it)
    }
    fun start() {
        if (started) return
        started = true
        try { manager.registerListener(listener); onChanged(manager.currentCarUxRestrictions) }
        catch (_: Exception) { close(); onChanged(null) }
    }
    /** Refresh for the host's state heartbeat; a cached callback must not masquerade as fresh telemetry. */
    fun refresh() {
        if (!started) { onChanged(null); return }
        try { onChanged(manager.currentCarUxRestrictions) } catch (_: Exception) { onChanged(null) }
    }
    override fun close() {
        if (!started) return
        started = false
        try { manager.unregisterListener() } catch (_: Exception) { } finally { onChanged(null) }
    }
}
