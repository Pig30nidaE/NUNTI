package ai.nunti.app.studio

import android.graphics.Rect
import android.os.Handler
import android.util.Log
import android.view.Choreographer
import android.view.View
import android.webkit.WebView
import android.widget.FrameLayout
import java.util.concurrent.Executor
import kotlin.math.roundToInt

/** Owns playback in the existing parked Studio stage. */
internal class StudioCharacterMotion(
    private val container: FrameLayout,
    private val web: WebView,
    private val shield: View,
    private val main: Handler,
    private val io: Executor,
    private val allowed: () -> Boolean,
    private val reportReady: (Int, Boolean) -> Unit,
    private val reportFinished: (Int) -> Unit,
    private val reportCompanionReady: (Int, Boolean) -> Unit,
) {
    private sealed class Request(val id: Int, val skin: String, val bounds: Rect) {
        var startedAt = 0L
        class Transform(id: Int, skin: String, bounds: Rect, val direction: Float) : Request(id, skin, bounds) {
            var revealed = false
            var finished = false
        }
        class Companion(id: Int, skin: String, bounds: Rect) : Request(id, skin, bounds) {
            var reaction: String? = null
            var faceStartedAt = 0L
            var focusX = 0f
            var focusY = 0f
            var lastTouchAt = 0L
        }
    }

    private class Prepared(
        val skin: String,
        val character: StudioCharacterAssets,
        val clips: Map<String, StudioCharacterClip>,
        val forTransform: Boolean,
        val masks: StudioEvolutionEffects.Masks?,
        val atlas: StudioAtlasVfx?,
    )

    private val choreographer = Choreographer.getInstance()
    private val pose = StudioCharacterPose()
    private var request: Request? = null
    private var lastTransformId = 0
    private var lastCompanionId = 0
    private var prepared: Prepared? = null
    private var actor: StudioCharacterCanvas? = null
    private var stage: FrameLayout? = null
    private var effects: StudioEvolutionEffects? = null
    private val deadline = Runnable { stop(notify = true) }
    private val tick = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            val current = request ?: return
            val art = prepared ?: return
            if (!allowed()) {
                stop(notify = true)
                return
            }
            val elapsed = ((frameTimeNanos - current.startedAt) * (60.0 / 1_000_000_000))
                .toFloat().coerceAtLeast(0f)
            when (current) {
                is Request.Transform -> if (!transform(current, art, elapsed + 1f)) return
                is Request.Companion -> {
                    pose.focusX = current.focusX
                    pose.focusY = current.focusY
                    val reaction = current.reaction
                    if (reaction != null && elapsed >= clipFrames(art,reaction)) {
                        current.reaction = null
                        current.startedAt = frameTimeNanos
                        draw(art, "idle", 0f, ((frameTimeNanos-current.faceStartedAt)*60.0/1_000_000_000).toFloat())
                    } else {
                        val name = reaction ?: "idle"
                        draw(art, name, elapsed % clipFrames(art,name),
                            ((frameTimeNanos-current.faceStartedAt)*60.0/1_000_000_000).toFloat())
                    }
                }
            }
            choreographer.postFrameCallback(this)
        }
    }

    fun start(id: Int, skin: String, left: Double, top: Double, width: Double, height: Double, direction: Double) {
        if (id <= lastTransformId) return
        lastTransformId = id
        stop(notify = request is Request.Companion)
        val bounds = stageBounds(left, top, width, height)
        if (!allowed() || (skin !in TRAVEL_SKINS && !NuntiSkinStyle.isWardrobe(skin)) || bounds == null) {
            reportReady(id, false)
            return
        }
        val lean = if (direction.isFinite()) direction.coerceIn(-1.0, 1.0).toFloat() else 0f
        load(Request.Transform(id, skin, bounds, lean))
    }

    fun startCompanion(id: Int, skin: String, left: Double, top: Double, width: Double, height: Double) {
        if (id <= lastCompanionId) return
        lastCompanionId = id
        val artSkin = if (skin == "default") "base" else skin
        val bounds = stageBounds(left, top, width, height)
        val current = request
        if (!allowed() || (artSkin != "base" && artSkin !in TRAVEL_SKINS && !NuntiSkinStyle.isWardrobe(artSkin)) || bounds == null ||
            (current is Request.Transform && !current.finished)
        ) {
            reportCompanionReady(id, false)
            return
        }
        val next = Request.Companion(id, artSkin, bounds)
        if (current is Request.Transform && current.finished && current.skin == artSkin && actor != null) {
            request = next
            companionReady(next, checkNotNull(prepared), checkNotNull(actor))
            return
        }
        stop()
        load(next)
    }

    fun reactCompanion(id: Int, reaction: String) {
        val current = request as? Request.Companion ?: return
        val shared = current.skin == "base" || current.skin.startsWith("wardrobe-shared1-")
        if (current.id != id || current.startedAt == 0L ||
            (if (shared) reaction !in ai.nunti.app.journey.NuntiCompanionMotion.reactions else reaction !in REACTIONS)) return
        if (!allowed()) {
            stop(notify = true)
            return
        }
        val now = System.nanoTime()
        if (now - current.lastTouchAt < 350_000_000L) return
        current.lastTouchAt = now
        current.reaction = reaction
        current.startedAt = System.nanoTime()
        Log.i(TAG, "CANVAS_REACTION skin=" + current.skin + " reaction=" + reaction)
    }

    fun focusCompanion(id: Int, x: Double, y: Double) {
        val current = request as? Request.Companion ?: return
        if (current.id != id || !x.isFinite() || !y.isFinite()) return
        if (!allowed()) { stop(notify = true); return }
        current.focusX = x.coerceIn(-1.0, 1.0).toFloat()
        current.focusY = y.coerceIn(-1.0, 1.0).toFloat()
    }

    private fun load(next: Request) {
        request = next
        main.postDelayed(deadline, if(next.skin.startsWith("wardrobe-")) 15000L else 1500L)
        val cached = prepared?.takeIf { it.skin == next.skin }
        val forTransform = next is Request.Transform
        if (cached != null && (!forTransform || cached.forTransform)) {
            prepare(next, cached)
            return
        }
        val assets = web.context.assets
        io.execute {
            val result = runCatching {
                val generated = next.skin.startsWith("wardrobe-")
                val clips = cached?.clips ?: StudioCharacterClip.load(assets, if(generated) "base" else next.skin)
                require(clips.keys.containsAll(BASE_REACTIONS + "idle"))
                if (forTransform && !generated) require(clips.keys.containsAll(TRANSFORM_CLIPS))
                val character=cached?.character ?: if(generated) StudioCharacterAssets.generated(web.context, next.skin) else StudioCharacterAssets.load(assets, next.skin)
                Prepared(
                    next.skin, character, clips, forTransform,
                    if (forTransform) { if(generated) StudioEvolutionEffects.decodeMasks(character.base,character.travel) else StudioEvolutionEffects.decodeMasks(assets, next.skin) } else null,
                    if (forTransform && !generated) StudioAtlasVfx.load(assets, next.skin) else null,
                )
            }
            main.post {
                if (request !== next) return@post
                result.onSuccess { prepare(next, it) }.onFailure {
                    Log.w(TAG, "Character artwork unavailable", it)
                    stop(notify = true)
                }
            }
        }
    }

    private fun prepare(next: Request, art: Prepared) {
        if (!allowed()) {
            stop(notify = true)
            return
        }
        prepared = art
        main.removeCallbacks(deadline)
        val view = actor ?: StudioCharacterCanvas(web.context).also {
            it.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
            val overlay = StudioEvolutionEffects(web.context)
            val bounded = FrameLayout(web.context).apply {
                clipChildren = true
                addView(overlay.behind, FrameLayout.LayoutParams(-1, -1))
                addView(it, FrameLayout.LayoutParams(-1, -1))
                addView(overlay, FrameLayout.LayoutParams(-1, -1))
            }
            container.addView(bounded, container.indexOfChild(shield), FrameLayout.LayoutParams(0, 0))
            actor = it
            effects = overlay
            stage = bounded
        }
        when (next) {
            is Request.Transform -> {
                placeStage(next.bounds, view)
                view.showEvolution(art.character, pose, 0f)
                view.visibility = View.VISIBLE
                next.startedAt = System.nanoTime()
                effects?.start(next.skin, art.masks, art.atlas, next.direction, { request === next && allowed() }) { scale ->
                    view.scaleX = scale
                    view.scaleY = scale
                }
                choreographer.postFrameCallback(tick)
                Log.i(TAG, "CANVAS_PLAYING skin=" + next.skin)
                reportReady(next.id, true)
            }
            is Request.Companion -> companionReady(next, art, view)
        }
    }

    private fun companionReady(next: Request.Companion, art: Prepared, view: StudioCharacterCanvas) {
        placeStage(next.bounds, view)
        draw(art, "idle", 0f)
        view.visibility = View.VISIBLE
        next.startedAt = System.nanoTime()
        next.faceStartedAt = next.startedAt
        choreographer.postFrameCallback(tick)
        Log.i(TAG, "CANVAS_COMPANION_READY skin=" + next.skin)
        reportCompanionReady(next.id, true)
    }

    private fun transform(next: Request.Transform, art: Prepared, elapsed: Float): Boolean {
        if (art.skin in TRAVEL_SKINS || art.skin.startsWith("wardrobe-")) {
            val seconds = elapsed / 60f
            actor?.showEvolution(art.character, pose, seconds)
            if (seconds < 4.6f) return true
            effects?.stop()
            draw(art, "idle", 0f)
            next.finished = true
            Log.i(TAG, "CANVAS_SIGNATURE_FINISHED skin=" + next.skin)
            reportFinished(next.id)
            return false
        }
        var local = elapsed
        for (name in TRANSFORM_CLIPS) {
            val clip = art.clips.getValue(name)
            if (local < clip.frames) {
                if (name == "signature" && !next.revealed) {
                    next.revealed = true
                    effects?.stop()
                    Log.i(TAG, "CANVAS_FINISHED skin=" + next.skin)
                }
                draw(art, name, local)
                return true
            }
            local -= clip.frames
        }
        draw(art, "idle", 0f)
        next.finished = true
        Log.i(TAG, "CANVAS_SIGNATURE_FINISHED skin=" + next.skin)
        reportFinished(next.id)
        return false
    }

    private fun clipFrames(art:Prepared,name:String):Float = when {
        (art.skin == "base" || art.skin.startsWith("wardrobe-shared1-")) && name in ai.nunti.app.journey.NuntiCompanionMotion.reactions -> ai.nunti.app.journey.NuntiCompanionMotion.duration(name) * 60f
        art.skin != "base" && name in REACTIONS -> ai.nunti.app.journey.NuntiLifeMotion.reactionSeconds(name) * 60f
        else -> art.clips.getValue(name).frames.toFloat()
    }

    private fun draw(art: Prepared, clip: String, frame: Float, faceFrame: Float = frame) {
        pose.reset(art.skin, clip)
        pose.faceTime = faceFrame
        pose.faceReactionTime = frame / clipFrames(art,clip)
        (art.clips[clip]?:art.clips.getValue("idle")).apply(frame, pose)
        actor?.show(art.character, pose)
    }

    fun stopTransform(id: Int) {
        if ((request as? Request.Transform)?.id == id) stop()
    }

    fun stopCompanion(id: Int) {
        if ((request as? Request.Companion)?.id == id) stop()
    }

    fun stop(notify: Boolean = false) {
        val current = request ?: return
        request = null
        main.removeCallbacks(deadline)
        choreographer.removeFrameCallback(tick)
        effects?.stop()
        actor?.visibility = View.GONE
        if (notify) when (current) {
            is Request.Transform -> reportReady(current.id, false)
            is Request.Companion -> reportCompanionReady(current.id, false)
        }
    }

    fun resetPage() {
        stop()
        lastTransformId = 0
        lastCompanionId = 0
    }

    private fun stageBounds(left: Double, top: Double, width: Double, height: Double): Rect? {
        val right = left + width
        val bottom = top + height
        if (!right.isFinite() || !bottom.isFinite() || left < 0 || top < 0 ||
            width < 1 || height < 1 || right > web.width + 1.0 || bottom > web.height + 1.0
        ) return null
        return Rect(left.roundToInt(), top.roundToInt(), right.roundToInt().coerceAtMost(web.width),
            bottom.roundToInt().coerceAtMost(web.height)).takeUnless { it.isEmpty }
    }

    private fun placeStage(bounds: Rect, view: StudioCharacterCanvas) {
        checkNotNull(stage).layoutParams = FrameLayout.LayoutParams(bounds.width(), bounds.height()).apply {
            leftMargin = web.left + bounds.left
            topMargin = web.top + bounds.top
        }
        val artboardSide = minOf(bounds.width(), bounds.height()).toFloat()
        view.pivotY = (bounds.height() - artboardSide) * .5f +
            artboardSide * StudioEvolutionEffects.CAMERA_PIVOT_FRACTION
    }

    private companion object {
        const val TAG = "NuntiCharacter"
        val TRAVEL_SKINS = setOf("sea", "city", "mountain")
        val BASE_REACTIONS = setOf("curious", "happy", "wink", "proud", "signature")
        val REACTIONS = BASE_REACTIONS + setOf("surprised","nod","sleepy")
        val TRANSFORM_CLIPS = listOf("anticipation", "transform", "reveal", "signature")
    }
}
