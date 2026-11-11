package ai.nunti.app.journey

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.PointF
import android.view.MotionEvent
import android.view.View
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.hypot

/** A trip diagram from received coordinates. Missing event locations are never placed on the route. */
internal class JourneyRouteView(context: Context, private val snapshot: JSONObject,
    private val theme: NuntiTheme, private val selected: (Int) -> Unit) : View(context) {
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG)
    private val line=Path()
    private val pins=mutableListOf<Pair<Int,PointF>>()
    private var picked=-1
    private data class Point(val x:Double,val y:Double,val t:Long=0)
    private val isDemo=snapshot.optString("source")=="DEMO"
    private val longitudeScale=cos(Math.toRadians(snapshot.optJSONArray("track")?.optJSONObject(0)
        ?.optJSONObject("position")?.optDouble("latitude",0.0)?:0.0))
    private fun point(position:JSONObject?,t:Long=0):Point? {
        position?:return null
        return when(position.optString("space")) {
            "SIMULATION"->if(isDemo) Point(position.optDouble("x"),position.optDouble("y"),t) else null
            "WGS84"->if(!isDemo) Point(position.optDouble("longitude")*longitudeScale,-position.optDouble("latitude"),t) else null
            else->null
        }?.takeIf { it.x.isFinite()&&it.y.isFinite() }
    }
    init { contentDescription="주행 경로와 이벤트 위치. 위치가 없는 이벤트는 목록에서 확인할 수 있어요.";isClickable=true }
    override fun onDraw(canvas:Canvas) {
        val track=snapshot.optJSONArray("track")
        val points=(0 until (track?.length()?:0)).mapNotNull { i->track?.optJSONObject(i)?.let { point(it.optJSONObject("position"),it.optLong("tMs")) } }
        val events=snapshot.optJSONArray("events")
        val eventPoints=(0 until minOf(events?.length()?:0,30)).mapNotNull { i->point(events?.optJSONObject(i)?.optJSONObject("position"))?.let { i to it } }
        val planned=snapshot.optJSONObject("route")?.optJSONArray("points")
        val displayed=if(points.size>=2) points else if(planned!=null) (0 until planned.length()).mapNotNull { i->planned.optJSONArray(i)?.let { Point(it.optDouble(0),it.optDouble(1)) } } else emptyList()
        pins.clear()
        if(displayed.isEmpty()) {
            paint.color=theme.muted;paint.textSize=24f*resources.displayMetrics.density;paint.typeface=NuntiFonts.get(context,400)
            canvas.drawText("위치를 받으면 경로를 함께 기록해요",30f,height*.5f,paint);return
        }
        val all=displayed+(if(points.size>=2) eventPoints.map { it.second } else emptyList())
        val minX=all.minOf { it.x };val minY=all.minOf { it.y }
        val rangeX=(all.maxOf { it.x }-minX).coerceAtLeast(.00001);val rangeY=(all.maxOf { it.y }-minY).coerceAtLeast(.00001)
        val inset=42f*resources.displayMetrics.density
        val scale=minOf((width-2*inset)/rangeX,(height-2*inset)/rangeY)
        val ox=(width-rangeX*scale)/2;val oy=(height-rangeY*scale)/2
        fun xy(p:Point)=PointF((ox+(p.x-minX)*scale).toFloat(),(oy+(p.y-minY)*scale).toFloat())
        paint.strokeCap=Paint.Cap.ROUND;paint.strokeJoin=Paint.Join.ROUND
        line.reset()
        displayed.forEachIndexed { i,p->val q=xy(p);if(i==0||(!isDemo&&p.t-displayed[i-1].t>4000))line.moveTo(q.x,q.y) else line.lineTo(q.x,q.y) }
        paint.style=Paint.Style.STROKE;paint.strokeWidth=14f;paint.color=theme.surface;canvas.drawPath(line,paint)
        paint.strokeWidth=7f;paint.color=theme.accent;canvas.drawPath(line,paint);paint.style=Paint.Style.FILL
        for(p in listOf(displayed.first(),displayed.last())) {val q=xy(p);canvas.drawCircle(q.x,q.y,10f,paint)}
        if(points.size>=2) for((i,p) in eventPoints) {
            val q=xy(p);pins+=i to q;paint.color=if(i==picked) theme.ink else theme.warm
            canvas.drawCircle(q.x,q.y,if(i==picked) 25f else 21f,paint)
            paint.color=theme.surface;paint.typeface=NuntiFonts.get(context,700);paint.textSize=22f;paint.textAlign=Paint.Align.CENTER
            canvas.drawText("${i+1}",q.x,q.y-(paint.ascent()+paint.descent())/2,paint)
        }
        paint.textAlign=Paint.Align.LEFT
    }
    override fun onTouchEvent(event:MotionEvent):Boolean {
        if(event.action==MotionEvent.ACTION_DOWN) return pins.any { hypot(event.x-it.second.x,event.y-it.second.y)<48f }
        if(event.action==MotionEvent.ACTION_UP) {
            val pin=pins.minByOrNull { hypot(event.x-it.second.x,event.y-it.second.y) } ?: return false
            if(hypot(event.x-pin.second.x,event.y-pin.second.y)>64f) return false
            picked=pin.first;selected(picked);performClick();invalidate();return true
        }
        return true
    }
    override fun performClick():Boolean {super.performClick();return true}
}
