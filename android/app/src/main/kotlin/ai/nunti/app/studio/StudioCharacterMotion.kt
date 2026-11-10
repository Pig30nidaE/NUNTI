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
                    val reaction = current.reaction
                    if (reaction != null && elapsed >= art.clips.getValue(reaction).frames) {
                        current.reaction = null
                        current.startedAt = frameTimeNanos
                        draw(art, "idle", 0f)
                    } else {
                        val name = reaction ?: "idle"
                        draw(art, name, elapsed % art.clips.getValue(name).frames)
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
        if (!allowed() || skin !in TRAVEL_SKINS || bounds == null) {
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
        if (!allowed() || (artSkin != "base" && artSkin !in TRAVEL_SKINS) || bounds == null ||
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
        if (current.id != id || current.startedAt == 0L || current.reaction != null || reaction !in REACTIONS) return
        if (!allowed()) {
            stop(notify = true)
            return
        }
        current.reaction = reaction
        current.startedAt = System.nanoTime()
        Log.i(TAG, "CANVAS_REACTION skin=" + current.skin + " reaction=" + reaction)
    }

    private fun load(next: Request) {
        request = next
        main.postDelayed(deadline, 1500L)
        val cached = prepared?.takeIf { it.skin == next.skin }
        val forTransform = next is Request.Transform
        if (cached != null && (!forTransform || cached.forTransform)) {
            prepare(next, cached)
            return
        }
        val assets = web.context.assets
        io.execute {
            val result = runCatching {
                val clips = cached?.clips ?: StudioCharacterClip.load(assets, next.skin)
                require(clips.keys.containsAll(REACTIONS + "idle"))
                if (forTransform) require(clips.keys.containsAll(TRANSFORM_CLIPS))
                Prepared(
                    next.skin, cached?.character ?: StudioCharacterAssets.load(assets, next.skin), clips, forTransform,
                    if (forTransform) StudioEvolutionEffects.decodeMasks(assets, next.skin) else null,
                    if (forTransform) StudioAtlasVfx.load(assets, next.skin) else null,
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
        choreographer.postFrameCallback(tick)
        Log.i(TAG, "CANVAS_COMPANION_READY skin=" + next.skin)
        reportCompanionReady(next.id, true)
    }

    private fun transform(next: Request.Transform, art: Prepared, elapsed: Float): Boolean {
        if (art.skin in TRAVEL_SKINS) {
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

    private fun draw(art: Prepared, clip: String, frame: Float) {
        pose.reset(art.skin, clip)
        art.clips.getValue(clip).apply(frame, pose)
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
        val REACTIONS = setOf("curious", "happy", "wink", "proud", "signature")
        val TRANSFORM_CLIPS = listOf("anticipation", "transform", "reveal", "signature")
    }
}
