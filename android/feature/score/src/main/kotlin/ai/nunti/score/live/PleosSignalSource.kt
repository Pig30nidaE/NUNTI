package ai.nunti.score.live

import android.car.Car
import android.car.VehiclePropertyIds
import android.car.hardware.CarPropertyValue
import android.car.hardware.property.CarPropertyManager
import android.content.Context
import android.os.SystemClock
import android.util.Log
import ai.pleos.playground.vehicle.Vehicle
import ai.pleos.playground.vehicle.api.model.area.DoorArea
import ai.pleos.playground.vehicle.api.model.area.SeatArea
import ai.pleos.playground.vehicle.constant.area.DoorValue
import ai.pleos.playground.vehicle.constant.area.SeatValue
import ai.pleos.playground.vehicle.constant.area.TurnSignalValue
import ai.pleos.playground.vehicle.constant.control.LightState
import ai.pleos.playground.vehicle.constant.control.VehicleGear
import ai.pleos.playground.vehicle.listener.BrakePedalStatusListener
import ai.pleos.playground.vehicle.listener.DoorPositionListener
import ai.pleos.playground.vehicle.listener.GearSelectionListener
import ai.pleos.playground.vehicle.listener.LightStateListener
import ai.pleos.playground.vehicle.listener.SeatBeltBuckledStateListener
import ai.pleos.playground.vehicle.listener.SeatOccupancyListener
import ai.pleos.playground.vehicle.listener.TurnSignalStateListener
import ai.nunti.score.Gear
import ai.nunti.score.SeatState
import ai.nunti.score.TurnSignal
import ai.nunti.score.VehicleSample

/**
 * One live subscription lifetime. Unknown/error/disconnected readings remain null.
 * Speed uses AAOS when available, plus the explicitly experimental VehicleService AIDL probe.
 * Change-only signals do not expire merely because a car stays at a constant speed or gear.
 */
class PleosSignalSource(private val context: Context) {
    private val gate = SignalSessionGate()
    private var carSpeed: Float? = null
    private var rawSpeedValue: Float? = null
    private var brake: Boolean? = null
    private var gear: Gear? = null
    private var turn: TurnSignal? = null
    private var lowBeam: Boolean? = null
    private val belts = mutableMapOf<SeatValue, Boolean>()
    private val occupied = mutableMapOf<SeatValue, Boolean>()
    private val doors = mutableMapOf<String, Boolean>()
    private val doorAreas = listOf(DoorValue.ROW_1_LEFT, DoorValue.ROW_1_RIGHT, DoorValue.ROW_2_LEFT, DoorValue.ROW_2_RIGHT)
    private val expectedDoors = doorAreas.map { it.name }.toSet()
    private val seatAreas = listOf(SeatValue.ROW_1_LEFT, SeatValue.ROW_1_RIGHT)

    private var vehicle: Vehicle? = null
    private var car: Car? = null
    private var carProps: CarPropertyManager? = null
    private var speedCallback: CarPropertyManager.CarPropertyEventCallback? = null
    private val registered = mutableSetOf<String>()
    private var speedRegistered = false
    private var startedAtMs = 0L
    private var lastSnapshotMs = 0L
    private var lastSnapshotSpeed: Float? = null
    private var lastNaviPollMs = Long.MIN_VALUE
    private var rawSpeed: RawSpeedProbe? = null
    private var navi: NaviSignalSource? = null

    private fun resetReadings() {
        carSpeed = null; rawSpeedValue = null; brake = null; gear = null; turn = null; lowBeam = null
        belts.clear(); occupied.clear(); doors.clear(); lastSnapshotMs = 0; lastSnapshotSpeed = null
    }

    @Synchronized
    fun start() {
        val epoch = gate.begin { resetReadings() } ?: return
        startedAtMs = SystemClock.elapsedRealtime()
        lastNaviPollMs = Long.MIN_VALUE
        registered.clear(); speedRegistered = false
        vehicle = runCatching { Vehicle(context).also { it.initialize() } }
            .onFailure { Log.w("NuntiSignal", "Vehicle init failed", it) }.getOrNull()
        rawSpeed = RawSpeedProbe(
            context,
            onSpeed = { value -> gate.accept(epoch) { rawSpeedValue = value.takeIf { it.isFinite() } } },
            onUnavailable = { gate.accept(epoch) { rawSpeedValue = null } },
        ).also { it.start() }
        navi = NaviSignalSource(context) { SystemClock.elapsedRealtime() - startedAtMs }.also { it.start() }
        retryRegistrations(epoch)
    }

    private fun retryRegistrations(epoch: Long) {
        if (vehicle == null) vehicle = runCatching { Vehicle(context).also { it.initialize() } }.getOrNull()
        vehicle?.let { registerVehicle(it, epoch) }
        if (!speedRegistered) speedRegistered = runCatching { registerSpeed(epoch) }
            .onFailure { Log.w("NuntiSignal", "Speed register failed: ${it.message}") }.getOrDefault(false)
    }

    private fun registerSpeed(epoch: Long): Boolean {
        val c = car ?: Car.createCar(context).also { car = it }
        val mgr = carProps ?: (c.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager).also { carProps = it }
        val cb = speedCallback ?: object : CarPropertyManager.CarPropertyEventCallback {
            override fun onChangeEvent(value: CarPropertyValue<*>) {
                gate.accept(epoch) {
                    carSpeed = if (value.status == CarPropertyValue.STATUS_AVAILABLE)
                        (value.value as? Float)?.takeIf { it.isFinite() }?.times(3.6f) else null
                }
            }
            override fun onErrorEvent(propId: Int, zone: Int) { gate.accept(epoch) { carSpeed = null } }
        }.also { speedCallback = it }
        return listOf(VehiclePropertyIds.PERF_VEHICLE_SPEED, VehiclePropertyIds.PERF_VEHICLE_SPEED_DISPLAY).any {
            runCatching { mgr.registerCallback(cb, it, CarPropertyManager.SENSOR_RATE_NORMAL) }.getOrDefault(false)
        }
    }

    /** A failure in one property does not register all the already-connected listeners a second time. */
    private fun registerOnce(key: String, block: () -> Unit) {
        if (key in registered) return
        runCatching { block(); registered += key }.onFailure { Log.w("NuntiSignal", "$key registration failed", it) }
    }

    private fun registerVehicle(v: Vehicle, epoch: Long) {
        registerOnce("brake") {
            v.getBrake().apply {
                runCatching { getCurrentBrakePedalStatus({ gate.accept(epoch) { brake = it } }, { gate.accept(epoch) { brake = null } }) }
                registerBrakePedalStatus(object : BrakePedalStatusListener {
                    override fun onBrakePedalStatusUpdated(p0: Boolean?) { gate.accept(epoch) { brake = p0 } }
                    override fun onFailed(p0: Exception) { gate.accept(epoch) { brake = null } }
                })
            }
        }
        registerOnce("gear") {
            v.getGear().apply {
                runCatching { getCurrentGearSelectionState({ gate.accept(epoch) { gear = it?.toGear() } }, { gate.accept(epoch) { gear = null } }) }
                registerGearSelection(object : GearSelectionListener {
                    override fun onSelected(p0: VehicleGear?) { gate.accept(epoch) { gear = p0?.toGear() } }
                    override fun onFailed(p0: Exception) { gate.accept(epoch) { gear = null } }
                })
            }
        }
        registerOnce("turn") {
            v.getTurnSignal().apply {
                runCatching { getCurrentTurnSignalState({ gate.accept(epoch) { turn = it?.toTurn() } }, { gate.accept(epoch) { turn = null } }) }
                registerTurnSignalState(object : TurnSignalStateListener {
                    override fun onTurnSignalStateUpdated(p0: TurnSignalValue?) { gate.accept(epoch) { turn = p0?.toTurn() } }
                    override fun onFailed(p0: Exception) { gate.accept(epoch) { turn = null } }
                })
            }
        }
        registerOnce("lowBeam") {
            v.getLight().apply {
                runCatching { getCurrentLowBeamLightState({ state -> gate.accept(epoch) { lowBeam = state?.let { it == LightState.ON } } }, { gate.accept(epoch) { lowBeam = null } }) }
                registerLowBeamLightState(object : LightStateListener {
                    override fun onLightStateUpdated(p0: LightState?) { gate.accept(epoch) { lowBeam = p0?.let { it == LightState.ON } } }
                    override fun onFailed(p0: Exception) { gate.accept(epoch) { lowBeam = null } }
                })
            }
        }
        for (seat in seatAreas) {
            registerOnce("belt:$seat") {
                v.getSeat().apply {
                    val area = SeatArea(seat)
                    fun update(value: Boolean?) { gate.accept(epoch) { if (value == null) belts.remove(seat) else belts[seat] = value } }
                    runCatching { getCurrentSeatBeltBuckledState(area, { update(it) }, { update(null) }) }
                    registerSeatBeltBuckledState(area, object : SeatBeltBuckledStateListener {
                        override fun onSeatBeltBuckledStateUpdated(p0: Boolean?) { update(p0) }
                        override fun onFailed(p0: Exception) { update(null) }
                    })
                }
            }
            registerOnce("occupancy:$seat") {
                v.getSeat().apply {
                    val area = SeatArea(seat)
                    fun update(value: Boolean?) { gate.accept(epoch) { if (value == null) occupied.remove(seat) else occupied[seat] = value } }
                    runCatching { getCurrentSeatOccupancy(area, { update(it) }, { update(null) }) }
                    registerSeatOccupancy(area, object : SeatOccupancyListener {
                        override fun onSeatOccupancyUpdated(p0: Boolean?) { update(p0) }
                        override fun onFailed(p0: Exception) { update(null) }
                    })
                }
            }
        }
        for (door in doorAreas) registerOnce("door:$door") {
            v.getDoor().apply {
                val area = DoorArea(door)
                fun update(value: Int?) { gate.accept(epoch) { if (value == null) doors.remove(door.name) else doors[door.name] = value > 0 } }
                runCatching { getCurrentDoorPosition(area, { update(it) }, { update(null) }) }
                registerDoorPosition(area, object : DoorPositionListener {
                    override fun onPositionUpdated(p0: Int?) { update(p0) }
                    override fun onFailed(p0: Exception) { update(null) }
                })
            }
        }
    }

    @Synchronized
    fun snapshot(): VehicleSample {
        val epoch = gate.current() ?: return VehicleSample(0)
        retryRegistrations(epoch)
        val now = SystemClock.elapsedRealtime() - startedAtMs
        if (lastNaviPollMs == Long.MIN_VALUE || now - lastNaviPollMs >= 1000) {
            lastNaviPollMs = now
            navi?.poll()
        }
        // Read transport health outside the readings lock: callbacks acquire transport then readings.
        val rawAlive = rawSpeed?.isConnected() == true
        val carAlive = car?.isConnected == true
        val speedLimit = navi?.speedLimitKmh
        return gate.read {
            fun seat(s: SeatValue) = if (occupied[s] == null && belts[s] == null) null else SeatState(occupied[s], belts[s])
            lastSnapshotMs = now
            lastSnapshotSpeed = (if (rawAlive) rawSpeedValue else null) ?: (if (carAlive) carSpeed else null)
            VehicleSample(
                tMs = now,
                speedKmh = lastSnapshotSpeed,
                brakePressed = brake, gear = gear, turnSignal = turn,
                driverSeat = seat(SeatValue.ROW_1_LEFT), passengerSeat = seat(SeatValue.ROW_1_RIGHT),
                doorOpen = aggregateDoorState(doors, expectedDoors), headlightOn = lowBeam, speedLimitKmh = speedLimit,
            )
        }
    }

    fun received(): List<Pair<String, String>> = gate.read {
        listOf(
            "속도" to (lastSnapshotSpeed?.let { "%.1f km/h".format(it) } ?: "미수신"),
            "속도(직접구독)" to (rawSpeed?.lastRaw ?: rawSpeed?.status ?: "중지"),
            "기어" to (gear?.name ?: "미수신"),
            "브레이크" to (brake?.let { if (it) "밟음" else "뗌" } ?: "미수신"),
            "지시등" to (turn?.name ?: "미수신"),
            "하향등" to (lowBeam?.let { if (it) "ON" else "OFF" } ?: "미수신"),
            "벨트 운전석/동승석" to "${belts[SeatValue.ROW_1_LEFT] ?: "-"} / ${belts[SeatValue.ROW_1_RIGHT] ?: "-"}",
            "내비" to (navi?.status ?: "중지"),
            "다음 회전" to (navi?.nextTurn ?: "-"),
            "제한속도" to (navi?.speedLimitKmh?.let { "$it km/h" } ?: "미수신"),
            "탑승 운전석/동승석" to "${occupied[SeatValue.ROW_1_LEFT] ?: "-"} / ${occupied[SeatValue.ROW_1_RIGHT] ?: "-"}",
            "문 열림" to (aggregateDoorState(doors, expectedDoors)?.toString() ?: "미수신"),
        )
    }

    fun events(): List<ai.nunti.score.DrivingEvent> {
        val observedUntil = gate.read { lastSnapshotMs }
        return navi?.events.orEmpty().filter { it.tMs <= observedUntil }
    }

    fun navigationLocation(): NavigationLocation? = navi?.location

    @Synchronized
    fun stop() {
        if (!gate.end { resetReadings() }) return
        navi?.stop(); rawSpeed?.stop()
        speedCallback?.let { runCatching { carProps?.unregisterCallback(it) } }
        runCatching { car?.disconnect() }
        runCatching { vehicle?.release() }
        navi = null; rawSpeed = null; vehicle = null; car = null; carProps = null; speedCallback = null
        registered.clear(); speedRegistered = false
    }

    private fun VehicleGear.toGear() = when (this) {
        VehicleGear.GEAR_PARK -> Gear.P
        VehicleGear.GEAR_REVERSE -> Gear.R
        VehicleGear.GEAR_NEUTRAL -> Gear.N
        VehicleGear.GEAR_UNKNOWN -> null
        else -> Gear.D
    }

    private fun TurnSignalValue.toTurn() = when (this) {
        TurnSignalValue.LEFT -> TurnSignal.LEFT
        TurnSignalValue.RIGHT -> TurnSignal.RIGHT
        else -> TurnSignal.NONE
    }
}
