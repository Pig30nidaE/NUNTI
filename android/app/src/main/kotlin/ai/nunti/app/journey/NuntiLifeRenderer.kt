package ai.nunti.app.journey

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import kotlin.math.cos
import kotlin.math.sin

/** Weighted shoulder/head joints animate the existing outfit without replacing the character. */
internal class NuntiLifeRenderer {
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val vertices=FloatArray((GRID+1)*(GRID+1)*2)
    private val face=NuntiFaceRig()
    private val pose=NuntiLifeMotion.Pose()
    private var autoStartedAt=0f
    private val headWeights=FloatArray((GRID+1)*(GRID+1))
    init {var i=0;for(row in 0..GRID)for(col in 0..GRID){val y=row*768f/GRID;headWeights[i++]=1-smooth((y-350)/55f)}}
    fun draw(canvas:Canvas,image:Bitmap,skin:String,time:Float,reaction:String="idle",progress:Float=0f,animated:Boolean=true,worry:Float=0f,joy:Float=0f) {
        if(reaction!="idle")autoStartedAt=time
        NuntiLifeMotion.sample(if(animated)(time-autoStartedAt).coerceAtLeast(0f) else 0f,if(animated)reaction else "idle",progress,pose)
        if(!animated){pose.head=0f;pose.left=0f;pose.right=0f;pose.lift=0f}
        val parts=NuntiPuppetParts.get(image)
        val head=pose.head*.0174533f
        val hc=cos(head);val hs=sin(head)
        var i=0;var v=0
        for(row in 0..GRID)for(col in 0..GRID){val x=col*768f/GRID;val y=row*768f/GRID
            val hx=x-384;val hy=y-370
            vertices[v++]=x+((hx*hc-hy*hs)-hx)*headWeights[i]
            vertices[v++]=y+((hx*hs+hy*hc)-hy)*headWeights[i];i++
        }
        val state=canvas.save();canvas.translate(0f,pose.lift)
        val breath=if(animated)sin(time*1.35f)*.003f else 0f
        canvas.scale(1+breath,1+breath,384f,721f)
        canvas.drawBitmapMesh(parts?.body?:image,GRID,GRID,vertices,0,null,0,paint)
        if(parts!=null) {
            var saved=canvas.save();canvas.rotate(pose.left*parts.leftGain,parts.leftPivot[0],parts.leftPivot[1]);canvas.drawBitmap(parts.left,0f,0f,paint);canvas.restoreToCount(saved)
            saved=canvas.save();canvas.rotate(pose.right*parts.rightGain,parts.rightPivot[0],parts.rightPivot[1]);canvas.drawBitmap(parts.right,0f,0f,paint);canvas.restoreToCount(saved)
        }
        canvas.rotate(pose.head,384f,370f)
        val expression=if(worry>.001f)4 else if(joy>.001f)1 else pose.expression
        val strength=if(worry>.001f)worry else if(joy>.001f)joy else pose.amount
        face.draw(canvas,image,skin,expression,strength,if(animated)NuntiFaceRig.blink(time) else 0f)
        canvas.restoreToCount(state)
    }
    companion object {private const val GRID=48;private fun smooth(t:Float):Float{val a=t.coerceIn(0f,1f);return a*a*(3-2*a)}}
}
