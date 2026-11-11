package ai.nunti.score.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.ui.platform.LocalContext
import ai.nunti.score.live.PleosSignalSource
import ai.nunti.score.live.PleosSpeechSink
import ai.nunti.score.EventSpeaker
import ai.nunti.score.sync.SourceTag
import ai.nunti.score.sync.SyncConfig
import ai.nunti.score.sync.TelemetrySync
import java.io.File
import ai.nunti.score.VehicleSample
import ai.nunti.score.AreaResult
import ai.nunti.score.Emotion
import ai.nunti.score.ClosingMessage
import ai.nunti.score.Readiness
import ai.nunti.score.TripLifecycle
import ai.nunti.score.TripStatus
import ai.nunti.score.ItemResult
import android.util.Log
import ai.nunti.score.ScoreEngine
import ai.nunti.score.ScoreReport
import ai.nunti.score.Scenarios
import kotlinx.coroutines.delay

private val Good = Color(0xFF4CAF50)
private val Warn = Color(0xFFFFB300)
private val Bad = Color(0xFFEF5350)
private val Muted = Color(0xFF8A8F98)

private fun scoreColor(s: Float?) = when {
    s == null -> Muted
    s >= 90f -> Good
    s >= 70f -> Warn
    else -> Bad
}

private fun fmt(s: Float?) = s?.let { "%.0f".format(it) } ?: "평가 불가"

@Composable
fun ScoreScreen() {
    val engine = remember { ScoreEngine() }
    val context = LocalContext.current
    var live by remember { mutableStateOf(false) }
    var lastLine by remember { mutableStateOf<String?>(null) }
    var sampleIdx by remember { mutableIntStateOf(-1) }
    var lastResult by remember { mutableStateOf<String?>(null) }
    var scenarioIdx by remember { mutableIntStateOf(0) }
    var cursor by remember { mutableIntStateOf(0) }
    var playing by remember { mutableStateOf(true) }
    var showSignals by remember { mutableStateOf(false) }
    var liveEndRequested by remember { mutableStateOf(false) } // 사용자가 주행 종료를 눌렀다 (확정 가능 여부는 별도)
    var liveStopped by remember { mutableStateOf(false) } // 확정되어 표본 수집을 멈췄다
    val scenario = Scenarios.all[scenarioIdx]
    val last = scenario.samples.lastIndex

    val source = remember { PleosSignalSource(context.applicationContext) }
    val liveSamples = remember { mutableStateListOf<VehicleSample>() }
    var received by remember { mutableStateOf(emptyList<ai.nunti.score.live.SignalReading>()) }
    var liveEvents by remember { mutableStateOf(emptyList<ai.nunti.score.DrivingEvent>()) }

    DisposableEffect(live) {
        if (live) { liveSamples.clear(); liveEndRequested = false; liveStopped = false; source.start() }
        onDispose { if (live) source.stop() }
    }
    var liveSpeed by remember { mutableStateOf<Float?>(null) } // 확정 뒤에도 계속 읽는다 (정차 확인용)
    LaunchedEffect(live) {
        while (live) {
            val snap = source.snapshot()
            liveSpeed = snap.speedKmh
            if (!liveStopped) liveSamples.add(snap) // 확정되면 점수 표본은 거기서 고정한다
            received = source.received()
            liveEvents = source.events()
            delay(1000)
        }
    }
    LaunchedEffect(scenarioIdx, playing, live) {
        while (!live && playing && cursor < last) {
            delay(40)
            cursor++
        }
    }

    val shown = if (live) liveSamples.toList().ifEmpty { listOf(VehicleSample(0)) } else scenario.samples.take(cursor + 1)
    val events = if (live) liveEvents else scenario.events.filter { it.tMs <= shown.last().tMs }
    val report = remember(live, scenarioIdx, cursor, liveSamples.size) {
        engine.evaluate(shown, events)
    }
    // 종료를 요청했는데 아직 확정할 수 없으면(정차·신호 부족) 일시저장하고, 충분해지면 이어서 확정한다.
    val ended = if (live) liveEndRequested else cursor >= last
    val status = if (!ended) TripStatus.DRIVING else TripLifecycle.onEndRequested(report)
    val finished = status == TripStatus.FINISHED
    val paused = status == TripStatus.PAUSED
    val readiness = TripLifecycle.readiness(report)
    LaunchedEffect(finished) { if (live) liveStopped = finished }
    val emotion = engine.emotion(report, finished)

    var voiceOn by remember { mutableStateOf(true) }
    var speakerId by remember { mutableStateOf<String?>(null) }
    val sink = remember(speakerId) { PleosSpeechSink(context, drivingAllowed = true, speaker = speakerId) { lastResult = it } }
    val speaker = remember(sink) { EventSpeaker(sink) }
    DisposableEffect(sink) { onDispose { sink.close() } }
    LaunchedEffect(live, scenarioIdx) { speaker.reset() }
    // 주행이 끝나면 마무리 멘트를 한 번 말한다 (쿨다운과 무관). 같은 분류가 이어지면 변형을 번갈아 쓴다.
    var closingCount by remember { mutableIntStateOf(0) }
    // 차가 멈춘 상태인가: 시연은 실제 주행이 아니므로 항상 true, 실시간은 마지막 속도가 거의 0일 때.
    val stopped = !live || (liveSpeed ?: 0f) < 1f
    var closingText by remember(live, scenarioIdx) { mutableStateOf<String?>(null) }
    var closingSpoken by remember(live, scenarioIdx) { mutableStateOf(false) }
    LaunchedEffect(finished, live, scenarioIdx) {
        if (finished && shown.size >= 2 && closingText == null) {
            closingText = ClosingMessage.compose(report, emotion, closingCount++).also { lastLine = it }
        }
    }
    // 마무리 멘트는 확정되고 차가 멈춘 뒤에 "주행 후 보고"로 한 번만 말한다 (달리는 중에 확정되면 멈출 때까지 기다린다).
    LaunchedEffect(closingText, stopped, voiceOn) {
        val text = closingText ?: return@LaunchedEffect
        if (closingSpoken || !stopped || !voiceOn) return@LaunchedEffect
        closingSpoken = true
        sink.speakTripReport(text, "nunti-closing-${System.currentTimeMillis()}", emotion)
    }
    // 일시저장 안내: 이유와 저장 사실을 한 번 말한다 (마무리 멘트는 하지 않는다). 같은 이유로는 다시 말하지 않는다.
    var pauseSpokenFor by remember(live, scenarioIdx) { mutableStateOf<Readiness?>(null) }
    LaunchedEffect(paused, readiness, stopped, voiceOn) {
        if (!paused) { pauseSpokenFor = null; return@LaunchedEffect }
        val text = TripLifecycle.pauseNotice(readiness) ?: return@LaunchedEffect
        lastLine = text
        if (pauseSpokenFor == readiness || !stopped || !voiceOn) return@LaunchedEffect
        pauseSpokenFor = readiness
        sink.speakTripReport(text, "nunti-pause-${System.currentTimeMillis()}", Emotion.NEUTRAL)
    }
    // 점수 확인용 로그: 항목별 점수·기어·상태를 한 줄로 남긴다 (adb logcat -s NuntiScore).
    LaunchedEffect(report, status) {
        Log.d("NuntiScore", "status=$status ready=$readiness total=${report.total?.let { "%.1f".format(it) }} cov=${"%.2f".format(report.coverage)} " +
            "moving=${report.movingSeconds}s gear=${shown.lastOrNull { it.gear != null }?.gear} " +
            "last=[v=${shown.last().speedKmh?.let { "%.1f".format(it) }} steer=${shown.last().steeringDeg?.let { "%.0f".format(it) }} brake=${shown.last().brakePressed} door=${shown.last().doorOpen}] " +
            "items=" + report.items.joinToString(",") { "${it.item.name}=${it.score?.let { v -> "%.0f".format(v) } ?: "-"}" } +
            " events=" + report.events.joinToString(",") { "${it.kind.name}@${it.tMs / 1000}" })
    }

    // 서버 저장: 사용자가 켠 경우에만(= 동의) 샘플과 점수를 서버로 보낸다. 서버 주소·토큰은 기기의 sync-config.json 에서 읽는다.
    val syncConfig = remember { SyncConfig.load(File(context.filesDir, "sync-config.json")) }
    var saveOn by remember { mutableStateOf(false) }
    val sync = remember(saveOn, live, scenarioIdx) {
        if (saveOn && syncConfig != null) {
            TelemetrySync(File(context.filesDir, "telemetry-outbox"), syncConfig, if (live) SourceTag.LIVE else SourceTag.DEMO)
        } else null
    }
    DisposableEffect(sync) { onDispose { sync?.close() } }
    var syncStatus by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(sync) {
        while (sync != null) {
            val st = sync.status(); val (samples, scores) = sync.recorder.counts()
            syncStatus = "서버: 샘플 $samples · 점수 $scores · 전송 ${st.sent} · 대기 ${st.pending}" +
                (if (st.blocked) " · 인증 필요" else "") + (st.lastError?.let { " · $it" } ?: "")
            delay(1000)
        }
        syncStatus = null
    }
    LaunchedEffect(sync, live, scenarioIdx, cursor, liveSamples.size) {
        // 실시간 모드에서 아직 한 번도 읽지 못했을 때의 자리표시 샘플은 기록하지 않는다.
        if (sync != null && !(live && liveSamples.isEmpty())) sync.recorder.onUpdate(shown, report, finished)
    }
    // 확정된 여정의 최종 결과(점수·커버리지·마무리 멘트·근거 사건)를 한 번 보낸다. 일시저장 중에는 마무리 멘트가 없어 보내지 않는다.
    LaunchedEffect(sync, closingText) {
        val text = closingText ?: return@LaunchedEffect
        if (finished) sync?.recorder?.finish(report, text)
    }

    val currentGear = shown.lastOrNull { it.gear != null }?.gear

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Row(Modifier.fillMaxSize().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Column(Modifier.width(260.dp).fillMaxHeight().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                NuntiCard(emotion, report, status)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = !live, onClick = { live = false }, label = { Text("시연") })
                    FilterChip(selected = live, onClick = { live = true }, label = { Text("실시간") })
                    FilterChip(selected = voiceOn, onClick = { voiceOn = !voiceOn }, label = { Text("음성") })
                }
                FilterChip(selected = saveOn, enabled = syncConfig != null, onClick = { saveOn = !saveOn },
                    label = { Text("서버 저장 (동의)", fontSize = 11.sp, maxLines = 1) })
                if (syncConfig == null) Text("서버 설정 없음 (sync-config.json)", color = Muted, fontSize = 11.sp)
                syncStatus?.let { Text(it, fontSize = 11.sp, color = Muted) }
                if (voiceOn) Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    val voices = listOf<String?>(null) + ai.nunti.tts.PleosSpeakers.KOREAN
                    voices.chunked(3).forEach { rowVoices ->
                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            rowVoices.forEach { id ->
                                FilterChip(selected = speakerId == id, onClick = { speakerId = id },
                                    label = { Text(id ?: "기본", fontSize = 11.sp, maxLines = 1) })
                            }
                        }
                    }
                }
                if (voiceOn) Button(onClick = {
                    val samples = listOf("안녕하세요, 눈티예요. 오늘도 안전하게 같이 가요.", "앗, 방금은 조금 급했어요. 천천히 가요.", "휴, 이제 좀 안심돼요. 잘하고 있어요!")
                    sampleIdx = (sampleIdx + 1) % samples.size
                    sink.speak(samples[sampleIdx], "nunti-sample-${System.currentTimeMillis()}", ai.nunti.score.Emotion.NEUTRAL)
                    lastLine = samples[sampleIdx]
                }) { Text("목소리 듣기", fontSize = 12.sp) }
                lastLine?.let { Text("눈티: $it  [${lastResult ?: "대기"}]", fontSize = 12.sp) }
                if (live) {
                    // 신호별 수신 값은 진단용이라 접어 둔다 (점수 카드와 겹쳐 보이고 아래 버튼을 밀어내서).
                    FilterChip(selected = showSignals, onClick = { showSignals = !showSignals },
                        label = { Text("수신 신호 ${received.count { it.value != null }}/${received.size}", fontSize = 11.sp, maxLines = 1) })
                    if (showSignals) received.forEach { Text("${it.label}: ${it.value ?: "미수신"}", fontSize = 12.sp, color = if (it.value == null) Warn else Good) }
                } else Text("시연 데이터 (실제 Pleos 수신값 아님)", color = Muted, fontSize = 12.sp)
                if (!live) Scenarios.all.forEachIndexed { i, sc ->
                    FilterChip(
                        selected = i == scenarioIdx,
                        onClick = { scenarioIdx = i; cursor = 0; playing = true },
                        label = { Text(sc.name) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                if (!live) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { playing = !playing }) { Text(if (playing) "일시정지" else "재생") }
                        Button(onClick = { cursor = last }) { Text("끝까지") }
                    }
                    Text("경과 ${cursor / 60}분 ${cursor % 60}초 / ${last / 60}분", color = Muted, fontSize = 12.sp)
                } else {
                    Text("경과 ${liveSamples.size}초", color = Muted, fontSize = 12.sp)
                    Button(enabled = !liveEndRequested && liveSamples.size >= 2, onClick = { liveEndRequested = true }) {
                        Text(if (paused) "일시저장 중" else "주행 종료")
                    }
                }
            }
            Column(Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    report.areas.forEach { AreaCard(it, Modifier.weight(1f)) }
                }
                if (paused) PausedBanner(readiness)
                WindowBars(report)
                GearRow(report, currentGear)
                // 후진 속도는 후진 기어(R)일 때만 보여 준다. 그 외에는 항목 자체를 숨긴다.
                report.items
                    .filter { it.item != ai.nunti.score.Item.REVERSE_SPEED || currentGear == ai.nunti.score.Gear.R }
                    .forEach { ItemRow(it) }
                EventLog(report)
            }
        }
    }
}

@Composable
private fun NuntiCard(emotion: Emotion, report: ScoreReport, status: TripStatus) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(MaterialTheme.colorScheme.surfaceVariant).padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        NuntiFace(emotion)
        Text("눈티 · ${emotion.label}", fontWeight = FontWeight.Bold)
        Text(emotion.line, fontSize = 13.sp)
        Spacer(Modifier.height(8.dp))
        if (status == TripStatus.PAUSED) {
            Text("평가 대기", fontSize = 28.sp, fontWeight = FontWeight.Bold, color = Muted) // 확정 전 점수를 숫자로 보여 주지 않는다
        } else Text(fmt(report.total), fontSize = 40.sp, fontWeight = FontWeight.Bold, color = scoreColor(report.total))
        Text(
            when (status) {
                TripStatus.FINISHED -> "최종 주행 점수"
                TripStatus.PAUSED -> "일시저장 · 아직 확정 아님"
                TripStatus.DRIVING -> "현재까지 점수"
            },
            fontSize = 12.sp, color = Muted,
        )
        Text("평가 범위 ${(report.coverage * 100).toInt()}%", fontSize = 12.sp, color = if (report.coverage < 1f) Warn else Muted)
    }
}

@Composable
private fun AreaCard(a: AreaResult, modifier: Modifier) {
    Column(
        modifier.clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.surfaceVariant).padding(12.dp),
    ) {
        Text(a.area.label, fontSize = 12.sp, color = Muted)
        Text(fmt(a.score), fontSize = 24.sp, fontWeight = FontWeight.Bold, color = scoreColor(a.score))
        Text(
            if (a.points != null) "%.1f / %d점".format(a.points, a.area.maxPoints) else "배점 ${a.area.maxPoints}점 제외",
            fontSize = 11.sp, color = Muted,
        )
    }
}

@Composable
private fun WindowBars(report: ScoreReport) {
    Column {
        Text("구간별 종합 (1분) — 회복 확인", fontSize = 12.sp, color = Muted)
        Row(Modifier.fillMaxWidth().height(48.dp), horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.Bottom) {
            report.windowOverall.forEach { s ->
                Box(
                    Modifier.weight(1f).height(((s ?: 6f) / 100f * 48f).dp)
                        .clip(RoundedCornerShape(3.dp)).background(scoreColor(s).copy(alpha = if (s == null) 0.3f else 1f)),
                )
            }
        }
    }
}

/** 일시저장 중임을 알리는 안내. 이유(정차/신호 부족)별로 문구가 다르다. */
@Composable
private fun PausedBanner(readiness: Readiness) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Warn.copy(alpha = 0.2f)).padding(12.dp),
    ) {
        Text("일시저장 중 — 아직 점수를 확정하지 않았어요", fontWeight = FontWeight.Bold, fontSize = 13.sp)
        Text(
            (readiness.notices.firstOrNull() ?: "") + " 신호가 충분히 들어오면 이어서 평가하고 마무리해요.",
            fontSize = 12.sp, color = Muted,
        )
    }
}

/** 기어(P/R/N/D)별 시간과 현재 기어. 후진 기어에 들어간 동안은 R 칸을 강조한다. */
@Composable
private fun GearRow(report: ScoreReport, current: ai.nunti.score.Gear?) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            when {
                report.gears.isEmpty() -> "기어별 시간 — 기어 신호 없음"
                current == ai.nunti.score.Gear.R -> "기어별 시간 — 지금 후진 중"
                else -> "기어별 시간 — 현재 ${current?.name ?: "-"}"
            },
            fontSize = 12.sp, color = if (current == ai.nunti.score.Gear.R) Warn else Muted,
        )
        if (report.gears.isNotEmpty()) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            report.gears.forEach { g ->
                val active = g.gear == current
                Column(
                    Modifier.weight(1f).clip(RoundedCornerShape(10.dp))
                        .background(if (active) (if (g.gear == ai.nunti.score.Gear.R) Warn else Good).copy(alpha = 0.25f) else MaterialTheme.colorScheme.surfaceVariant)
                        .padding(8.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(g.gear.name, fontWeight = FontWeight.Bold)
                    Text(if (g.seconds >= 60) "${g.seconds / 60}분 ${g.seconds % 60}초" else "${g.seconds}초", fontSize = 11.sp, color = Muted)
                }
            }
        }
    }
}

@Composable
private fun ItemRow(r: ItemResult) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(r.item.label, fontWeight = FontWeight.Medium)
            Text("${r.item.area.label} · ${r.basis.text}", fontSize = 11.sp, color = Muted)
        }
        Text(fmt(r.score), fontWeight = FontWeight.Bold, color = scoreColor(r.score))
    }
}

@Composable
private fun EventLog(report: ScoreReport) {
    if (report.events.isEmpty()) return
    Column {
        Text("감지된 순간 사건 (기록은 회복 후에도 유지)", fontSize = 12.sp, color = Muted)
        report.events.forEach {
            Text("${it.tMs / 60000}:%02d  ${it.label}".format(it.tMs / 1000 % 60), fontSize = 13.sp)
        }
    }
}
