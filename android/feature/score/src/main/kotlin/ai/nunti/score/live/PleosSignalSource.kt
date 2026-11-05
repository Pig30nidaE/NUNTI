package ai.nunti.score.live

import android.car.Car
import android.car.VehiclePropertyIds
import android.car.hardware.CarPropertyValue
import android.car.hardware.property.CarPropertyManager
import android.content.Context
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
import android.util.Log
import ai.nunti.score.Gear
import ai.nunti.score.SeatState
import ai.nunti.score.TurnSignal
import ai.nunti.score.VehicleSample

/**
 * 실제 차량 신호 수신. 마지막으로 받은 값을 보관하고 snapshot()에서 한 시점의 VehicleSample로 만든다.
 * 한 번도 수신하지 못한 신호는 null(평가 불가)로 남는다.
 * 속도는 Pleos Vehicle SDK 2.3.2에 없어 AAOS CarPropertyManager(PERF_VEHICLE_SPEED)로 받는다.
 */
class PleosSignalSource(private val context: Context) {
    private val tag = "NuntiSignal"

    @Volatile private var speedKmh: Float? = null
    @Volatile private var brake: Boolean? = null
    @Volatile private var gear: Gear? = null
    @Volatile private var turn: TurnSignal? = null
    @Volatile private var lowBeam: Boolean? = null
    private val belts = java.util.concurrent.ConcurrentHashMap<SeatValue, Boolean>()
    private val occupied = java.util.concurrent.ConcurrentHashMap<SeatValue, Boolean>()
    private val doorOpen = java.util.concurrent.ConcurrentHashMap<DoorValue, Boolean>()

    private var vehicle: Vehicle? = null
    private var car: Car? = null
    private var carProps: CarPropertyManager? = null
    private var vehicleRegistered = false
    private var speedRegistered = false
    private var startedAtMs = 0L
    private val rawSpeed = RawSpeedProbe(context) { speedKmh = it }
    private val navi = NaviSignalSource(context) { System.currentTimeMillis() - startedAtMs }

    private val speedCallback = object : CarPropertyManager.CarPropertyEventCallback {
        override fun onChangeEvent(value: CarPropertyValue<*>) {
            (value.value as? Float)?.let { speedKmh = it * 3.6f } // m/s -> km/h
        }
        override fun onErrorEvent(propId: Int, zone: Int) = Unit
    }

    private val doorAreas = listOf(DoorValue.ROW_1_LEFT, DoorValue.ROW_1_RIGHT, DoorValue.ROW_2_LEFT, DoorValue.ROW_2_RIGHT)
    private val seatAreas = listOf(SeatValue.ROW_1_LEFT, SeatValue.ROW_1_RIGHT)

    fun start() {
        startedAtMs = System.currentTimeMillis()
        runCatching {
            vehicle = Vehicle(context).also { it.initialize() }
        }.onFailure { Log.w(tag, "Vehicle init failed", it) }
        rawSpeed.start()
        navi.start()
        retryRegistrations()
    }

    /** 서비스 연결이 늦을 수 있어 snapshot 때마다 미등록 항목을 다시 시도한다. */
    private fun retryRegistrations() {
        if (!vehicleRegistered) vehicleRegistered = runCatching { registerVehicle() }
            .onFailure { Log.w(tag, "Vehicle register failed: ${it.message}") }.isSuccess
        if (!speedRegistered) speedRegistered = runCatching { registerSpeed() }
            .onFailure { Log.w(tag, "Speed register failed: ${it.message}") }.isSuccess
    }

    private fun registerSpeed() {
        val c = car ?: Car.createCar(context).also { car = it }
        val mgr = carProps ?: (c.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager).also { carProps = it }
        // 에뮬레이터에 따라 PERF_VEHICLE_SPEED 가 목록에 없을 수 있어 클러스터용 DISPLAY 속도를 대체로 쓴다.
        val ok = listOf(VehiclePropertyIds.PERF_VEHICLE_SPEED, VehiclePropertyIds.PERF_VEHICLE_SPEED_DISPLAY).any {
            mgr.registerCallback(speedCallback, it, CarPropertyManager.SENSOR_RATE_NORMAL)
        }
        check(ok) { "no speed property" }
    }

    private fun registerVehicle() {
        val v = vehicle ?: error("no vehicle")
        val noop = { _: Exception -> }

        v.getBrake().apply {
            getCurrentBrakePedalStatus({ brake = it }, noop)
            registerBrakePedalStatus(object : BrakePedalStatusListener {
                override fun onBrakePedalStatusUpdated(p0: Boolean?) { brake = p0 }
                override fun onFailed(p0: Exception) = Unit
            })
        }
        v.getGear().apply {
            getCurrentGearSelectionState({ gear = it?.toGear() }, noop)
            registerGearSelection(object : GearSelectionListener {
                override fun onSelected(p0: VehicleGear?) { gear = p0?.toGear() }
                override fun onFailed(p0: Exception) = Unit
            })
        }
        v.getTurnSignal().apply {
            getCurrentTurnSignalState({ turn = it?.toTurn() }, noop)
            registerTurnSignalState(object : TurnSignalStateListener {
                override fun onTurnSignalStateUpdated(p0: TurnSignalValue?) { turn = p0?.toTurn() }
                override fun onFailed(p0: Exception) = Unit
            })
        }
        v.getLight().apply {
            getCurrentLowBeamLightState({ lowBeam = it?.let { v -> v == LightState.ON } }, noop)
            registerLowBeamLightState(object : LightStateListener {
                override fun onLightStateUpdated(p0: LightState?) { lowBeam = p0?.let { it == LightState.ON } }
                override fun onFailed(p0: Exception) = Unit
            })
        }
        v.getSeat().apply {
            for (s in seatAreas) {
                val area = SeatArea(s)
                getCurrentSeatBeltBuckledState(area, { it?.let { v -> belts[s] = v } }, noop)
                registerSeatBeltBuckledState(area, object : SeatBeltBuckledStateListener {
                    override fun onSeatBeltBuckledStateUpdated(p0: Boolean?) { p0?.let { belts[s] = it } }
                    override fun onFailed(p0: Exception) = Unit
                })
                getCurrentSeatOccupancy(area, { it?.let { v -> occupied[s] = v } }, noop)
                registerSeatOccupancy(area, object : SeatOccupancyListener {
                    override fun onSeatOccupancyUpdated(p0: Boolean?) { p0?.let { occupied[s] = it } }
                    override fun onFailed(p0: Exception) = Unit
                })
            }
        }
        v.getDoor().apply {
            for (d in doorAreas) {
                val area = DoorArea(d)
                getCurrentDoorPosition(area, { it?.let { v -> doorOpen[d] = v > 0 } }, noop) // 0 = 닫힘 (에뮬레이터로 확인 필요)
                registerDoorPosition(area, object : DoorPositionListener {
                    override fun onPositionUpdated(p0: Int?) { p0?.let { doorOpen[d] = it > 0 } }
                    override fun onFailed(p0: Exception) = Unit
                })
            }
        }
    }

    fun snapshot(): VehicleSample {
        retryRegistrations()
        fun seat(s: SeatValue) =
            if (occupied[s] == null && belts[s] == null) null else SeatState(occupied[s], belts[s])
        val doors = doorOpen.values
        return VehicleSample(
            tMs = System.currentTimeMillis() - startedAtMs,
            speedKmh = speedKmh,
            brakePressed = brake,
            gear = gear,
            turnSignal = turn,
            driverSeat = seat(SeatValue.ROW_1_LEFT),
            passengerSeat = seat(SeatValue.ROW_1_RIGHT),
            doorOpen = if (doors.isEmpty()) null else doors.any { it },
            headlightOn = lowBeam,
            speedLimitKmh = navi.speedLimitKmh,
            // 어두움 감지는 보류 상태이므로 null → 야간 전조등은 평가 불가
        )
    }

    /** 화면 확인용: 항목별 수신 여부. */
    fun received(): List<Pair<String, String>> = listOf(
        "속도" to (speedKmh?.let { "%.1f km/h".format(it) } ?: "미수신"),
        "속도(직접구독)" to (rawSpeed.lastRaw ?: rawSpeed.status),
        "기어" to (gear?.name ?: "미수신"),
        "브레이크" to (brake?.let { if (it) "밟음" else "뗌" } ?: "미수신"),
        "지시등" to (turn?.name ?: "미수신"),
        "하향등" to (lowBeam?.let { if (it) "ON" else "OFF" } ?: "미수신"),
        "벨트 운전석/동승석" to "${belts[SeatValue.ROW_1_LEFT] ?: "-"} / ${belts[SeatValue.ROW_1_RIGHT] ?: "-"}",
        "내비" to navi.status,
        "다음 회전" to navi.nextTurn,
        "제한속도" to (navi.speedLimitKmh?.let { "$it km/h" } ?: "미수신"),
        "탑승 운전석/동승석" to "${occupied[SeatValue.ROW_1_LEFT] ?: "-"} / ${occupied[SeatValue.ROW_1_RIGHT] ?: "-"}",
        "문 열림" to (if (doorOpen.isEmpty()) "미수신" else doorOpen.values.any { it }.toString()),
    )

    fun events() = navi.events.toList()

    fun stop() {
        navi.stop()
        rawSpeed.stop()
        runCatching { carProps?.unregisterCallback(speedCallback) }
        runCatching { car?.disconnect() }
        runCatching { vehicle?.release() }
        vehicle = null; car = null; carProps = null
        vehicleRegistered = false; speedRegistered = false
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
