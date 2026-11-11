package ai.nunti.app.studio

import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** Costume-specific shapes, never a fallback to the sea flipbook. Everything is stage-local. */
internal class StudioWardrobeVfx(skin: String) : StudioVfxScene {
    private val theme=NuntiSkinStyle.theme(skin)
    private val tint=NuntiSkinStyle.tint(skin)
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG)
    private val path=Path()
    override fun drawBehind(canvas:Canvas,frame:StudioVfxFrame)=draw(canvas,frame,false)
    override fun drawFront(canvas:Canvas,frame:StudioVfxFrame)=draw(canvas,frame,true)
    private fun draw(canvas:Canvas,frame:StudioVfxFrame,front:Boolean) {
        val t=frame.time
        val amount=ease(t,.35f,.9f)*(1-ease(t,3.5f,4.25f))
        if(amount<=0)return
        paint.color=tint;paint.style=Paint.Style.STROKE;paint.strokeCap=Paint.Cap.ROUND
        if(!front) {
            paint.alpha=(amount*160).toInt();paint.strokeWidth=2.2f
            when(theme) {
                "football" -> {
                    canvas.drawOval(130f,635f,638f,740f,paint)
                    canvas.drawOval(312f,666f,456f,708f,paint)
                    canvas.drawLine(384f,635f,384f,740f,paint)
                    canvas.drawRoundRect(160f,655f,608f,722f,12f,12f,paint)
                }
                "medical" -> {
                    path.rewind();path.moveTo(115f,470f)
                    for(i in 0..80){val x=115f+i*6.7f;val u=(x-345f)/55f
                        val y=470f+if(u in -1.4f..1.4f) sin(u*PI.toFloat()*1.4f)*sin((u+1.4f)/2.8f*PI.toFloat())*72f else 0f
                        path.lineTo(x,y)}
                    canvas.drawPath(path,paint)
                }
                "formal" -> {
                    // Parallel seams gather upwards; short stitches refer to tailoring.
                    for(side in listOf(-1,1))for(seam in 0..1){
                        path.rewind();path.moveTo(384f+side*(250f+seam*10),670f)
                        path.cubicTo(384f+side*180f,580f,384f+side*255f,450f,384f+side*145f,350f)
                        paint.alpha=(amount*(if(seam==0)160 else 65)).toInt();canvas.drawPath(path,paint)
                    }
                }
                else -> canvas.drawOval(160f,630f,608f,730f,paint)
            }
        }
        for(i in 0 until 32) {
            val seed=((i*67+13)%97)/97f
            val u=((t-.4f-seed*.8f)/3.25f).coerceIn(0f,1f)
            if(u<=0||u>=1)continue
            val angle=i*2.39996f+u*2.4f;val depth=sin(angle)
            if((depth>0)!=front)continue
            val radius=255f-140f*ease(u,0f,.7f)+120f*ease(u,.72f,1f)
            val x=384f+cos(angle)*radius
            val y=680f-u*(330f+seed*185f)+depth*25f
            val alpha=amount*ease(u,0f,.12f)*(1-ease(u,.8f,1f))
            val size=4f+seed*5f
            val state=canvas.save();canvas.translate(x,y);canvas.rotate(angle*57.3f)
            paint.color=if(i%4==0)0xffffefcd.toInt() else tint;paint.alpha=(alpha*210).toInt();paint.strokeWidth=1.6f
            paint.style=Paint.Style.STROKE;path.rewind()
            when(theme) {
                "formal" -> if(i%3==0){canvas.drawCircle(0f,0f,size,paint);paint.style=Paint.Style.FILL;canvas.drawCircle(-2f,0f,1.1f,paint);canvas.drawCircle(2f,0f,1.1f,paint)}
                    else {canvas.drawLine(-size*1.8f,0f,size*1.8f,0f,paint);canvas.drawLine(-size*.6f,-3f,size*.6f,-3f,paint)}
                "football" -> {for(k in 0..5){val a=k*PI.toFloat()/3;val px=cos(a)*size;val py=sin(a)*size;if(k==0)path.moveTo(px,py)else path.lineTo(px,py)};path.close();canvas.drawPath(path,paint)}
                "medical" -> canvas.drawRoundRect(-size,-size*.55f,size,size*.55f,size*.55f,size*.55f,paint)
                "hiking" -> {path.moveTo(-size,0f);path.quadTo(0f,-size,size,0f);path.quadTo(0f,size,-size,0f);canvas.drawPath(path,paint)}
                else -> {canvas.drawCircle(0f,0f,size*.6f,paint)}
            }
            canvas.restoreToCount(state)
        }
    }
    private fun ease(t:Float,a:Float,b:Float):Float {val u=((t-a)/(b-a)).coerceIn(0f,1f);return u*u*(3-2*u)}
}
