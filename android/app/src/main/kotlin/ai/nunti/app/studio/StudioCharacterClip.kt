package ai.nunti.app.studio

import android.content.res.AssetManager
import org.json.JSONObject

/** The shipped character keyframes use 60 fps and the original pose easing. */
internal class StudioCharacterClip private constructor(val frames: Int, private val tracks: List<Track>) {
    private class Track(val joint: Int, val property: String, val times: IntArray, val values: FloatArray) {
        fun at(frame: Float): Float {
            for (next in 1 until times.size) {
                if (frame >= times[next]) continue
                val prior = next - 1
                val span = times[next] - times[prior]
                if (property == "opacity" && (joint >= 51 || span > 6)) return values[prior]
                val fraction = ease(((frame - times[prior]) / span).coerceIn(0f, 1f))
                return values[prior] + (values[next] - values[prior]) * fraction
            }
            return values.last()
        }
    }

    fun apply(frame: Float, pose: StudioCharacterPose) {
        for (track in tracks) pose.set(track.joint, track.property, track.at(frame))
    }

    companion object {
        fun load(assets: AssetManager, skin: String): Map<String, StudioCharacterClip> {
            val root = assets.open("nunti-character/motion.json").bufferedReader().use { JSONObject(it.readText()) }
            val clips = root.getJSONObject(skin)
            return clips.keys().asSequence().associateWith { name ->
                val clip = clips.getJSONObject(name)
                val frames = clip.getInt("frames")
                require(frames > 0)
                val rows = clip.getJSONArray("tracks")
                StudioCharacterClip(frames, List(rows.length()) { row ->
                    val data = rows.getJSONArray(row)
                    val keys = data.getJSONArray(2)
                    val times = IntArray(keys.length()) { keys.getJSONArray(it).getInt(0) }
                    val values = FloatArray(keys.length()) { keys.getJSONArray(it).getDouble(1).toFloat() }
                    require(times.isNotEmpty() && times.first() == 0 && times.last() <= frames)
                    require((1 until times.size).all { times[it] > times[it - 1] })
                    Track(data.getInt(0), data.getString(1), times, values)
                })
            }
        }

        private fun ease(fraction: Float): Float {
            if (fraction == 0f || fraction == 1f) return fraction
            var u = fraction
            repeat(4) {
                val v = 1f - u
                val x = 1.08f * v * v * u + 1.26f * v * u * u + u * u * u
                val slope = 1.08f * v * v + .36f * v * u + 1.74f * u * u
                u = (u - (x - fraction) / slope).coerceIn(0f, 1f)
            }
            return u * u * (3f - 2f * u)
        }
    }
}
