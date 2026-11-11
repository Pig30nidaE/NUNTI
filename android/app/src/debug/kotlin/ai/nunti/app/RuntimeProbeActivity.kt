package ai.nunti.app

import ai.nunti.avatar.AvatarSpec
import ai.nunti.avatar.AvatarEngine
import ai.nunti.avatar.CanvasPartProvider
import ai.nunti.avatar.CarUxPolicyBinding
import ai.nunti.avatar.MockRoutes
import ai.nunti.avatar.NuntiAppShell
import ai.nunti.avatar.RenderPolicy
import ai.nunti.avatar.TripPhase
import ai.nunti.emotion.Emotion
import ai.nunti.emotion.EmotionSnapshot
import ai.nunti.emotion.TransitionReason
import ai.nunti.tts.AudioActivity
import ai.nunti.tts.Permission
import ai.nunti.tts.PlaybackContext
import ai.nunti.tts.SpeechEvidence
import ai.nunti.tts.VehicleMotion
import ai.nunti.tts.WireSpeechRequest
import ai.nunti.tts.ApprovedSpeech
import ai.nunti.tts.AvatarVoiceInput
import ai.nunti.tts.CatalogTtsProvider
import ai.nunti.tts.ContentSource
import ai.nunti.tts.LocalFileTtsProvider
import ai.nunti.tts.LocalVoiceCatalog
import ai.nunti.tts.PleosTtsProvider
import ai.nunti.tts.Priority
import ai.nunti.tts.SpeechRequest
import ai.nunti.tts.VoiceProfile
import ai.nunti.tts.VoiceAssetException
import ai.nunti.voice.AndroidLocalAudioPlayer
import ai.nunti.voice.AndroidPleosConnection
import ai.nunti.voice.LocalVoiceManifest
import ai.nunti.voice.AndroidVoiceSession
import android.car.Car
import android.car.VehicleGear
import android.car.VehiclePropertyIds
import android.car.drivingstate.CarUxRestrictions
import android.car.drivingstate.CarUxRestrictionsManager
import android.car.hardware.property.CarPropertyManager
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.time.Instant
import java.util.UUID
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import kotlin.math.abs

/** Debug-only, emulator-only runtime harness. Production host remains fail-closed.
 * Route/emotion inputs are MOCK; gear/speed/UX are actually read from Car managers.
 * Audio silence is an explicit operator-controlled test precondition, not a vehicle API result.
 */
class RuntimeProbeActivity : ComponentActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private val engine = AvatarEngine()
    private val provider = CanvasPartProvider(engine.manifest)
    private val routes = MockRoutes.representative()
    private val tripId = "runtime-probe-${UUID.randomUUID()}"
    private var car: Car? = null
    private var properties: CarPropertyManager? = null
    private var binding: CarUxPolicyBinding? = null
    private var voice: AndroidVoiceSession? = null
    private var localCatalog: LocalVoiceCatalog? = null
    private var localAssetDirectory = "journey-voice"
    private var restrictions: CarUxRestrictions? = null
    private var gear: Int? = null
    private var speed: Float? = null
    private var foreground = false
    private var quietTestConfirmed = false
    private var routeIndex by mutableIntStateOf(0)
    private var emotion by mutableStateOf(Emotion.NEUTRAL)
    private var status by mutableStateOf("Connecting to Car service")
    private var lastVoice by mutableStateOf("No speech requested")
    private var observedAt by mutableLongStateOf(0)
    private val sessionEpoch = System.currentTimeMillis()
    private var activeRequest: String? = null
    private var lastState = ""
    private val poll = object : Runnable {
        override fun run() {
            if (!foreground) return
            binding?.refresh()
            refresh()
            handler.postDelayed(this, 1000)
        }
    }

    private fun event(kind: String, fields: Map<String, Any?> = emptyMap()) {
        val json = JSONObject().put("kind", kind).put("at", Instant.now().toString())
        fields.forEach { (key, value) -> json.put(key, value ?: JSONObject.NULL) }
        Log.i("NuntiRuntime", json.toString())
        filesDir.resolve("runtime-probe.jsonl").appendText(json.toString() + "\n")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Build.HARDWARE.contains("ranchu") && !Build.HARDWARE.contains("goldfish")) {
            Log.e("NuntiRuntime", "Emulator-only probe refused: ${Build.HARDWARE}")
            finish(); return
        }
        event("PROBE_CREATED", mapOf("hardware" to Build.HARDWARE, "fingerprint" to Build.FINGERPRINT,
            "source" to "DEBUG_EMULATOR_ONLY", "inputs" to "MOCK_ROUTE_AND_EMOTION"))
        val requestedCatalog = intent.getStringExtra("voice_catalog") ?: "legacy"
        if (requestedCatalog !in setOf("legacy", "dynamic")) {
            event("LOCAL_CATALOG_ERROR", mapOf("reason" to "UNKNOWN_CATALOG")); finish(); return
        }
        localAssetDirectory = if (requestedCatalog == "dynamic") "journey-dynamic" else "journey-voice"
        localCatalog = try {
            val manifest = assets.open("$localAssetDirectory/manifest.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
            LocalVoiceManifest.parse(manifest, filesDir.resolve(localAssetDirectory), filesDir.resolve("$localAssetDirectory-bindings.txt"))
        } catch (error: Exception) {
            event("LOCAL_CATALOG_ERROR", mapOf("reason" to ((error as? VoiceAssetException)?.reason ?: "VOICE_MANIFEST_UNAVAILABLE")))
            null
        }
        val catalog = localCatalog
        voice = AndroidVoiceSession(applicationContext,
            profiles = listOf(VoiceProfile()) + (catalog?.profiles ?: emptyList()),
            providerFactory = catalog?.let { loaded -> { attributes, lane ->
                CatalogTtsProvider(loaded,
                    { LocalFileTtsProvider(loaded) { AndroidLocalAudioPlayer(attributes, lane) } },
                    { PleosTtsProvider({ AndroidPleosConnection(applicationContext, it, attributes, lane) }) })
            } }) { value ->
            lastVoice = "${value.status}: ${value.reason ?: ""}"
            event("SPEECH", mapOf("requestId" to value.requestId, "status" to value.status.name,
                "reason" to value.reason, "mode" to value.mode?.name,
                "providerId" to value.providerId, "profileId" to value.appliedVoice?.profileId,
                "speakerId" to value.appliedVoice?.speakerId,
                "startLatencyMs" to value.startLatencyMs))
        }
        voice?.beginTrip(tripId)
        applyIntent(intent)
        val missing = arrayOf(Car.PERMISSION_POWERTRAIN, Car.PERMISSION_SPEED).filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 271)
        car = Car.createCar(this, handler, Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT) { connected, ready ->
            event("CAR_CONNECTION", mapOf("ready" to ready))
            binding?.close(); binding = null; properties = null; restrictions = null
            if (ready) runCatching {
                properties = connected.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager
                val manager = connected.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE) as CarUxRestrictionsManager
                binding = CarUxPolicyBinding(manager) { value -> restrictions = value; refresh() }.also { it.start() }
            }.onFailure { event("CAR_ERROR", mapOf("type" to it.javaClass.simpleName)) }
            refresh()
        }
        setContent {
            val spec = remember(routeIndex) { engine.generate(routes[routeIndex], 42L).avatar }
            val state = remember(emotion, spec) {
                snapshot(spec)
            }
            val now = observedAt
            val policy = displayPolicy(now)
            Column(Modifier.fillMaxSize()) {
                BasicText("Pleos 런타임 검증 · 경로/감정 MOCK", Modifier.padding(12.dp), style = TextStyle(fontSize = 20.sp))
                BasicText(status + " · " + lastVoice, Modifier.padding(horizontal = 12.dp), style = TextStyle(fontSize = 14.sp))
                if (parked()) {
                    Row(Modifier.padding(8.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        listOf("도심", "장거리", "해안", "산악").forEachIndexed { index, label ->
                            BasicText(label, Modifier.clickable { routeIndex = index; event("ROUTE", mapOf("index" to index)) }.padding(8.dp))
                        }
                        BasicText("TTS 재생", Modifier.clickable { speak() }.padding(8.dp))
                        BasicText("중지", Modifier.clickable { activeRequest?.let { voice?.cancel(it) } }.padding(8.dp))
                    }
                    BasicText("로컬 실험 음성 · 아래 기존 MOCK 외형과 별도 비교", Modifier.padding(horizontal = 12.dp))
                    Row(Modifier.padding(8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        BasicText("음원 설치", Modifier.clickable { installLocalClips() }.padding(8.dp))
                        val choices = if (localAssetDirectory == "journey-dynamic") {
                            localCatalog?.clips?.filter { it.clipId.endsWith("-common") }
                                ?.mapIndexed { index, clip -> clip.characterId to "생성 ${index + 1}" } ?: emptyList()
                        } else listOf("coast" to "파도빛", "mountain" to "이끼별", "city" to "조각빛")
                        choices.forEach { (key, label) ->
                            BasicText(label, Modifier.clickable { speakLocal(key, "common") }.padding(8.dp))
                        }
                    }
                }
                NuntiAppShell(spec, state, TripPhase.POST_DRIVE, policy, now, provider, modifier = Modifier.weight(1f))
            }
        }
    }

    private fun parked(): Boolean = gear == VehicleGear.GEAR_PARK && speed?.let { it.isFinite() && abs(it) < 0.01f } == true
    private fun displayPolicy(now: Long) = CarUxPolicyBinding.policy(restrictions, now,
        screenPermitted = foreground && parked(), approvedDistractionOptimizedHost = false,
        approvedStaticDriving = false, parkedConfirmed = parked(), foreground = foreground)

    private fun refresh(initialize: Boolean = false) {
        gear = runCatching { properties?.getIntProperty(VehiclePropertyIds.GEAR_SELECTION, 0) }.getOrNull()
        speed = runCatching { properties?.getFloatProperty(VehiclePropertyIds.PERF_VEHICLE_SPEED, 0) }.getOrNull()
        val now = SystemClock.elapsedRealtime()
        val audio = getSystemService(AUDIO_SERVICE) as AudioManager
        val quiet = quietTestConfirmed && audio.mode == AudioManager.MODE_NORMAL && !audio.isMusicActive
        val motion = when {
            gear == null || speed == null -> VehicleMotion.UNKNOWN
            parked() -> VehicleMotion.PARKED
            abs(speed!!) > 0.01f -> VehicleMotion.MOVING
            else -> VehicleMotion.STOPPED
        }
        val context = PlaybackContext(tripId, ai.nunti.tts.TripPhase.POST_TRIP,
            now, voiceEnabled = true, foreground = foreground, suspended = false,
            motion = motion, uxRestrictionsKnown = restrictions != null,
            requiresDistractionOptimization = restrictions?.isRequiresDistractionOptimization ?: true,
            activeRestrictions = restrictions?.activeRestrictions ?: 0,
            appAllowedWhileDriving = Permission.DENIED,
            speechPermission = if (parked() && restrictions?.isRequiresDistractionOptimization == false) Permission.ALLOWED else Permission.DENIED,
            call = if (quiet) AudioActivity.QUIET else AudioActivity.UNKNOWN,
            navigation = if (quiet) AudioActivity.QUIET else AudioActivity.UNKNOWN,
            criticalAudio = if (quiet) AudioActivity.QUIET else AudioActivity.UNKNOWN)
        if (initialize) voice?.onForeground(context) else voice?.updateContext(context)
        val render = RenderPolicy.resolve(TripPhase.POST_DRIVE, emotion, displayPolicy(now), now)
        status = "gear=$gear speed=$speed UX=${restrictions?.activeRestrictions} avatar=${render.visible}"
        val key = "$status foreground=$foreground quietTest=$quiet"
        if (key != lastState) {
            lastState = key
            event("PLATFORM", mapOf("gear" to gear, "speed" to speed, "parked" to parked(),
                "uxKnown" to (restrictions != null), "requiresDO" to restrictions?.isRequiresDistractionOptimization,
                "avatarVisible" to render.visible, "reason" to render.reason,
                "audioContext" to if (quiet) "OPERATOR_CONTROLLED_TEST" else "UNKNOWN"))
        }
        observedAt = now
    }

    private fun snapshot(spec: AvatarSpec) = EmotionSnapshot("$tripId-$routeIndex-${emotion.name}", tripId,
        spec.avatarId, emotion, 0, null, 1.0, TransitionReason.MOCK_RUNTIME_PROBE)

    private fun speak() {
        refresh()
        val spec = engine.generate(routes[routeIndex], 42L).avatar
        val stamp = Instant.now()
        val id = "probe-${UUID.randomUUID()}"
        activeRequest = id
        val state = snapshot(spec)
        val emotionId = state.emotionId
        val wire = WireSpeechRequest("1.0", id, tripId, spec.avatarId,
            "안녕하세요. 눈티예요. 오늘의 여행도 함께할게요.", spec.identity.voiceProfileId,
            emotion.name, "POST_TRIP", "NORMAL", stamp.toString(), stamp.plusSeconds(25).toString(),
            "MOCK", "USER_INITIATED", null, emotionId)
        voice?.submitWire(wire, spec.toVoiceInput(), state.toVoiceEmotion(sessionEpoch),
            SpeechEvidence(approvedText = true, userInitiated = true, allowMock = true))
    }

    private fun applyIntent(value: Intent) {
        quietTestConfirmed = value.getBooleanExtra("confirm_quiet_test", quietTestConfirmed)
        if (value.hasExtra("route")) routeIndex = value.getIntExtra("route", 0).coerceIn(0, 3)
        value.getStringExtra("emotion")?.let { name -> runCatching { emotion = Emotion.valueOf(name) } }
        when (value.getStringExtra("probe_action")) {
            "speak" -> handler.post { speak() }
            "stop" -> activeRequest?.let { voice?.cancel(it) }
            "local_install" -> handler.post { installLocalClips() }
            "local_speak" -> handler.post { speakLocal(value.getStringExtra("character") ?: "coast", "common") }
            "local_greeting" -> handler.post { speakLocal(value.getStringExtra("character") ?: "coast", "greeting") }
            "local_arrival" -> handler.post { speakLocal(value.getStringExtra("character") ?: "coast", "arrival") }
        }
    }

    private fun installLocalClips() {
        refresh()
        if (!foreground || !parked() || restrictions?.isRequiresDistractionOptimization != false) {
            event("LOCAL_INSTALL_REJECTED", mapOf("reason" to "PARKING_REQUIRED")); return
        }
        val catalog = localCatalog ?: return
        try {
            val directory = filesDir.resolve(localAssetDirectory).also { it.mkdirs() }
            catalog.clips.forEach { clip ->
                val target = directory.resolve(clip.audioPath)
                val temporary = directory.resolve(clip.audioPath + ".pending")
                assets.open("$localAssetDirectory/${clip.audioPath}").use { input -> temporary.outputStream().use { input.copyTo(it) } }
                Files.move(temporary.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            }
            event("LOCAL_ASSETS_INSTALLED", mapOf("count" to catalog.clips.size, "providerId" to catalog.providerId,
                "quality" to "LISTENING_CANDIDATES_NOT_PRODUCT_APPROVED"))
        } catch (_: Exception) { event("LOCAL_INSTALL_REJECTED", mapOf("reason" to "VOICE_ASSET_INSTALL_FAILED")) }
    }

    private fun speakLocal(character: String, category: String) {
        refresh()
        val catalog = localCatalog
        val clipId = "$character-$category"
        val clip = catalog?.clips?.singleOrNull { it.clipId == clipId }
        if (clip == null) {
            event("LOCAL_REQUEST_REJECTED", mapOf("reason" to "UNKNOWN_VOICE_CLIP")); return
        }
        val id = "local-${UUID.randomUUID()}"
        val now = System.currentTimeMillis()
        activeRequest = id
        event("LOCAL_REQUEST", mapOf("requestId" to id, "clipId" to clip.clipId, "characterId" to clip.characterId,
            "profileId" to clip.profileId, "speakerId" to clip.speakerId, "textSha256" to clip.textSha256,
            "audioSha256" to clip.audioSha256, "providerId" to catalog.providerId,
            "visualIntegration" to "SEPARATE_FROM_LEGACY_MOCK_AVATAR"))
        val request = SpeechRequest(id, tripId, clip.characterId, clip.text, ai.nunti.tts.Emotion.NEUTRAL,
            clip.profileId, ai.nunti.tts.TripPhase.POST_TRIP, Priority.NORMAL, now, now + 25000, ContentSource.USER_INITIATED)
        voice?.submit(ApprovedSpeech(request, AvatarVoiceInput(clip.characterId, clip.characterId, clip.profileId), null, true))
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); applyIntent(intent) }
    override fun onStart() { super.onStart(); foreground = true; refresh(initialize = true); handler.removeCallbacks(poll); handler.post(poll) }
    override fun onStop() {
        foreground = false; handler.removeCallbacks(poll); voice?.onBackground(); refresh(); super.onStop()
    }
    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null); binding?.close(); voice?.close(); car?.disconnect(); super.onDestroy()
    }
}
