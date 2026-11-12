package ai.nunti.score.journey

import ai.nunti.score.*
import kotlin.math.abs

/** Geographic observations and normalized simulator locations are deliberately different types. */
sealed interface TripPosition {
    data class Geographic(val latitude: Double, val longitude: Double) : TripPosition
    data class Simulation(val x: Double, val y: Double) : TripPosition
}
data class TripObservation(val sample: VehicleSample, val position: TripPosition?)
data class TripEvent(val tMs: Long, val label: String, val evidence: String, val advice: String,
    val position: TripPosition?, val speedKmh: Float?, val includedInScore: Boolean)
data class HabitAdvice(val positive: Boolean, val title: String, val detail: String)
data class TripAnalysis(val events: List<TripEvent>, val habits: List<HabitAdvice>, val distanceKm: Double,
    val steeringAvailable: Boolean, val observationCount: Int)

/** Adds explanations and positions without changing the team's scoring formula. */
class JourneyAnalysis(private val config: ScoreConfig = ScoreConfig()) {
    private val observations = mutableListOf<TripObservation>()
    private val turns = linkedSetOf<DrivingEvent>()
    private val abrupt = mutableListOf<TripEvent>()
    private var lastSteeringEvent = -10_000L
    private var distance = 0.0

    fun observe(sample: VehicleSample, position: TripPosition?, opportunities: List<DrivingEvent>) {
        val prev=observations.lastOrNull()?.sample
        if(prev?.tMs==sample.tMs) return
        if(prev!=null) {
            val dt=sample.tMs-prev.tMs
            if(dt in 1..config.maxGapMs) {
                if(prev.speedKmh!=null && sample.speedKmh!=null) distance += (prev.speedKmh+sample.speedKmh)/2.0*dt/3_600_000.0
                val a=prev.steeringDeg; val b=sample.steeringDeg
                if(a!=null&&b!=null&&(sample.speedKmh?:0f)>=20f && abs(b-a)/(dt/1000f)>=100f && sample.tMs-lastSteeringEvent>=5000) {
                    abrupt+=TripEvent(sample.tMs,"급회전", "핸들 %.0f° → %.0f° · %.0f km/h".format(a,b,sample.speedKmh),
                        "회전 전에 속도를 줄이고 핸들을 천천히 돌려 보세요.",position,sample.speedKmh,false)
                    lastSteeringEvent=sample.tMs
                }
            }
        }
        observations+=TripObservation(sample,position)
        turns+=opportunities
    }

    fun build(report: ScoreReport): TripAnalysis {
        val events=report.events.map { e ->
            val index=observations.indexOfFirst { it.sample.tMs>=e.tMs }
            val at=observations.getOrNull(index)
            val prev=observations.getOrNull(index-1)?.sample
            val speed=at?.sample?.speedKmh
            val evidence=when {
                e.kind==DetectedEvent.Kind.PARK_WHILE_MOVING -> speed?.let { "P단 변속 때 %.0f km/h".format(abs(it)) } ?: "P단 변속 때 움직임 감지"
                prev?.speedKmh!=null&&speed!=null -> "%.0f → %.0f km/h · %.1f초".format(prev.speedKmh,speed,(at.sample.tMs-prev.tMs)/1000f)
                else -> "수신된 속도 변화로 감지"
            }
            TripEvent(e.tMs,e.label,evidence,when(e.kind){
                DetectedEvent.Kind.HARD_ACCEL->"출발할 때 가속 페달을 조금 더 천천히 밟아 보세요."
                DetectedEvent.Kind.PARK_WHILE_MOVING->"브레이크로 완전히 멈춘 다음 P단으로 바꿔 주세요."
                else->"앞차와 거리를 두고 정지 전에 일찍 속도를 줄여 보세요."},
                at?.position,speed,true)
        }.toMutableList()
        for(turn in turns.filter { it.kind==DrivingEvent.Kind.TURN }) {
            val before=observations.lastOrNull { it.sample.tMs<=turn.tMs-config.turnLookbackMs }?.sample?.speedKmh
            val at=observations.lastOrNull { it.sample.tMs<=turn.tMs }
            val speed=at?.sample?.speedKmh
            if(before!=null&&speed!=null&&speed>before*config.turnDecelRatio&&speed>config.turnLowSpeedKmh) {
                events+=TripEvent(turn.tMs,"회전 전 감속 부족","진입 %.0f km/h · 5초 전 %.0f km/h".format(speed,before),
                    "회전하기 전에 속도를 충분히 줄여 보세요.",at.position,speed,true)
            }
        }
        events+=abrupt
        val known=report.items.filter { it.score!=null }
        val habits=mutableListOf<HabitAdvice>()
        for(item in known.sortedBy { it.score }) {
            val good=item.score!!>=90
            val detail=when(item.item){
                Item.ACCEL_DECEL->if(good) "가속과 제동이 부드러웠어요. 지금의 페달 조작을 유지해 주세요." else "앞차와 거리를 두고, 가속과 제동을 조금 더 일찍 나눠 해 보세요."
                Item.LEAD_GAP->if(good) "앞차와 충분한 거리를 유지했어요." else "앞차와 간격이 짧았어요. 여유를 두면 급제동을 줄이는 데 도움이 돼요."
                Item.CURVE_SPEED->if(good) "커브에서 속도를 알맞게 줄였어요." else "커브에서 속도가 빨랐어요. 커브에 들어가기 전에 미리 속도를 줄여 보세요."
                Item.TURN_DECEL->if(good) "회전 전에 속도를 잘 줄였어요." else "회전 전 감속이 부족했어요. 직선 구간에서 미리 속도를 줄여 보세요."
                Item.SPEED_LIMIT->if(good) "수신된 제한속도를 잘 지켰어요." else "제한속도를 넘긴 구간이 있어요. 표지판과 내비 안내를 함께 살펴주세요."
                Item.SEATBELT->if(good) "확인된 좌석의 안전벨트를 잘 착용했어요." else "주행 중 안전벨트 미착용이 기록됐어요. 출발 전에 착용을 확인해 주세요."
                Item.DOOR->if(good) "주행 중 문이 닫힌 상태를 유지했어요." else "주행 중 문 열림 신호가 있었어요. 출발 전에 문이 닫혔는지 확인해 주세요."
                Item.LANE_SIGNAL->if(good) "차선 변경 전에 방향지시등을 사용했어요." else "차선을 바꾸기 전에 방향지시등을 켜 주세요."
                Item.HEADLIGHT->if(good) "야간에 전조등을 켰어요." else "야간 주행 때 전조등을 확인해 주세요."
                Item.REVERSE_SPEED->if(good) "후진 속도를 낮게 유지했어요." else "후진할 때는 속도를 낮추고 주변을 살펴주세요."
                Item.PARK_SHIFT->if(good) "완전히 멈춘 뒤에 P단으로 바꿨어요." else "차가 움직이는 중에 P단으로 바꾼 적이 있어요. 완전히 멈춘 다음 바꿔 주세요."
                Item.EFFICIENCY->"연비·전비는 수신된 정보로만 평가해요."
            }
            habits+=HabitAdvice(good,item.item.label,detail)
        }
        if(abrupt.isNotEmpty()) habits.add(0,HabitAdvice(false,"핸들 조작","급격한 핸들 조작 ${abrupt.size}회가 기록됐어요. 회전 전에 속도를 줄여 보세요. 이 참고 항목은 총점에 반영하지 않아요."))
        return TripAnalysis(events.sortedBy { it.tMs },habits,distance,observations.any { it.sample.steeringDeg!=null },observations.size)
    }
    fun track(): List<TripObservation> = observations.filter { it.position!=null }
}
