package ai.nunti.app.studio

import ai.nunti.avatar.CarUxPolicyBinding
import ai.nunti.app.navigation.PleosNavigationAdapter
import android.app.Activity
import android.car.Car
import android.car.VehicleGear
import android.car.VehiclePropertyIds
import android.car.drivingstate.CarUxRestrictions
import android.car.drivingstate.CarUxRestrictionsManager
import android.car.hardware.property.CarPropertyManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.View
import android.webkit.CookieManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.Executors
import kotlin.math.abs
import org.json.JSONObject

/** The same tested generator UI is used by the browser and the actual Android host.
 * Vehicle display is gated with actual Car service values; no query flag can authorize it.
 * Provider credentials never enter this host. Connection is to a loopback-forwarded studio.
 */
class AvatarStudioActivity : Activity() {
    private val main = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private lateinit var web: WebView
    private lateinit var shield: TextView
    private var carGate: StudioCarGate? = null
    private var navigation: PleosNavigationAdapter? = null
    private var foreground = false
    @Volatile private var allowed = false
    private var loaded = false
    private var connected = false
    private var connectionFailed = false
    private var tts: TextToSpeech? = null
    private var activeUtterance: String? = null
    private var activeSpeechRequest: String? = null
    private var utteranceSequence = 0L
    private var voicePlayer: MediaPlayer? = null
    private var voiceFocus: AudioFocusRequest? = null
    private val audioManager by lazy { getSystemService(AudioManager::class.java) }
    @Volatile private var ttsReady = false
    private var picker: ValueCallback<Array<Uri>>? = null
    private val base = "http://127.0.0.1:8768"
    private val tick = object : Runnable {
        override fun run() { refreshGate(); main.postDelayed(this, 250) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val container = FrameLayout(this)
        web = WebView(this)
        shield = TextView(this).apply {
            text = "눈티는 주차 중에 만날 수 있어요.\n차량 상태를 확인하고 있습니다."
            textSize = 20f; gravity = android.view.Gravity.CENTER
            setTextColor(0xff42695a.toInt()); setBackgroundColor(0xfff4f3ee.toInt())
        }
        container.addView(web, FrameLayout.LayoutParams(-1, -1))
        container.addView(shield, FrameLayout.LayoutParams(-1, -1))
        setContentView(container)
        shield.setOnClickListener {
            if (allowed && connectionFailed) { connectionFailed = false; web.reload(); refreshGate() }
        }
        WebView.setWebContentsDebuggingEnabled(applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0)
        web.settings.apply {
            javaScriptEnabled = true; domStorageEnabled = true
            allowFileAccess = false; allowContentAccess = false
            mediaPlaybackRequiresUserGesture = true
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setSupportMultipleWindows(false)
        }
        web.addJavascriptInterface(NativeBridge(), "NuntiNative")
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = !isStudio(request.url)
            override fun onPageFinished(view: WebView, url: String) {
                if (!isStudio(Uri.parse(url))) return
                loaded = true; notifyGate(); notifyNavigation()
                android.util.Log.i("NuntiStudio", "STUDIO_PAGE_READY")
            }
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: android.webkit.WebResourceError) {
                if (request.isForMainFrame) {
                    connectionFailed = true
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
            }
        }
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) { android.util.Log.i("NuntiStudio", "STUDIO_SPEECH_STARTED") }
            override fun onDone(id: String?) { deviceSpeechFinished(id) }
            @Deprecated("Android platform callback")
            override fun onError(id: String?) { deviceSpeechFinished(id) }
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
        if (next != allowed) {
            allowed = next
            android.util.Log.i("NuntiStudio", "STUDIO_GATE allowed=$allowed source=${if (vehicle == null) "NON_VEHICLE" else "ACTUAL_CAR_SERVICE"}")
            if (!allowed) { stopDeviceSpeech(); stopVoicePlayer(); web.onPause() } else web.onResume()
            notifyGate()
            if (allowed) notifyNavigation()
        }
        web.visibility = if (allowed && connected && !connectionFailed) View.VISIBLE else View.INVISIBLE
        shield.visibility = if (allowed && connected && !connectionFailed) View.GONE else View.VISIBLE
        if (!allowed) shield.text = if (foreground) "주차한 뒤 눈티를 만나세요.\n기어 P · 정차 · 차량 화면 사용 허가가 필요해요." else "눈티가 잠시 쉬고 있어요."
        else if (connectionFailed) shield.text = "컴퓨터에서 로컬 눈티 생성기를 먼저 실행해 주세요.\npython3 scripts/run_avatar_generator.py\n준비되면 이 화면을 눌러 다시 연결할 수 있어요."
    }

    private fun notifyGate() { if (loaded) web.evaluateJavascript("window.nuntiVehicleAllowed && window.nuntiVehicleAllowed($allowed)", null) }
    private fun notifyNavigation(snapshot: String? = null) {
        if (!isDestroyed && loaded && allowed) web.evaluateJavascript("window.nuntiNavigationChanged && window.nuntiNavigationChanged(${JSONObject.quote(snapshot ?: navigation?.snapshot() ?: "{}")})", null)
    }
    private fun speechFinished(requestId: String) { main.post { if (!isDestroyed && loaded) web.evaluateJavascript("window.nuntiSpeechFinished && window.nuntiSpeechFinished(${JSONObject.quote(requestId)})", null) } }
    private fun stopDeviceSpeech() { activeUtterance = null; activeSpeechRequest = null; tts?.stop() }
    private fun deviceSpeechFinished(id: String?) {
        main.post {
            if (id != null && id == activeUtterance && voicePlayer == null) {
                val requestId = activeSpeechRequest
                activeUtterance = null; activeSpeechRequest = null
                if (requestId != null) speechFinished(requestId)
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
        @JavascriptInterface fun getNavigationSnapshot(): String = if (allowed) navigation?.snapshot() ?: "{\"status\":\"UNAVAILABLE\"}" else "{\"status\":\"GATE_BLOCKED\"}"
        @JavascriptInterface fun navigationCommand(command: String, payloadJson: String): String =
            if (allowed) navigation?.dispatch(command, payloadJson) ?: "{\"accepted\":false,\"error\":\"NAVIGATION_UNAVAILABLE\"}" else "{\"accepted\":false,\"error\":\"VEHICLE_GATE_BLOCKED\"}"
        @JavascriptInterface fun isSpeechAvailable(): Boolean = ttsReady
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
                tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, id)
            }
        }
        @JavascriptInterface fun playVoice(path: String, requestId: String) { main.post { playVoiceAsset(path, requestId) } }
        @JavascriptInterface fun stopSpeaking() { main.post { stopDeviceSpeech(); stopVoicePlayer() } }
    }

    @Deprecated("Android platform file chooser callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 701) { picker?.onReceiveValue(if (resultCode == RESULT_OK) WebChromeClient.FileChooserParams.parseResult(resultCode, data) else null); picker = null }
    }
    override fun onResume() { super.onResume(); foreground = true; main.removeCallbacks(tick); main.post(tick); navigation?.dispatch("refresh") }
    override fun onPause() { foreground = false; refreshGate(); stopDeviceSpeech(); super.onPause() }
    override fun onStop() { main.removeCallbacks(tick); super.onStop() }
    override fun onDestroy() { loaded = false; allowed = false; main.removeCallbacksAndMessages(null); picker?.onReceiveValue(null); picker = null; tts?.stop(); tts?.shutdown(); stopVoicePlayer(); navigation?.close(); carGate?.close(); web.removeJavascriptInterface("NuntiNative"); web.destroy(); io.shutdownNow(); super.onDestroy() }
}

private class StudioCarGate(context: android.content.Context, private val changed: () -> Unit) : AutoCloseable {
    private var properties: CarPropertyManager? = null
    private var restrictions: CarUxRestrictions? = null
    private var binding: CarUxPolicyBinding? = null
    private val car = Car.createCar(context, Handler(Looper.getMainLooper()), Car.CAR_WAIT_TIMEOUT_DO_NOT_WAIT) { connected, ready ->
        binding?.close(); binding = null; properties = null; restrictions = null
        if (ready) runCatching {
            properties = connected.getCarManager(Car.PROPERTY_SERVICE) as CarPropertyManager
            val manager = connected.getCarManager(Car.CAR_UX_RESTRICTION_SERVICE) as CarUxRestrictionsManager
            binding = CarUxPolicyBinding(manager) { restrictions = it; changed() }.also { it.start() }
        }
        changed()
    }
    fun canDisplay(): Boolean {
        val gear = runCatching { properties?.getIntProperty(VehiclePropertyIds.GEAR_SELECTION, 0) }.getOrNull()
        val speed = runCatching { properties?.getFloatProperty(VehiclePropertyIds.PERF_VEHICLE_SPEED, 0) }.getOrNull()
        val ux = restrictions ?: return false
        return gear == VehicleGear.GEAR_PARK && speed?.let { it.isFinite() && abs(it) < .01f } == true &&
            !ux.isRequiresDistractionOptimization && ux.activeRestrictions == 0
    }
    override fun close() { binding?.close(); car?.disconnect() }
}
