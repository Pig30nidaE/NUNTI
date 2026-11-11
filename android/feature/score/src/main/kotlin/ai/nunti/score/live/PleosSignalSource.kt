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
import ai.pleos.playground.vehicle.constant.telltale.TelltaleState
import ai.pleos.playground.vehicle.constant.telltale.TelltaleType
import ai.pleos.playground.vehicle.listener.BrakePedalStatusListener
import ai.pleos.playground.vehicle.listener.DoorPositionListener
import ai.pleos.playground.vehicle.listener.EvBatteryEfficiencyListener
import ai.pleos.playground.vehicle.listener.GearSelectionListener
import ai.pleos.playground.vehicle.listener.LightStateListener
import ai.pleos.playground.vehicle.listener.SeatBeltBuckledStateListener
import ai.pleos.playground.vehicle.listener.SeatOccupancyListener
import ai.pleos.playground.vehicle.listener.SteeringWheelAngleListener
import ai.pleos.playground.vehicle.listener.TurnSignalStateListener
import ai.nunti.score.DrivingEvent
import ai.nunti.score.Gear
import ai.nunti.score.SeatState
import ai.nunti.score.TurnSignal
import ai.nunti.score.VehicleSample

/**
 * 실제 차량 신호 수신. 마지막으로 받은 값을 보관하고 snapshot()에서 한 시점의 VehicleSample로 만든다.
 * 한 번도 수신하지 못했거나 오류·끊김이 난 신호는 null(평가 불가)로 남는다.
 * 바뀔 때만 오는 신호는 차가 같은 속도·기어로 계속 달린다고 해서 만료시키지 않는다.
 * 속도는 Pleos Vehicle SDK 2.3.2에 없어 AAOS CarPropertyManager(PERF_VEHICLE_SPEED)와 실험적 직접 구독(RawSpeedProbe)으로 받는다.
 * 구독 한 번(start~stop)마다 세대(epoch)를 두어, 해제한 서비스의 늦은 콜백이 다음 구독에 섞이지 않게 한다.
 */
class PleosSignalSource(private val context: Context) {
    private val gate = SignalSessionGate()
    private var carSpeed: Float? = null
    private var rawSpeedValue: Float? = null
    private var brake: Boolean? = null
    private var gear: Gear? = null
    private var turn: TurnSignal? = null
    private var steering: Float? = null
    private var lowBeam: Boolean? = null
    private var overSpeed: Boolean? = null
    private var night: Boolean? = null
    private var evEfficiency: Float? = null
    // 앞차 거리(mm): Vehicle 서비스 직접 구독으로 받는다 (RawSpeedProbe). 표준 CarPropertyManager 경로는 앱에 막혀 있다.
    private var leadDistanceMm: Int? = null
    private var leadReceivedAtMs = 0L
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
    /** 신호 묶음별로 따로 등록한다. 한 묶음이 실패(권한·미지원)해도 나머지는 등록되고, 실패한 묶음만 다시 시도한다. */
    private enum class Group { BRAKE, GEAR, STEERING, TURN_SIGNAL, LIGHT, ENERGY, TELLTALES, SEATS, DOORS }
    private val registered = mutableSetOf<Group>()
    private val failed = mutableMapOf<Group, String>()
    private var speedRegistered = false
    private var startedAtMs = 0L
    private var lastSnapshotMs = 0L
    private var lastSnapshotSpeed: Float? = null
    private var lastNaviPollMs = Long.MIN_VALUE
    private var telltalesReadAtMs = 0L
    private var rawSpeed: RawSpeedProbe? = null
    private var navi: NaviSignalSource? = null

    private fun resetReadings() {
        carSpeed = null; rawSpeedValue = null; brake = null; gear = null; turn = null; lowBeam = null; steering = null
        overSpeed = null; night = null; evEfficiency = null; leadDistanceMm = null; leadReceivedAtMs = 0
        belts.clear(); occupied.clear(); doors.clear(); lastSnapshotMs = 0; lastSnapshotSpeed = null
    }

    @Synchronized
    fun start() {
        val epoch = gate.begin { resetReadings() } ?: return
        startedAtMs = SystemClock.elapsedRealtime()
        lastNaviPollMs = Long.MIN_VALUE
        telltalesReadAtMs = 0
        registered.clear(); failed.clear(); speedRegistered = false
        vehicle = runCatching { Vehicle(context).also { it.initialize() } }
            .onFailure { Log.w(TAG, "Vehicle init failed", it) }.getOrNull()
        rawSpeed = RawSpeedProbe(
            context,
            onLeadDistanceMm = { mm -> gate.accept(epoch) { leadDistanceMm = mm; leadReceivedAtMs = SystemClock.elapsedRealtime() } },
            onNightMode = { value -> gate.accept(epoch) { night = value } },
            onUnavailable = { gate.accept(epoch) { rawSpeedValue = null } },
            onSpeed = { value -> gate.accept(epoch) { rawSpeedValue = value.takeIf { it.isFinite() } } },
        ).also { it.start() }
        navi = NaviSignalSource(context) { SystemClock.elapsedRealtime() - startedAtMs }.also { it.start() }
        retryRegistrations(epoch)
    }

    /** 서비스 연결이 늦을 수 있어 snapshot 때마다 미등록 항목을 다시 시도한다. */
    private fun retryRegistrations(epoch: Long) {
        if (vehicle == null) vehicle = runCatching { Vehicle(context).also { it.initialize() } }.getOrNull()
        val v = vehicle
        if (v != null) for (g in Group.entries) {
            if (g in registered) continue
            runCatching { register(v, g, epoch) }
                .onSuccess { registered += g; failed.remove(g) }
                .onFailure { e ->
                    val why = e.message ?: e.javaClass.simpleName
                    if (failed.put(g, why) != why) Log.w(TAG, "Vehicle register failed: $g: $why") // 같은 실패는 한 번만 남긴다
                }
        }
        if (!speedRegistered) speedRegistered = runCatching { registerSpeed(epoch) }
            .onFailure { Log.w(TAG, "Speed register failed: ${it.message}") }.getOrDefault(false)
    }

    private fun registerSpeed(epoch: Long): Boolean {
        val c = car ?: Car.createCar(context).also { car = it }
        val mgr = carProps ?: (c.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager).also { carProps = it }
        val cb = speedCallback ?: object : CarPropertyManager.CarPropertyEventCallback {
            override fun onChangeEvent(value: CarPropertyValue<*>) {
                gate.accept(epoch) {
                    carSpeed = if (value.status == CarPropertyValue.STATUS_AVAILABLE)
                        (value.value as? Float)?.takeIf { it.isFinite() }?.times(3.6f) else null // m/s -> km/h
                }
            }
            override fun onErrorEvent(propId: Int, zone: Int) { gate.accept(epoch) { carSpeed = null } }
        }.also { speedCallback = it }
        // 에뮬레이터에 따라 PERF_VEHICLE_SPEED 가 목록에 없을 수 있어 클러스터용 DISPLAY 속도를 대체로 쓴다.
        return listOf(VehiclePropertyIds.PERF_VEHICLE_SPEED, VehiclePropertyIds.PERF_VEHICLE_SPEED_DISPLAY).any {
            runCatching { mgr.registerCallback(cb, it, CarPropertyManager.SENSOR_RATE_NORMAL) }.getOrDefault(false)
        }
    }

    /** 실패 콜백은 그 신호를 null(평가 불가)로 되돌린다. 현재값 조회 실패는 등록 실패로 보지 않는다. */
    private fun register(v: Vehicle, group: Group, epoch: Long) {
        fun set(update: () -> Unit) { gate.accept(epoch, update) }
        when (group) {
            Group.BRAKE -> v.getBrake().apply {
                runCatching { getCurrentBrakePedalStatus({ set { brake = it } }, { set { brake = null } }) }
                registerBrakePedalStatus(object : BrakePedalStatusListener {
                    override fun onBrakePedalStatusUpdated(p0: Boolean?) { set { brake = p0 } }
                    override fun onFailed(p0: Exception) { set { brake = null } }
                })
            }
            Group.GEAR -> v.getGear().apply {
                runCatching { getCurrentGearSelectionState({ set { gear = it?.toGear() } }, { set { gear = null } }) }
                registerGearSelection(object : GearSelectionListener {
                    override fun onSelected(p0: VehicleGear?) { set { gear = p0?.toGear() } }
                    override fun onFailed(p0: Exception) { set { gear = null } }
                })
            }
            Group.STEERING -> v.getSteeringWheel().apply {
                fun update(value: Float?) = set { steering = value?.takeIf { it.isFinite() && kotlin.math.abs(it) <= 1080f } }
                runCatching { getCurrentSteeringWheelAngle({ update(it) }, { update(null) }) }
                registerSteeringWheelAngle(object : SteeringWheelAngleListener {
                    override fun onSteeringWheelAngleUpdated(p0: Float?) { update(p0) }
                    override fun onFailed(p0: Exception) { update(null) }
                })
            }
            Group.TURN_SIGNAL -> v.getTurnSignal().apply {
                runCatching { getCurrentTurnSignalState({ set { turn = it?.toTurn() } }, { set { turn = null } }) }
                registerTurnSignalState(object : TurnSignalStateListener {
                    override fun onTurnSignalStateUpdated(p0: TurnSignalValue?) { set { turn = p0?.toTurn() } }
                    override fun onFailed(p0: Exception) { set { turn = null } }
                })
            }
            Group.LIGHT -> v.getLight().apply {
                runCatching { getCurrentLowBeamLightState({ s -> set { lowBeam = s?.let { it == LightState.ON } } }, { set { lowBeam = null } }) }
                registerLowBeamLightState(object : LightStateListener {
                    override fun onLightStateUpdated(p0: LightState?) { set { lowBeam = p0?.let { it == LightState.ON } } }
                    override fun onFailed(p0: Exception) { set { lowBeam = null } }
                })
            }
            Group.ENERGY -> v.getEvBattery().registerCurrentEvEfficiency(object : EvBatteryEfficiencyListener { // 이번 주행 평균 전비
                override fun onEvBatteryEfficiencyUpdated(p0: Float?) { p0?.takeIf { it.isFinite() }?.let { set { evEfficiency = it } } }
                override fun onFailed(p0: Exception) = Unit
            })
            // 경고등 구독(registerTelltales)은 PRIVATE_CAR_SAFETY(signature|privileged)라 일반 앱은 못 쓴다.
            // 한 번 읽기(getTelltalesInfo)는 CAR_SAFETY(normal)이므로 snapshot 때 주기적으로 읽는다.
            Group.TELLTALES -> pollTelltales(v, epoch, force = true)
            Group.SEATS -> v.getSeat().apply {
                for (s in seatAreas) {
                    val area = SeatArea(s)
                    fun belt(value: Boolean?) = set { if (value == null) belts.remove(s) else belts[s] = value }
                    fun occupancy(value: Boolean?) = set { if (value == null) occupied.remove(s) else occupied[s] = value }
                    runCatching { getCurrentSeatBeltBuckledState(area, { belt(it) }, { belt(null) }) }
                    registerSeatBeltBuckledState(area, object : SeatBeltBuckledStateListener {
                        override fun onSeatBeltBuckledStateUpdated(p0: Boolean?) { belt(p0) }
                        override fun onFailed(p0: Exception) { belt(null) }
                    })
                    runCatching { getCurrentSeatOccupancy(area, { occupancy(it) }, { occupancy(null) }) }
                    registerSeatOccupancy(area, object : SeatOccupancyListener {
                        override fun onSeatOccupancyUpdated(p0: Boolean?) { occupancy(p0) }
                        override fun onFailed(p0: Exception) { occupancy(null) }
                    })
                }
            }
            Group.DOORS -> v.getDoor().apply {
                for (d in doorAreas) {
                    val area = DoorArea(d)
                    // 0 = 닫힘 (에뮬레이터로 확인 필요)
                    fun update(value: Int?) = set { if (value == null) doors.remove(d.name) else doors[d.name] = value > 0 }
                    runCatching { getCurrentDoorPosition(area, { update(it) }, { update(null) }) }
                    registerDoorPosition(area, object : DoorPositionListener {
                        override fun onPositionUpdated(p0: Int?) { update(p0) }
                        override fun onFailed(p0: Exception) { update(null) }
                    })
                }
            }
        }
    }

    /** OVER_SPEED 가 목록에 없으면 이 차가 그 경고등을 지원하지 않는 것으로 보고 null(평가 불가)로 둔다. */
    private fun pollTelltales(v: Vehicle, epoch: Long, force: Boolean = false) {
        val now = SystemClock.elapsedRealtime()
        if (!force && now - telltalesReadAtMs < TELLTALE_POLL_MS) return
        telltalesReadAtMs = now
        v.getSafety().getTelltalesInfo({ t ->
            t.telltales.firstOrNull { it.type == TelltaleType.OVER_SPEED }?.let { o -> gate.accept(epoch) { overSpeed = o.state != TelltaleState.OFF } }
        }, { _ -> })
    }

    @Synchronized
    fun snapshot(): VehicleSample {
        val epoch = gate.current() ?: return VehicleSample(0)
        retryRegistrations(epoch)
        vehicle?.takeIf { Group.TELLTALES in registered }?.let { v -> runCatching { pollTelltales(v, epoch) } }
        val now = SystemClock.elapsedRealtime() - startedAtMs
        if (lastNaviPollMs == Long.MIN_VALUE || now - lastNaviPollMs >= 1000) {
            lastNaviPollMs = now
            navi?.poll()
        }
        // Read transport health outside the readings lock: callbacks acquire transport then readings.
        val rawAlive = rawSpeed?.isConnected() == true
        val carAlive = car?.isConnected == true
        val speedLimit = navi?.speedLimitKmh
        val naviConnected = if (navi?.status?.state == LinkState.CONNECTED) true else null
        return gate.read {
            lastSnapshotMs = now
            lastSnapshotSpeed = (if (rawAlive) rawSpeedValue else null) ?: (if (carAlive) carSpeed else null)
            VehicleSample(
                tMs = now,
                speedKmh = lastSnapshotSpeed,
                brakePressed = brake, gear = gear, turnSignal = turn,
                driverSeat = seat(SeatValue.ROW_1_LEFT), passengerSeat = seat(SeatValue.ROW_1_RIGHT),
                doorOpen = aggregateDoorState(doors, expectedDoors), headlightOn = lowBeam, speedLimitKmh = speedLimit,
                leadDistanceM = leadDistanceM(),
                steeringDeg = steering,
                naviConnected = naviConnected,
                overSpeedWarning = overSpeed,
                isNight = night,
                evEfficiencyKmPerKwh = evEfficiency,
            )
        }
    }

    private fun seat(s: SeatValue) = if (occupied[s] == null && belts[s] == null) null else SeatState(occupied[s], belts[s])

    /** 앞차 거리(m). 최근 3초 안에 받은 양수 값만 쓴다 (앞차가 없으면 값이 오지 않거나 0이다). */
    private fun leadDistanceM(): Float? {
        val mm = leadDistanceMm ?: return null
        if (mm <= 0 || SystemClock.elapsedRealtime() - leadReceivedAtMs > LEAD_STALE_MS) return null
        return mm / 1000f
    }

    /** 화면 확인용: 항목별 수신 여부. */
    fun received(): List<SignalReading> {
        val probe = rawSpeed
        val n = navi
        return gate.read {
            listOf(
                SignalReading("속도", lastSnapshotSpeed?.let { "%.1f km/h".format(it) }),
                SignalReading("속도(직접구독)", probe?.let { it.lastRaw ?: it.status.text } ?: "중지"),
                SignalReading("기어", gear?.name),
                SignalReading("브레이크", brake?.let { if (it) "밟음" else "뗌" }),
                SignalReading("지시등", turn?.name),
                SignalReading("핸들 각도", steering?.let { "%.0f°".format(it) }),
                SignalReading("앞차 거리", leadDistanceM()?.let { "%.1f m".format(it) }),
                SignalReading("앞차 거리 구독", probe?.let { "${it.leadStatus.text}${it.lastLeadRaw?.let { r -> " ($r)" } ?: ""}" } ?: "중지"),
                SignalReading("하향등", lowBeam?.let { if (it) "ON" else "OFF" }),
                SignalReading("밤 모드", night?.let { if (it) "밤" else "낮" }),
                SignalReading("과속 경고등", overSpeed?.let { if (it) "ON" else "OFF" }),
                SignalReading("전비", evEfficiency?.let { "%.1f".format(it) }),
                SignalReading("벨트 운전석/동승석", "${belts[SeatValue.ROW_1_LEFT] ?: "-"} / ${belts[SeatValue.ROW_1_RIGHT] ?: "-"}"),
                SignalReading("내비", n?.status?.text ?: "중지"),
                SignalReading("다음 회전", n?.nextTurn ?: "-"),
                SignalReading("제한속도", n?.speedLimitKmh?.let { "$it km/h" }),
                SignalReading("탑승 운전석/동승석", "${occupied[SeatValue.ROW_1_LEFT] ?: "-"} / ${occupied[SeatValue.ROW_1_RIGHT] ?: "-"}"),
                SignalReading("문 열림", aggregateDoorState(doors, expectedDoors)?.toString()),
                SignalReading("등록 실패", failed.keys.sorted().joinToString().ifEmpty { "없음" }),
            )
        }
    }

    /** 마지막 snapshot 시각까지의 회전 이벤트만 준다 (아직 샘플로 관측하지 않은 구간의 이벤트는 다음에). */
    fun events(): List<DrivingEvent> {
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
        registered.clear(); failed.clear(); speedRegistered = false
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
        const val TAG = "NuntiSignal"
        const val LEAD_STALE_MS = 3_000L
        const val TELLTALE_POLL_MS = 2_000L
    }
}
