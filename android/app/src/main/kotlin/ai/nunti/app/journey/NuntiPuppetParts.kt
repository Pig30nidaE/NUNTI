package ai.nunti.app.journey

import android.content.res.AssetManager
import android.graphics.*
import org.json.JSONObject
import java.util.WeakHashMap

/** Worker-prepared limb layers. Only legacy rigs use generated underlays. */
internal object NuntiPuppetParts {
    class Parts(val body:Bitmap,val left:Bitmap,val right:Bitmap,val leftPivot:FloatArray,val rightPivot:FloatArray,val leftGain:Float,val rightGain:Float,
        val leftX:Float=0f,val leftY:Float=0f,val rightX:Float=0f,val rightY:Float=0f)
    private val cache=WeakHashMap<Bitmap,Parts>()
    @Synchronized fun get(image:Bitmap)=cache[image]
    @Synchronized fun prepareShared(image: Bitmap) {
        if (cache.containsKey(image)) return
        require(image.width == 768 && image.height == 768)
        val leftPath = Path().apply {
            moveTo(292f, 410f)
            cubicTo(240f, 413f, 180f, 455f, 170f, 510f)
            lineTo(170f, 580f); lineTo(244f, 580f); lineTo(248f, 545f)
            lineTo(246f, 529f)
            cubicTo(246f, 516f, 265f, 507f, 281f, 503f)
            cubicTo(289f, 480f, 300f, 451f, 316f, 425f)
            lineTo(308f, 416f); close()
        }
        val rightPath = Path(leftPath).apply { transform(Matrix().apply { setScale(-1f,1f); postTranslate(768f,0f) }) }
        val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
        fun arm(path: Path): Pair<Bitmap,Rect> {
            val bounds = RectF(); path.computeBounds(bounds, true)
            val rect = Rect(); bounds.roundOut(rect)
            val result = Bitmap.createBitmap(rect.width(), rect.height(), Bitmap.Config.ARGB_8888)
            Canvas(result).apply { translate(-rect.left.toFloat(),-rect.top.toFloat()); clipPath(path); drawBitmap(image,0f,0f,paint) }
            return result to rect
        }
        val (left,leftRect) = arm(leftPath); val (right,rightRect) = arm(rightPath)
        val front = image.copy(Bitmap.Config.ARGB_8888,true)
        val clear = Paint(Paint.ANTI_ALIAS_FLAG).apply { xfermode=PorterDuffXfermode(PorterDuff.Mode.CLEAR) }
        Canvas(front).apply { drawPath(leftPath,clear); drawPath(rightPath,clear) }
        val body = Bitmap.createBitmap(768,768,Bitmap.Config.ARGB_8888)
        val canvas = Canvas(body)
        // A registered side panel extends visible coat fabric into the area uncovered by the arm.
        // It is a local 2D construction, not recovered anatomy or a generated hidden surface.
        fun sidePanel(mirror: Boolean) {
            val saved = canvas.save()
            if (mirror) { canvas.translate(768f, 0f); canvas.scale(-1f, 1f) }
            val shape = Path().apply {
                moveTo(285f, 399f); cubicTo(271f, 414f, 263f, 442f, 257f, 476f)
                cubicTo(251f, 510f, 255f, 549f, 272f, 578f)
                lineTo(322f, 578f); lineTo(322f, 407f); close()
            }
            canvas.clipPath(shape)
            val source = if (mirror) Rect(472, 440, 482, 490) else Rect(286, 440, 296, 490)
            canvas.drawBitmap(image, source, RectF(250f, 399f, 324f, 581f), paint)
            canvas.restoreToCount(saved)
        }
        sidePanel(false)
        sidePanel(true)
        canvas.drawBitmap(front,0f,0f,paint); front.recycle()
        cache[image]=Parts(body,left,right,floatArrayOf(287f,414f),floatArrayOf(488f,414f),1f,1f,
            leftRect.left.toFloat(),leftRect.top.toFloat(),rightRect.left.toFloat(),rightRect.top.toFloat())
    }
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
