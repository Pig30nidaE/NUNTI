package ai.nunti.avatar

import android.car.drivingstate.CarUxRestrictions
import android.car.drivingstate.CarUxRestrictionsManager

/** Owns one manager listener: do not share the manager registration with another feed.
 * Read failures/disconnection are UNKNOWN. Host approval and parked status are separate inputs.
 */
class CarUxPolicyBinding(private val manager: CarUxRestrictionsManager, private val onRestrictions: (CarUxRestrictions?) -> Unit) : AutoCloseable {
    private var connected = false
    fun start() {
        if (connected) return
        try {
            manager.registerListener { value -> onRestrictions(value) }
            connected = true
            refresh()
        } catch (_: Exception) { onRestrictions(null) }
    }
    fun refresh() {
        if (!connected) { onRestrictions(null); return }
        try { onRestrictions(manager.currentCarUxRestrictions) } catch (_: Exception) { onRestrictions(null) }
    }
    override fun close() {
        try { if (connected) manager.unregisterListener() } catch (_: Exception) { /* invalid connection is already UNKNOWN */ }
        finally { connected = false; onRestrictions(null) }
    }
    companion object {
        fun policy(restrictions: CarUxRestrictions?, observedAtMillis: Long, screenPermitted: Boolean,
            approvedDistractionOptimizedHost: Boolean, approvedStaticDriving: Boolean, parkedConfirmed: Boolean,
            foreground: Boolean): PlatformDisplayPolicy = PlatformDisplayPolicy(observedAtMillis,
                restrictionsKnown = restrictions != null,
                platformAllowsAvatarScreen = screenPermitted,
                requiresDistractionOptimization = restrictions?.isRequiresDistractionOptimization ?: true,
                hostIsApprovedForDistractionOptimization = approvedDistractionOptimizedHost,
                permitsStaticAvatarWhileDriving = approvedStaticDriving,
                parkedConfirmed = parkedConfirmed, foreground = foreground)
    }
}
