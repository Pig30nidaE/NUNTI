package ai.nunti.app.journey

import ai.nunti.app.studio.StudioCarGate
import ai.nunti.score.ClosingMessage
import ai.nunti.score.EventSpeaker
import ai.nunti.score.Scenarios
import ai.nunti.score.SpeechSink
import ai.nunti.score.journey.JourneySession
import ai.nunti.score.journey.JourneySnapshot
import ai.nunti.score.journey.JourneySource
import ai.nunti.score.journey.JourneyAnalysis
import ai.nunti.score.journey.TripPosition
import ai.nunti.score.live.PleosSignalSource
import ai.nunti.score.live.PleosSpeechSink
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
    private val analysis = JourneyAnalysis()
    private var source: PleosSignalSource? = null
    private var locationSource: JourneyLocationSource? = null
    private var gate: StudioCarGate? = null
    private lateinit var metadata: JSONObject
    private var voiceStatus = "캐릭터 음성 미준비 · 화면으로 안내해요"
    private var muted = false
    private var consumedFeedback: String? = null
    private var player: MediaPlayer? = null
    private var focus: AudioFocusRequest? = null
    private val audioManager by lazy { getSystemService(AudioManager::class.java) }
    /**
     * 캐릭터 감정 음원이 4개 다 있지 않으면 눈티 목소리가 대신 말한다: 녹음한 문장은 음원으로, 나머지는 Pleos TTS 로.
     * 주행 중에는 사건 반응과 감정 변화([EventSpeaker], 점수 화면과 같은 규칙), 끝나면 마무리 멘트([ClosingMessage]).
     */
    private var nuntiVoice: PleosSpeechSink? = null
    private var nuntiSpeaker: EventSpeaker? = null
    private var demoCursor = 0
    private var lastPersist = 0L
    private var lastCanFinish = false
    private val tick = object : Runnable {
        override fun run() {
            val journey = session ?: return
            if (journey.snapshot().finished) return
            val snapshot = if (journey.source == JourneySource.LIVE) {
                val signals = source ?: return
                val sample = signals.snapshot()
                if(locationSource==null)locationSource=JourneyLocationSource(this@JourneyService)
                analysis.observe(sample, locationSource?.position(), signals.events())
                journey.add(sample, signals.events())
            } else {
                if (!canFinish()) { publish(journey.snapshot(), false); main.postDelayed(this, 500); return }
                val scenario = Scenarios.contextDrive
                if (demoCursor > scenario.samples.lastIndex) {
                    publish(journey.snapshot(), false); main.postDelayed(this, 500); return
                }
                val sample = scenario.samples[demoCursor++]
                analysis.observe(sample, simulationPosition(sample.tMs.toDouble()/scenario.samples.last().tMs), scenario.events.filter { it.tMs<=sample.tMs })
                journey.add(sample, scenario.events.filter { it.tMs <= sample.tMs })
            }
            publish(snapshot, false)
            // 간격(15초)은 여정 시간으로 잰다. 실제 주행에서는 실제 시간과 같고, 빨리 재생하는 시연에서도 사건을 덜 놓친다.
            nuntiSpeaker?.onUpdate(snapshot.report, snapshot.emotion, snapshot.elapsedMs)
            snapshot.feedback?.let { feedback ->
                if (feedback.key != consumedFeedback) {
                    consumedFeedback = feedback.key
                    publish(snapshot, true) // Claim before playback: restore never repeats a spoken event.
                    speak(feedback.kind.name)
                }
            }
            main.postDelayed(this, if (journey.source == JourneySource.LIVE) 1000 else 180)
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
        voiceStatus = if (ready == 4) "보관된 캐릭터 음성" else "눈티 목소리로 안내해요"
        if (ready < 4) {
            // 시연(DEMO)은 정차한 채 재생하므로 주행 중 음성을 허용한다. 실제 주행은 검토 전이라 막고, 마무리 멘트(정차 후)만 말한다.
            val voice = PleosSpeechSink(applicationContext, drivingAllowed = session!!.source == JourneySource.DEMO) {
                Log.i(TAG, "NUNTI_VOICE $it")
            }
            nuntiVoice = voice
            nuntiSpeaker = EventSpeaker(SpeechSink { text, id, emotion -> if (!muted) voice.speak(text, id, emotion) })
        }
        publish(session!!.snapshot(), true)
        startForeground(9201, notification("${metadata.getString("displayName")}와 함께하는 여정"))
        Log.i(TAG, "JOURNEY_STARTED id=${session!!.sessionId} character=${session!!.characterId} source=${session!!.source}")
        speak("GREETING")
        main.post(tick)
    }

    private fun canFinish() = gate?.canDisplay() ?: !packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)

    private fun simulationPosition(progress: Double): TripPosition.Simulation {
        val points=metadata.optJSONObject("route")?.optJSONArray("points")
        val fallback=listOf(.08 to .8,.25 to .8,.25 to .48,.58 to .48,.58 to .22,.9 to .22)
        val route=if(points!=null&&points.length()>=2) (0 until points.length()).map { i ->
            val p=points.getJSONArray(i);p.getDouble(0) to p.getDouble(1)
        } else fallback
        val cursor=progress.coerceIn(0.0,1.0)*(route.size-1)
        val index=cursor.toInt().coerceAtMost(route.size-2);val part=cursor-index
        val a=route[index];val b=route[index+1]
        return TripPosition.Simulation(a.first+(b.first-a.first)*part,a.second+(b.second-a.second)*part)
    }

    private fun finishJourney() {
        val journey = session ?: return
        if (!canFinish() || journey.snapshot().finished) return
        main.removeCallbacks(tick)
        source?.stop(); source = null
        locationSource?.close()
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
        val insights = analysis.build(report)
        val recent = insights.events.lastOrNull()?.takeIf { !snapshot.finished && snapshot.currentSample!=null && snapshot.elapsedMs-it.tMs in 0..15_000 }
        val eventAge = recent?.let { snapshot.elapsedMs-it.tMs }
        // Vehicle events affect this presentation only; explicit mood and the team's score stay intact.
        val expression = when { eventAge==null -> snapshot.emotion.name; eventAge<8000 -> "WORRY"; else -> "RELIEF" }
        val line = when {
            snapshot.finished && report.total == null -> "수신된 주행 정보가 부족해 점수를 매기지 않았어요."
            eventAge!=null && eventAge<8000 -> recent.advice
            eventAge!=null -> "다시 부드럽게 달리고 있어요."
            else -> snapshot.emotion.line
        }
        val value = JSONObject(metadata.toString())
            .put("state", if (snapshot.finished) "FINISHED" else "ACTIVE")
            .put("elapsedMs", snapshot.elapsedMs).put("sampleCount", snapshot.sampleCount)
            .put("total", report.total ?: JSONObject.NULL).put("coverage", report.coverage)
            .put("emotion", expression).put("line", line).put("canFinish", parked)
            .put("voiceStatus", if (muted) "음성 꺼짐" else voiceStatus).put("muted", muted)
            .put("updatedAtEpochMs", System.currentTimeMillis()).put("feedbackKey", consumedFeedback)
            .put("items", JSONArray().apply { report.items.forEach { item -> put(JSONObject()
                .put("id",item.item.name).put("area",item.item.area.label).put("label", item.item.label).put("score", item.score ?: JSONObject.NULL).put("basis", item.basis.text)) } })
            .put("areas",JSONArray().apply { report.areas.forEach { area -> put(JSONObject().put("label",area.area.label).put("maxPoints",area.area.maxPoints).put("score",area.score?:JSONObject.NULL)) } })
            .put("events", JSONArray().apply { insights.events.forEach { event -> put(JSONObject().put("tMs",event.tMs).put("label",event.label)
                .put("evidence",event.evidence).put("advice",event.advice).put("position",positionJson(event.position))
                .put("speedKmh",event.speedKmh?:JSONObject.NULL).put("includedInScore",event.includedInScore)) } })
            .put("habits",JSONArray().apply { insights.habits.forEach { habit -> put(JSONObject().put("positive",habit.positive).put("title",habit.title).put("detail",habit.detail)) } })
            .put("distanceKm",insights.distanceKm).put("steeringAvailable",insights.steeringAvailable)
            .put("locationStatus",locationSource?.status?:"시뮬레이션 경로")
            .put("track",JSONArray().apply { val track=analysis.track(); val step=maxOf(1,track.size/600);track.filterIndexed { i,_ -> i%step==0||i==track.lastIndex }.forEach { point ->
                put(JSONObject().put("tMs",point.sample.tMs).put("position",positionJson(point.position)).put("speedKmh",point.sample.speedKmh?:JSONObject.NULL)) } })
            .put("windowScores",JSONArray().apply { report.windowOverall.forEach { put(it?:JSONObject.NULL) } })
            .put("speedKmh", snapshot.currentSample?.speedKmh ?: JSONObject.NULL)
            .put("gear", snapshot.currentSample?.gear?.name ?: JSONObject.NULL)
            .put("steeringAngleDeg",snapshot.currentSample?.steeringDeg?:JSONObject.NULL)
            .put("signalDetails", JSONArray().apply { source?.received()?.forEach { (key, value) -> put(JSONObject().put("label", key).put("value", value ?: "미수신")) } })
        JourneyRuntime.publish(this, value, persist)
        if (persist) {
            lastPersist = now
            JourneyRuntime.write(File(filesDir, "journeys/${metadata.getString("sessionId")}-report.json"), value)
        }
    }

    private fun positionJson(position: TripPosition?): Any = when(position) {
        is TripPosition.Geographic -> JSONObject().put("space","WGS84").put("latitude",position.latitude).put("longitude",position.longitude)
        is TripPosition.Simulation -> JSONObject().put("space","SIMULATION").put("x",position.x).put("y",position.y)
        null -> JSONObject.NULL
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
        nuntiVoice?.let { voice ->
            // 주행 중 대사(인사 포함)는 nuntiSpeaker 가 tick 에서 맡는다. 여기서는 마무리 멘트만.
            if (finishing) speakClosing(voice)
            return
        }
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

    /** 마무리 멘트를 말하고, 끝나면(또는 늦어도 30초 뒤) 서비스를 닫는다. */
    private fun speakClosing(voice: PleosSpeechSink) {
        val journey = session?.snapshot()
        if (muted || journey == null) { stopSelf(); return }
        val prefs = getSharedPreferences("nunti-voice", MODE_PRIVATE)
        val variant = prefs.getInt("closingCount", 0).also { prefs.edit().putInt("closingCount", it + 1).apply() }
        val text = ClosingMessage.compose(journey.report, journey.emotion, variant)
        Log.i(TAG, "JOURNEY_CLOSING text=$text")
        var stopped = false
        val stop = Runnable { if (!stopped) { stopped = true; stopSelf() } }
        voice.speakTripReport(text, "nunti-closing-${journey.elapsedMs}", journey.emotion) { main.post(stop) }
        main.postDelayed(stop, 30_000)
    }

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null); stopAudio(); nuntiVoice?.close(); nuntiVoice = null; source?.stop(); locationSource?.close(); gate?.close()
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
