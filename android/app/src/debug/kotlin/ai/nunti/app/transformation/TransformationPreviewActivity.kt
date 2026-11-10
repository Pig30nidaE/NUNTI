package ai.nunti.app.transformation

import ai.nunti.app.studio.StudioCarGate
import android.animation.ValueAnimator
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.AtomicFile
import android.util.Log
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.Executors

/** Debug-only, offline comparison prototype. No vehicle permission can be supplied by an Intent. */
class TransformationPreviewActivity : Activity() {
    private val main = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private val playback = TransformationPlayback()
    private val preferences by lazy { getSharedPreferences("nunti-transformation-preview", MODE_PRIVATE) }
    private val automotive by lazy { packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE) }
    private var carGate: StudioCarGate? = null
    private var foreground = false
    private var gateAllowed = false
    private var destroyed = false
    private var base: Bitmap? = null
    private var bundle: TransformationAssets? = null
    private var sample = "coast-curious"
    private var style = TransformationStyle.LIGHT_TRAIL
    private var night = false
    private var reduced = false
    private var readOnlyCapture = false
    private var simulateMissingAsset = false
    private var loadDelayMs = 0L
    private var loadEpoch = 0L
    private var loadError: String? = null
    private var pendingSeek: Long? = null
    private var pendingCapture = false
    private var pendingAutoPlay = false
    private var captureWritten = false
    private var captureAtMs = 0L
    private var captureError: String? = null
    private var restoreStatic = false
    private var playbackId = UUID.randomUUID().toString()
    private var lastFrameAt = 0L
    private val frameIntervals = mutableListOf<Long>()
    private var lastDiagnosticAt = 0L
    private var lastPhase = ""
    private lateinit var root: FrameLayout
    private lateinit var content: LinearLayout
    private lateinit var body: LinearLayout
    private lateinit var controls: LinearLayout
    private lateinit var stage: FrameLayout
    private lateinit var artwork: TransformationCanvasView
    private lateinit var title: TextView
    private lateinit var subtitle: TextView
    private lateinit var sampleLabel: TextView
    private lateinit var status: TextView
    private lateinit var details: TextView
    private lateinit var shield: TextView
    private lateinit var playButton: Button
    private lateinit var skipButton: Button
    private lateinit var styleButton: Button
    private lateinit var reducedButton: Button
    private lateinit var destinationButton: Button
    private lateinit var moodButton: Button
    private lateinit var themeButton: Button

    private val heartbeat = object : Runnable {
        override fun run() {
            if (!foreground || destroyed) return
            refreshGate()
            if (playback.state.running && effectiveReducedMotion()) finishMotion(StopReason.REDUCED_MOTION)
            processDebugRequest()
            updateUi()
            diagnostics()
            main.postDelayed(this, 250)
        }
    }

    private val frameTick = object : Runnable {
        override fun run() {
            if (!foreground || destroyed || !playback.state.running) return
            // Actual P/speed are re-read each frame; CarUxRestrictions also has an immediate callback.
            refreshGate()
            val now = SystemClock.elapsedRealtime()
            if (lastFrameAt != 0L) frameIntervals += now - lastFrameAt
            lastFrameAt = now
            playback.advance(now, gateAllowed, foreground, effectiveReducedMotion())
            render()
            val phase = TransformationTimeline.at(playback.state.elapsedMs).phase
            if (phase != lastPhase || !playback.state.running) { lastPhase = phase; updateUi(); diagnostics(force = true) }
            if (playback.state.running) main.postDelayed(this, 33)
            else artwork.announceForAccessibility("여행의 모습을 담은 눈티가 준비됐어요")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        reduced = preferences.getBoolean("reducedMotion", false)
        readOptions(intent)
        if (savedInstanceState != null) {
            sample = savedInstanceState.getString("sample", sample)
            style = runCatching { TransformationStyle.valueOf(savedInstanceState.getString("style", style.name)) }.getOrDefault(style)
            night = savedInstanceState.getBoolean("night", night)
            restoreStatic = savedInstanceState.getBoolean("consumed", false)
            pendingAutoPlay = false
            pendingSeek = null
            pendingCapture = false
        }
        base = TransformationAssets.base(this)
        buildUi()
        if (automotive) carGate = StudioCarGate(this) { main.post {
            if (!destroyed) { refreshGate(); updateUi(); diagnostics(force = true) }
        } }
        loadSample()
    }

    private fun readOptions(value: Intent) {
        sample = (value.getStringExtra("sample") ?: "coast-curious").takeIf { it in TransformationAssets.SAMPLE_IDS } ?: "base"
        style = runCatching { TransformationStyle.valueOf(value.getStringExtra("style") ?: "LIGHT_TRAIL") }.getOrDefault(TransformationStyle.LIGHT_TRAIL)
        night = value.getStringExtra("displayMode") == "night"
        readOnlyCapture = value.getBooleanExtra("readOnlyCapture", false)
        simulateMissingAsset = value.getBooleanExtra("simulateMissingAsset", false)
        loadDelayMs = numberExtra(value, "loadDelayMs").coerceIn(0, 3000)
        pendingSeek = if (value.hasExtra("seekMs")) numberExtra(value, "seekMs").coerceIn(0, 4000) else null
        pendingCapture = value.getBooleanExtra("captureFrame", false)
        pendingAutoPlay = value.getBooleanExtra("autoPlay", false) && !readOnlyCapture
    }

    private fun buildUi() {
        root = FrameLayout(this)
        content = column().apply { setPadding(dp(26), dp(18), dp(26), dp(20)) }
        val header = row().apply { gravity = Gravity.CENTER_VERTICAL }
        val headings = column()
        title = label(26, true).apply { text = "같은 눈티, 여행의 새 모습" }
        subtitle = label(14).apply { text = "승인 A · 4초 변신 시안 · 오프라인"; setPadding(0, dp(5), 0, 0) }
        headings.addView(title); headings.addView(subtitle)
        header.addView(headings, LinearLayout.LayoutParams(0, -2, 1f))
        themeButton = button("") { night = !night; applyTheme(); updateUi(); diagnostics(force = true) }
        header.addView(themeButton, LinearLayout.LayoutParams(dp(112), dp(56)).apply { leftMargin = dp(12) })
        content.addView(header)
        body = row().apply { setPadding(0, dp(18), 0, 0) }
        stage = FrameLayout(this)
        artwork = TransformationCanvasView(this)
        stage.addView(artwork, FrameLayout.LayoutParams(-1, -1))
        body.addView(stage)
        controls = column().apply { gravity = Gravity.CENTER_VERTICAL }
        sampleLabel = label(25, true)
        status = label(18, true).apply { setPadding(0, dp(12), 0, dp(8)); minLines = 2 }
        details = label(15).apply { setPadding(0, 0, 0, dp(20)); minLines = 2 }
        controls.addView(sampleLabel); controls.addView(status); controls.addView(details)
        val choices = row()
        destinationButton = button("") { cycleDestination() }
        moodButton = button("") { cycleMood() }
        addPair(choices, destinationButton, moodButton)
        controls.addView(choices)
        styleButton = button("") {
            if (playback.state.running) finishMotion(StopReason.SKIPPED)
            style = if (style == TransformationStyle.LIGHT_TRAIL) TransformationStyle.QUIET_COLOR else TransformationStyle.LIGHT_TRAIL
            render(); updateUi(); diagnostics(force = true)
        }
        controls.addView(styleButton, LinearLayout.LayoutParams(-1, dp(58)).apply { topMargin = dp(10) })
        reducedButton = button("") {
            reduced = !reduced
            preferences.edit().putBoolean("reducedMotion", reduced).apply()
            if (effectiveReducedMotion()) finishMotion(StopReason.REDUCED_MOTION)
            updateUi(); diagnostics(force = true)
        }
        controls.addView(reducedButton, LinearLayout.LayoutParams(-1, dp(58)).apply { topMargin = dp(10) })
        val actions = row()
        playButton = button("변신 보기") { startMotion() }
        skipButton = button("바로 보기") { finishMotion(StopReason.SKIPPED) }
        addPair(actions, playButton, skipButton)
        controls.addView(actions, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(18) })
        body.addView(controls)
        content.addView(body, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(content, FrameLayout.LayoutParams(-1, -1))
        shield = label(22, true).apply {
            gravity = Gravity.CENTER
            text = "주차한 뒤 눈티를 만나세요.\n기어 P · 정차 · 차량 화면 사용 허가가 필요해요."
            isClickable = true; isFocusable = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        }
        root.addView(shield, FrameLayout.LayoutParams(-1, -1))
        setContentView(root)
        root.addOnLayoutChangeListener { _, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom ->
            if (right - left != oldRight - oldLeft || bottom - top != oldBottom - oldTop) adaptLayout(right - left, bottom - top)
        }
        applyTheme()
        updateUi()
    }

    private fun adaptLayout(width: Int, height: Int) {
        val horizontal = width >= dp(840) && width > height * 1.1
        body.orientation = if (horizontal) LinearLayout.HORIZONTAL else LinearLayout.VERTICAL
        stage.layoutParams = if (horizontal) LinearLayout.LayoutParams(0, -1, 1f)
            else LinearLayout.LayoutParams(-1, 0, 1f)
        controls.layoutParams = if (horizontal) LinearLayout.LayoutParams(dp(350), -1).apply { leftMargin = dp(28) }
            else LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) }
        val compact = height < dp(700)
        status.minLines = if (horizontal && !compact) 2 else 1
        details.minLines = if (horizontal) 2 else 1
        details.visibility = if (compact || (!horizontal && height < dp(800))) View.GONE else View.VISIBLE
        render()
    }

    private fun applyTheme() {
        val background = if (night) Color.rgb(28, 45, 41) else Color.rgb(246, 244, 239)
        val surface = if (night) Color.rgb(38, 60, 56) else Color.rgb(238, 242, 231)
        val ink = if (night) Color.rgb(237, 244, 234) else Color.rgb(42, 64, 54)
        val secondary = if (night) Color.rgb(190, 209, 195) else Color.rgb(92, 114, 99)
        content.setBackgroundColor(background)
        shield.setBackgroundColor(background); shield.setTextColor(ink)
        stage.background = rounded(surface, 24)
        for (view in listOf(title, sampleLabel, status)) view.setTextColor(ink)
        subtitle.setTextColor(secondary); details.setTextColor(secondary)
        for (button in listOf(themeButton, destinationButton, moodButton, styleButton, reducedButton, skipButton)) {
            button.setTextColor(ink); button.background = rounded(surface, 13, if (night) 0xff476659.toInt() else 0xffc8d6c4.toInt())
        }
        playButton.setTextColor(Color.rgb(34, 61, 44))
        playButton.background = rounded(Color.rgb(194, 220, 180), 13)
    }

    private fun loadSample() {
        val epoch = ++loadEpoch
        val selected = sample
        main.removeCallbacks(frameTick)
        bundle = null; loadError = null; playback.loading(); lastFrameAt = 0; frameIntervals.clear()
        captureWritten = false; captureAtMs = 0L; captureError = null
        render(); updateUi(); diagnostics(force = true)
        io.execute {
            val result = runCatching {
                if (loadDelayMs > 0) Thread.sleep(loadDelayMs)
                TransformationAssets.load(this, selected, simulateMissingAsset)
            }
            main.post {
                if (destroyed || epoch != loadEpoch) return@post
                result.onSuccess {
                    bundle = it; playback.ready()
                    if (restoreStatic) { playback.stop(StopReason.BACKGROUNDED); restoreStatic = false }
                    else if (effectiveReducedMotion()) playback.stop(StopReason.REDUCED_MOTION)
                }.onFailure {
                    loadError = it.javaClass.simpleName + ":" + (it.message ?: "ASSET_UNAVAILABLE")
                    playback.failed()
                }
                refreshGate()
                // An explicit debug play request denied at readiness never waits for parking to auto-start.
                if (!gateAllowed) pendingAutoPlay = false
                processDebugRequest()
                render(); updateUi(); diagnostics(force = true)
            }
        }
    }

    private fun refreshGate() {
        val next = foreground && (if (automotive) carGate?.canDisplay() == true else true)
        if (!next && gateAllowed && playback.state.running) finishMotion(if (foreground) StopReason.RESTRICTED else StopReason.BACKGROUNDED)
        if (!next && gateAllowed) pendingAutoPlay = false
        gateAllowed = next
        content.importantForAccessibility = if (next) View.IMPORTANT_FOR_ACCESSIBILITY_AUTO else View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        content.visibility = if (next) View.VISIBLE else View.INVISIBLE
        shield.visibility = if (next) View.GONE else View.VISIBLE
        shield.text = if (foreground) "주차한 뒤 눈티를 만나세요.\n기어 P · 정차 · 차량 화면 사용 허가가 필요해요." else "눈티가 잠시 쉬고 있어요."
    }

    private fun startMotion() {
        refreshGate()
        if (!playback.play(SystemClock.elapsedRealtime(), gateAllowed, effectiveReducedMotion())) {
            render(); updateUi(); diagnostics(force = true); return
        }
        playbackId = UUID.randomUUID().toString(); lastFrameAt = 0; frameIntervals.clear(); lastPhase = ""
        main.removeCallbacks(frameTick); main.post(frameTick)
        artwork.announceForAccessibility("같은 눈티에 여행의 장식과 표정이 더해집니다. 바로 보기로 건너뛸 수 있어요")
        render(); updateUi(); diagnostics(force = true)
    }

    private fun finishMotion(reason: StopReason) {
        playback.stop(reason)
        main.removeCallbacks(frameTick)
        render(); updateUi(); diagnostics(force = true)
    }

    private fun processDebugRequest() {
        if (!gateAllowed || (!playback.state.assetsReady && playback.state.status != PlaybackStatus.FAILED)) return
        pendingSeek?.let {
            main.removeCallbacks(frameTick)
            playback.seek(if (effectiveReducedMotion()) 4000 else it, gateAllowed)
            pendingSeek = null
            render(); updateUi()
        }
        if (pendingAutoPlay) { pendingAutoPlay = false; startMotion() }
        if (pendingCapture) { pendingCapture = false; captureFrame() }
    }

    private fun captureFrame() {
        // The same actual gate applies to debug captures. It cannot enable playback or vehicle UI.
        if (!foreground || !gateAllowed) return
        captureWritten = false; captureError = null
        val captured = artwork.captureArtwork()
        val final = bundle?.finalImage ?: base
        val captureEpoch = loadEpoch
        io.execute {
            val result = runCatching {
                File(filesDir, "nunti-transformation-frame.png").outputStream().use { check(captured.compress(Bitmap.CompressFormat.PNG, 100, it)) }
                final?.let { image -> File(filesDir, "nunti-transformation-final-reference.png").outputStream().use { check(image.compress(Bitmap.CompressFormat.PNG, 100, it)) } }
            }.onFailure { Log.w("NuntiTransform", "CAPTURE_FAILED", it) }
            captured.recycle()
            main.post {
                if (!destroyed && captureEpoch == loadEpoch) {
                    captureError = result.exceptionOrNull()?.javaClass?.simpleName
                    diagnostics(force = true, captured = result.isSuccess)
                }
            }
        }
    }

    private fun cycleDestination() {
        val categories = listOf("coast", "mountain", "city")
        val next = categories[(categories.indexOf(sample.substringBefore('-')) + 1).mod(3)]
        val mood = sample.substringAfter('-', "curious").takeIf { it in listOf("calm", "curious", "adventurous") } ?: "curious"
        sample = "$next-$mood"; loadSample()
    }

    private fun cycleMood() {
        val moods = listOf("calm", "curious", "adventurous")
        val next = moods[(moods.indexOf(sample.substringAfter('-', "curious")) + 1).mod(3)]
        val destination = sample.substringBefore('-').takeIf { it in listOf("coast", "mountain", "city") } ?: "coast"
        sample = "$destination-$next"; loadSample()
    }

    private fun effectiveReducedMotion() = reduced || !ValueAnimator.areAnimatorsEnabled()

    private fun render() { artwork.update(base, bundle, playback.state, style) }

    private fun updateUi() {
        val destination = when (sample.substringBefore('-')) { "coast" -> "바다"; "mountain" -> "산"; "city" -> "도시"; else -> "기본" }
        val mood = when (sample.substringAfter('-', "")) { "calm" -> "차분함"; "curious" -> "호기심"; "adventurous" -> "모험심"; else -> "친근함" }
        sampleLabel.text = "$destination · $mood"
        destinationButton.text = "목적지: $destination"
        moodButton.text = "기분: $mood"
        styleButton.text = if (style == TransformationStyle.LIGHT_TRAIL) "방향: 빛의 길" else "방향: 고요한 색"
        reducedButton.text = "움직임 줄이기: " + if (effectiveReducedMotion()) "켜짐" else "꺼짐"
        reducedButton.contentDescription = reducedButton.text.toString() + if (!ValueAnimator.areAnimatorsEnabled()) ". 시스템 설정 적용 중" else ""
        themeButton.text = if (night) "야간" else "주간"
        val state = playback.state
        status.text = when {
            state.status == PlaybackStatus.LOADING -> "익숙한 기본 눈티와 기다려요"
            state.status == PlaybackStatus.FAILED -> "기본 눈티와 함께해요"
            state.running -> when (TransformationTimeline.at(state.elapsedMs).phase) {
                "BASE" -> "늘 함께하던 눈티에서 시작해요"
                "ROUTE" -> "여행의 길을 작은 무늬로"
                "COLOR", "DESTINATION" -> "목적지의 풍경을 조금 더해요"
                "EXPRESSION" -> "직접 고른 기분을 담아요"
                else -> "여행의 모습이 완성됐어요"
            }
            state.finalVisible -> "같은 눈티, 새로운 여행의 모습"
            state.stopReason == StopReason.CAPTURE -> "같은 눈티의 변신 중간 모습"
            else -> "기본 눈티에 여행의 모습을 더해요"
        }
        details.text = when {
            state.status == PlaybackStatus.FAILED -> "장식을 불러오지 못해 기본 모습으로 보여드려요. 다른 모습을 선택하면 다시 준비해요."
            effectiveReducedMotion() -> "움직임 없이 완성된 모습으로 만나요."
            state.stopReason == StopReason.RESTRICTED || state.stopReason == StopReason.BACKGROUNDED -> "멈춘 변신은 자동으로 다시 재생하지 않아요."
            else -> "몸과 얼굴의 자리는 그대로, 장식과 표정만 변해요."
        }
        val interactive = gateAllowed && !readOnlyCapture
        playButton.isEnabled = interactive && state.assetsReady && !state.running
        skipButton.isEnabled = interactive
        for (button in listOf(styleButton, destinationButton, moodButton)) button.isEnabled = interactive && !state.running
        reducedButton.isEnabled = interactive
        themeButton.isEnabled = interactive
        for (button in listOf(playButton, skipButton, styleButton, destinationButton, moodButton, reducedButton, themeButton)) {
            button.alpha = if (button.isEnabled) 1f else .45f
        }
    }

    private fun diagnostics(force: Boolean = false, captured: Boolean = false) {
        val now = SystemClock.elapsedRealtime()
        if (captured) { captureWritten = true; captureAtMs = now }
        if (!force && now - lastDiagnosticAt < 250) return
        lastDiagnosticAt = now
        val state = playback.state
        val json = JSONObject().put("schemaVersion", 1).put("elapsedRealtimeMs", now).put("playbackId", playbackId)
            .put("sample", sample).put("style", style.name).put("displayMode", if (night) "night" else "day")
            .put("status", state.status.name).put("phase", TransformationTimeline.at(state.elapsedMs).phase)
            .put("elapsedMs", state.elapsedMs).put("animationRunning", state.running)
            .put("stopReason", state.stopReason.name).put("foreground", foreground).put("gateAllowed", gateAllowed)
            .put("gateSource", if (automotive) "ACTUAL_CAR_SERVICE" else "NON_VEHICLE_DESKTOP")
            .put("assetsReady", state.assetsReady).put("baseReady", base != null).put("reducedMotion", effectiveReducedMotion())
            .put("systemAnimatorsEnabled", ValueAnimator.areAnimatorsEnabled()).put("readOnlyCapture", readOnlyCapture)
            .put("frameCount", artwork.frameCount).put("targetFps", 30).put("frameIntervalsMs", JSONArray(frameIntervals.toList()))
            .put("maxFrameIntervalMs", frameIntervals.maxOrNull() ?: 0)
            .put("meanFrameIntervalMs", if (frameIntervals.isEmpty()) 0.0 else frameIntervals.average())
            .put("finalSourceHash", bundle?.finalSourceHash ?: JSONObject.NULL)
            .put("variantId", bundle?.variantId ?: JSONObject.NULL).put("loadError", loadError ?: JSONObject.NULL)
            .put("simulateMissingAsset", simulateMissingAsset).put("captureWritten", captureWritten).put("captureAtMs", captureAtMs)
            .put("captureReference", if (bundle == null) "APPROVED_BASE" else "FINAL_VARIANT")
            .put("captureError", captureError ?: JSONObject.NULL)
        val text = json.toString()
        if (force) Log.i("NuntiTransform", text)
        if (!destroyed) io.execute {
            val file = AtomicFile(File(filesDir, "nunti-transformation-state.json"))
            val stream = file.startWrite()
            try { stream.write(text.toByteArray()); file.finishWrite(stream) }
            catch (error: Exception) { file.failWrite(stream); Log.w("NuntiTransform", "DIAGNOSTIC_WRITE_FAILED", error) }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (playback.state.running) finishMotion(StopReason.SKIPPED)
        readOptions(intent)
        restoreStatic = false
        playbackId = UUID.randomUUID().toString()
        applyTheme(); loadSample()
    }

    override fun onResume() {
        super.onResume()
        foreground = true
        main.removeCallbacks(heartbeat); main.post(heartbeat)
        refreshGate(); updateUi(); diagnostics(force = true)
    }

    override fun onPause() {
        foreground = false; pendingAutoPlay = false
        if (playback.state.running) finishMotion(StopReason.BACKGROUNDED)
        main.removeCallbacks(frameTick); main.removeCallbacks(heartbeat)
        refreshGate(); diagnostics(force = true)
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("sample", sample); outState.putString("style", style.name); outState.putBoolean("night", night)
        outState.putBoolean("consumed", playback.state.running || playback.state.status == PlaybackStatus.SETTLED)
        super.onSaveInstanceState(outState)
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        root.post { adaptLayout(root.width, root.height); diagnostics(force = true) }
    }

    override fun onDestroy() {
        destroyed = true; loadEpoch++
        main.removeCallbacksAndMessages(null); carGate?.close(); io.shutdown()
        super.onDestroy()
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density + .5f).toInt()
    @Suppress("DEPRECATION")
    private fun numberExtra(value: Intent, key: String): Long = (value.extras?.get(key) as? Number)?.toLong() ?: 0L
    private fun column() = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
    private fun row() = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
    private fun label(size: Int, bold: Boolean = false) = TextView(this).apply {
        textSize = size.toFloat(); if (bold) setTypeface(typeface, Typeface.BOLD)
    }
    private fun button(text: String, action: () -> Unit) = Button(this).apply {
        this.text = text; textSize = 16f; isAllCaps = false; minHeight = dp(56)
        setPadding(dp(10), dp(5), dp(10), dp(5)); setOnClickListener { if (gateAllowed && this@TransformationPreviewActivity.foreground) action() }
    }
    private fun addPair(parent: LinearLayout, first: Button, second: Button) {
        parent.addView(first, LinearLayout.LayoutParams(0, dp(58), 1f).apply { rightMargin = dp(5) })
        parent.addView(second, LinearLayout.LayoutParams(0, dp(58), 1f).apply { leftMargin = dp(5) })
    }
    private fun rounded(color: Int, radius: Int, stroke: Int? = null) = GradientDrawable().apply {
        setColor(color); cornerRadius = dp(radius).toFloat(); if (stroke != null) setStroke(dp(1), stroke)
    }
}
