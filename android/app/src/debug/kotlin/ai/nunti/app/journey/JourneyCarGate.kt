package ai.nunti.app.journey

import ai.nunti.avatar.CarUxPolicyBinding
import ai.nunti.tts.VehicleMotion
import android.car.Car
import android.car.VehicleGear
import android.car.VehiclePropertyIds
import android.car.drivingstate.CarUxRestrictions
import android.car.drivingstate.CarUxRestrictionsManager
import android.car.hardware.property.CarPropertyManager
import android.content.Context
import android.os.Handler
import android.os.Looper
import kotlin.math.abs

data class JourneyGate(val source: String, val motion: VehicleMotion, val parked: Boolean,
    val knownUX: Boolean, val requiresDO: Boolean, val activeRestrictions: Int)

/** Automotive-only adapter. A missing Car connection remains UNKNOWN and never becomes a lab. */
class JourneyCarGate(context: Context, private val changed: () -> Unit) : AutoCloseable {
    private var properties: CarPropertyManager? = null
    private var restrictions: CarUxRestrictions? = null
    private var binding: CarUxPolicyBinding? = null
    private val car = Car.createCar(context, Handler(Looper.getMainLooper()), Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT) { connected, ready ->
        binding?.close(); binding = null; properties = null; restrictions = null
        if (ready) runCatching {
            properties = connected.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager
            val manager = connected.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE) as CarUxRestrictionsManager
            binding = CarUxPolicyBinding(manager) { restrictions = it; changed() }.also { it.start() }
        }
        changed()
    }
    fun observe(): JourneyGate {
        val gear = runCatching { properties?.getIntProperty(VehiclePropertyIds.GEAR_SELECTION, 0) }.getOrNull()
        val speed = runCatching { properties?.getFloatProperty(VehiclePropertyIds.PERF_VEHICLE_SPEED, 0) }.getOrNull()
        val parked = gear == VehicleGear.GEAR_PARK && speed?.let { it.isFinite() && abs(it) < .01f } == true
        val motion = when {
            gear == null || speed == null || !speed.isFinite() -> VehicleMotion.UNKNOWN
            parked -> VehicleMotion.PARKED
            abs(speed) > .01f -> VehicleMotion.MOVING
            else -> VehicleMotion.STOPPED
        }
        return JourneyGate("ACTUAL_CAR_SERVICE", motion, parked, restrictions != null,
            restrictions?.isRequiresDistractionOptimization ?: true, restrictions?.activeRestrictions ?: 0)
    }
    fun refresh() { binding?.refresh() }
    override fun close() { binding?.close(); car?.disconnect() }
}
