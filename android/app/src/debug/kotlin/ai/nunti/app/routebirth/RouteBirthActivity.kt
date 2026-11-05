package ai.nunti.app.routebirth

import ai.nunti.app.journey.JourneyCarGate
import ai.nunti.app.journey.JourneyGate
import ai.nunti.avatar.RouteBornCompanion
import ai.nunti.emotion.Emotion
import ai.nunti.tts.*
import ai.nunti.voice.AndroidVoiceSession
import ai.nunti.voice.AndroidLocalAudioPlayer
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.*
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.UUID
import java.util.concurrent.Executors

/** One APK, fresh route input, runtime local synthesis. Never calls external APIs. */
class RouteBirthActivity : ComponentActivity() {
    private val main = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private val bridge = BornBridge()
    private val emulator get() = Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")
    private val automotive by lazy { packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE) }
    private var namespace = "route-birth"
    private lateinit var store: BornStore
    private var car: JourneyCarGate? = null
    private var foreground by mutableStateOf(false)
    private var gate by mutableStateOf(JourneyGate("CONNECTING", VehicleMotion.UNKNOWN, false, false, true, 0))
    private var blocked by mutableStateOf(false)
    private var quiet by mutableStateOf(false)
    private var destination by mutableStateOf("")
    private var traits by mutableStateOf("")
    private var purpose by mutableStateOf("")
    private var route by mutableStateOf<List<Offset>>(emptyList())
    private var artifact by mutableStateOf<BornArtifact?>(null)
    private var selected by mutableStateOf<String?>(null)
    private var state by mutableStateOf("INPUT")
    private var error by mutableStateOf<String?>(null)
    private var message by mutableStateOf("여행의 선에서, 오늘의 작은 동반자가 태어나요.")
    private var lastSpeech by mutableStateOf("")
    private var arrived by mutableStateOf(false)
    private var collected by mutableStateOf<List<String>>(emptyList())
    private var birthToken by mutableIntStateOf(0)
    private var emotion by mutableStateOf(Emotion.NEUTRAL)
    private var voices: LocalVoiceCatalog? = null
    private var voice: AndroidVoiceSession? = null
    private var busy = false
    private var lastGate = ""
    private var pendingIntent: Intent? = null
    private val ticker = object : Runnable {
        override fun run() {
            if (!foreground) return
            car?.refresh(); refresh()
            if (state == "GENERATING" && !busy) selected?.let { fetch(it, false) }
            main.postDelayed(this, 750)
        }
    }
    private fun event(kind: String, values: Map<String, Any?> = emptyMap()) {
        val json = JSONObject().put("kind", kind).put("at", Instant.now().toString()).put("namespace", namespace)
        values.forEach { (key, value) -> json.put(key, JSONObject.wrap(value) ?: JSONObject.NULL) }
        Log.i("NuntiRouteBirth", json.toString())
        val file = filesDir.resolve("route-born-events.jsonl")
        if (file.length() > 4000000) file.renameTo(filesDir.resolve("route-born-events.previous.jsonl"))
        file.appendText(json.toString() + "\n")
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (emulator && intent.getStringExtra("rb_namespace") == "validation") namespace = "route-birth-validation"
        pendingIntent = intent
        try {
            store = BornStore(filesDir.resolve(namespace))
            collected = store.collected()
            if (automotive) {
                val permissions = arrayOf("android.car.permission.CAR_POWERTRAIN", "android.car.permission.CAR_SPEED")
                    .filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
                if (permissions.isNotEmpty()) requestPermissions(permissions.toTypedArray(), 273)
                car = JourneyCarGate(this) { refresh() }
            }
            store.state.optString("selected").takeIf { it.isNotEmpty() }?.let { restore(it) }
        } catch (e: Exception) { fail(e) }
        setContent { Screen() }
    }
    private fun permitted() = foreground && gate.parked && gate.knownUX && !gate.requiresDO && !blocked
    private fun refresh() {
        gate = if (automotive) car?.observe() ?: JourneyGate("ACTUAL_CAR_SERVICE", VehicleMotion.UNKNOWN, false, false, true, 0)
            else JourneyGate("NON_AUTOMOTIVE_LAB", VehicleMotion.PARKED, true, true, false, 0)
        val audio = getSystemService(AUDIO_SERVICE) as AudioManager
        val quietNow = quiet && audio.mode == AudioManager.MODE_NORMAL && !audio.isMusicActive
        selected?.let { id -> voice?.updateContext(PlaybackContext(id, phase(), SystemClock.elapsedRealtime(), true,
            foreground, false, gate.motion, gate.knownUX, gate.requiresDO, gate.activeRestrictions, Permission.DENIED,
            if (permitted()) Permission.ALLOWED else Permission.DENIED,
            if (quietNow) AudioActivity.QUIET else AudioActivity.UNKNOWN,
            if (quietNow) AudioActivity.QUIET else AudioActivity.UNKNOWN,
            if (quietNow) AudioActivity.QUIET else AudioActivity.UNKNOWN)) }
        val fingerprint = listOf(gate, foreground, blocked, quiet, audio.mode, audio.isMusicActive).toString()
        if (lastGate != fingerprint) {
            lastGate = fingerprint
            event("RB_GATE", mapOf("source" to gate.source, "parked" to gate.parked, "motion" to gate.motion.name,
                "foreground" to foreground, "visible" to permitted(), "knownUX" to gate.knownUX,
                "requiresDO" to gate.requiresDO, "quietConfirmed" to quiet, "quietAccepted" to quietNow))
        }
    }
    private fun phase() = if (arrived) TripPhase.POST_TRIP else TripPhase.PRE_TRIP
    private fun fail(e: Exception) {
        error = e.message ?: "GENERATION_FAILED"; state = "FAILED"; voice?.stop()
        event("RB_ERROR", mapOf("requestId" to selected, "reason" to error))
    }
    private fun requestFromInput(): JSONObject {
        require(destination.isNotBlank() && destination.length <= 60) { "목적지를 입력해 주세요." }
        require(traits.length <= 240 && purpose.length <= 120) { "설명을 조금 짧게 입력해 주세요." }
        require(route.size in 2..512) { "경로를 두 점 이상 이어 그려 주세요." }
        return JSONObject().put("requestId", UUID.randomUUID().toString()).put("destination",
            JSONObject().put("name", destination.trim()).put("traits", traits.trim())).put("purpose", purpose.trim())
            .put("route", JSONObject().put("points", JSONArray(route.map { listOf(it.x.toDouble(), it.y.toDouble()) })))
    }
    private fun submit(input: JSONObject) {
        refresh(); if (!permitted() || busy) return
        try {
            val id = rbUuid(input.getString("requestId"))
            voice?.close(); voice = null; voices = null
            store.input(input); selected = id; artifact = null; arrived = false; error = null; state = "GENERATING"
            destination = input.getJSONObject("destination").getString("name")
            traits = input.getJSONObject("destination").getString("traits"); purpose = input.getString("purpose")
            route = input.getJSONObject("route").getJSONArray("points").let { p -> (0 until p.length()).map { i ->
                p.getJSONArray(i).let { Offset(it.getDouble(0).toFloat(), it.getDouble(1).toFloat()) } } }
            event("RB_SUBMITTED", mapOf("requestId" to id, "pointCount" to route.size))
            event("RB_STATE", mapOf("requestId" to id, "state" to "GENERATING"))
            fetch(id, true, input)
        } catch (e: Exception) { fail(e) }
    }
    private fun fetch(id: String, post: Boolean, input: JSONObject? = null) {
        if (busy) return
        busy = true
        io.execute {
            try {
                val response = if (post) bridge.submit(input ?: store.input(id)) else bridge.poll(id)
                require(response.getString("requestId") == id)
                val responseState = response.getString("state")
                require(responseState in listOf("GENERATING", "READY", "FAILED"))
                val parsed = if (response.has("artifact") && !response.isNull("artifact")) BornArtifact.parse(response.getJSONObject("artifact"), id, store.input(id)) else null
                require(responseState != "READY" || parsed?.ready == true)
                val catalog = if (responseState == "READY") bridge.install(parsed!!, store.audio(id)) else null
                parsed?.let { store.put(it) }
                main.post {
                    busy = false
                    if (selected != id || isDestroyed) return@post
                    try {
                        val first = artifact == null && parsed != null
                        if (parsed != null) artifact = parsed
                        if (first) {
                            birthToken++
                            event("RB_VISUAL", mapOf("requestId" to id, "characterId" to parsed!!.characterId,
                                "inputSha256" to parsed.json.getString("inputSha256"), "visualSha256" to parsed.visualSha))
                        }
                        if (state != responseState) event("RB_STATE", mapOf("requestId" to id, "state" to responseState))
                        state = responseState
                        if (responseState == "FAILED") error = response.optString("error", "PC_GENERATION_FAILED")
                        if (catalog != null) bindVoice(parsed!!, catalog)
                    } catch (e: Exception) { fail(e) }
                }
            } catch (e: Exception) { main.post { busy = false; if (selected == id && !isDestroyed) fail(e) } }
        }
    }
    private fun bindVoice(value: BornArtifact, catalog: LocalVoiceCatalog) {
        if (voice != null && voices?.clips?.firstOrNull()?.characterId == value.characterId) return
        voice?.close(); voices = catalog
        voice = AndroidVoiceSession(applicationContext, profiles = catalog.profiles,
            providerFactory = { attributes, lane -> LocalFileTtsProvider(catalog) { AndroidLocalAudioPlayer(attributes, lane) } }) { speech ->
            lastSpeech = when (speech.status) {
                SpeechStatus.QUEUED -> "목소리를 준비하고 있어요."
                SpeechStatus.STARTED -> "${value.name}가 이야기하고 있어요."
                SpeechStatus.COMPLETED -> "다 들었어요."
                SpeechStatus.CANCELLED -> "재생을 멈췄어요."
                SpeechStatus.REJECTED -> if (speech.reason == "REPEATED_TEXT") "같은 문장은 잠시 뒤 다시 들을 수 있어요." else "주차와 음성 시험 상태를 확인해 주세요."
                SpeechStatus.FAILED -> "음원을 재생하지 못했어요."
            }
            event("RB_SPEECH", mapOf("requestId" to speech.requestId, "tripId" to speech.tripId, "status" to speech.status.name,
                "reason" to speech.reason, "profileId" to speech.appliedVoice?.profileId, "providerId" to speech.providerId))
        }.also { it.beginTrip(value.requestId) }
        refresh()
        message = "${value.name}가 준비됐어요. 이번 여행을 함께해요."
        event("RB_READY", mapOf("requestId" to value.requestId, "characterId" to value.characterId,
            "visualSha256" to value.visualSha, "bindingId" to value.json.getJSONObject("voice").getString("bindingId")))
    }
    private fun restore(id: String) {
        try {
            voice?.close(); voice = null; voices = null; store.select(id); selected = id
            val input = store.input(id)
            destination = input.getJSONObject("destination").getString("name"); traits = input.getJSONObject("destination").getString("traits"); purpose = input.getString("purpose")
            route = input.getJSONObject("route").getJSONArray("points").let { p -> (0 until p.length()).map { i -> p.getJSONArray(i).let { Offset(it.getDouble(0).toFloat(), it.getDouble(1).toFloat()) } } }
            artifact = store.get(id); arrived = store.record(id).getBoolean("arrived"); error = null
            state = if (artifact?.ready == true) "LOADING" else "GENERATING"
            event("RB_RESTORED", mapOf("requestId" to id, "characterId" to artifact?.characterId, "visualSha256" to artifact?.visualSha,
                "arrived" to arrived, "collected" to collected.size, "automaticSpeech" to false))
            if (artifact?.ready == true) {
                busy = true
                io.execute {
                    try {
                        val value = store.get(id)!!; val catalog = bridge.install(value, store.audio(id))
                        main.post { busy = false; if (selected == id && !isDestroyed) { state = "READY"; bindVoice(value, catalog) } }
                    } catch (e: Exception) { main.post { busy = false; fail(e) } }
                }
            }
        } catch (e: Exception) { fail(e) }
    }
    private fun speak(category: String) {
        refresh(); if (!permitted() || error != null || state != "READY" || !quiet) return
        val value = artifact ?: return
        val clip = voices?.clips?.singleOrNull { it.clipId == "${value.characterId}-$category" } ?: return
        val request = "rb-${UUID.randomUUID()}"; val epoch = System.currentTimeMillis(); val emotionId = "rb-emotion-${UUID.randomUUID()}"
        val snapshot = EmotionSnapshot(emotionId, value.requestId, value.characterId, ai.nunti.tts.Emotion.valueOf(emotion.name), epoch)
        event("RB_SPEECH_REQUEST", mapOf("requestId" to request, "tripId" to value.requestId, "clipId" to clip.clipId,
            "characterId" to value.characterId, "profileId" to clip.profileId, "audioSha256" to clip.audioSha256))
        voice?.submit(ApprovedSpeech(SpeechRequest(request, value.requestId, value.characterId, clip.text, snapshot.emotion,
            clip.profileId, phase(), Priority.NORMAL, epoch, epoch + 25000, ContentSource.USER_INITIATED, emotionId),
            AvatarVoiceInput(value.characterId, value.characterId, clip.profileId), snapshot, true))
    }
    private fun arrive() {
        if (!permitted() || state != "READY") return
        voice?.stop(); selected?.let { store.arrive(it) }; arrived = true; emotion = Emotion.JOYFUL; refresh()
        event("RB_ARRIVED", mapOf("requestId" to selected, "characterId" to artifact?.characterId))
    }
    private fun collect() {
        if (!permitted() || !arrived || state != "READY") return
        selected?.let { store.collect(it) }; collected = store.collected(); message = "오늘의 동반자를 보관했어요."
        event("RB_SAVED", mapOf("requestId" to selected, "characterId" to artifact?.characterId, "count" to collected.size))
    }
    private fun act(value: Intent) {
        if (!emulator) return
        if (value.getBooleanExtra("confirm_quiet_test", false)) quiet = true
        when (value.getStringExtra("rb_action")) {
            "submit" -> runCatching { submit(JSONObject(value.getStringExtra("rb_input_json") ?: "")) }.onFailure { fail(Exception(it)) }
            "retry" -> selected?.let { fetch(it, true) }
            "poll" -> selected?.let { fetch(it, false) }
            "restore" -> value.getStringExtra("rb_request_id")?.let { restore(it) }
            "greeting", "common", "arrival" -> speak(value.getStringExtra("rb_action")!!)
            "arrive" -> arrive()
            "save" -> collect()
            "stop" -> voice?.stop()
            "block" -> { blocked = true; refresh() }
            "unblock" -> { blocked = false; refresh() }
            "verify_boundaries" -> artifact?.takeIf { it.ready }?.let { current ->
                try { val results = RouteBirthBoundaryChecks.run(current, store.input(current.requestId), cacheDir)
                    event("RB_BOUNDARIES", mapOf("passed" to results.length(), "checks" to results))
                } catch (e: Exception) { fail(e) }
            }
            "clear_input" -> { destination = ""; route = emptyList() }
        }
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); act(intent) }
    override fun onResume() {
        super.onResume(); foreground = true; refresh(); main.removeCallbacks(ticker); main.post(ticker)
        pendingIntent?.let { pendingIntent = null; act(it) }
    }
    override fun onStop() {
        foreground = false; quiet = false; main.removeCallbacks(ticker); refresh(); voice?.onBackground(); super.onStop()
    }
    override fun onDestroy() { main.removeCallbacks(ticker); voice?.close(); car?.close(); io.shutdown(); super.onDestroy() }

    @Composable private fun Action(label: String, enabled: Boolean = true, primary: Boolean = false, action: () -> Unit) {
        BasicText(label, Modifier.background(if (primary) Color(0xFF315D55) else Color(0xFFE8EEE5), RoundedCornerShape(14.dp))
            .clickable(enabled = enabled, role = Role.Button, onClick = action).padding(horizontal = 15.dp, vertical = 12.dp),
            style = TextStyle(fontSize = 14.sp, color = if (!enabled) Color(0xFF9AA59F) else if (primary) Color.White else Color(0xFF315D55)))
    }
    @Composable private fun Input(label: String, value: String, change: (String) -> Unit) {
        Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
            BasicText(label, style = TextStyle(fontSize = 13.sp, color = Color(0xFF5A776B)))
            BasicTextField(value, change, Modifier.fillMaxWidth().background(Color.White, RoundedCornerShape(12.dp))
                .border(1.dp, Color(0xFFD9E3D6), RoundedCornerShape(12.dp)).padding(13.dp), singleLine = true,
                textStyle = TextStyle(fontSize = 15.sp, color = Color(0xFF28433C)))
        }
    }
    @Composable private fun RouteInput() {
        Canvas(Modifier.fillMaxWidth().height(185.dp).background(Color(0xFFFEFDF7), RoundedCornerShape(18.dp))
            .border(1.dp, Color(0xFFD6E3D6), RoundedCornerShape(18.dp)).pointerInput(permitted()) {
                if (permitted()) detectDragGestures(onDragStart = { start ->
                    route = listOf(Offset((start.x / size.width).coerceIn(0f, 1f), (start.y / size.height).coerceIn(0f, 1f)))
                }) { change, _ ->
                    change.consume()
                    val point = Offset((change.position.x / size.width).coerceIn(0f, 1f), (change.position.y / size.height).coerceIn(0f, 1f))
                    if (route.size < 512 && (route.isEmpty() || (point - route.last()).getDistance() > .003f)) route = route + point
                }
            }) {
            for (x in 1..7) for (y in 1..4) drawCircle(Color(0xFFDDE6DC), 1.6f, Offset(size.width * x / 8f, size.height * y / 5f))
            if (route.size >= 2) {
                val path = Path().apply { moveTo(route.first().x * size.width, route.first().y * size.height)
                    route.drop(1).forEach { lineTo(it.x * size.width, it.y * size.height) } }
                drawPath(path, Color(0xFF629F92), style = Stroke(6f))
                drawCircle(Color(0xFF315D55), 7f, Offset(route.first().x * size.width, route.first().y * size.height))
                drawCircle(Color(0xFFD8AA73), 8f, Offset(route.last().x * size.width, route.last().y * size.height))
            }
        }
    }
    @Composable private fun Screen() {
        val progress = remember { Animatable(1f) }
        val visible = permitted()
        var playedToken by remember { mutableIntStateOf(0) }
        LaunchedEffect(birthToken, visible) {
            if (birthToken > playedToken && visible) {
                playedToken = birthToken
                progress.snapTo(0f)
                event("RB_ANIMATION", mapOf("requestId" to selected, "stage" to "ROUTE_TRACE"))
                progress.animateTo(.35f, tween(1700, easing = LinearEasing))
                event("RB_ANIMATION", mapOf("requestId" to selected, "stage" to "ROUTE_TO_BODY"))
                progress.animateTo(.8f, tween(2100, easing = LinearEasing))
                event("RB_ANIMATION", mapOf("requestId" to selected, "stage" to "FACE_REVEAL"))
                progress.animateTo(1f, tween(1000))
                event("RB_ANIMATION", mapOf("requestId" to selected, "stage" to "COMPLETE"))
            } else progress.snapTo(1f)
        }
        Column(Modifier.fillMaxSize().background(Color(0xFFF5F4EC)).padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    BasicText("NUNTI / ROUTE COMPANION", style = TextStyle(fontSize = 12.sp, color = Color(0xFF789183)))
                    BasicText("여행의 선이, 나의 동반자로", style = TextStyle(fontSize = 27.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF29463D)))
                }
                Action(if (quiet) "음성 시험 켜짐" else "음성 시험 시작", visible && state == "READY", !quiet) { quiet = true; refresh() }
            }
            if (!visible) {
                BasicText("주차 상태와 화면 사용 허가를 확인하고 있어요.", style = TextStyle(fontSize = 18.sp))
                return@Column
            }
            Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                Column(Modifier.width(310.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Input("어디로 떠나나요?", destination) { if (it.length <= 60) destination = it }
                    Input("그곳의 느낌", traits) { if (it.length <= 240) traits = it }
                    Input("이번 여행의 목적", purpose) { if (it.length <= 120) purpose = it }
                    BasicText("경로를 이어 그려 주세요", style = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Medium, color = Color(0xFF315D55)))
                    RouteInput()
                    BasicText("외부 지도 연결 없이 직접 그린 선을 사용해요.", style = TextStyle(fontSize = 12.sp, color = Color(0xFF7D8C80)))
                    Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                        Action("동반자 만나기", !busy && state != "GENERATING", true) { try { submit(requestFromInput()) } catch (e: Exception) { error = e.message } }
                        Action("지우기", state != "GENERATING") { route = emptyList() }
                    }
                    if (collected.isNotEmpty()) {
                        BasicText("간직한 동반자 ${collected.size}", style = TextStyle(fontSize = 14.sp, color = Color(0xFF315D55)))
                        collected.forEach { id -> val saved = remember(id) { store.get(id) }
                            Action(saved?.name ?: "보관한 동반자", !busy) { restore(id) }
                        }
                    }
                }
                Column(Modifier.weight(1f).fillMaxHeight().background(Color(0xFFFFFEF8), RoundedCornerShape(28.dp)).padding(22.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    val value = artifact
                    BasicText(if (value == null) "아직 만나지 않은 작은 친구" else value.name,
                        style = TextStyle(fontSize = 25.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF315D55)))
                    Box(Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                        if (value != null) RouteBornCompanion(value.spec, progress.value, emotion, Modifier.size(360.dp))
                        else BasicText(if (state == "GENERATING") "여행의 선을 살펴보고 있어요…" else "경로를 그리면 여기서 태어나요.", style = TextStyle(fontSize = 17.sp, color = Color(0xFF9BA78C)))
                    }
                    BasicText(when { error != null -> if (error!!.any { it in '가'..'힣' }) error!! else "준비를 마치지 못했어요. PC 실행 상태를 확인하고 다시 시도해 주세요."
                        state == "GENERATING" -> "외형에서 느껴지는 성격에 맞춰 목소리를 만들고 있어요."
                        state == "READY" -> value!!.json.getJSONObject("voice").getString("description").substringBefore(" Sohee")
                        else -> message }, style = TextStyle(fontSize = 14.sp, color = Color(0xFF6A7F70)))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Action("인사 듣기", state == "READY" && quiet) { speak("greeting") }
                        Action("응원 듣기", state == "READY" && quiet) { speak("common") }
                        Action("중지") { voice?.stop() }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Action(if (arrived) "도착 대사" else "도착했어요", state == "READY") { if (arrived) speak("arrival") else arrive() }
                        Action("동반자 보관", state == "READY" && arrived) { collect() }
                        if (state == "FAILED") Action("다시 연결", selected != null && !busy) { error = null; state = "GENERATING"; selected?.let { fetch(it, true) } }
                    }
                    BasicText(lastSpeech.ifEmpty { if (state == "GENERATING") "외형을 만드는 동안 음성 준비도 이어집니다." else message },
                        style = TextStyle(fontSize = 12.sp, color = Color(0xFF7A8D78)))
                }
            }
        }
    }
}
