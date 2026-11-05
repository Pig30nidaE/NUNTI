package ai.nunti.app.journey

import ai.nunti.avatar.*
import ai.nunti.emotion.Emotion
import ai.nunti.tts.*
import ai.nunti.voice.AndroidLocalAudioPlayer
import ai.nunti.voice.AndroidVoiceSession
import ai.nunti.voice.LocalVoiceManifest
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.*
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.time.Instant
import java.util.UUID

/** API-free MVP lab. PC generates pinned assets; this app renders the recipe and owns one TTS queue. */
class JourneyMvpActivity : ComponentActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private val emulator get() = Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")
    private val automotive by lazy { packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE) }
    private var car: JourneyCarGate? = null
    private var foreground = false
    private var quietConfirmed by mutableStateOf(false)
    private var forceBlocked = false
    private var catalog: JourneyMvpCatalog? = null
    private var voices: LocalVoiceCatalog? = null
    private var store: JourneyMvpStore? = null
    private var voice: AndroidVoiceSession? = null
    private var selection by mutableStateOf<JourneySelection?>(null)
    private var emotion by mutableStateOf(Emotion.NEUTRAL)
    private var dark by mutableStateOf(false)
    private var qaMode by mutableStateOf<String?>(null)
    private var error by mutableStateOf<String?>(null)
    private var message by mutableStateOf("여행을 고르면 작은 동반자가 기다려요.")
    private var lastSpeech by mutableStateOf("대사를 눌러 목소리를 들어보세요.")
    private var gate by mutableStateOf(JourneyGate("CONNECTING", VehicleMotion.UNKNOWN, false, false, true, 0))
    private var now by mutableLongStateOf(0)
    private var lastGate = ""
    private var lastPresentation = ""
    private var deferredIntent: Intent? = null
    private var dataNamespace = "journey-mvp"
    private val poll = object : Runnable {
        override fun run() {
            if (!foreground) return
            car?.refresh(); refresh()
            handler.postDelayed(this, 750)
        }
    }

    private fun event(kind: String, values: Map<String, Any?> = emptyMap()) {
        val json = JSONObject().put("kind", kind).put("at", Instant.now().toString()).put("namespace", dataNamespace)
        values.forEach { (key, value) -> json.put(key, JSONObject.wrap(value) ?: JSONObject.NULL) }
        Log.i("NuntiJourney", json.toString())
        val file = filesDir.resolve("journey-mvp-events.jsonl")
        // Debug diagnostics are bounded; no actual route or personal destination is logged.
        if (file.length() > 4_000_000) file.renameTo(filesDir.resolve("journey-mvp-events.previous.jsonl"))
        file.appendText(json.toString() + "\n")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (emulator && intent.getStringExtra("mvp_namespace") == "validation") dataNamespace = "journey-mvp-validation"
        deferredIntent = intent
        if (automotive) {
            val permissions = arrayOf("android.car.permission.CAR_POWERTRAIN", "android.car.permission.CAR_SPEED")
                .filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
            if (permissions.isNotEmpty()) requestPermissions(permissions.toTypedArray(), 272)
            car = JourneyCarGate(this) { refresh() }
        }
        initialize()
        setContent { Screen() }
    }

    private fun initialize(repair: Boolean = false) {
        voice?.close(); voice = null
        try {
            val manifestText = assets.open("journey-mvp/voice/manifest.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
            val directory = filesDir.resolve("$dataNamespace/voice").also { it.mkdirs() }
            val parsedVoices = LocalVoiceManifest.parse(manifestText, directory, filesDir.resolve("$dataNamespace/voice-bindings.txt"))
            val bundleText = assets.open("journey-mvp/bundle.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
            val parsed = JourneyMvpCatalog.parse(bundleText, parsedVoices)
            parsedVoices.clips.forEach { clip ->
                val target = directory.resolve(clip.audioPath)
                if (target.exists() && !repair) {
                    require(voiceSha256(target.readBytes()) == clip.audioSha256) { "INSTALLED_AUDIO_CHANGED" }
                } else {
                    val bytes = assets.open("journey-mvp/voice/${clip.audioPath}").use { it.readBytes() }
                    require(voiceSha256(bytes) == clip.audioSha256) { "BUNDLED_AUDIO_CHANGED" }
                    val temporary = directory.resolve(clip.audioPath + ".pending")
                    FileOutputStream(temporary).use { it.write(bytes); it.fd.sync() }
                    Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
                }
            }
            val loadedStore = JourneyMvpStore(filesDir.resolve("$dataNamespace/selection.json"), parsed)
            val restored = loadedStore.restore()
            catalog = parsed; voices = parsedVoices; store = loadedStore; selection = restored
            voice = AndroidVoiceSession(applicationContext, profiles = parsedVoices.profiles,
                providerFactory = { attributes, lane -> LocalFileTtsProvider(parsedVoices) { AndroidLocalAudioPlayer(attributes, lane) } }) { value ->
                lastSpeech = when (value.status) {
                    SpeechStatus.QUEUED -> "목소리를 준비하고 있어요."
                    SpeechStatus.STARTED -> "작은 동반자가 이야기하고 있어요."
                    SpeechStatus.COMPLETED -> "다 들었어요. 다른 대사도 만나보세요."
                    SpeechStatus.CANCELLED -> "재생을 멈췄어요."
                    SpeechStatus.REJECTED -> if (value.reason == "REPEATED_TEXT") "같은 대사는 잠시 뒤 다시 들을 수 있어요." else "지금은 재생할 수 없어요. 주차와 음성 시험 상태를 확인해 주세요."
                    SpeechStatus.FAILED -> "음원을 재생하지 못했어요."
                }
                event("MVP_SPEECH", mapOf("requestId" to value.requestId, "status" to value.status.name, "reason" to value.reason,
                    "providerId" to value.providerId, "profileId" to value.appliedVoice?.profileId,
                    "speakerId" to value.appliedVoice?.speakerId, "mode" to value.mode?.name))
            }
            voice?.beginTrip(current().journeyId)
            error = null
            event("MVP_READY", mapOf("cases" to parsed.characters.size, "bundleId" to parsed.bundleId))
            event("MVP_RESTORED", mapOf("characterId" to restored.characterId, "identity" to current().identity,
                "stage" to restored.stage.name, "collectedCount" to restored.collected.size, "automaticSpeech" to false))
            refresh()
            deferredIntent?.let { pending -> deferredIntent = null; applyIntent(pending) }
        } catch (failure: Exception) {
            error = failure.message ?: failure.javaClass.simpleName
            catalog = null; voices = null; store = null; selection = null
            event("MVP_ERROR", mapOf("reason" to error))
        }
    }

    private fun current() = catalog!!.characters.single { it.characterId == selection!!.characterId }
    private fun phase() = if (selection?.stage == JourneyStage.ARRIVED) ai.nunti.tts.TripPhase.POST_TRIP else ai.nunti.tts.TripPhase.PRE_TRIP
    private fun display() = RenderPolicy.resolve(if (selection?.stage == JourneyStage.ARRIVED) ai.nunti.avatar.TripPhase.POST_DRIVE else ai.nunti.avatar.TripPhase.PRE_DRIVE,
        emotion, PlatformDisplayPolicy(now, gate.knownUX, foreground && gate.parked && !forceBlocked,
            gate.requiresDO, parkedConfirmed = gate.parked, foreground = foreground), now)

    private fun refresh() {
        gate = if (automotive) car?.observe() ?: JourneyGate("ACTUAL_CAR_SERVICE", VehicleMotion.UNKNOWN, false, false, true, 0)
            else JourneyGate("NON_AUTOMOTIVE_LAB", VehicleMotion.PARKED, true, true, false, 0)
        now = SystemClock.elapsedRealtime()
        val audio = getSystemService(AUDIO_SERVICE) as AudioManager
        val musicActive = audio.isMusicActive
        val audioMode = audio.mode
        val quiet = quietConfirmed && audioMode == AudioManager.MODE_NORMAL && !musicActive
        selection?.let {
            voice?.updateContext(PlaybackContext(current().journeyId, phase(), now,
                voiceEnabled = true, foreground = foreground, suspended = false,
                motion = gate.motion, uxRestrictionsKnown = gate.knownUX, requiresDistractionOptimization = gate.requiresDO,
                activeRestrictions = gate.activeRestrictions, appAllowedWhileDriving = Permission.DENIED,
                speechPermission = if (gate.parked && gate.knownUX && !gate.requiresDO && !forceBlocked) Permission.ALLOWED else Permission.DENIED,
                call = if (quiet) AudioActivity.QUIET else AudioActivity.UNKNOWN,
                navigation = if (quiet) AudioActivity.QUIET else AudioActivity.UNKNOWN,
                criticalAudio = if (quiet) AudioActivity.QUIET else AudioActivity.UNKNOWN))
        }
        val visible = display().visible
        val fingerprint = listOf(gate, visible, foreground, forceBlocked, audioMode, musicActive, quietConfirmed).toString()
        if (fingerprint != lastGate) {
            lastGate = fingerprint
            event("MVP_GATE", mapOf("source" to gate.source, "motion" to gate.motion.name, "parked" to gate.parked,
                "visible" to visible, "foreground" to foreground, "knownUX" to gate.knownUX, "requiresDO" to gate.requiresDO,
                "audioMode" to audioMode, "musicActive" to musicActive, "quietConfirmed" to quietConfirmed, "quietAccepted" to quiet))
        }
    }

    private fun save(value: JourneySelection): Boolean = try {
        store!!.save(value); selection = value; true
    } catch (failure: Exception) {
        error = "선택을 저장하지 못했어요. 기존 기록은 보존됩니다."
        voice?.onBackground(); event("MVP_ERROR", mapOf("reason" to (failure.message ?: "STATE_WRITE_FAILED"))); false
    }
    private fun allowed() = selection != null && display().interactionsAllowed && error == null
    private fun choose(caseId: String) {
        refresh(); if (!allowed()) return
        val target = catalog!!.characters.singleOrNull { it.caseId == caseId } ?: return
        if (target.characterId == selection!!.characterId) return
        voice?.stop()
        if (!save(JourneySelection(target.characterId, JourneyStage.PREVIEW, selection!!.collected))) return
        emotion = Emotion.NEUTRAL
        voice?.beginTrip(target.journeyId); refresh()
        message = "${target.displayName}와 이번 여행을 준비해요."
        event("MVP_SELECTION", mapOf("caseId" to caseId, "characterId" to target.characterId, "identity" to target.identity))
    }
    private fun arrive() {
        refresh(); if (!allowed()) return
        voice?.stop()
        if (!save(selection!!.copy(stage = JourneyStage.ARRIVED))) return
        emotion = Emotion.JOYFUL; refresh(); message = "도착했어요. 오늘의 동반자를 간직해 볼까요?"
        event("MVP_ARRIVED", mapOf("characterId" to current().characterId, "identity" to current().identity))
    }
    private fun collect() {
        refresh(); if (!allowed() || selection!!.stage != JourneyStage.ARRIVED) return
        if (!save(selection!!.copy(collected = selection!!.collected + current().characterId))) return
        message = "${current().displayName}를 보관했어요. 다시 열어도 같은 모습과 목소리예요."
        event("MVP_SAVED", mapOf("characterId" to current().characterId, "identity" to current().identity,
            "collectedCount" to selection!!.collected.size))
    }
    private fun reroute() {
        refresh(); if (!allowed()) return
        message = "경로가 바뀌어도 ${current().displayName}와 계속 함께해요."
        event("MVP_REROUTE", mapOf("characterId" to current().characterId, "identity" to current().identity))
    }
    private fun speak(category: String) {
        refresh()
        if (selection == null || error != null) return
        val character = current()
        val clipId = character.clipIds[category] ?: return
        val clip = voices!!.clips.single { it.clipId == clipId }
        val requestId = "mvp-${UUID.randomUUID()}"
        event("MVP_SPEECH_REQUEST", mapOf("requestId" to requestId, "clipId" to clipId, "characterId" to character.characterId,
            "profileId" to clip.profileId, "audioSha256" to clip.audioSha256, "textSha256" to clip.textSha256, "identity" to character.identity))
        val epoch = System.currentTimeMillis()
        val emotionId = "mvp-emotion-${UUID.randomUUID()}"
        val snapshot = ai.nunti.tts.EmotionSnapshot(emotionId, character.journeyId, character.characterId,
            ai.nunti.tts.Emotion.valueOf(emotion.name), epoch)
        val request = SpeechRequest(requestId, character.journeyId, character.characterId, clip.text,
            snapshot.emotion, clip.profileId, phase(), Priority.NORMAL, epoch, epoch + 25000, ContentSource.USER_INITIATED,
            emotionId = emotionId)
        voice?.submit(ApprovedSpeech(request, AvatarVoiceInput(character.characterId, character.characterId, clip.profileId), snapshot, true))
    }

    private fun applyIntent(value: Intent) {
        if (!emulator) return
        if (value.getBooleanExtra("confirm_quiet_test", false)) quietConfirmed = true
        when (value.getStringExtra("mvp_action")) {
            "select" -> choose(value.getStringExtra("case_id") ?: "")
            "greeting", "common", "arrival" -> speak(value.getStringExtra("mvp_action")!!)
            "arrive" -> arrive()
            "save" -> collect()
            "reroute" -> reroute()
            "stop" -> voice?.stop()
            "emotion" -> if (allowed()) value.getStringExtra("emotion")?.let { runCatching { emotion = Emotion.valueOf(it) } }
            "theme" -> if (allowed()) dark = value.getBooleanExtra("dark", false)
            "force_block" -> { forceBlocked = value.getBooleanExtra("blocked", true); refresh() }
            "qa" -> if (allowed()) qaMode = value.getStringExtra("qa_mode") ?: "thumbnails"
            "experience" -> qaMode = null
            "verify_boundaries" -> if (allowed()) {
                val bundle = assets.open("journey-mvp/bundle.json").bufferedReader().use { it.readText() }
                val checks = JourneyMvpBoundaryChecks.run(bundle, voices!!, cacheDir)
                event("MVP_BOUNDARY_TESTS", mapOf("checks" to checks, "passed" to checks.count { it["passed"] == true }, "total" to checks.size))
            }
        }
        refresh()
    }

    @Composable private fun Action(label: String, enabled: Boolean = true, primary: Boolean = false, action: () -> Unit) {
        val background = if (primary && enabled) Color(0xFF345D52) else Color(0xFFEAEFE6)
        BasicText(label, Modifier.background(background, RoundedCornerShape(14.dp))
            .clickable(enabled = enabled, role = Role.Button, onClick = action).padding(horizontal = 16.dp, vertical = 12.dp),
            style = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.Medium,
                color = if (!enabled) Color(0xFF96A29B) else if (primary) Color.White else Color(0xFF345D52)))
    }

    @Composable private fun Screen() {
        val ink = Color(0xFF283E39)
        Column(Modifier.fillMaxSize().background(Color(0xFFF7F5EE)).padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Column {
                    BasicText("NUNTI  /  여정 MVP", style = TextStyle(color = Color(0xFF688172), fontSize = 13.sp))
                    BasicText("오늘의 작은 동반자", style = TextStyle(color = ink, fontWeight = FontWeight.Bold, fontSize = 28.sp))
                }
                if (error == null && selection != null && display().interactionsAllowed) Action(if (quietConfirmed) "음성 시험 켜짐" else "음성 시험 시작", primary = !quietConfirmed) {
                    quietConfirmed = !quietConfirmed
                    if (!quietConfirmed) voice?.stop()
                    refresh()
                }
            }
            if (error != null) {
                BasicText("준비한 캐릭터를 열지 못했어요. 저장된 선택과 음성은 자동으로 바꾸지 않습니다.", style = TextStyle(color = ink, fontSize = 20.sp))
                BasicText(error!!, style = TextStyle(color = Color(0xFF8A5848), fontSize = 14.sp))
                Action("번들 음원 복구") { initialize(repair = true) }
                return@Column
            }
            if (selection == null) return@Column
            val render = display()
            if (!render.visible) {
                BasicText("주차가 확인되면 동반자를 만날 수 있어요.", Modifier.padding(32.dp), style = TextStyle(color = ink, fontSize = 22.sp))
                return@Column
            }
            BasicText(if (automotive) "주차 중 · 준비된 시험 여행 ${catalog!!.characters.size}개 · 외부 API 없음" else "일반 Android의 합성 여행 시험 · 실제 차량 상태와 연결되지 않습니다.",
                style = TextStyle(color = Color(0xFF718176), fontSize = 13.sp))
            if (qaMode != null) { Qa(render); return@Column }
            BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
                if (maxWidth >= 700.dp) Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(22.dp)) {
                    Cases(Modifier.width(270.dp)); Detail(Modifier.weight(1f), render)
                } else Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Cases(Modifier.fillMaxWidth().height(200.dp)); Detail(Modifier.fillMaxWidth().weight(1f), render)
                }
            }
        }
    }

    @Composable private fun Qa(render: RenderState) {
        val density = LocalDensity.current
        val sampleSizes = listOf(64, 128)
        val cells = if (qaMode == "expressions") Emotion.entries.map { current() to it }
            else catalog!!.characters.map { it to Emotion.NEUTRAL }
        Action("여행 화면으로") { qaMode = null }
        BasicText("실제 Canvas 64px / 128px · ${if (qaMode == "expressions") "6표정" else "8체형"}", style = TextStyle(fontSize = 16.sp))
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            cells.chunked(4).forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    row.forEach { (character, expression) ->
                        Column(Modifier.background(if (dark) Color(0xFF1E3034) else Color.White, RoundedCornerShape(16.dp)).padding(8.dp)) {
                            BasicText("${character.displayName} · ${expression.name}", style = TextStyle(fontSize = 11.sp, color = if (dark) Color.White else Color(0xFF283E39)))
                            Row(verticalAlignment = Alignment.Bottom) {
                                sampleSizes.forEach { pixels ->
                                    JourneyKeepsake(character.visual, render.copy(emotion = expression), Modifier.size(with(density) { pixels.toDp() }))
                                }
                            }
                        }
                    }
                }
            }
        }
        SideEffect {
            val fingerprint = "qa:$qaMode:$dark:${current().characterId}"
            if (lastPresentation != fingerprint) {
                lastPresentation = fingerprint
                event("MVP_QA_PRESENTED", mapOf("mode" to qaMode, "sizesPx" to listOf(64, 128),
                    "density" to density.density, "dark" to dark, "characterIds" to cells.map { it.first.characterId }))
            }
        }
    }

    @Composable private fun Cases(modifier: Modifier) {
        Column(modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            BasicText("어떤 여행을 떠나나요?", style = TextStyle(color = Color(0xFF345D52), fontSize = 18.sp, fontWeight = FontWeight.Bold))
            catalog!!.characters.forEach { character ->
                val selected = character.characterId == selection!!.characterId
                val collected = character.characterId in selection!!.collected
                Column(Modifier.fillMaxWidth().background(if (selected) Color(0xFFE3EBDF) else Color(0xFFFEFDF9), RoundedCornerShape(16.dp))
                    .border(1.dp, if (selected) Color(0xFF89A78B) else Color(0xFFE7E8DE), RoundedCornerShape(16.dp))
                    .clickable(role = Role.Button) { choose(character.caseId) }.padding(14.dp)) {
                    BasicText(character.label + if (collected) "  · 보관함" else "", style = TextStyle(color = Color(0xFF2F4B3F), fontSize = 16.sp, fontWeight = FontWeight.Medium))
                    BasicText(character.displayName, style = TextStyle(color = Color(0xFF738274), fontSize = 13.sp))
                }
            }
        }
    }

    @OptIn(ExperimentalLayoutApi::class)
    @Composable private fun Detail(modifier: Modifier, render: RenderState) {
        val character = current()
        val state = selection!!
        SideEffect {
            val fingerprint = listOf(character.identity, emotion, state.stage, dark, render.visible).toString()
            if (fingerprint != lastPresentation) {
                lastPresentation = fingerprint
                event("MVP_PRESENTED", mapOf("characterId" to character.characterId, "identity" to character.identity,
                    "bodyFamily" to character.visual.bodyFamily.name.lowercase(), "shapeId" to character.visual.shapeId,
                    "emotion" to emotion.name, "stage" to state.stage.name, "visible" to render.visible,
                    "rendererVersion" to "journey-keepsake-canvas-1", "visualVoiceJoined" to true))
            }
        }
        Column(modifier.fillMaxHeight().verticalScroll(rememberScrollState())
            .background(if (dark) Color(0xFF1E3034) else Color(0xFFFFFDF7), RoundedCornerShape(28.dp)).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            val ink = if (dark) Color(0xFFF5EFE3) else Color(0xFF283E39)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    BasicText(if (state.stage == JourneyStage.ARRIVED) "도착 후의 기억" else "이번 여행에서 만난", style = TextStyle(color = Color(0xFF8B9A84), fontSize = 13.sp))
                    BasicText(character.displayName, style = TextStyle(color = ink, fontSize = 27.sp, fontWeight = FontWeight.Bold))
                }
                Action(if (dark) "밝은 배경" else "어두운 배경") { dark = !dark }
            }
            JourneyKeepsake(character.visual, render, Modifier.fillMaxWidth().height(380.dp))
            BasicText(character.summary, style = TextStyle(color = ink, fontSize = 16.sp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Action("인사 듣기", quietConfirmed, true) { speak("greeting") }
                Action("같은 문장", quietConfirmed) { speak("common") }
                Action("중지") { voice?.stop() }
            }
            BasicText(lastSpeech, style = TextStyle(color = if (dark) Color(0xFFB8C8B7) else Color(0xFF768775), fontSize = 13.sp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.stage == JourneyStage.PREVIEW) Action("도착했어요", primary = true) { arrive() }
                else {
                    Action("도착 대사", quietConfirmed) { speak("arrival") }
                    Action(if (character.characterId in state.collected) "보관됨" else "동반자 보관", primary = true) { collect() }
                }
                Action("경로 변경 시험") { reroute() }
            }
            BasicText(message, style = TextStyle(color = ink, fontSize = 14.sp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(Emotion.NEUTRAL to "기본", Emotion.RELAXED to "편안", Emotion.CONCERNED to "걱정", Emotion.STARTLED to "놀람", Emotion.RELIEVED to "안도", Emotion.JOYFUL to "기쁨").forEach { (target, label) ->
                    BasicText(label, Modifier.clickable(role = Role.Button) { emotion = target }.padding(8.dp),
                        style = TextStyle(color = if (emotion == target) Color(0xFF7CB48A) else if (dark) Color(0xFFB8C8B7) else Color(0xFF768775), fontSize = 13.sp))
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); applyIntent(intent) }
    override fun onStart() {
        super.onStart(); foreground = true; refresh(); handler.removeCallbacks(poll); handler.post(poll)
    }
    override fun onStop() {
        foreground = false; quietConfirmed = false; handler.removeCallbacks(poll); voice?.onBackground(); refresh(); super.onStop()
    }
    override fun onDestroy() { handler.removeCallbacksAndMessages(null); voice?.close(); car?.close(); super.onDestroy() }
}
