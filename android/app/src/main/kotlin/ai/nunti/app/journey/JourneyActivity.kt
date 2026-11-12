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
    private var locationPermissionAsked = false
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
            NuntiLifeMotion.prepare(assets)
            NuntiFaceRig.prepare(assets)
            val fallback = runCatching {
                assets.open("nunti-motion/base.png").use { BitmapFactory.decodeStream(it) }?.also {
                    NuntiFaceRig.prepareSharedImage(it); NuntiPuppetParts.prepareShared(it)
                }
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
        if(active && parked && snapshot?.optString("source")=="LIVE" && !locationPermissionAsked) {
            locationPermissionAsked=true
            if(checkSelfPermission(JourneyLocationSource.PERMISSION)!=PackageManager.PERMISSION_GRANTED && JourneyLocationSource.supported(this))
                requestPermissions(arrayOf(JourneyLocationSource.PERMISSION),2041)
        }
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
            Screen.REPORT -> if (finished) "이번 길을 돌아봐요" else "마지막 여정을 돌아봐요"
            else -> if (active) "이번 길도, 눈티와 함께" else "정차 후 여정을 확인해요"
        }
        val place = snapshot.optString("destination").takeIf { it.isNotBlank() }
        val purpose = snapshot.optString("purpose").takeIf { it.isNotBlank() }
        val trip = listOfNotNull(place, purpose).joinToString(" · ")
        destination?.text = if (nextScreen == Screen.REPORT && !compact) {
            if (finished) trip
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
        scoreContext?.text = if (total == null) "신호가 더 필요해요" else "수신한 항목만 평가 · 100점 기준"
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
        avatarView.setFaceRig(snapshot.optString("faceRig", "none"))
        avatarView.setEmotion(emotion, animate = resumed && parked)
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
        val snapshot = JourneyRuntime.current ?: restored ?: JSONObject()
        val summary = card(theme.soft, 28)
        summary.addView(text("이번 길의 운전 점수", 24, 36, color=theme.muted),layout(-1,-2))
        score=text("",68,88,700);summary.addView(score,layout(-1,-2,top=8))
        scoreContext=text("",22,34,color=theme.muted);summary.addView(scoreContext,layout(-1,-2,top=8))
        if(!compact) summary.addView(avatarView,layout(-1,290,top=8))
        elapsed=text("",28,42,500);summary.addView(elapsed,layout(-1,-2,top=16))
        summary.addView(text("추정 주행 거리  %.2f km".format(snapshot.optDouble("distanceKm",0.0)),22,34,color=theme.muted),layout(-1,-2,top=8))
        coverage=text("",22,34,color=theme.accent);summary.addView(coverage,layout(-1,-2,top=12))
        summary.addView(button("점수 산정 기준",quiet=true){showDetails()},layout(-1,80,top=20))
        val report=column()
        val route=card(theme.surface,24)
        route.addView(text("구간별 기록",30,44,700),layout(-1,-2))
        val events=snapshot.optJSONArray("events")
        val n=events?.length()?:0
        val located=(0 until n).count { events?.optJSONObject(it)?.optJSONObject("position")!=null }
        val source=if(snapshot.optString("source")=="DEMO") "시뮬레이션 경로 · 실제 GPS 기록 아님" else if(located>0) "수신한 위치와 차량 신호로 기록했어요" else "위치 미수신 · 이벤트는 시간순으로 확인해요"
        route.addView(text(source,22,34,color=theme.muted),layout(-1,-2,top=4))
        val detail=text(if(n>0) "번호를 누르면 그 순간을 볼 수 있어요" else "기록된 급격한 조작이 없어요",24,36,500)
        val map=JourneyRouteView(this,snapshot,theme){ index ->
            val e=events?.optJSONObject(index)
            if(e!=null) detail.text="${index+1}. ${e.optString("label")} · ${clock(e.optLong("tMs")/1000)}\n${e.optString("evidence")}"
        }
        route.addView(map,layout(-1,230,top=8))
        route.addView(detail,layout(-1,-2,top=8))
        report.addView(route,layout(-1,-2))
        val habits=snapshot.optJSONArray("habits")
        fun habitCard(positive:Boolean):View {
            val card=card(if(positive) theme.soft else theme.surface,24)
            card.addView(text(if(positive) "잘한 습관" else "다음에는 이렇게",24,36,700,color=if(positive) theme.accent else theme.warm),layout(-1,-2))
            val choices=(0 until (habits?.length()?:0)).mapNotNull { habits?.optJSONObject(it) }.filter { it.optBoolean("positive")==positive }.take(2)
            if(choices.isEmpty()) card.addView(text(if(positive) "충분한 주행 정보를 받으면 잘한 습관을 알려드려요." else if(snapshot.numberOrNull("total")!=null) "평가된 항목에서 개선할 습관이 발견되지 않았어요." else "이번 기록은 정보가 부족해 습관을 평가하지 않았어요.",24,38),layout(-1,-2,top=12))
            for(h in choices) card.addView(text(h.optString("detail"),24,38),layout(-1,-2,top=12))
            return card
        }
        report.addView(habitCard(false),layout(-1,-2,top=20))
        report.addView(habitCard(true),layout(-1,-2,top=20))
        val log=card(theme.surface,24)
        log.addView(text("기억할 순간  ${n}회",28,42,700),layout(-1,-2))
        for(i in 0 until minOf(n,30)) {
            val event=events?.optJSONObject(i)?:continue
            val row=column()
            row.addView(text("${i+1}  ${event.optString("label")}    ${clock(event.optLong("tMs")/1000)}",26,40,500),layout(-1,-2))
            row.addView(text(event.optString("evidence"),22,34,color=theme.muted),layout(-1,-2,top=4))
            row.addView(text(event.optString("advice"),22,34),layout(-1,-2,top=8))
            if(event.optJSONObject("position")==null) row.addView(text("위치 정보 없음",20,30,color=theme.muted),layout(-1,-2,top=4))
            log.addView(row,layout(-1,-2,top=24))
        }
        if(!snapshot.optBoolean("steeringAvailable"))log.addView(text("핸들 각도 미수신 · 급회전은 평가하지 않았어요",22,34,color=theme.muted),layout(-1,-2,top=16))
        report.addView(log,layout(-1,-2,top=20))
        if(compact) {
            val all=column();all.addView(summary,layout(-1,-2));all.addView(report,layout(-1,-2,top=20))
            return ScrollView(this).apply {addView(all);isFillViewport=false}
        }
        val body=row()
        body.addView(ScrollView(this).apply {addView(summary)},LinearLayout.LayoutParams(0,-1,.85f))
        body.addView(ScrollView(this).apply {addView(report);isFillViewport=false},LinearLayout.LayoutParams(0,-1,1.75f).apply {leftMargin=dp(24)})
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
        val faceRig = (JourneyRuntime.current ?: restored)?.optString("faceRig")
        val shared = faceRig == NuntiCompanionMotion.VERSION || faceRig == "base-v1"
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
                BitmapFactory.decodeFile(file.path, options)?.also {
                    if (shared) NuntiPuppetParts.prepareShared(it)
                    else NuntiPuppetParts.prepare(assets,file.nameWithoutExtension,it)
                    if (it.width == 768 && it.height == 768) NuntiFaceRig.prepareSharedImage(it)
                }
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
        details.addView(text("무엇을 평가하나요?",30,44,700),layout(-1,-2))
        details.addView(text("속도·제어 35점, 주변 대응 35점, 안전 상태 20점, 효율 10점. 수신한 영역의 배점을 100점으로 환산해요.",24,38,color=theme.muted),layout(-1,-2,top=12))
        details.addView(text("미수신 항목은 0점이나 만점으로 넣지 않아요. 점수는 프로젝트의 시험 기준이며 공인 운전 등급이 아닙니다.",22,34,color=theme.muted),layout(-1,-2,top=12))
        val items=snapshot.optJSONArray("items")
        val criteria=mapOf(
            "ACCEL_DECEL" to "일반도로: 1초에 +10 km/h 이상 가속, −12 km/h 이상 감속. 고속도로는 +7 / −9. 연속 조작은 1회로 묶고 1분 구간에서 강도에 따라 20~40점을 차감해요.",
            "TURN_DECEL" to "회전 진입 속도가 5초 전보다 15% 이상 낮거나 20 km/h 이하면 충족해요. 내비 안내 통과를 회전 기회로 사용해요.",
            "LEAD_GAP" to "현재 속도로 앞차까지 2초 이상이면 100점, 0.5초 이하면 0점으로 계산해요.",
            "SPEED_LIMIT" to "수신된 제한속도에 5 km/h 여유를 두고, 초과 1 km/h마다 4점을 차감해요.",
            "LANE_SIGNAL" to "차선 변경 전 3초 안에 해당 방향의 지시등을 사용했는지 확인해요.",
            "REVERSE_SPEED" to "후진 8 km/h 이하를 기준으로 계산해요.",
            "SEATBELT" to "주행 중 탑승이 확인된 좌석의 벨트 상태를 확인해요.",
            "DOOR" to "주행 중 문이 열린 시간이 있는지 확인해요.",
            "HEADLIGHT" to "야간 신호가 확인된 주행에서 실제 전조등 점등을 확인해요.",
            "EFFICIENCY" to "연비·전비 신호가 제공되지 않아 현재 총점에서 제외해요.")
        for(i in 0 until (items?.length()?:0)) {
            val item=items?.optJSONObject(i)?:continue
            val value=item.numberOrNull("score")
            val card=card(theme.soft,24)
            card.addView(text(item.optString("label"),26,40,500),layout(-1,-2))
            card.addView(text(if(value==null) "평가하지 않음 · ${item.optString("basis")}" else "%.0f점 · %s".format(value,item.optString("basis")),24,36,color=if(value!=null&&value<70) theme.warm else theme.accent),layout(-1,-2,top=8))
            if(value!=null) card.addView(android.widget.ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal).apply {
                max=100;progress=value.toInt();progressTintList=ColorStateList.valueOf(if(value<70) theme.warm else theme.accent)
                progressBackgroundTintList=ColorStateList.valueOf(theme.surface)
                contentDescription="${item.optString("label")} ${value.toInt()}점"
            },layout(-1,12,top=12))
            card.addView(text(criteria[item.optString("id")]?:item.optString("basis"),22,34,color=theme.muted),layout(-1,-2,top=12))
            details.addView(card,layout(-1,-2,top=20))
        }
        details.addView(text("급회전 참고 기록: 20 km/h 이상에서 핸들 각도가 초당 100° 이상 변할 때 표시해요. 총점에는 중복 반영하지 않아요.",22,34,color=theme.muted),layout(-1,-2,top=24))
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
