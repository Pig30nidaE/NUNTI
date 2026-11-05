package ai.nunti.app.generated

import ai.nunti.app.routebirth.rbUuid

import ai.nunti.app.journey.JourneyCarGate
import ai.nunti.app.journey.JourneyGate
import ai.nunti.avatar.GeneratedCompanion
import ai.nunti.avatar.GeneratedPoint
import androidx.compose.ui.graphics.asImageBitmap
import android.graphics.Bitmap
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.UUID
import java.util.concurrent.Executors

/** Native v2 host. API credentials remain on the server; fixture origin stays visible. */
class GeneratedCompanionActivity : ComponentActivity() {
    private val main = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private val bridge by lazy { GeneratedBridge(GeneratedConnection(filesDir.resolve("generative-connection.json"))) }
    private val emulator get() = Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")
    private val automotive by lazy { packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE) }
    private var namespace = "generated-companion"
    private lateinit var store: GeneratedStore
    private var car: JourneyCarGate? = null
    private var foreground by mutableStateOf(false)
    private var gate by mutableStateOf(JourneyGate("CONNECTING", VehicleMotion.UNKNOWN, false, false, true, 0))
    private var blocked by mutableStateOf(false)
    private var quiet by mutableStateOf(false)
    private var destination by mutableStateOf("")
    private var traits by mutableStateOf("")
    private var purpose by mutableStateOf("")
    private var route by mutableStateOf<List<Offset>>(emptyList())
    private var artifact by mutableStateOf<GeneratedArtifact?>(null)
    private var bitmap by mutableStateOf<Bitmap?>(null)
    private var mode by mutableStateOf("UNKNOWN")
    private var stage by mutableStateOf("")
    private var followup by mutableStateOf("")
    private var speechMessage by mutableStateOf("")
    private var pendingSpeech: JSONObject? = null
    private var selected by mutableStateOf<String?>(null)
    private var state by mutableStateOf("INPUT")
    private var error by mutableStateOf<String?>(null)
    private var message by mutableStateOf("여행의 선에서, 오늘의 작은 동반자가 태어나요.")
    private var lastSpeech by mutableStateOf("")
    private var arrived by mutableStateOf(false)
    private var collected by mutableStateOf<List<String>>(emptyList())
    private var birthRequestId by mutableStateOf<String?>(null)
    private var preparedBirthRequestId by mutableStateOf<String?>(null)
    private var emotion by mutableStateOf(Emotion.NEUTRAL)
    private var voices: LocalVoiceCatalog? = null
    private var voice: AndroidVoiceSession? = null
    private var localProvider: LocalFileTtsProvider? = null
    private var busy = false
    private var lastGate = ""
    private var pendingIntent: Intent? = null
    private val ticker = object : Runnable {
        override fun run() {
            if (!foreground) return
            car?.refresh(); refresh()
            if (state in listOf("QUEUED", "RUNNING") && !busy) selected?.let { fetch(it, false) }
            else if (state == "READY" && pendingSpeech != null && !busy) fetchSpeech(false)
            main.postDelayed(this, 750)
        }
    }
    private fun event(kind: String, values: Map<String, Any?> = emptyMap()) {
        val json = JSONObject().put("kind", kind).put("at", Instant.now().toString()).put("namespace", namespace)
        values.forEach { (key, value) -> json.put(key, JSONObject.wrap(value) ?: JSONObject.NULL) }
        Log.i("NuntiGenerated", json.toString())
        val file = filesDir.resolve("generated-events.jsonl")
        if (file.length() > 4000000) file.renameTo(filesDir.resolve("generated-events.previous.jsonl"))
        file.appendText(json.toString() + "\n")
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (emulator && intent.getStringExtra("g_namespace") == "validation") namespace = "generated-companion-validation"
        pendingIntent = intent
        try {
            store = GeneratedStore(filesDir.resolve(namespace))
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
            event("GEN_GATE", mapOf("source" to gate.source, "parked" to gate.parked, "motion" to gate.motion.name,
                "foreground" to foreground, "visible" to permitted(), "knownUX" to gate.knownUX,
                "requiresDO" to gate.requiresDO, "quietConfirmed" to quiet, "quietAccepted" to quietNow))
        }
    }
    private fun phase() = if (arrived) TripPhase.POST_TRIP else TripPhase.PRE_TRIP
    private fun fail(e: Exception) {
        error = e.message ?: "GENERATION_FAILED"; state = "FAILED"; voice?.stop()
        event("GEN_ERROR", mapOf("requestId" to selected, "reason" to error))
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
            voice?.close(); voice = null; voices = null; localProvider = null
            store.input(input); selected = id; artifact = null; bitmap = null; birthRequestId = null; preparedBirthRequestId = null; arrived = false; error = null; state = "QUEUED"
            pendingSpeech = null; speechMessage = ""; stage = "PLANNING"; mode = "UNKNOWN"
            destination = input.getJSONObject("destination").getString("name")
            traits = input.getJSONObject("destination").getString("traits"); purpose = input.getString("purpose")
            route = input.getJSONObject("route").getJSONArray("points").let { p -> (0 until p.length()).map { i ->
                p.getJSONArray(i).let { Offset(it.getDouble(0).toFloat(), it.getDouble(1).toFloat()) } } }
            event("GEN_SUBMITTED", mapOf("requestId" to id, "pointCount" to route.size))
            event("GEN_STATE", mapOf("requestId" to id, "state" to "QUEUED"))
            fetch(id, true, input)
        } catch (e: Exception) { fail(e) }
    }
    private fun fetch(id: String, post: Boolean, input: JSONObject? = null) {
        if (busy) return
        busy = true
        io.execute {
            try {
                val response = if (post) bridge.submit(input ?: store.input(id)) else bridge.poll(id)
                require(response.getString("requestId") == id && response.getString("jobId") == id)
                val responseState = response.getString("state")
                require(responseState in listOf("QUEUED", "RUNNING", "READY", "FAILED", "RESULT_UNKNOWN"))
                val responseMode = response.getString("mode")
                require(responseMode in listOf("API", "OFFLINE_FIXTURE"))
                val parsed = if (response.has("artifact") && !response.isNull("artifact")) GeneratedArtifact.parse(response.getJSONObject("artifact"), id, store.input(id)) else null
                require(responseState != "READY" || parsed != null)
                require(parsed == null || parsed.mode == responseMode)
                val media = if (responseState == "READY") bridge.install(parsed!!, store.media(id), store.speeches(id)) else null
                parsed?.let { store.put(it) }
                main.post {
                    busy = false
                    if (selected != id || isDestroyed) return@post
                    try {
                        val first = artifact == null && parsed != null
                        if (parsed != null) artifact = parsed
                        mode = responseMode; stage = response.optString("stage")
                        if (first) {
                            birthRequestId = id
                            event("GEN_VISUAL", mapOf("requestId" to id, "characterId" to parsed!!.characterId,
                                "inputSha256" to parsed.json.getString("inputSha256"), "imageSha256" to parsed.imageSha, "mode" to mode))
                        }
                        if (state != responseState) event("GEN_STATE", mapOf("requestId" to id, "state" to responseState))
                        state = responseState
                        if (responseState in listOf("FAILED", "RESULT_UNKNOWN")) error = response.optString("error", "GENERATION_FAILED")
                        if (media != null) { bitmap = media.bitmap; bindVoice(parsed!!, media.catalog) }
                    } catch (e: Exception) { fail(e) }
                }
            } catch (e: Exception) { main.post { busy = false; if (selected == id && !isDestroyed) fail(e) } }
        }
    }
    private fun bindVoice(value: GeneratedArtifact, catalog: LocalVoiceCatalog) {
        if (voice != null && voices?.clips?.map { it.clipId } == catalog.clips.map { it.clipId }) return
        if (voice != null && voices?.clips?.firstOrNull()?.characterId == value.characterId) {
            requireNotNull(localProvider).updateCatalog(catalog); voices = catalog
            event("GEN_CATALOG_EXPANDED", mapOf("characterId" to value.characterId, "clipCount" to catalog.clips.size,
                "bindingId" to value.bindingId, "queuePreserved" to true))
            return
        }
        voice?.close(); voices = catalog
        voice = AndroidVoiceSession(applicationContext, profiles = catalog.profiles,
            providerFactory = { attributes, lane -> LocalFileTtsProvider(catalog) { AndroidLocalAudioPlayer(attributes, lane) }.also { localProvider = it } }) { speech ->
            lastSpeech = when (speech.status) {
                SpeechStatus.QUEUED -> "목소리를 준비하고 있어요."
                SpeechStatus.STARTED -> "${value.name}가 이야기하고 있어요."
                SpeechStatus.COMPLETED -> "다 들었어요."
                SpeechStatus.CANCELLED -> "재생을 멈췄어요."
                SpeechStatus.REJECTED -> if (speech.reason == "REPEATED_TEXT") "같은 문장은 잠시 뒤 다시 들을 수 있어요." else "주차와 음성 시험 상태를 확인해 주세요."
                SpeechStatus.FAILED -> "음원을 재생하지 못했어요."
            }
            event("GEN_SPEECH", mapOf("requestId" to speech.requestId, "tripId" to speech.tripId, "status" to speech.status.name,
                "reason" to speech.reason, "profileId" to speech.appliedVoice?.profileId, "providerId" to speech.providerId))
        }.also { it.beginTrip(value.requestId) }
        refresh()
        message = "${value.name}가 준비됐어요. 이번 여행을 함께해요."
        event("GEN_READY", mapOf("requestId" to value.requestId, "characterId" to value.characterId,
            "imageSha256" to value.imageSha, "bindingId" to value.bindingId, "mode" to value.mode,
            "clipCount" to catalog.clips.size, "automaticSpeech" to false))
    }
    private fun restore(id: String) {
        try {
            voice?.close(); voice = null; voices = null; localProvider = null; store.select(id); selected = id
            val input = store.input(id)
            destination = input.getJSONObject("destination").getString("name"); traits = input.getJSONObject("destination").getString("traits"); purpose = input.getString("purpose")
            route = input.getJSONObject("route").getJSONArray("points").let { p -> (0 until p.length()).map { i -> p.getJSONArray(i).let { Offset(it.getDouble(0).toFloat(), it.getDouble(1).toFloat()) } } }
            artifact = store.get(id); bitmap = null; birthRequestId = null; preparedBirthRequestId = null; arrived = store.record(id).getBoolean("arrived"); error = null
            pendingSpeech = store.pendingSpeech(id); mode = artifact?.mode ?: "UNKNOWN"
            state = if (artifact != null) "LOADING" else "QUEUED"
            event("GEN_RESTORED", mapOf("requestId" to id, "characterId" to artifact?.characterId, "imageSha256" to artifact?.imageSha,
                "arrived" to arrived, "collected" to collected.size, "automaticSpeech" to false))
            if (artifact != null) {
                busy = true
                io.execute {
                    try {
                        val value = store.get(id)!!; val media = bridge.install(value, store.media(id), store.speeches(id))
                        main.post { busy = false; if (selected == id && !isDestroyed) { bitmap = media.bitmap; state = "READY"; bindVoice(value, media.catalog) } }
                    } catch (e: Exception) { main.post { busy = false; fail(e) } }
                }
            }
        } catch (e: Exception) { fail(e) }
    }
    private fun speak(category: String) {
        refresh(); if (!permitted() || error != null || state != "READY" || !quiet) return
        val value = artifact ?: return
        val clip = if (category == "followup") voices?.clips?.singleOrNull { it.clipId == store.latestSpeechClip(value.requestId) }
            else voices?.clips?.singleOrNull { it.clipId == "${value.characterId}-$category" }
        if (clip == null) return
        val request = "g-${UUID.randomUUID()}"; val epoch = System.currentTimeMillis(); val emotionId = "g-emotion-${UUID.randomUUID()}"
        val snapshot = EmotionSnapshot(emotionId, value.requestId, value.characterId, ai.nunti.tts.Emotion.valueOf(emotion.name), epoch)
        event("GEN_SPEECH_REQUEST", mapOf("requestId" to request, "tripId" to value.requestId, "clipId" to clip.clipId,
            "characterId" to value.characterId, "profileId" to clip.profileId, "audioSha256" to clip.audioSha256))
        voice?.submit(ApprovedSpeech(SpeechRequest(request, value.requestId, value.characterId, clip.text, snapshot.emotion,
            clip.profileId, phase(), Priority.NORMAL, epoch, epoch + 25000, ContentSource.USER_INITIATED, emotionId),
            AvatarVoiceInput(value.characterId, value.characterId, clip.profileId), snapshot, true))
    }
    private fun arrive() {
        if (!permitted() || state != "READY") return
        voice?.stop(); selected?.let { store.arrive(it) }; arrived = true; emotion = Emotion.JOYFUL; refresh()
        event("GEN_ARRIVED", mapOf("requestId" to selected, "characterId" to artifact?.characterId))
    }
    private fun collect() {
        if (!permitted() || !arrived || state != "READY") return
        selected?.let { store.collect(it) }; collected = store.collected(); message = "오늘의 동반자를 보관했어요."
        event("GEN_SAVED", mapOf("requestId" to selected, "characterId" to artifact?.characterId, "count" to collected.size))
    }
    private fun requestSpeech(text: String) {
        if (!permitted() || state != "READY" || busy || pendingSpeech != null) return
        val id = selected ?: return
        if (store.pendingSpeech(id) != null) { speechMessage = "이전 대사의 결과를 먼저 다시 연결해 주세요."; return }
        require(text.isNotBlank() && text.length <= 100) { "대사는 100자 안으로 입력해 주세요." }
        val input = JSONObject().put("requestId", UUID.randomUUID().toString()).put("text", text.trim())
        store.speechInput(id, input); pendingSpeech = input; speechMessage = "같은 목소리로 새 대사를 준비하고 있어요."
        fetchSpeech(true)
    }
    private fun fetchSpeech(post: Boolean) {
        val value = artifact ?: return; val input = pendingSpeech ?: return
        if (busy) return
        busy = true
        io.execute {
            try {
                val jobId = rbUuid(input.getString("requestId"))
                val response = if (post) bridge.speech(value.characterId, input) else bridge.poll(jobId)
                require(response.getString("jobId") == jobId && response.getString("requestId") == jobId && response.getString("mode") == value.mode)
                val status = response.getString("state")
                require(status in listOf("QUEUED", "RUNNING", "READY", "FAILED", "RESULT_UNKNOWN"))
                var media: GeneratedMedia? = null
                if (status == "READY") {
                    val manifest = response.getJSONObject("speechManifest")
                    val clips = manifest.getJSONArray("clips"); require(clips.length() == 1)
                    require(clips.getJSONObject(0).getString("text") == input.getString("text")) { "FOLLOWUP_TEXT_MISMATCH" }
                    GeneratedArtifact.validateClip(value.json, clips.getJSONObject(0))
                    val original = value.json.getJSONObject("voiceManifest").getJSONArray("clips").getJSONObject(0).getJSONObject("source")
                    require(ai.nunti.app.routebirth.rbEqual(original, clips.getJSONObject(0).getJSONObject("source"))) { "FOLLOWUP_VOICE_CHANGED" }
                    val existing = store.speeches(value.requestId)
                    media = bridge.install(value, store.media(value.requestId), existing + manifest)
                    store.appendSpeech(value.requestId, jobId, manifest); store.finishSpeech(value.requestId)
                }
                val installed = media
                main.post {
                    busy = false
                    if (selected != value.requestId || isDestroyed) return@post
                    when (status) {
                        "READY" -> { pendingSpeech = null; speechMessage = "새 대사가 준비됐어요. 듣기를 눌러 주세요."; bindVoice(value, installed!!.catalog)
                            event("GEN_FOLLOWUP_READY", mapOf("requestId" to jobId, "characterId" to value.characterId, "bindingId" to value.bindingId, "automaticSpeech" to false)) }
                        "FAILED" -> { pendingSpeech = null; store.finishSpeech(value.requestId)
                            speechMessage = if (value.mode == "OFFLINE_FIXTURE") "샘플 모드에서는 등록된 샘플 본문만 시험할 수 있어요." else "새 대사를 준비하지 못했어요. 보관된 음성은 그대로 들을 수 있어요."
                            event("GEN_FOLLOWUP_FAILED", mapOf("requestId" to jobId, "reason" to response.optString("error"))) }
                        "RESULT_UNKNOWN" -> { pendingSpeech = null; speechMessage = "대사 생성 결과를 확인하고 있어요. 같은 요청으로 다시 연결해 주세요."
                            event("GEN_FOLLOWUP_UNKNOWN", mapOf("requestId" to jobId)) }
                    }
                }
            } catch (e: Exception) { main.post { busy = false
                if (selected == value.requestId && !isDestroyed) { pendingSpeech = null; speechMessage = "대사 연결이 끊겼어요. 다시 연결하면 같은 요청을 조회해요."
                    event("GEN_FOLLOWUP_DISCONNECTED", mapOf("reason" to (e.message ?: "CONNECTION_FAILED").take(160))) }
            } }
        }
    }
    private fun act(value: Intent) {
        if (!emulator) return
        if (value.getBooleanExtra("confirm_quiet_test", false)) quiet = true
        when (value.getStringExtra("g_action")) {
            "submit" -> runCatching { submit(JSONObject(value.getStringExtra("g_input_json") ?: "")) }.onFailure { fail(Exception(it)) }
            "retry" -> selected?.let { fetch(it, true) }
            "poll" -> selected?.let { fetch(it, false) }
            "restore" -> value.getStringExtra("g_request_id")?.let { restore(it) }
            "greeting", "common", "arrival" -> speak(value.getStringExtra("g_action")!!)
            "followup" -> runCatching { requestSpeech(value.getStringExtra("g_text") ?: "") }.onFailure { speechMessage = it.message ?: "INVALID_SPEECH" }
            "followup_listen" -> speak("followup")
            "followup_retry" -> { selected?.let { pendingSpeech = store.pendingSpeech(it) }; fetchSpeech(true) }
            "arrive" -> arrive()
            "save" -> collect()
            "stop" -> voice?.stop()
            "block" -> { blocked = true; refresh() }
            "unblock" -> { blocked = false; refresh() }
            "verify_boundaries" -> artifact?.let { current ->
                try { val results = GeneratedBoundaryChecks.run(current, store.input(current.requestId), store, cacheDir)
                    event("GEN_BOUNDARIES", mapOf("passed" to results.length(), "checks" to results))
                } catch (e: Exception) { fail(e) }
            }
            "clear_input" -> {
                voice?.close(); voice = null; voices = null; localProvider = null
                selected = null; artifact = null; bitmap = null; birthRequestId = null; preparedBirthRequestId = null
                destination = ""; traits = ""; purpose = ""; route = emptyList()
                arrived = false; quiet = false; error = null; state = "INPUT"
                pendingSpeech = null; speechMessage = ""; lastSpeech = ""
            }
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
                .border(1.dp, Color(0xFFD9E3D6), RoundedCornerShape(12.dp)).padding(13.dp)
                .semantics { contentDescription = label }, singleLine = true,
                enabled = permitted() && state !in listOf("QUEUED", "RUNNING", "LOADING"),
                textStyle = TextStyle(fontSize = 15.sp, color = Color(0xFF28433C)))
        }
    }
    @Composable private fun RouteInput() {
        Canvas(Modifier.fillMaxWidth().height(185.dp).background(Color(0xFFFEFDF7), RoundedCornerShape(18.dp))
            .border(1.dp, Color(0xFFD6E3D6), RoundedCornerShape(18.dp)).semantics { contentDescription = "여정 경로 입력" }
            .pointerInput(permitted(), state) {
                if (permitted() && state !in listOf("QUEUED", "RUNNING", "LOADING")) detectDragGestures(onDragStart = { start ->
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
        val birthId = birthRequestId
        // A new image starts at zero in the same composition that makes it available.
        // Restored companions start complete; neither a stale frame nor a new birth is replayed.
        val progress = remember(birthId) { Animatable(if (birthId == null) 1f else 0f) }
        val visible = permitted()
        val formationPrepared = birthId != null && preparedBirthRequestId == birthId
        LaunchedEffect(birthId, visible, formationPrepared) {
            if (birthId == null || !visible) {
                progress.snapTo(1f)
            } else if (formationPrepared && progress.value < 1f) {
                event("GEN_ANIMATION", mapOf("requestId" to birthId, "stage" to "ROUTE_TRACE", "progress" to progress.value,
                    "design" to "ROUTE_RIBBON_V1"))
                progress.animateTo(.18f, tween(1200, easing = LinearEasing))
                event("GEN_ANIMATION", mapOf("requestId" to birthId, "stage" to "ROUTE_TO_BODY"))
                progress.animateTo(.50f, tween(2300, easing = LinearEasing))
                event("GEN_ANIMATION", mapOf("requestId" to birthId, "stage" to "IMAGE_REVEAL"))
                progress.animateTo(.90f, tween(2500, easing = LinearEasing))
                event("GEN_ANIMATION", mapOf("requestId" to birthId, "stage" to "SETTLE"))
                progress.animateTo(1f, tween(900))
                event("GEN_ANIMATION", mapOf("requestId" to birthId, "stage" to "COMPLETE"))
            }
        }
        Column(Modifier.fillMaxSize().background(Color(0xFFF5F4EC)).padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    BasicText("NUNTI / JOURNEY KEEPSAKE", style = TextStyle(fontSize = 12.sp, color = Color(0xFF789183)))
                    BasicText("여행의 선이, 나의 동반자로", style = TextStyle(fontSize = 27.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF29463D)))
                }
                Action(if (quiet) "음성 시험 켜짐" else "음성 시험 시작", visible && state == "READY", !quiet) { quiet = true; refresh() }
            }
            if (!visible) {
                BasicText("주차 상태와 화면 사용 허가를 확인하고 있어요.", style = TextStyle(fontSize = 18.sp))
                return@Column
            }
            BasicText(if (mode == "OFFLINE_FIXTURE") "샘플 미디어로 연결 시험 중 · 새 이미지·음색 생성은 API 연결 후 검증해요."
                else if (mode == "API") "여정에서 새 이미지와 목소리를 생성해요."
                else "목적지와 경로를 입력해 생성 연결을 시험해요.",
                style = TextStyle(fontSize = 13.sp, color = Color(0xFF91683B)))
            Row(Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                Column(Modifier.width(310.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Input("어디로 떠나나요?", destination) { if (it.length <= 60) destination = it }
                    Input("그곳의 느낌", traits) { if (it.length <= 240) traits = it }
                    Input("이번 여행의 목적", purpose) { if (it.length <= 120) purpose = it }
                    BasicText("경로를 이어 그려 주세요", style = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Medium, color = Color(0xFF315D55)))
                    RouteInput()
                    BasicText("외부 지도 연결 없이 직접 그린 선을 사용해요.", style = TextStyle(fontSize = 12.sp, color = Color(0xFF7D8C80)))
                    Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                        Action("동반자 만나기", !busy && state !in listOf("QUEUED", "RUNNING"), true) { try { submit(requestFromInput()) } catch (e: Exception) { error = e.message } }
                        Action("지우기", state !in listOf("QUEUED", "RUNNING")) { route = emptyList() }
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
                        val image = remember(bitmap) { bitmap?.asImageBitmap() }
                        if (value != null || route.size > 1) GeneratedCompanion(image, value?.route ?: route.map { GeneratedPoint(it.x, it.y) },
                            if (value != null) progress.value else 0f, state == "READY", Modifier.fillMaxSize(), animate = visible,
                            onFormationPrepared = {
                                if (birthId != null && birthRequestId == birthId && selected == birthId && preparedBirthRequestId != birthId) {
                                    preparedBirthRequestId = birthId
                                    event("GEN_FORMATION_PREPARED", mapOf("requestId" to birthId, "progress" to progress.value,
                                        "imageSha256" to value?.imageSha))
                                }
                            })
                        else BasicText("경로를 그리면 여기서 태어나요.", style = TextStyle(fontSize = 17.sp, color = Color(0xFF9BA78C)))
                    }
                    BasicText(when { error != null -> when {
                            error!!.contains("MISSING_PROVIDER_CREDENTIALS", true) -> "API 키가 연결되지 않았어요. 샘플 시험 모드로 실행할 수 있어요."
                            error!!.any { it in '가'..'힣' } -> error!!
                            state == "RESULT_UNKNOWN" -> "생성 결과를 확인하고 있어요. 중복 요청 없이 다시 연결해 주세요."
                            else -> "연결을 마치지 못했어요. 실행 도구에서 서버 상태를 확인해 주세요."
                        }
                        state in listOf("QUEUED", "RUNNING") -> when (stage) {
                            "PLANNING" -> "여행의 선과 목적지에서 성격을 찾고 있어요."
                            "MEDIA" -> "몸과 목소리를 만들고 있어요."
                            "SELECTING" -> "그림과 목소리의 어울림을 살펴보고 있어요."
                            else -> "동반자의 이미지와 음성을 준비하고 있어요."
                        }
                        state == "READY" && birthId != null && progress.value < .18f -> "그려 준 길을 따라 빛이 흐르고 있어요."
                        state == "READY" && birthId != null && progress.value < .50f -> "여행의 선이 동반자의 몸을 빚고 있어요."
                        state == "READY" && birthId != null && progress.value < .90f -> "선을 따라 오늘의 색이 채워지고 있어요."
                        state == "READY" && birthId != null && progress.value < 1f -> "오늘의 작은 동반자를 만나 보세요."
                        state == "READY" -> "오늘의 동반자가 준비됐어요. 목소리는 듣기를 눌러 확인해 주세요."
                        else -> message }, style = TextStyle(fontSize = 14.sp, color = Color(0xFF6A7F70)))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Action("인사 듣기", state == "READY" && quiet) { speak("greeting") }
                        Action("응원 듣기", state == "READY" && quiet) { speak("common") }
                        Action("중지") { voice?.stop() }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Action(if (arrived) "도착 대사" else "도착했어요", state == "READY") { if (arrived) speak("arrival") else arrive() }
                        Action("동반자 보관", state == "READY" && arrived) { collect() }
                        if (state in listOf("FAILED", "RESULT_UNKNOWN")) Action("다시 연결", selected != null && !busy) { error = null; selected?.let { fetch(it, true) } }
                    }
                    if (state == "READY") {
                        Input("같은 목소리로 새 대사", followup) { if (it.length <= 100) followup = it }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Action("대사 준비", followup.isNotBlank() && !busy && pendingSpeech == null) { runCatching { requestSpeech(followup) }.onFailure { speechMessage = it.message ?: "대사를 확인해 주세요." } }
                            Action("새 대사 듣기", quiet && !busy) { speak("followup") }
                            if (store.pendingSpeech(value!!.requestId) != null && pendingSpeech == null) Action("대사 다시 연결", !busy) { pendingSpeech = store.pendingSpeech(value.requestId); fetchSpeech(true) }
                        }
                        if (mode == "OFFLINE_FIXTURE") BasicText("샘플 모드에서는 안내서의 등록된 본문으로 연결을 시험해요.", style = TextStyle(fontSize = 12.sp, color = Color(0xFF91683B)))
                        if (speechMessage.isNotEmpty()) BasicText(speechMessage, style = TextStyle(fontSize = 12.sp, color = Color(0xFF6A7F70)))
                    }
                    BasicText(lastSpeech.ifEmpty { message },
                        style = TextStyle(fontSize = 12.sp, color = Color(0xFF7A8D78)))
                }
            }
        }
    }
}
