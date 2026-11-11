package ai.nunti.app.journey

import android.content.res.AssetManager
import android.graphics.*
import org.json.JSONObject
import java.util.WeakHashMap

/** Registered shoulder cutouts with generated hidden torso surfaces. Built only on the asset worker. */
internal object NuntiPuppetParts {
    class Parts(val body:Bitmap,val left:Bitmap,val right:Bitmap,val leftPivot:FloatArray,val rightPivot:FloatArray,val leftGain:Float,val rightGain:Float)
    private val cache=WeakHashMap<Bitmap,Parts>()
    @Synchronized fun get(image:Bitmap)=cache[image]
    @Synchronized fun prepare(assets:AssetManager,identity:String,image:Bitmap) {
        if(cache.containsKey(image))return
        val root=assets.open("nunti-life-v5/rigs.json").bufferedReader().use{JSONObject(it.readText())}
        val rig=root.getJSONObject("rigs").optJSONObject(identity.takeLast(64))?:return
        fun path(key:String):Path {val rows=rig.getJSONArray(key);return Path().apply{for(i in 0 until rows.length()){val r=rows.getJSONArray(i);val x=r.getDouble(0).toFloat();val y=r.getDouble(1).toFloat();if(i==0)moveTo(x,y)else lineTo(x,y)};close()}}
        val leftPath=path("left");val rightPath=path("right")
        val paint=Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
        fun arm(shape:Path):Bitmap {val out=Bitmap.createBitmap(768,768,Bitmap.Config.ARGB_8888);val c=Canvas(out);c.clipPath(shape);c.drawBitmap(image,0f,0f,paint);return out}
        val left=arm(leftPath);val right=arm(rightPath)
        val front=image.copy(Bitmap.Config.ARGB_8888,true);val cut=Canvas(front)
        // Remove the antialiased fringe too: an exact polygon leaves old fingers
        // and sleeve-edge pixels behind when the arm rotates away.
        val clear=Paint(Paint.ANTI_ALIAS_FLAG).apply{style=Paint.Style.FILL_AND_STROKE;strokeWidth=12f;strokeJoin=Paint.Join.ROUND;xfermode=PorterDuffXfermode(PorterDuff.Mode.CLEAR)}
        cut.drawPath(leftPath,clear);cut.drawPath(rightPath,clear)
        val body=Bitmap.createBitmap(768,768,Bitmap.Config.ARGB_8888);val c=Canvas(body)
        val underlay=assets.open("nunti-life-v5/"+rig.getString("underlay")).use{BitmapFactory.decodeStream(it)}
        val hidden=Path().apply{addRect(155f,366f,600f,600f,Path.Direction.CW)}
        for(shape in listOf(leftPath,rightPath)){val edge=Path();clear.getFillPath(shape,edge);hidden.op(edge,Path.Op.UNION)}
        c.save();c.clipPath(hidden);c.drawBitmap(underlay,null,RectF(0f,0f,768f,768f),paint);c.restore()
        c.drawBitmap(front,0f,0f,paint);front.recycle();underlay.recycle()
        fun pivot(key:String)=rig.getJSONArray(key).let{floatArrayOf(it.getDouble(0).toFloat(),it.getDouble(1).toFloat())}
        cache[image]=Parts(body,left,right,pivot("leftPivot"),pivot("rightPivot"),rig.getDouble("leftGain").toFloat(),rig.getDouble("rightGain").toFloat())
    }
}
