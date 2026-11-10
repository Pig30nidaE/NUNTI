package ai.nunti.app.journey

import ai.nunti.app.studio.StudioCarGate
import android.app.Activity
import android.app.AlertDialog
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.util.Locale
import java.util.concurrent.Executors
import org.json.JSONObject

/** Presentation only: JourneyService remains the owner of the session, scoring and vehicle gate. */
class JourneyActivity : Activity() {
    private enum class Screen { EMPTY, PARKED, DRIVING, REPORT }
    private val main = Handler(Looper.getMainLooper())
    private val images = Executors.newSingleThreadExecutor()
    private lateinit var host: FrameLayout
    private lateinit var avatarView: JourneyCompanionView
    private var theme = NuntiTheme(false, 0, 0, 0, 0, 0, 0, 0, 0)
    private var screen: Screen? = null
    private var compact = false
    private var viewportWidth = 0
    private var viewportHeight = 0
    private var headerState: TextView? = null
    private var title: TextView? = null
    private var destination: TextView? = null
    private var score: TextView? = null
    private var scoreCaption: TextView? = null
    private var scoreContext: TextView? = null
    private var elapsed: TextView? = null
    private var elapsedContext: TextView? = null
    private var line: TextView? = null
    private var coverage: TextView? = null
    private var sourceLabel: TextView? = null
    private var characterLabel: TextView? = null
    private var characterName: TextView? = null
    private var muteButton: Button? = null
    private var finishButton: Button? = null
    private var detailDialog: AlertDialog? = null
    private var restored: JSONObject? = null
    private var carGate: StudioCarGate? = null
    private var imagePath: String? = null
    private var imageRequest = 0L
    private var illustration: Bitmap? = null
    private var base: Bitmap? = null
    private var imageLoaded = false
    private var imageFallback = false
    private var displayName = "눈티"
    private var muted = false
    private var resumed = false
    private val poll = object : Runnable {
        override fun run() {
            if (!resumed) return
            refresh()
            main.postDelayed(this, 500)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        muted = savedInstanceState?.getBoolean("muted") ?: false
        restored = JourneyRuntime.latest(this)
        host = FrameLayout(this)
        host.addOnLayoutChangeListener { _, left, top, right, bottom, _, _, _, _ ->
            val w = right - left
            val h = bottom - top
            if (w > 0 && h > 0 && (w != viewportWidth || h != viewportHeight)) {
                viewportWidth = w
                viewportHeight = h
                main.post { if (!isDestroyed) refresh(rebuild = true) }
            }
        }
        setContentView(host)
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)) {
            carGate = StudioCarGate(this) { main.post { if (resumed) refresh() } }
        }
        // One bundled fallback decode per Activity, never during drawing or periodic refresh.
        images.execute {
            val fallback = runCatching {
                assets.open("nunti-motion/base.png").use { BitmapFactory.decodeStream(it) }
            }.getOrNull()
            main.post {
                if (!isDestroyed) {
                    base = fallback
                    applyImage()
                } else fallback?.recycle()
            }
        }
        refresh()
    }

    private fun refresh(rebuild: Boolean = false) {
        val snapshot = JourneyRuntime.current ?: restored
        val state = snapshot?.optString("state", "INTERRUPTED")
        val active = state == "ACTIVE" && JourneyRuntime.isRunning
        val parked = parkedNow() && (!active || snapshot?.optBoolean("canFinish", false) == true)
        val nextScreen = when {
            snapshot == null -> Screen.EMPTY
            active && parked -> Screen.PARKED
            !active && parked -> Screen.REPORT
            else -> Screen.DRIVING
        }
        if (!parked || active) dismissDetails()
        val nextTheme = NuntiTheme.from(this)
        val nextCompact = (if (viewportWidth > 0) viewportWidth / resources.displayMetrics.density
            else resources.configuration.screenWidthDp.toFloat()) < 1520f
        if (rebuild || screen != nextScreen || theme != nextTheme || compact != nextCompact) {
            screen = nextScreen
            theme = nextTheme
            compact = nextCompact
            buildView(nextScreen)
        }
        if (snapshot == null) {
            headerState?.text = "여정 준비"
            title?.text = "눈티를 먼저 선택해 주세요"
            destination?.text = "보관한 눈티를 열어 여정을 시작할 수 있어요."
            line?.text = "이번 길을 함께할 눈티를 기다려요."
            updateImage("", "눈티")
            avatarView.setEmotion("NEUTRAL", animate = false)
            return
        }
        val finished = state == "FINISHED"
        headerState?.text = when {
            active && parked -> "정차 중"
            active -> "주행 중"
            finished -> "여정 완료"
            else -> "중단된 여정"
        }
        title?.text = when (nextScreen) {
            Screen.PARKED -> "눈티와 함께 출발해요"
            Screen.REPORT -> if (finished) "함께한 길을 돌아봐요" else "마지막 여정을 돌아봐요"
            else -> if (active) "이번 길도, 눈티와 함께" else "정차 후 여정을 확인해요"
        }
        val place = snapshot.optString("destination").takeIf { it.isNotBlank() }
        val purpose = snapshot.optString("purpose").takeIf { it.isNotBlank() }
        val trip = listOfNotNull(place, purpose).joinToString(" · ")
        destination?.text = if (nextScreen == Screen.REPORT && !compact) {
            if (finished) "여정을 마친 뒤, 이번 운전을 차분히 살펴봐요."
            else "중단 전까지 받은 신호만 남겼어요. 중단 구간은 평가하지 않았어요."
        } else if (!compact && place != null && purpose == null) "${place}으로 가는 길" else trip
        displayName = snapshot.optString("displayName", "눈티")
        characterName?.text = trip.ifBlank { displayName }
        characterName?.contentDescription = "$displayName, $trip"
        val seconds = snapshot.optLong("elapsedMs").coerceAtLeast(0) / 1000
        elapsed?.text = if (nextScreen == Screen.REPORT) duration(seconds) else "함께한 시간  ${clock(seconds)}"
        elapsedContext?.text = if (finished) "여정 완료" else "중단된 여정"
        val total = snapshot.numberOrNull("total")
        scoreCaption?.text = if (finished) "이번 길의 운전 점수" else "운전 점수"
        score?.text = total?.let { String.format(Locale.KOREA, "%.0f점", it) } ?: if (finished) "점수 없음" else "기록 중"
        scoreContext?.text = if (total == null) "신호가 더 필요해요" else "확인된 항목으로 계산했어요"
        val evaluated = (snapshot.optDouble("coverage", 0.0).coerceIn(0.0, 1.0) * 100).toInt()
        coverage?.text = if (nextScreen == Screen.REPORT) "평가 가능한 범위  $evaluated%"
            else if (total == null) "운전 정보를 모으고 있어요"
            else "평가 가능한 범위 $evaluated% · 미수신 항목 제외"
        line?.text = snapshot.optString("line", "함께 살펴보고 있어요.")
        val emotion = snapshot.optString("emotion", "NEUTRAL")
        characterLabel?.text = JourneyCompanionView.emotionLabel(emotion)
        val source = if (snapshot.optString("source") == "DEMO") "시연 데이터" else "실시간 차량 신호"
        sourceLabel?.text = if (snapshot.optString("source") == "DEMO") "시연 데이터" else ""
        if (snapshot.has("muted")) muted = snapshot.optBoolean("muted")
        muteButton?.text = if (muted) "음성 켜기" else "음성 끄기"
        muteButton?.visibility = if (active) View.VISIBLE else View.GONE
        finishButton?.isEnabled = active && parked
        avatarView.setEmotion(emotion, animate = resumed && active && parked && !snapshot.optBoolean("staticOnly", false))
        updateImage(snapshot.optString("imageFile"), displayName)
    }

    private fun buildView(mode: Screen) {
        if (::avatarView.isInitialized) avatarView.stopMotion()
        headerState = null; title = null; destination = null; score = null; scoreCaption = null; scoreContext = null
        elapsed = null; elapsedContext = null; line = null; coverage = null; sourceLabel = null
        characterLabel = null; characterName = null; muteButton = null; finishButton = null
        val root = column().apply {
            val inset = dp(if (compact) 32 else 40)
            setPadding(inset, inset, inset, inset)
            setBackgroundColor(theme.background)
        }
        val heading = row().apply { gravity = Gravity.CENTER_VERTICAL }
        heading.addView(text("눈티", 34, 48, 700))
        headerState = text("", 22, 34, color = theme.muted)
        heading.addView(headerState, layout(-2, -2, left = 24))
        root.addView(heading, layout(-1, 80))
        val intro = column()
        title = text("", if (compact) 38 else 48, if (compact) 52 else 64, 700).apply { maxLines = 1; ellipsize = TextUtils.TruncateAt.END }
        intro.addView(title, layout(-1, -2))
        destination = text("", if (compact) 22 else 26, if (compact) 34 else 40, color = theme.muted)
            .apply { maxLines = 2; ellipsize = TextUtils.TruncateAt.END }
        intro.addView(destination, layout(-1, -2, top = 8))
        root.addView(intro, layout(-1, if (compact) 108 else 120, top = 24))
        avatarView = JourneyCompanionView(this)
        val body = if (mode == Screen.REPORT) buildReport() else buildCompanion(mode)
        root.addView(body, LinearLayout.LayoutParams(-1, 0, 1f).apply { topMargin = dp(24) })
        root.addView(buildActions(mode), layout(-1, 80, top = 24))
        host.removeAllViews()
        host.addView(root, FrameLayout.LayoutParams(-1, -1))
        applyImage()
    }

    private fun buildCompanion(mode: Screen): View {
        val parked = mode == Screen.PARKED
        if (compact) {
            val stage = card(theme.soft, 24).apply { gravity = Gravity.CENTER_HORIZONTAL }
            val available = bodyHeight() - (if (parked) 390 else 292)
            stage.addView(avatarView, layout(-1, minOf(420, available.coerceAtLeast(160))))
            line = text("", 26, 40, 500).apply { gravity = Gravity.CENTER; maxLines = 2 }
            stage.addView(line, layout(-1, -2, top = 16))
            val metrics = row().apply { gravity = Gravity.CENTER_VERTICAL }
            val scoreBlock = column().apply { gravity = Gravity.CENTER }
            scoreCaption = text("운전 점수", 22, 34, color = theme.muted)
            scoreBlock.addView(scoreCaption, layout(-2, -2))
            score = text("—", 48, 64, 700)
            scoreBlock.addView(score, layout(-2, -2, top = 4))
            metrics.addView(scoreBlock, LinearLayout.LayoutParams(0, -2, 1f))
            val timeBlock = column().apply { gravity = Gravity.CENTER }
            elapsed = text("", 26, 40, 500).apply { gravity = Gravity.CENTER; maxLines = 2 }
            timeBlock.addView(elapsed, layout(-1, -2))
            metrics.addView(timeBlock, LinearLayout.LayoutParams(0, -2, 1f).apply { leftMargin = dp(24) })
            stage.addView(metrics, layout(-1, -2, top = 24))
            if (parked) {
                coverage = text("", 22, 34, color = theme.muted).apply { gravity = Gravity.CENTER; maxLines = 2 }
                stage.addView(coverage, layout(-1, -2, top = 16))
                stage.addView(optionalControls(), layout(-1, 80, top = 20))
            }
            sourceLabel = text("", 20, 30, color = theme.muted).apply { gravity = Gravity.CENTER }
            stage.addView(sourceLabel, layout(-1, -2, top = 8))
            return stage
        }
        val body = row()
        val stage = card(theme.soft, 28).apply { gravity = Gravity.CENTER }
        stage.addView(avatarView, layout(-1, minOf(680, (bodyHeight() - 70).coerceAtLeast(160))))
        body.addView(stage, LinearLayout.LayoutParams(0, -1, 1.08f))
        val info = column().apply { gravity = Gravity.CENTER_VERTICAL; setPadding(dp(16), dp(28), dp(16), dp(28)) }
        line = text("", 34, 48, 500)
        info.addView(line, layout(-1, -2))
        scoreCaption = text("운전 점수", 24, 36, color = theme.muted)
        info.addView(scoreCaption, layout(-1, -2, top = 48))
        score = text("—", 72, 88, 700)
        info.addView(score, layout(-1, -2, top = 8))
        elapsed = text("", 28, 42, 500)
        info.addView(elapsed, layout(-1, -2, top = 32))
        if (parked) {
            coverage = text("", 22, 34, color = theme.muted)
            info.addView(coverage, layout(-1, -2, top = 16))
        }
        sourceLabel = text("", 20, 30, color = theme.muted)
        info.addView(sourceLabel, layout(-1, -2, top = 16))
        body.addView(info, LinearLayout.LayoutParams(0, -1, 1f).apply { leftMargin = dp(40) })
        return body
    }

    private fun buildReport(): View {
        val report = column()
        if (compact) {
            report.background = shape(theme.surface, 28)
            report.setPadding(dp(24), dp(24), dp(24), dp(24))
            val saved = row().apply { gravity = Gravity.CENTER_VERTICAL }
            saved.addView(avatarView, layout(220, 220))
            val caption = column()
            caption.addView(text("함께 다녀온 눈티", 30, 44, 500), layout(-1, -2))
            caption.addView(text("내 눈티에서 다시 만나요.", 22, 34, color = theme.muted), layout(-1, -2, top = 16))
            saved.addView(caption, LinearLayout.LayoutParams(0, -2, 1f).apply { leftMargin = dp(24) })
            report.addView(saved, layout(-1, 220))
        }
        val metrics = row()
        val scoreCard = card(theme.surface, 24, 20)
        scoreCard.addView(text("이번 길의 운전 점수", 22, 34, color = theme.muted), layout(-1, -2))
        score = text("", 38, 52, 700)
        scoreCard.addView(score, layout(-1, -2, top = 8))
        scoreContext = text("", 22, 34, color = theme.muted)
        scoreCard.addView(scoreContext, layout(-1, -2, top = 8))
        metrics.addView(scoreCard, LinearLayout.LayoutParams(0, -1, 1f))
        val timeCard = card(theme.surface, 24, 20)
        timeCard.addView(text("함께한 시간", 22, 34, color = theme.muted), layout(-1, -2))
        elapsed = text("", 38, 52, 700)
        timeCard.addView(elapsed, layout(-1, -2, top = 8))
        elapsedContext = text("", 22, 34, color = theme.muted)
        timeCard.addView(elapsedContext, layout(-1, -2, top = 8))
        metrics.addView(timeCard, LinearLayout.LayoutParams(0, -1, 1f).apply { leftMargin = dp(if (compact) 16 else 24) })
        report.addView(metrics, layout(-1, 204, top = if (compact) 16 else 0))
        val explanation = if (compact) column() else card(theme.surface, 32)
        line = text("", 30, 44, 500)
        explanation.addView(line, layout(-1, -2))
        explanation.addView(text("받지 못한 항목은 점수에서 제외해요.", 26, 40, color = theme.muted), layout(-1, -2, top = 16))
        coverage = text("", 22, 34, color = theme.accent).apply {
            background = shape(theme.soft, 12)
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(16), dp(16), dp(16))
        }
        explanation.addView(coverage, layout(-1, 72, top = 16))
        report.addView(explanation, layout(-1, -2, top = if (compact) 16 else 24))
        val details = if (compact) column() else card(theme.surface, 32)
        if (!compact) details.addView(text("이번 여정의 세부 기록", 30, 44, 500), layout(-1, -2))
        details.addView(button("세부 기록 보기", quiet = true) { showDetails() }, layout(if (compact) -1 else -2, 80, top = if (compact) 0 else 16))
        report.addView(details, layout(-1, if (compact) -2 else 160, top = if (compact) 16 else 24))
        val scroll = ScrollView(this).apply { isFillViewport = false; addView(report); isVerticalScrollBarEnabled = true }
        if (compact) return scroll
        val body = row()
        val stage = card(theme.soft, 32).apply { gravity = Gravity.CENTER_HORIZONTAL }
        stage.addView(avatarView, layout(-1, minOf(566, (bodyHeight() - 174).coerceAtLeast(100))))
        characterName = text("", 30, 44, 500).apply { gravity = Gravity.CENTER; maxLines = 2 }
        stage.addView(characterName, layout(-1, -2, top = 16))
        stage.addView(text("내 눈티에 보관됐어요", 22, 34, color = theme.muted), layout(-2, -2, top = 16))
        body.addView(stage, LinearLayout.LayoutParams(0, -1, 650f))
        body.addView(scroll, LinearLayout.LayoutParams(0, -1, 920f).apply { leftMargin = dp(32) })
        return body
    }

    private fun buildActions(mode: Screen): View {
        val actions = row().apply { gravity = Gravity.CENTER_VERTICAL }
        when (mode) {
            Screen.PARKED -> {
                val back = button("눈티로 돌아가기") { if (parkedNow()) finish() }
                if (compact) {
                    actions.addView(back, LinearLayout.LayoutParams(0, -1, 304f))
                    finishButton = finishAction()
                    actions.addView(finishButton, LinearLayout.LayoutParams(0, -1, 438f).apply { leftMargin = dp(24) })
                } else {
                    actions.addView(back, layout(320, -1))
                    actions.addView(muteAction(), layout(240, -1, left = 24))
                    actions.addView(button("현대 내비 열기") { openNavigation() }, layout(320, -1, left = 24))
                    actions.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
                    finishButton = finishAction()
                    actions.addView(finishButton, layout(450, -1, left = 24))
                }
            }
            Screen.REPORT -> {
                if (!compact) {
                    actions.addView(text("이번 여행을 기기에 보관했어요", 26, 40, color = theme.muted),
                        LinearLayout.LayoutParams(0, -2, 1f))
                }
                actions.addView(button("눈티로 돌아가기", primary = true) { if (parkedNow()) finish() },
                    layout(if (compact) -1 else 450, -1))
            }
            Screen.DRIVING -> {
                if (!compact) actions.addView(text("자세한 내용은 정차 후 확인해요.", 26, 40, color = theme.muted),
                    LinearLayout.LayoutParams(0, -2, 1f))
                actions.addView(muteAction(), if (compact) LinearLayout.LayoutParams(0, -1, 310f) else layout(240, -1))
                actions.addView(button("현대 내비 열기") { openNavigation() },
                    if (compact) LinearLayout.LayoutParams(0, -1, 432f).apply { leftMargin = dp(24) } else layout(320, -1, left = 24))
            }
            Screen.EMPTY -> {
                actions.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f))
                actions.addView(button("눈티로 돌아가기", primary = true) { finish() }, layout(if (compact) -1 else 450, -1))
            }
        }
        return actions
    }

    private fun optionalControls() = row().apply {
        addView(muteAction(), LinearLayout.LayoutParams(0, -1, 270f))
        addView(button("현대 내비 열기") { openNavigation() },
            LinearLayout.LayoutParams(0, -1, 432f).apply { leftMargin = dp(16) })
    }

    private fun muteAction() = button(if (muted) "음성 켜기" else "음성 끄기") {
        if (JourneyRuntime.isRunning) {
            muted = !muted
            startService(Intent(this, JourneyService::class.java)
                .setAction(JourneyService.ACTION_MUTE).putExtra("mute", muted))
            muteButton?.text = if (muted) "음성 켜기" else "음성 끄기"
        }
    }.also { muteButton = it }

    private fun finishAction() = button("여정 마치기", primary = true) {
        val current = JourneyRuntime.current
        if (JourneyRuntime.isRunning && parkedNow() && current?.optBoolean("canFinish") == true &&
            current.optString("state") == "ACTIVE") {
            finishButton?.isEnabled = false
            startService(Intent(this, JourneyService::class.java).setAction(JourneyService.ACTION_FINISH))
        }
    }

    private fun updateImage(path: String, name: String) {
        displayName = name
        if (path == imagePath) return
        imagePath = path
        val request = ++imageRequest
        illustration = null
        imageLoaded = false
        imageFallback = path.isBlank()
        applyImage()
        if (path.isBlank()) { imageLoaded = true; applyImage(); return }
        images.execute {
            val bitmap = runCatching {
                val file = File(path).canonicalFile
                check(file.toPath().startsWith(filesDir.canonicalFile.toPath()) ||
                    file.toPath().startsWith(cacheDir.canonicalFile.toPath()))
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeFile(file.path, bounds)
                check(bounds.outWidth > 0 && bounds.outHeight > 0)
                val options = BitmapFactory.Options().apply { inSampleSize = 1 }
                while (maxOf(bounds.outWidth, bounds.outHeight) / options.inSampleSize > 1600) options.inSampleSize *= 2
                BitmapFactory.decodeFile(file.path, options)
            }.getOrNull()
            main.post {
                if (!isDestroyed && request == imageRequest) {
                    illustration = bitmap
                    imageLoaded = true
                    imageFallback = bitmap == null
                    applyImage()
                } else bitmap?.recycle()
            }
        }
    }

    private fun applyImage() {
        if (!::avatarView.isInitialized) return
        avatarView.setIllustration(illustration ?: base, displayName, imageLoaded, fallback = imageFallback)
    }

    private fun showDetails() {
        val snapshot = JourneyRuntime.current ?: restored ?: return
        if (!parkedNow() || (snapshot.optString("state") == "ACTIVE" && JourneyRuntime.isRunning)) return
        dismissDetails()
        val details = column().apply { setPadding(dp(32), dp(24), dp(32), dp(24)); setBackgroundColor(theme.surface) }
        updateDetails(snapshot, details)
        val scroll = ScrollView(this).apply { addView(details) }
        val dialogTitle = text("이번 여정의 세부 기록", 30, 44, 500).apply {
            setPadding(dp(32), dp(24), dp(32), dp(8))
        }
        detailDialog = AlertDialog.Builder(this).setCustomTitle(dialogTitle).setView(scroll)
            .setPositiveButton("닫기", null).create().also { dialog ->
                dialog.setOnShowListener {
                    dialog.window?.setBackgroundDrawable(shape(theme.surface, 28))
                    dialog.window?.setLayout(minOf(viewportWidth - dp(64), dp(1100)), (viewportHeight * .85f).toInt())
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE)?.apply {
                        textSize = 26f; typeface = NuntiFonts.get(this@JourneyActivity, 500)
                        setTextColor(theme.accent); minHeight = dp(80)
                    }
                }
                dialog.show()
            }
    }

    private fun updateDetails(snapshot: JSONObject, details: LinearLayout) {
        details.addView(text(snapshot.optString("displayName", "눈티"), 30, 44, 500), layout(-1, -2))
        details.addView(text(listOf(snapshot.optString("destination"), snapshot.optString("purpose"))
            .filter { it.isNotBlank() }.joinToString(" · "), 22, 34, color = theme.muted), layout(-1, -2, top = 8))
        val source = if (snapshot.optString("source") == "DEMO") "시연 데이터" else "실시간 차량 신호"
        details.addView(text(source, 22, 34, color = theme.muted), layout(-1, -2, top = 8))
        val voice = snapshot.optString("voiceStatus")
        if (voice.isNotBlank()) details.addView(text(voice, 22, 34, color = theme.muted), layout(-1, -2, top = 8))
        if (snapshot.optString("state") == "INTERRUPTED") details.addView(text(
            "중단 전까지 받은 신호만 남겼어요. 중단 구간은 평가하지 않았어요.", 26, 40, color = theme.warm), layout(-1, -2, top = 24))
        val items = snapshot.optJSONArray("items")
        for (i in 0 until (items?.length() ?: 0)) {
            val item = items?.optJSONObject(i) ?: continue
            val value = item.numberOrNull("score")?.let { String.format(Locale.KOREA, "%.0f점", it) } ?: "평가 불가"
            details.addView(text("${item.optString("label")}  $value", 26, 40, 500), layout(-1, -2, top = 24))
            details.addView(text(item.optString("basis"), 22, 34, color = theme.muted), layout(-1, -2, top = 8))
        }
        val events = snapshot.optJSONArray("events")
        if ((events?.length() ?: 0) > 0) {
            details.addView(text("기억할 순간", 30, 44, 500), layout(-1, -2, top = 32))
            for (i in 0 until minOf(events?.length() ?: 0, 30)) {
                val event = events?.optJSONObject(i) ?: continue
                details.addView(text("${duration(event.optLong("tMs") / 1000)}  ${event.optString("label")}",
                    22, 34, color = theme.muted), layout(-1, -2, top = 12))
            }
        }
        details.addView(button("현대 내비 열기") { openNavigation() }, layout(-1, 80, top = 32))
    }

    private fun dismissDetails() { detailDialog?.dismiss(); detailDialog = null }

    private fun openNavigation() {
        val request = Intent("ai.pleos.playground.intent.action.NAVI_START")
        val resolved = packageManager.resolveActivity(request, 0)
        if (resolved == null) {
            Toast.makeText(this, "내비게이션 앱을 찾지 못했어요.", Toast.LENGTH_SHORT).show()
            return
        }
        request.component = ComponentName(resolved.activityInfo.packageName, resolved.activityInfo.name)
        runCatching { startActivity(request) }.onFailure {
            Toast.makeText(this, "내비게이션을 열지 못했어요. 앱 목록에서 열어 주세요.", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onResume() {
        super.onResume()
        restored = JourneyRuntime.latest(this)
        resumed = true
        main.removeCallbacks(poll)
        main.post(poll)
    }

    override fun onPause() {
        resumed = false
        if (::avatarView.isInitialized) avatarView.stopMotion()
        dismissDetails()
        main.removeCallbacks(poll)
        super.onPause()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        dismissDetails()
        refresh(rebuild = true)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean("muted", muted)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        imageRequest++
        dismissDetails()
        carGate?.close()
        main.removeCallbacksAndMessages(null)
        images.shutdownNow()
        super.onDestroy()
    }

    private fun JSONObject.numberOrNull(key: String): Double? =
        (opt(key) as? Number)?.toDouble()?.takeIf { it.isFinite() }
    private fun parkedNow(): Boolean = carGate?.canDisplay()
        ?: !packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)
    private fun duration(seconds: Long): String = when {
        seconds >= 3600 -> "${seconds / 3600}시간 ${seconds / 60 % 60}분"
        seconds >= 60 -> "${seconds / 60}분 ${seconds % 60}초"
        else -> "${seconds}초"
    }
    private fun clock(seconds: Long): String = if (seconds >= 3600) duration(seconds)
        else String.format(Locale.KOREA, "%02d:%02d", seconds / 60, seconds % 60)
    private fun bodyHeight(): Int = (if (viewportHeight > 0) viewportHeight / resources.displayMetrics.density
        else resources.configuration.screenHeightDp.toFloat()).toInt() - (if (compact) 64 else 80) - 80 -
        (if (compact) 108 else 120) - 80 - 72
    private fun column() = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
    private fun row() = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
    private fun card(color: Int, padding: Int, radius: Int = 28) = column().apply {
        background = shape(color, radius)
        setPadding(dp(padding), dp(padding), dp(padding), dp(padding))
    }
    private fun text(value: String, size: Int, lineHeight: Int, weight: Int = 400, color: Int = theme.ink) = TextView(this).apply {
        text = value; textSize = size.toFloat(); setTextColor(color)
        typeface = NuntiFonts.get(this@JourneyActivity, weight)
        includeFontPadding = false
        setLineHeight(dp(lineHeight)); minHeight = dp(lineHeight)
        gravity = Gravity.CENTER_VERTICAL
    }
    private fun shape(color: Int, radius: Int, border: Boolean = false) = GradientDrawable().apply {
        setColor(color); cornerRadius = dp(radius).toFloat()
        if (border) setStroke(dp(1).coerceAtLeast(1), theme.accent)
    }
    private fun button(label: String, primary: Boolean = false, quiet: Boolean = false, action: () -> Unit) = Button(this).apply {
        text = label; textSize = 26f; isAllCaps = false
        typeface = NuntiFonts.get(this@JourneyActivity, 500)
        includeFontPadding = false
        setTextColor(if (primary) theme.onAccent else theme.accent)
        val fill = if (primary) theme.accent else if (quiet) theme.soft else theme.surface
        background = RippleDrawable(ColorStateList.valueOf((theme.accent and 0x00ffffff) or 0x26000000),
            shape(fill, 16, border = !primary && !quiet), shape(android.graphics.Color.WHITE, 16))
        setPadding(dp(if (compact) 20 else 32), dp(16), dp(if (compact) 20 else 32), dp(16))
        minWidth = dp(120); minimumWidth = dp(120); minHeight = dp(80); minimumHeight = dp(80)
        maxLines = 1; ellipsize = TextUtils.TruncateAt.END
        stateListAnimator = null
        setOnClickListener { action() }
    }
    private fun layout(width: Int, height: Int, top: Int = 0, left: Int = 0) =
        LinearLayout.LayoutParams(if (width < 0) width else dp(width), if (height < 0) height else dp(height))
            .apply { topMargin = dp(top); leftMargin = dp(left) }
    private fun dp(value: Int) = (value * resources.displayMetrics.density + .5f).toInt()
}
