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
import ai.pleos.playground.vehicle.listener.SteeringWheelAngleListener
import ai.pleos.playground.vehicle.listener.LightStateListener
import ai.pleos.playground.vehicle.listener.EvBatteryEfficiencyListener
import ai.pleos.playground.vehicle.listener.TelltaleInfoListener
import ai.pleos.playground.vehicle.api.model.telltale.Telltales
import ai.pleos.playground.vehicle.constant.telltale.TelltaleState
import ai.pleos.playground.vehicle.constant.telltale.TelltaleType
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
    @Volatile private var steeringDeg: Float? = null
    @Volatile private var overSpeed: Boolean? = null
    @Volatile private var night: Boolean? = null
    @Volatile private var evEfficiency: Float? = null
    // 앞차 거리(mm): Vehicle 서비스 직접 구독으로 받는다 (RawSpeedProbe). 표준 CarPropertyManager 경로는 앱에 막혀 있다.
    @Volatile private var leadDistanceMm: Int? = null
    @Volatile private var leadReceivedAtMs = 0L
    private val belts = java.util.concurrent.ConcurrentHashMap<SeatValue, Boolean>()
    private val occupied = java.util.concurrent.ConcurrentHashMap<SeatValue, Boolean>()
    private val doorOpen = java.util.concurrent.ConcurrentHashMap<DoorValue, Boolean>()

    private var vehicle: Vehicle? = null
    private var car: Car? = null
    private var carProps: CarPropertyManager? = null
    private var vehicleRegistered = false
    private var speedRegistered = false
    private var startedAtMs = 0L
    private val rawSpeed = RawSpeedProbe(context, onLeadDistanceMm = {
        leadDistanceMm = it; leadReceivedAtMs = System.currentTimeMillis()
    }, onNightMode = { night = it }) { speedKmh = it }
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
        v.getSteeringWheel().apply {
            getCurrentSteeringWheelAngle({ steeringDeg = it }, noop)
            registerSteeringWheelAngle(object : SteeringWheelAngleListener {
                override fun onSteeringWheelAngleUpdated(p0: Float?) { steeringDeg = p0 }
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
        v.getEvBattery().apply {
            val efficiency = object : EvBatteryEfficiencyListener {
                override fun onEvBatteryEfficiencyUpdated(p0: Float?) { p0?.let { evEfficiency = it } }
                override fun onFailed(p0: Exception) = Unit
            }
            registerCurrentEvEfficiency(efficiency) // 이번 주행 평균 전비
        }
        v.getSafety().apply {
            // 목록에 OVER_SPEED 가 없으면 이 차가 그 경고등을 지원하지 않는 것으로 보고 null(평가 불가)로 둔다.
            // false 로 두면 경고등이 없는 차(에뮬레이터 포함)에서 제한속도가 늘 100점이 된다.
            val onTelltales: (Telltales?) -> Unit = { t ->
                t?.telltales?.firstOrNull { it.type == TelltaleType.OVER_SPEED }
                    ?.let { overSpeed = it.state != TelltaleState.OFF }
            }
            getTelltalesInfo(onTelltales, noop)
            registerTelltales(object : TelltaleInfoListener {
                override fun onTelltaleInfoUpdated(p0: Telltales?) = onTelltales(p0)
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
            leadDistanceM = leadDistanceM(),
            steeringDeg = steeringDeg,
            overSpeedWarning = overSpeed,
            isNight = night,
            evEfficiencyKmPerKwh = evEfficiency,
        )
    }

    /** 앞차 거리(m). 최근 3초 안에 받은 양수 값만 쓴다 (앞차가 없으면 값이 오지 않거나 0이다). */
    private fun leadDistanceM(): Float? {
        val mm = leadDistanceMm ?: return null
        if (mm <= 0 || System.currentTimeMillis() - leadReceivedAtMs > LEAD_STALE_MS) return null
        return mm / 1000f
    }

    /** 화면 확인용: 항목별 수신 여부. */
    fun received(): List<SignalReading> = listOf(
        SignalReading("속도", speedKmh?.let { "%.1f km/h".format(it) }),
        SignalReading("속도(직접구독)", rawSpeed.lastRaw ?: rawSpeed.status.text),
        SignalReading("기어", gear?.name),
        SignalReading("브레이크", brake?.let { if (it) "밟음" else "뗌" }),
        SignalReading("지시등", turn?.name),
        SignalReading("핸들 각도", steeringDeg?.let { "%.0f°".format(it) }),
        SignalReading("앞차 거리", leadDistanceM()?.let { "%.1f m".format(it) }),
        SignalReading("앞차 거리 구독", "${rawSpeed.leadStatus.text}${rawSpeed.lastLeadRaw?.let { " ($it)" } ?: ""}"),
        SignalReading("하향등", lowBeam?.let { if (it) "ON" else "OFF" }),
        SignalReading("밤 모드", night?.let { if (it) "밤" else "낮" }),
        SignalReading("과속 경고등", overSpeed?.let { if (it) "ON" else "OFF" }),
        SignalReading("전비", evEfficiency?.let { "%.1f".format(it) }),
        SignalReading("벨트 운전석/동승석", "${belts[SeatValue.ROW_1_LEFT] ?: "-"} / ${belts[SeatValue.ROW_1_RIGHT] ?: "-"}"),
        SignalReading("내비", navi.status.text),
        SignalReading("다음 회전", navi.nextTurn),
        SignalReading("제한속도", navi.speedLimitKmh?.let { "$it km/h" }),
        SignalReading("탑승 운전석/동승석", "${occupied[SeatValue.ROW_1_LEFT] ?: "-"} / ${occupied[SeatValue.ROW_1_RIGHT] ?: "-"}"),
        SignalReading("문 열림", if (doorOpen.isEmpty()) null else doorOpen.values.any { it }.toString()),
    )

    fun events() = navi.events.toList()

    fun stop() {
        navi.stop()
        rawSpeed.stop()
        runCatching { carProps?.unregisterCallback(speedCallback) }
        runCatching { car?.disconnect() }
        runCatching { vehicle?.release() }
        vehicle = null; car = null; carProps = null
        vehicleRegistered = false; speedRegistered = false; leadDistanceMm = null
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

    private companion object {
        const val LEAD_STALE_MS = 3_000L
    }
}
