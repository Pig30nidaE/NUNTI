package ai.nunti.app.journey

import ai.nunti.app.studio.StudioCarGate
import ai.nunti.tts.ContentSource
import ai.nunti.tts.TripPhase
import ai.nunti.tts.Emotion
import ai.nunti.tts.SpeechStatus
import ai.nunti.score.Scenarios
import ai.nunti.score.journey.JourneySession
import ai.nunti.score.journey.JourneySnapshot
import ai.nunti.score.journey.JourneySource
import ai.nunti.score.live.PleosSignalSource
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Sampling and audio outlive the foreground screen, including while navigation is visible. */
class JourneyService : Service() {
    private val main = Handler(Looper.getMainLooper())
    private var session: JourneySession? = null
    private var source: PleosSignalSource? = null
    private var gate: StudioCarGate? = null
    private lateinit var metadata: JSONObject
    private var voiceStatus = "눈티 목소리 준비 중"
    private var muted = false
    private var consumedFeedback: String? = null
    private var speech: CompanionSpeech? = null
    private var finishingSpeech = false
    private var demoCursor = 0
    private var lastPersist = 0L
    private var lastCanFinish = false
    private val tick = object : Runnable {
        override fun run() {
            val journey = session ?: return
            speech?.refresh()
            if (journey.snapshot().finished) return
            val snapshot = if (journey.source == JourneySource.LIVE) {
                val signals = source ?: return
                journey.add(signals.snapshot(), signals.events())
            } else {
                if (!canFinish()) { publish(journey.snapshot(), false); main.postDelayed(this, 500); return }
                val scenario = Scenarios.recovery
                if (demoCursor > scenario.samples.lastIndex) {
                    publish(journey.snapshot(), false); main.postDelayed(this, 500); return
                }
                val sample = scenario.samples[demoCursor++]
                journey.add(sample, scenario.events.filter { it.tMs <= sample.tMs })
            }
            publish(snapshot, false)
            snapshot.feedback?.let { feedback ->
                if (feedback.key != consumedFeedback) {
                    consumedFeedback = feedback.key
                    publish(snapshot, true) // Claim before playback: restore never repeats a spoken event.
                    speak(feedback.kind.name)
                }
            }
            main.postDelayed(this, if (journey.source == JourneySource.LIVE) 1000 else 100)
        }
    }

    override fun onCreate() {
        super.onCreate()
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)) {
            gate = StudioCarGate(this) { main.post {
                speech?.refresh()
                if (::metadata.isInitialized) session?.let { publish(it.snapshot(), false) }
            } }
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "눈티 여정", NotificationManager.IMPORTANCE_LOW))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_FINISH -> finishJourney()
            ACTION_MUTE -> {
                muted = intent.getBooleanExtra("mute", true)
                if (muted) stopAudio()
                session?.let { publish(it.snapshot(), true) }
            }
            ACTION_START -> {
                if (session != null) return START_NOT_STICKY
                startForeground(9201, notification("여정 준비 중"))
                runCatching { startJourney(intent.getStringExtra("input") ?: error("missing input")) }
                    .onFailure { Log.e(TAG, "JOURNEY_START_FAILED", it); stopSelf() }
            }
            else -> if (session == null) stopSelf()
        }
        // Process death is an interrupted trip, never an automatic replay of prior audio.
        return START_NOT_STICKY
    }

    private fun startJourney(path: String) {
        val file = File(path).canonicalFile
        require(file.parentFile == File(filesDir, "journeys").canonicalFile && file.name.endsWith("-input.json"))
        metadata = JSONObject(file.readText())
        session = JourneySession(metadata.getString("sessionId"), metadata.getString("characterId"),
            metadata.optString("routePlanId").ifBlank { null }, JourneySource.valueOf(metadata.getString("source")),
            metadata.getLong("startedAtEpochMs"))
        if (session!!.source == JourneySource.LIVE) source = PleosSignalSource(applicationContext).also { it.start() }
        JourneyRuntime.isRunning = true
        val clips = metadata.optJSONObject("voices") ?: JSONObject()
        speech = CompanionSpeech(this, metadata.getString("sessionId"), metadata.getString("characterId"),
            gate = { gate }, enabled = { !muted }, active = { JourneyRuntime.isRunning },
            clips = clips.keys().asSequence().associateWith { File(clips.getString(it)) }) { event ->
            when (event.status) {
                SpeechStatus.STARTED -> {
                    voiceStatus = when (event.providerId) {
                        "pleos" -> "Pleos 목소리"
                        "android-on-device" -> "기기 기본 목소리"
                        else -> "눈티 목소리"
                    }
                    Log.i(TAG, "JOURNEY_VOICE_STARTED request=${event.requestId} provider=${event.providerId}")
                }
                SpeechStatus.COMPLETED -> Log.i(TAG, "JOURNEY_VOICE_COMPLETED request=${event.requestId}")
                SpeechStatus.FAILED -> voiceStatus = "목소리를 재생하지 못했어요"
                SpeechStatus.REJECTED, SpeechStatus.CANCELLED -> {
                    if (event.reason == "OTHER_AUDIO" || event.reason == "FOCUS_LOST" || event.reason == "FOCUS_DENIED")
                        voiceStatus = "다른 안내가 끝날 때까지 쉬고 있어요"
                    Log.i(TAG, "JOURNEY_VOICE_SKIPPED reason=${event.reason}")
                }
                else -> Unit
            }
            session?.let { publish(it.snapshot(), true) }
            if (finishingSpeech && event.status in setOf(SpeechStatus.COMPLETED, SpeechStatus.FAILED,
                    SpeechStatus.CANCELLED, SpeechStatus.REJECTED)) stopSelf()
        }
        voiceStatus = "눈티 목소리 켜짐"
        publish(session!!.snapshot(), true)
        startForeground(9201, notification("${metadata.getString("displayName")}와 함께하는 여정"))
        Log.i(TAG, "JOURNEY_STARTED id=${session!!.sessionId} character=${session!!.characterId} source=${session!!.source}")
        speak("GREETING")
        main.post(tick)
    }

    private fun canFinish() = gate?.canDisplay() ?: !packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)

    private fun finishJourney() {
        val journey = session ?: return
        if (!canFinish() || journey.snapshot().finished) return
        main.removeCallbacks(tick)
        source?.stop(); source = null
        val snapshot = journey.finish()
        consumedFeedback = snapshot.feedback?.key
        publish(snapshot, true)
        Log.i(TAG, "JOURNEY_FINISHED id=${journey.sessionId} total=${snapshot.report.total} coverage=${snapshot.report.coverage}")
        speak(snapshot.emotion.name, finishing = true)
    }

    private fun publish(snapshot: JourneySnapshot, force: Boolean) {
        val parked = canFinish()
        val now = SystemClock.elapsedRealtime()
        val persist = force || parked != lastCanFinish || now - lastPersist >= 5000
        lastCanFinish = parked
        val report = snapshot.report
        val line = if (snapshot.finished && report.total == null) "수신된 주행 정보가 부족해 점수를 매기지 않았어요." else snapshot.emotion.line
        val value = JSONObject(metadata.toString())
            .put("state", if (snapshot.finished) "FINISHED" else "ACTIVE")
            .put("elapsedMs", snapshot.elapsedMs).put("sampleCount", snapshot.sampleCount)
            .put("total", report.total ?: JSONObject.NULL).put("coverage", report.coverage)
            .put("emotion", snapshot.emotion.name).put("line", line).put("canFinish", parked)
            .put("voiceStatus", if (muted) "음성 꺼짐" else voiceStatus).put("muted", muted)
            .put("updatedAtEpochMs", System.currentTimeMillis()).put("feedbackKey", consumedFeedback)
            .put("items", JSONArray().apply { report.items.forEach { item -> put(JSONObject()
                .put("label", item.item.label).put("score", item.score ?: JSONObject.NULL).put("basis", item.basis)) } })
            .put("events", JSONArray().apply { report.events.forEach { event -> put(JSONObject().put("tMs", event.tMs).put("label", event.label)) } })
            .put("speedKmh", snapshot.currentSample?.speedKmh ?: JSONObject.NULL)
            .put("gear", snapshot.currentSample?.gear?.name ?: JSONObject.NULL)
            .put("signalDetails", JSONArray().apply { source?.received()?.forEach { (key, value) -> put(JSONObject().put("label", key).put("value", value)) } })
        JourneyRuntime.publish(this, value, persist)
        if (persist) {
            lastPersist = now
            JourneyRuntime.write(File(filesDir, "journeys/${metadata.getString("sessionId")}-report.json"), value)
        }
    }

    private fun notification(text: String): Notification = Notification.Builder(this, CHANNEL)
        .setSmallIcon(android.R.drawable.ic_media_play).setContentTitle("눈티 · 함께하는 여정").setContentText(text)
        .setOngoing(true).setContentIntent(PendingIntent.getActivity(this, 0, Intent(this, JourneyActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)).build()

    private fun stopAudio() { speech?.stop() }

    private fun speak(kind: String, finishing: Boolean = false) {
        if (muted) { if (finishing) stopSelf(); return }
        val journey = session ?: return
        val snapshot = journey.snapshot()
        finishingSpeech = finishing
        val phase = when { finishing -> TripPhase.POST_TRIP; kind == "GREETING" -> TripPhase.PRE_TRIP
            else -> TripPhase.DRIVING }
        val source = when { finishing -> ContentSource.POST_DRIVE_REPORT; kind == "GREETING" -> ContentSource.PRE_DRIVE_GREETING
            else -> ContentSource.VERIFIED_EVENT_RESPONSE }
        val emotion = when (kind) { "WORRY" -> Emotion.CONCERNED; "RELIEF" -> Emotion.RELIEVED
            "JOY" -> Emotion.JOYFUL; else -> Emotion.NEUTRAL }
        val text = when {
            kind == "GREETING" -> "준비됐어. 우리 같이 출발하자."
            finishing && snapshot.report.total == null -> "도착했어. 이번 길은 주행 정보가 부족해서 점수는 남기지 못했어."
            finishing -> "도착했어. 오늘도 같이 와 줘서 고마워."
            kind == "WORRY" -> "조금만 천천히 가자."
            kind == "RELIEF" -> "이제 한결 편안해졌어."
            kind == "JOY" -> "편안한 길이네. 좋아."
            else -> "나도 옆에서 함께할게."
        }
        speech?.say(if (finishing) "ARRIVAL" else kind, text, phase, source, emotion, snapshot.feedback?.key)
            ?: if (finishing) stopSelf() else Unit
    }

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null); finishingSpeech = false; speech?.close(); speech = null; source?.stop(); gate?.close()
        session?.let { journey ->
            if (!journey.snapshot().finished) {
                val saved = JourneyRuntime.current
                if (saved != null) JourneyRuntime.publish(this, saved.put("state", "INTERRUPTED").put("canFinish", false)
                    .put("line", "여정 기록이 중단됐어요. 마지막 저장 기록입니다."), true)
            }
        }
        JourneyRuntime.isRunning = false
        super.onDestroy()
    }
    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "ai.nunti.journey.START"
        const val ACTION_FINISH = "ai.nunti.journey.FINISH"
        const val ACTION_MUTE = "ai.nunti.journey.MUTE"
        private const val CHANNEL = "nunti-journey"
        private const val TAG = "NuntiJourney"
    }
}
