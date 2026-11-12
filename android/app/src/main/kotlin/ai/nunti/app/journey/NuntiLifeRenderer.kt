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
    private val shared = NuntiSharedRenderer()
    private val pose=NuntiLifeMotion.Pose()
    private var autoStartedAt=0f
    private var previousTime=0f
    private var previousImage:Bitmap?=null
    private val headWeights = FloatArray((GRID + 1) * (GRID + 1))
    private val leftWeights = FloatArray(headWeights.size)
    private val rightWeights = FloatArray(headWeights.size)

    init {
        for (row in 0..GRID) for (col in 0..GRID) {
            val i = row * (GRID + 1) + col
            val x = col * 768f / GRID
            val y = row * 768f / GRID
            headWeights[i] = 1 - smooth((y - 350) / 55f)
            // The silhouette follows the sleeve. The center of the coat and the feet stay pinned.
            val sleeve = smooth((y - 400) / 80f) * (1 - smooth((y - 560) / 66f))
            leftWeights[i] = sleeve * (1 - smooth((x - 230) / 75f))
            rightWeights[i] = sleeve * smooth((x - 463) / 75f)
        }
    }
    fun draw(canvas:Canvas,image:Bitmap,skin:String,time:Float,reaction:String="idle",progress:Float=0f,animated:Boolean=true,worry:Float=0f,joy:Float=0f,focusX:Float=0f,focusY:Float=0f) {
        if (skin == "base" || skin == "base-v1" || skin == NuntiCompanionMotion.VERSION || skin.startsWith("wardrobe-shared1-")) {
            shared.draw(canvas, image, time, reaction, progress, focusX, focusY, animated)
            return
        }
        if(image!==previousImage||time<previousTime)autoStartedAt=0f
        previousImage=image;previousTime=time
        if(reaction!="idle")autoStartedAt=time
        NuntiLifeMotion.sample(if(animated)(time-autoStartedAt).coerceAtLeast(0f) else 0f,if(animated)reaction else "idle",progress,pose)
        if(!animated){pose.head=0f;pose.left=0f;pose.right=0f;pose.lift=0f}
        val parts=NuntiPuppetParts.get(image)
        val bundledRig=skin in setOf("sea","city","mountain")||parts!=null
        if(!bundledRig){
            val state=canvas.save();canvas.translate(0f,pose.lift)
            val breath=if(animated)sin(time*1.35f)*.003f else 0f
            canvas.scale(1+breath,1+breath,384f,721f)
            if(animated)canvas.rotate(pose.head*.22f,384f,700f)
            canvas.drawBitmap(image,0f,0f,paint)
            canvas.restoreToCount(state)
            return
        }
        val head=pose.head*.0174533f
        val hc=cos(head);val hs=sin(head)
        val left = if (parts == null) pose.left.coerceIn(-24f, 28f) * .0174533f else 0f
        // The compass is raised on the coastal illustration.
        val rightGain = if (skin == "sea") .0069813f else .0174533f
        val right = if (parts == null) pose.right.coerceIn(-28f, 24f) * rightGain else 0f
        val lc = cos(left) - 1f
        val ls = sin(left)
        val rc = cos(right) - 1f
        val rs = sin(right)
        var i=0;var v=0
        for(row in 0..GRID)for(col in 0..GRID){val x=col*768f/GRID;val y=row*768f/GRID
            val hx=x-384;val hy=y-370
            val lx = x - 287f
            val rx = x - 488f
            val armY = y - 418f
            vertices[v++] = x + ((hx * hc - hy * hs) - hx) * headWeights[i] +
                (lx * lc - armY * ls) * leftWeights[i] + (rx * rc - armY * rs) * rightWeights[i]
            vertices[v++] = y + ((hx * hs + hy * hc) - hy) * headWeights[i] +
                (lx * ls + armY * lc) * leftWeights[i] + (rx * rs + armY * rc) * rightWeights[i]
            i++
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
