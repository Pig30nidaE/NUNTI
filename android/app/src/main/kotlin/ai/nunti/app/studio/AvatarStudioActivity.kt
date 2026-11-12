package ai.nunti.app.studio

import ai.nunti.avatar.CarUxPolicyBinding
import ai.nunti.app.navigation.PleosNavigationAdapter
import ai.nunti.tts.SpeechStatus
import android.animation.ValueAnimator
import android.car.Car
import android.car.VehicleGear
import android.car.VehiclePropertyIds
import android.car.drivingstate.CarUxRestrictions
import android.car.drivingstate.CarUxRestrictionsManager
import android.car.hardware.property.CarPropertyManager
import android.car.hardware.CarPropertyValue
import android.content.Intent
import android.content.res.Configuration
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.View
import android.view.WindowInsets
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.addCallback
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.Executors
import kotlin.math.abs
import org.json.JSONObject

private const val MOCK_SKIN_MODE = true
private val PARKED_STUDIO_MUTATIONS = setOf("/v3/wardrobe", "/v3/avatars", "/v3/conversation")
private val STUDIO_MUTATIONS = PARKED_STUDIO_MUTATIONS + setOf("/session", "/v3/route-extractions", "/v3/route-plans")

/** The same tested generator UI is used by the browser and the actual Android host.
 * Vehicle display is gated with actual Car service values; no query flag can authorize it.
 * Provider credentials never enter this host. Connection is to a loopback-forwarded studio.
 */
class AvatarStudioActivity : ComponentActivity() {
    private val main = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private lateinit var web: WebView
    private lateinit var shield: TextView
    private lateinit var characterMotion: StudioCharacterMotion
    private var carGate: StudioCarGate? = null
    private var navigation: PleosNavigationAdapter? = null
    private var foreground = false
    @Volatile private var allowed = false
    @Volatile private var characterPageEpoch = 0
    private var loaded = false
    private var connected = false
    private var connectionFailed = false
    private var appearanceKey = ""
    private var tts: TextToSpeech? = null
    private var conversationVoice: StudioConversationVoice? = null
    private var activeUtterance: String? = null
    private var activeSpeechRequest: String? = null
    private var lastSpeechAmplitudeAt = 0L
    private var utteranceSequence = 0L
    private var voicePlayer: MediaPlayer? = null
    private var voiceFocus: AudioFocusRequest? = null
    private val audioManager by lazy { getSystemService(AudioManager::class.java) }
    @Volatile private var ttsReady = false
    private var picker: ValueCallback<Array<Uri>>? = null
    @Volatile private var preparingJourney = false
    private val base = "http://127.0.0.1:8768"
    private val tick = object : Runnable {
        override fun run() { refreshGate(); main.postDelayed(this, 250) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        val container = FrameLayout(this)
        web = WebView(this)
        web.addOnLayoutChangeListener { _, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom ->
            if (right - left != oldRight - oldLeft || bottom - top != oldBottom - oldTop) {
                characterMotion.stop(notify = true)
                notifyAppearance(force = true)
            }
        }
        shield = TextView(this).apply {
            text = "눈티는 주차 중에 만날 수 있어요.\n차량 상태를 확인하고 있습니다."
            textSize = 20f; gravity = android.view.Gravity.CENTER
            setTextColor(0xff42695a.toInt()); setBackgroundColor(0xfff4f3ee.toInt())
        }
        container.addView(web, FrameLayout.LayoutParams(-1, -1))
        container.addView(shield, FrameLayout.LayoutParams(-1, -1))
        characterMotion = StudioCharacterMotion(
            container, web, shield, main, io, ::canPlayCharacterMotion, ::reportCharacterReady, ::reportCharacterFinished, ::reportCompanionReady,
        )
        setContentView(container)
        if (android.os.Build.VERSION.SDK_INT >= 30) container.setOnApplyWindowInsetsListener { _, insets ->
            if (insets.isVisible(WindowInsets.Type.ime())) characterMotion.stop(notify = true)
            insets
        }
        onBackPressedDispatcher.addCallback(this) {
            web.evaluateJavascript("window.NuntiChat?.close() === true") { closed ->
                if (closed != "true") {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                    isEnabled = true
                }
            }
        }
        shield.setOnClickListener {
            if (allowed && connectionFailed) { connectionFailed = false; web.reload(); refreshGate() }
        }
        WebView.setWebContentsDebuggingEnabled(applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0)
        web.settings.apply {
            javaScriptEnabled = true; domStorageEnabled = true
            // Pleos WebView has its own DPR. Honor our measured-window viewport
            // instead of treating the physical Figma artboard as device-width CSS pixels.
            useWideViewPort = true
            allowFileAccess = false; allowContentAccess = false
            mediaPlaybackRequiresUserGesture = true
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setSupportMultipleWindows(false)
        }
        web.addJavascriptInterface(NativeBridge(), "NuntiNative")
        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                if (request.method == "POST" && request.url.encodedPath in PARKED_STUDIO_MUTATIONS && !allowed) {
                    return WebResourceResponse("application/json", "UTF-8", 403, "Forbidden", emptyMap(),
                        "{\"error\":{\"code\":\"PARK_REQUIRED\"}}".byteInputStream())
                }
                if (!isStudio(request.url) || (request.method != "GET" && request.url.encodedPath !in STUDIO_MUTATIONS)) {
                    return WebResourceResponse("application/json", "UTF-8", 403, "Forbidden", emptyMap(),
                        "{\"error\":{\"code\":\"FORBIDDEN\"}}".byteInputStream())
                }
                if (request.method != "GET") return null
                val path = request.url.path?.removePrefix("/").orEmpty().ifEmpty { "index.html" }
                val mime = when (path.substringAfterLast('.')) {
                    "png" -> "image/png"; "svg" -> "image/svg+xml"; "woff2" -> "font/woff2"; "ttf" -> "font/ttf"
                    else -> return null
                }
                if (path.startsWith("v3/") || path.startsWith("examples/") || path.split('/').any { it == ".." || it.isEmpty() }) return null
                return runCatching { WebResourceResponse(mime, "UTF-8", assets.open(path)) }.getOrNull()
            }
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = !isStudio(request.url)
            override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                loaded = false
                characterPageEpoch++
                characterMotion.resetPage()
            }
            override fun onPageFinished(view: WebView, url: String) {
                if (!isStudio(Uri.parse(url))) return
                loaded = true; connectionFailed = false; notifyGate(); notifyNavigation(); notifyAppearance(force = true)
                android.util.Log.i("NuntiStudio", "STUDIO_PAGE_READY")
            }
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: android.webkit.WebResourceError) {
                if (request.isForMainFrame) {
                    connectionFailed = true
                    characterMotion.stop()
                    shield.text = "컴퓨터에서 로컬 눈티 생성기를 먼저 실행해 주세요.\npython3 scripts/run_avatar_generator.py\n준비되면 이 화면을 눌러 다시 연결할 수 있어요."
                    shield.visibility = View.VISIBLE
                    android.util.Log.w("NuntiStudio", "STUDIO_CONNECTION_FAILED")
                }
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams): Boolean {
                if (!allowed) return false
                picker?.onReceiveValue(null); picker = callback
                val types = params.acceptTypes.filter { it.isNotBlank() }.toTypedArray()
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE); type = "*/*"
                    putExtra(Intent.EXTRA_MIME_TYPES, if (types.isEmpty()) arrayOf("image/png", "image/jpeg", "application/json") else types)
                }
                return try { startActivityForResult(intent, 701); true } catch (_: Exception) { picker?.onReceiveValue(null); picker = null; false }
            }
        }
        CookieManager.getInstance().setAcceptCookie(true)
        tts = TextToSpeech(this) { status ->
            main.post {
                ttsReady = status == TextToSpeech.SUCCESS &&
                    (tts?.setLanguage(Locale.KOREAN) ?: TextToSpeech.LANG_NOT_SUPPORTED) >= TextToSpeech.LANG_AVAILABLE
                if (ttsReady && MOCK_SKIN_MODE) {
                    val offline = tts?.voices?.filter { !it.isNetworkConnectionRequired && it.locale.language == Locale.KOREAN.language }
                        ?.maxByOrNull { it.quality }
                    ttsReady = offline != null && tts?.setVoice(offline) == TextToSpeech.SUCCESS
                }
            }
        }
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) {
                android.util.Log.i("NuntiStudio", "STUDIO_SPEECH_STARTED")
                deviceSpeechProgress(id, "nuntiSpeechStarted")
            }
            override fun onRangeStart(id: String?, start: Int, end: Int, frame: Int) {
                deviceSpeechProgress(id, "nuntiSpeechRange")
            }
            override fun onDone(id: String?) { deviceSpeechFinished(id) }
            @Deprecated("Android platform callback")
            override fun onError(id: String?) { deviceSpeechFinished(id, failed = true) }
            override fun onError(id: String?, errorCode: Int) { deviceSpeechFinished(id, failed = true) }
        })
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)) {
            carGate = StudioCarGate(this) { main.post { refreshGate() } }
            navigation = PleosNavigationAdapter(this) { snapshot -> notifyNavigation(snapshot) }.also { it.start() }
        }
        connect()
    }

    private fun isStudio(uri: Uri) = uri.scheme == "http" && uri.host == "127.0.0.1" && uri.port == 8768

    private fun connect() {
        io.execute {
            // Debug launcher provisions a local studio token. Release can use the same /session form.
            val file = File(filesDir, "avatar-studio-connection.json")
            if (file.isFile) runCatching {
                val config = JSONObject(file.readText())
                require(config.getString("baseUrl") == base)
                val token = config.getString("token")
                require(token.length in 32..256 && token.all { it.code in 33..126 })
                val http = URL("$base/session").openConnection() as HttpURLConnection
                try {
                    http.connectTimeout = 4000; http.readTimeout = 4000; http.instanceFollowRedirects = false
                    http.requestMethod = "POST"; http.doOutput = true
                    http.setRequestProperty("Content-Type", "application/json")
                    http.setRequestProperty("Origin", base)
                    http.outputStream.use { it.write(JSONObject().put("token", token).toString().toByteArray()) }
                    require(http.responseCode in 200..299)
                    val cookies = http.headerFields.entries.filter { it.key?.equals("Set-Cookie", true) == true }.flatMap { it.value }
                    require(cookies.isNotEmpty())
                    main.post { cookies.forEach { CookieManager.getInstance().setCookie(base, it) }; CookieManager.getInstance().flush() }
                } finally { http.disconnect() }
            }
            main.post {
                if (isDestroyed) return@post
                connected = true; web.loadUrl(base); refreshGate()
            }
        }
    }

    private fun refreshGate() {
        val vehicle = carGate
        val next = foreground && (vehicle?.canDisplay() ?: !packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE))
        if (next) conversationVoice?.refreshParkedContext()
        if (next != allowed) {
            allowed = next
            android.util.Log.i("NuntiStudio", "STUDIO_GATE allowed=$allowed source=${if (vehicle == null) "NON_VEHICLE" else "ACTUAL_CAR_SERVICE"}")
            if (!allowed) {
                characterMotion.stop(); stopDeviceSpeech(); stopVoicePlayer()
                conversationVoice?.close(); conversationVoice = null
                notifyGate(); web.onPause()
            }
            else { web.onResume(); notifyGate(); notifyNavigation() }
        }
        web.visibility = if (allowed && connected && !connectionFailed) View.VISIBLE else View.INVISIBLE
        shield.visibility = if (allowed && connected && !connectionFailed) View.GONE else View.VISIBLE
        if (!allowed) shield.text = if (foreground) "주차한 뒤 눈티를 만나세요.\n기어 P · 정차 · 차량 화면 사용 허가가 필요해요." else "눈티가 잠시 쉬고 있어요."
        else if (connectionFailed) shield.text = "컴퓨터에서 로컬 눈티 생성기를 먼저 실행해 주세요.\npython3 scripts/run_avatar_generator.py\n준비되면 이 화면을 눌러 다시 연결할 수 있어요."
        notifyAppearance()
    }

    private fun notifyAppearance(force: Boolean = false) {
        val night = resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES
        val reduced = !ValueAnimator.areAnimatorsEnabled()
        val key = "$night:$reduced:${web.width}:${web.height}"
        if (!force && key == appearanceKey) return
        appearanceKey = key
        if (reduced) characterMotion.stop(notify = true)
        shield.setTextColor(if (night) 0xffeaf2e6.toInt() else 0xff253e3e.toInt())
        shield.setBackgroundColor(if (night) 0xff131d1b.toInt() else 0xfff4f3ee.toInt())
        web.setBackgroundColor(if (night) 0xff131d1b.toInt() else 0xfff4f3ee.toInt())
        if (loaded) {
            val value = JSONObject().put("theme", if (night) "night" else "day").put("systemReducedMotion", reduced)
                .put("viewportWidth", web.width).put("viewportHeight", web.height)
            web.evaluateJavascript("window.NuntiAppearance && window.NuntiAppearance.apply($value); window.dispatchEvent(new CustomEvent('nunti:appearance',{detail:$value}));", null)
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        notifyAppearance(force = true)
    }

    private fun notifyGate() {
        val reason = if (foreground) "RESTRICTED" else "BACKGROUNDED"
        if (loaded) web.evaluateJavascript("window.nuntiVehicleAllowed && window.nuntiVehicleAllowed($allowed, '$reason')", null)
    }
    private fun canPlayCharacterMotion(): Boolean = loaded && connected && !connectionFailed && foreground &&
        allowed && !isDestroyed && ValueAnimator.areAnimatorsEnabled() && (carGate?.canDisplay() ?: true) &&
        (android.os.Build.VERSION.SDK_INT < 30 || web.rootWindowInsets?.isVisible(WindowInsets.Type.ime()) != true)

    private fun reportCharacterReady(requestId: Int, ready: Boolean) {
        if (loaded && !isDestroyed) web.evaluateJavascript("window.nuntiCharacterMotionReady?.($requestId,$ready)", null)
    }
    private fun reportCharacterFinished(requestId: Int) {
        if (loaded && !isDestroyed) web.evaluateJavascript("window.nuntiCharacterMotionFinished?.($requestId)", null)
    }
    private fun reportCompanionReady(requestId: Int, ready: Boolean) {
        if (loaded && !isDestroyed) web.evaluateJavascript("window.nuntiCharacterCompanionReady?.($requestId,$ready)", null)
    }
    private fun dispatchCharacter(action: () -> Unit) {
        val epoch = characterPageEpoch
        main.post { if (epoch == characterPageEpoch && loaded && !isDestroyed) action() }
    }
    private fun notifyNavigation(snapshot: String? = null) {
        if (!isDestroyed && loaded && allowed) web.evaluateJavascript("window.nuntiNavigationChanged && window.nuntiNavigationChanged(${JSONObject.quote(snapshot ?: navigation?.snapshot() ?: "{}")})", null)
    }
    private fun speechSignal(callback: String, requestId: String) {
        if (!isDestroyed && loaded) web.evaluateJavascript("window.$callback?.(${JSONObject.quote(requestId)})", null)
    }
    private fun speechAmplitude(requestId: String, level: Double) {
        val now = SystemClock.uptimeMillis()
        if (!allowed || !loaded || isDestroyed || !requestId.startsWith("chat-") ||
            !level.isFinite() || now - lastSpeechAmplitudeAt < 33) return
        lastSpeechAmplitudeAt = now
        web.evaluateJavascript("window.NuntiChat?.speechAmplitude(${JSONObject.quote(requestId)}, $level)", null)
    }
    private fun speechFinished(requestId: String) { main.post { speechSignal("nuntiSpeechFinished", requestId) } }
    private fun stopDeviceSpeech() { activeUtterance = null; activeSpeechRequest = null; tts?.stop() }
    private fun deviceSpeechProgress(id: String?, callback: String) {
        main.post {
            if (id != null && id == activeUtterance && allowed) activeSpeechRequest?.let { speechSignal(callback, it) }
        }
    }
    private fun deviceSpeechFinished(id: String?, failed: Boolean = false) {
        main.post {
            if (id != null && id == activeUtterance && voicePlayer == null) {
                val requestId = activeSpeechRequest
                activeUtterance = null; activeSpeechRequest = null
                if (requestId != null) speechSignal(if (failed) "nuntiSpeechFailed" else "nuntiSpeechFinished", requestId)
            }
        }
    }
    private fun stopVoicePlayer() {
        voicePlayer?.release(); voicePlayer = null
        voiceFocus?.let { audioManager.abandonAudioFocusRequest(it) }; voiceFocus = null
    }
    private fun playVoiceAsset(path: String, requestId: String) {
        if (!allowed || !loaded || !Regex("/v3/assets/[0-9a-f]{64}").matches(path)) { speechFinished(requestId); return }
        stopVoicePlayer(); stopDeviceSpeech()
        val attributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
        val player = MediaPlayer(); voicePlayer = player
        fun failed() {
            if (voicePlayer !== player) return
            stopVoicePlayer()
            if (!isDestroyed && loaded) web.evaluateJavascript("window.nuntiSpeechFailed && window.nuntiSpeechFailed(${JSONObject.quote(requestId)})", null)
        }
        player.setAudioAttributes(attributes)
        player.setOnErrorListener { _, _, _ -> failed(); true }
        player.setOnCompletionListener {
            if (voicePlayer === player) {
                android.util.Log.i("NuntiStudio", "STUDIO_GENERATED_VOICE_COMPLETED")
                stopVoicePlayer(); speechFinished(requestId)
            }
        }
        player.setOnPreparedListener {
            if (voicePlayer !== player) return@setOnPreparedListener
            if (!allowed || !loaded) { stopVoicePlayer(); speechFinished(requestId); return@setOnPreparedListener }
            val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(attributes).setOnAudioFocusChangeListener({ change ->
                    if (change < 0 && voicePlayer === player) { stopVoicePlayer(); speechFinished(requestId) }
                }, main).build()
            voiceFocus = focus
            if (audioManager.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) { failed(); return@setOnPreparedListener }
            player.start()
            android.util.Log.i("NuntiStudio", "STUDIO_GENERATED_VOICE_STARTED durationMs=${player.duration}")
        }
        runCatching {
            player.setDataSource(this, Uri.parse(base + path), mapOf("Cookie" to (CookieManager.getInstance().getCookie(base) ?: "")))
            player.prepareAsync()
        }.onFailure { failed() }
    }

    inner class NativeBridge {
        @JavascriptInterface fun startCharacterMotion(
            requestId: Int, skinId: String, left: Double, top: Double, width: Double, height: Double,
            direction: Double,
        ) {
            dispatchCharacter { characterMotion.start(requestId, skinId, left, top, width, height, direction) }
        }
        @JavascriptInterface fun stopCharacterMotion(requestId: Int) {
            dispatchCharacter { characterMotion.stopTransform(requestId) }
        }
        @JavascriptInterface fun startCharacterCompanion(
            requestId: Int, skinId: String, left: Double, top: Double, width: Double, height: Double,
        ) {
            dispatchCharacter { characterMotion.startCompanion(requestId, skinId, left, top, width, height) }
        }
        @JavascriptInterface fun stopCharacterCompanion(requestId: Int) {
            dispatchCharacter { characterMotion.stopCompanion(requestId) }
        }
        @JavascriptInterface fun reactCharacterCompanion(requestId: Int, reaction: String) {
            dispatchCharacter { characterMotion.reactCompanion(requestId, reaction) }
        }
        @JavascriptInterface fun focusCharacterCompanion(requestId: Int, x: Double, y: Double) {
            dispatchCharacter { characterMotion.focusCompanion(requestId, x, y) }
        }
        @JavascriptInterface fun openJourney() { main.post {
            startActivity(Intent(this@AvatarStudioActivity, ai.nunti.app.journey.JourneyActivity::class.java))
        } }
        @JavascriptInterface fun startJourney(characterId: String, source: String): String {
            if (!characterId.matches(Regex("nunti-[0-9a-f-]{36}")))
                return "{\"accepted\":false,\"error\":\"INVALID_JOURNEY\"}"
            return startPreparedJourney(source) { ai.nunti.app.journey.JourneyAssets(this@AvatarStudioActivity).prepare(characterId, source) }
        }
        @JavascriptInterface fun startSkinJourney(selection: String, source: String): String {
            if (!MOCK_SKIN_MODE || selection.length > 65536) return "{\"accepted\":false,\"error\":\"INVALID_JOURNEY\"}"
            return startPreparedJourney(source) { ai.nunti.app.journey.prepareBundledSkinJourney(this@AvatarStudioActivity, selection, source) }
        }
        private fun startPreparedJourney(source: String, prepare: () -> File): String {
            if (!allowed || preparingJourney) return "{\"accepted\":false,\"error\":\"PARKED_REQUIRED_OR_BUSY\"}"
            if (source !in listOf("LIVE", "DEMO")) return "{\"accepted\":false,\"error\":\"INVALID_JOURNEY\"}"
            if (ai.nunti.app.journey.JourneyRuntime.isRunning) {
                openJourney()
                return "{\"accepted\":true,\"existing\":true}"
            }
            preparingJourney = true
            io.execute {
                val result = runCatching(prepare)
                main.post {
                    preparingJourney = false
                    if (isDestroyed) return@post
                    if (!allowed || result.isFailure) {
                        val text = if (!allowed) "주차 상태에서 다시 시작해 주세요." else "여정 자산을 준비하지 못했어요. 로컬 서버 연결을 확인해 주세요."
                        web.evaluateJavascript("window.nuntiJourneyResult?.(${JSONObject.quote(text)})", null)
                        return@post
                    }
                    // The generating host releases its observer before the journey owns live navigation.
                    navigation?.close(); navigation = null
                    startForegroundService(Intent(this@AvatarStudioActivity, ai.nunti.app.journey.JourneyService::class.java)
                        .setAction(ai.nunti.app.journey.JourneyService.ACTION_START).putExtra("input", result.getOrThrow().absolutePath))
                    startActivity(Intent(this@AvatarStudioActivity, ai.nunti.app.journey.JourneyActivity::class.java))
                    web.evaluateJavascript("window.nuntiJourneyResult?.('')", null)
                }
            }
            return "{\"accepted\":true}"
        }
        @JavascriptInterface fun getNavigationSnapshot(): String = if (allowed) navigation?.snapshot() ?: "{\"status\":\"UNAVAILABLE\"}" else "{\"status\":\"GATE_BLOCKED\"}"
        @JavascriptInterface fun navigationCommand(command: String, payloadJson: String): String =
            if (allowed) navigation?.dispatch(command, payloadJson) ?: "{\"accepted\":false,\"error\":\"NAVIGATION_UNAVAILABLE\"}" else "{\"accepted\":false,\"error\":\"VEHICLE_GATE_BLOCKED\"}"
        @JavascriptInterface fun isSpeechAvailable(): Boolean = ttsReady
        @JavascriptInterface fun speakConversation(text: String, requestId: String) {
            dispatchCharacter {
                if (!allowed || text.length !in 1..600 || requestId.length !in 1..96) {
                    speechSignal("nuntiSpeechFailed", requestId)
                    return@dispatchCharacter
                }
                if (carGate == null) {
                    if (ttsReady) speak(text, 1.0, 1.08, requestId)
                    else speechSignal("nuntiSpeechFailed", requestId)
                    return@dispatchCharacter
                }
                if (carGate?.canDisplay() != true) {
                    speechSignal("nuntiSpeechFailed", requestId)
                    return@dispatchCharacter
                }
                stopDeviceSpeech()
                stopVoicePlayer()
                val speaker = conversationVoice ?: StudioConversationVoice(this@AvatarStudioActivity, ::speechAmplitude) { event ->
                    when (event.status) {
                        SpeechStatus.STARTED -> {
                            android.util.Log.i("NuntiStudio", "STUDIO_CONVERSATION_SPEECH_STARTED")
                            speechSignal("nuntiSpeechStarted", event.requestId)
                        }
                        SpeechStatus.COMPLETED -> speechSignal("nuntiSpeechFinished", event.requestId)
                        SpeechStatus.CANCELLED, SpeechStatus.REJECTED, SpeechStatus.FAILED ->
                            speechSignal("nuntiSpeechFailed", event.requestId)
                        SpeechStatus.QUEUED -> Unit
                    }
                }.also { conversationVoice = it }
                speaker.speak(text, requestId)
            }
        }
        @JavascriptInterface fun speak(text: String, rate: Double, pitch: Double, requestId: String) {
            main.post {
                if (!allowed || !loaded || !ttsReady || text.length !in 1..600 || !rate.isFinite() || !pitch.isFinite()) { speechFinished(requestId); return@post }
                stopVoicePlayer()
                stopDeviceSpeech()
                tts?.setSpeechRate(rate.toFloat().coerceIn(.75f, 1.2f))
                tts?.setPitch(pitch.toFloat().coerceIn(.8f, 1.3f))
                val id = "nunti-avatar-${++utteranceSequence}"
                activeUtterance = id
                activeSpeechRequest = requestId
                if (tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, id) != TextToSpeech.SUCCESS) deviceSpeechFinished(id, failed = true)
            }
        }
        @JavascriptInterface fun playVoice(path: String, requestId: String) { main.post { playVoiceAsset(path, requestId) } }
        @JavascriptInterface fun stopSpeaking() { main.post { stopDeviceSpeech(); stopVoicePlayer(); conversationVoice?.stop() } }
    }

    @Deprecated("Android platform file chooser callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 701) { picker?.onReceiveValue(if (resultCode == RESULT_OK) WebChromeClient.FileChooserParams.parseResult(resultCode, data) else null); picker = null }
    }
    override fun onResume() {
        super.onResume(); foreground = true; main.removeCallbacks(tick); main.post(tick)
        if (navigation == null && !ai.nunti.app.journey.JourneyRuntime.isRunning && packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE))
            navigation = PleosNavigationAdapter(this) { snapshot -> notifyNavigation(snapshot) }.also { it.start() }
        navigation?.dispatch("refresh")
    }
    override fun onPause() { foreground = false; refreshGate(); stopDeviceSpeech(); navigation?.close(); navigation = null; super.onPause() }
    override fun onStop() { main.removeCallbacks(tick); super.onStop() }
    override fun onDestroy() { loaded = false; allowed = false; characterMotion.stop(); main.removeCallbacksAndMessages(null); picker?.onReceiveValue(null); picker = null; tts?.stop(); tts?.shutdown(); stopVoicePlayer(); conversationVoice?.close(); navigation?.close(); carGate?.close(); web.removeJavascriptInterface("NuntiNative"); web.destroy(); io.shutdownNow(); super.onDestroy() }
}

internal class StudioCarGate(context: android.content.Context, private val changed: () -> Unit) : AutoCloseable {
    private var properties: CarPropertyManager? = null
    private var restrictions: CarUxRestrictions? = null
    private var binding: CarUxPolicyBinding? = null
    private val unavailableProperties = mutableSetOf<Int>()
    private val propertyCallback = object : CarPropertyManager.CarPropertyEventCallback {
        override fun onChangeEvent(value: CarPropertyValue<*>) {
            if (value.status == CarPropertyValue.STATUS_AVAILABLE) unavailableProperties.remove(value.propertyId)
            else unavailableProperties.add(value.propertyId)
            changed()
        }
        override fun onErrorEvent(propId: Int, zone: Int) { unavailableProperties.add(propId); changed() }
    }
    private val car = Car.createCar(context, Handler(Looper.getMainLooper()), Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT) { connected, ready ->
        runCatching { properties?.unregisterCallback(propertyCallback) }
        binding?.close(); binding = null; properties = null; restrictions = null; unavailableProperties.clear()
        if (ready) runCatching {
            properties = connected.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager
            for (property in listOf(VehiclePropertyIds.GEAR_SELECTION, VehiclePropertyIds.PERF_VEHICLE_SPEED)) {
                runCatching { properties?.registerCallback(propertyCallback, property, CarPropertyManager.SENSOR_RATE_ONCHANGE) }
            }
            val manager = connected.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE) as CarUxRestrictionsManager
            binding = CarUxPolicyBinding(manager) { restrictions = it; changed() }.also { it.start() }
        }
        changed()
    }
    fun canDisplay(): Boolean {
        if (unavailableProperties.isNotEmpty()) return false
        val gear = runCatching { properties?.getIntProperty(VehiclePropertyIds.GEAR_SELECTION, 0) }.getOrNull()
        val speed = runCatching { properties?.getFloatProperty(VehiclePropertyIds.PERF_VEHICLE_SPEED, 0) }.getOrNull()
        val ux = restrictions ?: return false
        return gear == VehicleGear.GEAR_PARK && speed?.let { it.isFinite() && abs(it) < .01f } == true &&
            !ux.isRequiresDistractionOptimization && ux.activeRestrictions == 0
    }
    override fun close() { runCatching { properties?.unregisterCallback(propertyCallback) }; binding?.close(); car?.disconnect() }
}
