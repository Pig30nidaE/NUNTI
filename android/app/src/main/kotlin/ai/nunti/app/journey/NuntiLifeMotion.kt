package ai.nunti.app.journey

import android.content.res.AssetManager
import org.json.JSONObject
import kotlin.math.sin

/** Authored local gesture tracks. No inference, random state, or allocations in the frame loop. */
internal object NuntiLifeMotion {
    class Pose { var head=0f;var left=0f;var right=0f;var lift=0f;var expression=0;var amount=0f;var name="rest" }
    private class Track(val times:FloatArray,val values:FloatArray) {
        fun at(t:Float):Float {for(i in 1 until times.size)if(t<times[i]){val u=smooth((t-times[i-1])/(times[i]-times[i-1]));return values[i-1]+(values[i]-values[i-1])*u};return values.last()}
    }
    private class Clip(val duration:Float,val expression:Int,val tracks:List<Track>)
    private var clips=emptyMap<String,Clip>()
    private var schedule=emptyList<Pair<Float,String>>()
    @Synchronized fun prepare(assets:AssetManager) {
        if(clips.isNotEmpty())return
        val root=assets.open("nunti-life-v5/manifest.json").bufferedReader().use{JSONObject(it.readText())}
        val data=root.getJSONObject("clips")
        clips=data.keys().asSequence().associateWith { name ->
            val c=data.getJSONObject(name)
            Clip(c.getDouble("duration").toFloat(),c.getInt("expression"),listOf("head","leftArm","rightArm","lift").map { key ->
                val a=c.getJSONArray(key);Track(FloatArray(a.length()){a.getJSONArray(it).getDouble(0).toFloat()},FloatArray(a.length()){a.getJSONArray(it).getDouble(1).toFloat()})
            })
        }
        val rows=root.getJSONArray("idleSchedule")
        schedule=List(rows.length()){val r=rows.getJSONArray(it);r.getDouble(0).toFloat() to r.getString(1)}
    }
    fun reactionSeconds(reaction:String):Float = clips[when(reaction){"curious"->"curious";"happy"->"laugh";"wink"->"wave";"proud"->"stretch";"signature"->"celebrate";"surprised"->"surprised";"nod"->"nod";"sleepy"->"sleepy";else->"nod"}]?.duration ?: 3.2f
    fun sample(seconds:Float,reaction:String,progress:Float,out:Pose) {
        out.head=sin(seconds*.7f)*.7f;out.left=0f;out.right=0f;out.lift=sin(seconds*1.4f)*1.3f;out.expression=0;out.amount=0f;out.name="rest"
        val manual=when(reaction){"curious"->"curious";"happy"->"laugh";"wink"->"wave";"proud"->"stretch";"signature"->"celebrate";"surprised"->"surprised";"nod"->"nod";"sleepy"->"sleepy";else->null}
        val time=seconds%58f
        val idle=if(manual==null)schedule.firstOrNull{(at,name)->time>=at&&time<at+(clips[name]?.duration?:0f)} else null
        val name=manual?:idle?.second?:return
        val clip=clips[name]?:return
        val t=if(manual!=null)progress.coerceIn(0f,1f) else ((time-checkNotNull(idle).first)/clip.duration).coerceIn(0f,1f)
        out.name=name;out.head+=clip.tracks[0].at(t);out.left=clip.tracks[1].at(t);out.right=clip.tracks[2].at(t);out.lift+=clip.tracks[3].at(t)
        out.expression=clip.expression;out.amount=smooth(t/.22f)*(1-smooth((t-.76f)/.24f))
    }
    private fun smooth(value:Float):Float {val v=value.coerceIn(0f,1f);return v*v*(3-2*v)}
}
