package ai.nunti.score

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * 시간 구간별 평가 후 유효 시간(또는 기회 수)으로 가중 평균하는 점수 엔진.
 * - 미수신/평가 불가 데이터는 분모에서 제외한다 (만점·0점 처리 금지).
 * - 평가 가능한 영역만 배점 비율로 재정규화한다.
 */
class ScoreEngine(private val cfg: ScoreConfig = ScoreConfig()) {

    private class Acc {
        var weight = 0.0
        var weighted = 0.0
        fun add(score: Double, w: Double) { weight += w; weighted += score * w }
        val score: Double? get() = if (weight > 0) weighted / weight else null
    }

    private class Open(val windowIdx: Int, val startT: Long, var peak: Float, val kind: DetectedEvent.Kind, val threshold: Float)

    fun evaluate(samples: List<VehicleSample>, events: List<DrivingEvent>): ScoreReport {
        if (samples.isEmpty()) return emptyReport()
        val t0 = samples.first().tMs
        val windowCount = ((samples.last().tMs - t0) / cfg.windowMs).toInt() + 1
        fun win(t: Long) = ((t - t0) / cfg.windowMs).toInt().coerceIn(0, windowCount - 1)

        val acc = Item.entries.associateWith { List(windowCount) { Acc() } }
        val detected = mutableListOf<DetectedEvent>()

        accumulateStates(samples, ::win, acc)
        accumulateAccelDecel(samples, ::win, acc, detected)
        accumulateCurves(samples, ::win, acc, detected)
        detectReverseEngaged(samples, detected)
        val gears = gearUsage(samples)
        val speedSeconds = samples.indices.sumOf { if (samples[it].speedKmh != null) duration(samples, it) else 0.0 }.toInt()
        val movingSeconds = samples.indices.sumOf { if (moving(samples[it])) duration(samples, it) else 0.0 }.toInt()
        accumulateOpportunities(samples, events, ::win, acc)

        val items = Item.entries.map { item ->
            val per = acc.getValue(item)
            val total = Acc().also { a -> per.forEach { if (it.weight > 0) a.add(it.score!!, it.weight) } }
            // 후진은 주차처럼 짧게 쓰는 기능이라 1초만 있어도 평가한다.
            val minWeight = if (item.byOpportunity || item == Item.REVERSE_SPEED) 1.0 else cfg.minValidSec
            val enough = total.weight >= minWeight
            val basis = when {
                total.weight == 0.0 && item == Item.REVERSE_SPEED ->
                    Basis(if (gears.isEmpty()) BasisKind.NO_GEAR_SIGNAL else BasisKind.REVERSE_UNUSED)
                item == Item.REVERSE_SPEED && enough -> Basis(BasisKind.REVERSE_SECONDS, total.weight.toInt())
                total.weight == 0.0 -> Basis(BasisKind.NO_SIGNAL)
                !enough -> Basis(BasisKind.TOO_FEW)
                item.byOpportunity -> Basis(BasisKind.OPPORTUNITIES, total.weight.toInt())
                else -> Basis(BasisKind.VALID_SECONDS, total.weight.toInt())
            }
            ItemResult(
                item,
                if (enough) total.score!!.toFloat() else null,
                basis,
                per.map { it.score?.toFloat() },
            )
        }

        val windowOverall = (0 until windowCount).map { w ->
            overall(items.map { it.item to it.windowScores[w] })
        }
        val areas = Area.entries.map { area ->
            val s = areaScore(items.filter { it.item.area == area }.map { it.score })
            AreaResult(area, s, s?.let { it * area.maxPoints / 100f })
        }
        val evaluable = areas.filter { it.score != null }
        val maxSum = evaluable.sumOf { it.area.maxPoints }
        val total = if (maxSum == 0) null else evaluable.sumOf { it.points!!.toDouble() }.toFloat() * 100f / maxSum
        return ScoreReport(total, maxSum / 100f, areas, items, windowOverall, detected.sortedBy { it.tMs }, gears, speedSeconds, movingSeconds)
    }

    private fun areaScore(scores: List<Float?>): Float? =
        scores.filterNotNull().takeIf { it.isNotEmpty() }?.average()?.toFloat()

    private fun overall(itemScores: List<Pair<Item, Float?>>): Float? {
        val areaScores = Area.entries.mapNotNull { area ->
            areaScore(itemScores.filter { it.first.area == area }.map { it.second })?.let { area to it }
        }
        val maxSum = areaScores.sumOf { it.first.maxPoints }
        if (maxSum == 0) return null
        return areaScores.sumOf { (a, s) -> (s * a.maxPoints).toDouble() }.toFloat() / maxSum
    }

    private fun duration(samples: List<VehicleSample>, i: Int): Double {
        if (i >= samples.lastIndex) return 0.0
        val dt = samples[i + 1].tMs - samples[i].tMs
        return if (dt in 1..cfg.maxGapMs) dt / 1000.0 else 0.0
    }

    /** 후진 중에는 속도가 음수로 올 수 있으므로 크기로 판단한다. */
    private fun moving(s: VehicleSample): Boolean = abs(s.speedKmh ?: 0f) > cfg.movingKmh

    private fun inCurve(s: VehicleSample): Boolean {
        val steer = s.steeringDeg ?: return false
        return abs(steer) >= cfg.curveSteeringDeg && abs(s.speedKmh ?: 0f) >= cfg.curveMinKmh && !reversing(s)
    }

    /**
     * 커브 속도 조절. 핸들을 크게 꺾은 상태가 이어지는 구간을 커브 하나(평가 기회)로 본다.
     * 점수 = 횡가속도(v²·tan(바퀴각)/축거)가 한도 이하면 100, 넘으면 한도/횡가속도 비율.
     * 진입 속도보다 충분히 줄였으면 최소 80점을 준다 ("줄이는지"를 본다). 한도를 크게 넘기면 사건으로 남긴다.
     */
    private fun accumulateCurves(
        samples: List<VehicleSample>,
        win: (Long) -> Int,
        acc: Map<Item, List<Acc>>,
        detected: MutableList<DetectedEvent>,
    ) {
        var i = 0
        while (i < samples.size) {
            if (!inCurve(samples[i])) { i++; continue }
            var j = i
            while (j + 1 < samples.size && inCurve(samples[j + 1]) && samples[j + 1].tMs - samples[j].tMs <= cfg.maxGapMs) j++
            val start = samples[i].tMs
            if (samples[j].tMs - start >= cfg.curveMinHoldMs) {
                val score = curveScore(samples, i, j)
                acc.getValue(Item.CURVE_SPEED)[win(start)].add(score, 1.0)
                if (score < CURVE_EVENT_BELOW) detected += DetectedEvent(start, DetectedEvent.Kind.CURVE_TOO_FAST)
            }
            i = j + 1
        }
    }

    private fun curveScore(samples: List<VehicleSample>, from: Int, to: Int): Double {
        val segment = samples.subList(from, to + 1)
        val start = segment.first().tMs
        val entry = samples.filter { it.tMs in (start - cfg.curveEntryLookbackMs)..start }
            .maxOf { abs(it.speedKmh ?: 0f) }
        val slowest = segment.minOf { abs(it.speedKmh ?: 0f) }
        val sharpest = segment.maxBy { abs(it.steeringDeg ?: 0f) }
        val v = abs(sharpest.speedKmh ?: 0f) / 3.6f
        val wheelAngle = Math.toRadians((abs(sharpest.steeringDeg ?: 0f) / cfg.steeringRatio).toDouble())
        val latAccel = v * v * kotlin.math.tan(wheelAngle) / cfg.wheelbaseM
        var score = if (latAccel <= cfg.curveComfortLatAccel) 100.0 else 100.0 * cfg.curveComfortLatAccel / latAccel
        if (slowest <= entry * cfg.curveSlowRatio) score = max(score, 80.0)
        return score.coerceIn(0.0, 100.0)
    }

    private fun reversing(s: VehicleSample) = s.gear == Gear.R

    private fun gearUsage(samples: List<VehicleSample>): List<GearUsage> {
        val seconds = HashMap<Gear, Double>()
        samples.forEachIndexed { i, s ->
            val g = s.gear ?: return@forEachIndexed
            seconds.merge(g, duration(samples, i), Double::plus)
        }
        if (samples.none { it.gear != null }) return emptyList()
        return Gear.entries.map { GearUsage(it, (seconds[it] ?: 0.0).toInt()) }
    }

    /** 직전 표본이 후진이 아니었다가 후진이 된 순간을 사건으로 남긴다 (첫 표본이 R 이어도 포함). */
    private fun detectReverseEngaged(samples: List<VehicleSample>, detected: MutableList<DetectedEvent>) {
        samples.forEachIndexed { i, s ->
            if (s.gear == Gear.R && (i == 0 || samples[i - 1].gear != Gear.R)) {
                detected += DetectedEvent(s.tMs, DetectedEvent.Kind.REVERSE_ENGAGED)
            }
        }
    }

    private fun accumulateStates(
        samples: List<VehicleSample>,
        win: (Long) -> Int,
        acc: Map<Item, List<Acc>>,
    ) {
        samples.forEachIndexed { i, s ->
            val dt = duration(samples, i)
            if (dt == 0.0) return@forEachIndexed
            val w = win(s.tMs)
            fun put(item: Item, score: Double?) { if (score != null) acc.getValue(item)[w].add(score, dt) }
            put(Item.SEATBELT, seatbelt(s))
            put(Item.DOOR, if (moving(s) && s.doorOpen != null) (if (s.doorOpen) 0.0 else 100.0) else null)
            put(Item.HEADLIGHT, headlight(s))
            // 앞차 거리·제한속도는 전진 기준이라 후진 중에는 평가하지 않는다.
            put(Item.LEAD_GAP, if (reversing(s)) null else leadGap(s))
            put(Item.SPEED_LIMIT, if (reversing(s)) null else speedLimit(s))
            put(Item.REVERSE_SPEED, reverse(s))
        }
    }

    private fun seatbelt(s: VehicleSample): Double? {
        if (!moving(s)) return null
        val seats = listOfNotNull(
            s.driverSeat?.takeIf { it.occupied != false && it.buckled != null },
            s.passengerSeat?.takeIf { it.occupied == true && it.buckled != null },
        )
        if (seats.isEmpty()) return null
        return if (seats.any { it.buckled == false }) 0.0 else 100.0
    }

    private fun headlight(s: VehicleSample): Double? {
        if (s.isNight != true || s.headlightOn == null || !moving(s)) return null
        return if (s.headlightOn) 100.0 else 0.0
    }

    private fun leadGap(s: VehicleSample): Double? {
        val d = s.leadDistanceM ?: return null
        if (!moving(s)) return null
        val gapSec = d / (abs(s.speedKmh!!) / 3.6f)
        val ratio = (gapSec - cfg.gapZeroSec) / (cfg.gapFullSec - cfg.gapZeroSec)
        return (ratio.coerceIn(0f, 1f) * 100f).toDouble()
    }

    private fun speedLimit(s: VehicleSample): Double? {
        val limit = s.speedLimitKmh?.takeIf { it > 0 } ?: return null
        val sp = abs(s.speedKmh ?: return null)
        val over = sp - limit - cfg.overLimitToleranceKmh
        return if (over <= 0f) 100.0 else max(0f, 100f - over * cfg.overLimitPenaltyPerKmh).toDouble()
    }

    private fun reverse(s: VehicleSample): Double? {
        if (s.gear != Gear.R) return null
        val sp = abs(s.speedKmh ?: return null)
        return if (sp <= cfg.reverseOkKmh) 100.0 else max(0f, 100f - (sp - cfg.reverseOkKmh) * 8f).toDouble()
    }

    /**
     * 급가속/급감속/급제동. 연속 구간은 하나의 사건으로 묶고, 제동 중 급감속은 급제동 한 곳에서만 감점한다.
     * 순간 사건은 구간 점수에서 감점하고 유효 주행 시간 가중 평균으로 희석된다.
     */
    private fun accumulateAccelDecel(
        samples: List<VehicleSample>,
        win: (Long) -> Int,
        acc: Map<Item, List<Acc>>,
        detected: MutableList<DetectedEvent>,
    ) {
        val penalties = DoubleArray(acc.getValue(Item.ACCEL_DECEL).size)
        val driving = DoubleArray(penalties.size)
        var openAccel: Open? = null
        var openDecel: Open? = null

        fun close(o: Open?) {
            o ?: return
            val severity = min(1f, o.peak / o.threshold - 1f)
            penalties[o.windowIdx] += 20.0 + 20.0 * severity
            detected += DetectedEvent(o.startT, o.kind)
        }

        for (i in 1 until samples.size) {
            val prev = samples[i - 1]
            val cur = samples[i]
            val dtMs = cur.tMs - prev.tMs
            val a = if (prev.speedKmh != null && cur.speedKmh != null && dtMs in 1..cfg.maxGapMs) {
                (abs(cur.speedKmh) - abs(prev.speedKmh)) / (dtMs / 1000f)
            } else null
            if (a == null) {
                close(openAccel); openAccel = null
                close(openDecel); openDecel = null
                continue
            }
            driving[win(prev.tMs)] += dtMs / 1000.0

            val accelLimit = accelThr(cur, abs(prev.speedKmh!!))
            if (a >= accelLimit) {
                openAccel = (openAccel ?: Open(win(cur.tMs), cur.tMs, a, DetectedEvent.Kind.HARD_ACCEL, accelLimit)).also { it.peak = max(it.peak, a) }
            } else {
                close(openAccel); openAccel = null
            }
            val decelLimit = decelThr(cur)
            if (-a >= decelLimit) {
                val kind = if (cur.brakePressed == true) DetectedEvent.Kind.HARD_BRAKE else DetectedEvent.Kind.HARD_DECEL
                openDecel = (openDecel ?: Open(win(cur.tMs), cur.tMs, -a, kind, decelLimit)).also { it.peak = max(it.peak, -a) }
            } else {
                close(openDecel); openDecel = null
            }
        }
        close(openAccel)
        close(openDecel)

        val list = acc.getValue(Item.ACCEL_DECEL)
        for (w in list.indices) if (driving[w] > 0) list[w].add(max(0.0, 100.0 - penalties[w]), driving[w])
    }

    /**
     * 급가속 기준. 정차·저속에서 출발하는 가속(구간 시작 속도가 [ScoreConfig.launchSpeedKmh] 미만)은 차가 원래 힘이 가장 세므로
     * 더 높은 기준([ScoreConfig.harshAccelLaunch])을 쓴다. 신호 대기 후 보통의 출발을 급가속으로 보지 않기 위함이다.
     */
    private fun accelThr(s: VehicleSample, startKmh: Float) = when {
        startKmh < cfg.launchSpeedKmh -> cfg.harshAccelLaunch
        s.roadType == RoadType.HIGHWAY -> cfg.harshAccelHighway
        else -> cfg.harshAccelGeneral
    }

    private fun decelThr(s: VehicleSample) =
        if (s.roadType == RoadType.HIGHWAY) cfg.harshDecelHighway else cfg.harshDecelGeneral

    /** 실제 행동 기회가 있었을 때만 평가. 기회가 없거나 신호가 없으면 평가하지 않는다. */
    private fun accumulateOpportunities(
        samples: List<VehicleSample>,
        events: List<DrivingEvent>,
        win: (Long) -> Int,
        acc: Map<Item, List<Acc>>,
    ) {
        for (e in events) {
            if (e.tMs < samples.first().tMs || e.tMs > samples.last().tMs) continue
            val w = win(e.tMs)
            when (e.kind) {
                DrivingEvent.Kind.TURN -> {
                    val before = samples.lastOrNull { it.tMs <= e.tMs - cfg.turnLookbackMs }?.speedKmh
                    val at = samples.lastOrNull { it.tMs <= e.tMs }?.speedKmh
                    if (before == null || at == null) continue
                    val ok = at <= before * cfg.turnDecelRatio || at <= cfg.turnLowSpeedKmh
                    acc.getValue(Item.TURN_DECEL)[w].add(if (ok) 100.0 else 0.0, 1.0)
                }
                DrivingEvent.Kind.LANE_CHANGE -> {
                    val near = samples.filter { it.tMs in (e.tMs - cfg.laneSignalLookbackMs)..e.tMs }
                    if (near.none { it.turnSignal != null }) continue
                    val ok = near.any { it.turnSignal == e.direction }
                    acc.getValue(Item.LANE_SIGNAL)[w].add(if (ok) 100.0 else 0.0, 1.0)
                }
            }
        }
    }

    private fun emptyReport() = ScoreReport(
        null, 0f,
        Area.entries.map { AreaResult(it, null, null) },
        Item.entries.map { ItemResult(it, null, Basis(BasisKind.NO_SIGNAL), emptyList()) },
        emptyList(), emptyList(),
    )

    /** 점수와 별도의 감정. 불확실하면 중립. 걱정 뒤 회복되면 안도. */
    fun emotion(report: ScoreReport, finished: Boolean): Emotion {
        val known = report.windowOverall.filterNotNull()
        val last = report.windowOverall.lastOrNull { it != null } ?: return Emotion.NEUTRAL
        val worried = known.any { it < 70f }
        return when {
            last < 70f -> Emotion.WORRY
            last >= 90f && worried -> Emotion.RELIEF
            last >= 90f && finished -> Emotion.JOY
            else -> Emotion.NEUTRAL
        }
    }

    private companion object {
        /** 이 점수 미만의 커브는 "커브 과속" 사건으로 남긴다. */
        const val CURVE_EVENT_BELOW = 50.0
    }
}
