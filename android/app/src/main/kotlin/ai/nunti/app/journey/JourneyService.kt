package ai.nunti.app.journey

import ai.nunti.app.studio.StudioCarGate
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
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
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
    private var voiceStatus = "캐릭터 음성 미준비 · 화면으로 안내해요"
    private var muted = false
    private var consumedFeedback: String? = null
    private var player: MediaPlayer? = null
    private var focus: AudioFocusRequest? = null
    private val audioManager by lazy { getSystemService(AudioManager::class.java) }
    private var demoCursor = 0
    private var lastPersist = 0L
    private var lastCanFinish = false
    private val tick = object : Runnable {
        override fun run() {
            val journey = session ?: return
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
        val ready = listOf("NEUTRAL", "WORRY", "RELIEF", "JOY").count { metadata.getJSONObject("voices").has(it) }
        voiceStatus = if (ready == 4) "보관된 캐릭터 음성" else "감정 음성 $ready/4 준비 · 없는 대사는 화면으로 안내해요"
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

    private fun stopAudio() {
        player?.setOnCompletionListener(null); player?.release(); player = null
        focus?.let { audioManager.abandonAudioFocusRequest(it) }; focus = null
    }

    private fun speak(kind: String, finishing: Boolean = false) {
        stopAudio()
        val path = metadata.getJSONObject("voices").optString(kind)
        if (muted || path.isBlank()) {
            if (!muted && kind != "GREETING") voiceStatus = "이 감정의 캐릭터 음성이 아직 준비되지 않았어요"
            session?.let { publish(it.snapshot(), true) }
            if (finishing) stopSelf()
            return
        }
        val file = File(path).canonicalFile
        if (file.parentFile != File(filesDir, "journeys/assets").canonicalFile || !file.isFile) {
            voiceStatus = "보관된 음원을 찾지 못했어요"; if (finishing) stopSelf(); return
        }
        val attributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
        val media = MediaPlayer(); player = media
        fun complete() { if (player === media) stopAudio(); if (finishing) stopSelf() }
        media.setAudioAttributes(attributes)
        media.setOnCompletionListener { Log.i(TAG, "JOURNEY_VOICE_COMPLETED kind=$kind"); complete() }
        media.setOnErrorListener { _, _, _ -> voiceStatus = "음원 재생에 실패했어요"; complete(); true }
        media.setOnPreparedListener {
            if (player !== media) return@setOnPreparedListener
            val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(attributes).setOnAudioFocusChangeListener({ change -> if (change < 0) complete() }, main).build()
            focus = request
            if (audioManager.requestAudioFocus(request) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) { complete(); return@setOnPreparedListener }
            media.start(); voiceStatus = "보관된 캐릭터 음성"
            Log.i(TAG, "JOURNEY_VOICE_STARTED kind=$kind character=${metadata.getString("characterId")}")
        }
        runCatching { media.setDataSource(file.path); media.prepareAsync() }.onFailure { complete() }
    }

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null); stopAudio(); source?.stop(); gate?.close()
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
