package ai.nunti.app.journey

import android.content.res.AssetManager
import android.graphics.*
import kotlin.math.abs
import kotlin.math.sin

/** Face assets and eyelids are rasterized once. No animated hardware clipPath touches the WebView. */
internal class NuntiFaceRig {
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private var source:Bitmap?=null
    private var lids:List<List<Bitmap>> = emptyList()
    fun draw(canvas:Canvas,image:Bitmap,skin:String,expression:Int,amount:Float,blink:Float,gaze:Float=0f) {
        val shift=if(skin=="city"||skin=="mountain")12f else 0f
        val state=canvas.save();canvas.translate(shift,0f)
        patches.firstOrNull()?.let { paint.alpha=255;canvas.drawBitmap(it,244f,148f,paint) }
        if(expression!=0&&amount>.001f)patches.getOrNull(expression)?.let{paint.alpha=(255*amount.coerceIn(0f,1f)).toInt();canvas.drawBitmap(it,244f,148f,paint)}
        paint.alpha=255
        // Laughing and sleepy art already has authored eyelids.
        if(blink>.002f && !(expression in listOf(1,5)&&amount>.3f)) {
            if(source!==image)prepareLids(image,shift.toInt())
            val index=(blink*24).toInt().coerceIn(0,24)
            canvas.drawBitmap(lids[0][index],276f,201f,paint)
            canvas.drawBitmap(lids[1][index],387f,201f,paint)
        }
        canvas.restoreToCount(state)
    }
    private fun prepareLids(image:Bitmap,shift:Int) {
        lids.flatten().forEach{it.recycle()}
        lids=listOf(326,437).map { x -> List(25) { index ->
            val b=index/24f;val result=Bitmap.createBitmap(100,96,Bitmap.Config.ARGB_8888)
            val c=Canvas(result);val p=Paint(Paint.ANTI_ALIAS_FLAG);val path=Path()
            // Software-only clipping during preparation. The live frame draws two ordinary bitmaps.
            path.addOval(RectF(0f,3f,100f,88f),Path.Direction.CW);c.clipPath(path)
            p.shader=LinearGradient(0f,3f,0f,91f,image.getPixel(x+shift,204),image.getPixel(x+shift,299),Shader.TileMode.CLAMP)
            val edge=49+5*b
            path.reset();path.moveTo(-3f,-12f);path.lineTo(103f,-12f);path.lineTo(103f,edge);path.quadTo(50f,-47+86*b,-3f,edge);path.close();c.drawPath(path,p)
            path.reset();path.moveTo(-3f,edge);path.quadTo(50f,139-100*b,103f,edge);path.lineTo(103f,108f);path.lineTo(-3f,108f);path.close();c.drawPath(path,p)
            p.shader=null;p.color=Color.rgb(88,57,43);p.alpha=(((b-.6f)/.4f).coerceIn(0f,1f)*255).toInt();p.style=Paint.Style.STROKE;p.strokeWidth=3.4f;p.strokeCap=Paint.Cap.ROUND
            path.reset();path.moveTo(14f,53f);path.quadTo(50f,39f,86f,53f);c.drawPath(path,p);result
        }}
        source=image
    }
    companion object {
        @Volatile private var patches:List<Bitmap> = emptyList()
        @Synchronized fun prepare(assets:AssetManager) {
            if(patches.isNotEmpty())return
            val atlas=assets.open("nunti-life-v5/expressions.png").use{BitmapFactory.decodeStream(it)}
            require(atlas.width==1536&&atlas.height==1024)
            val scale=111f/157f
            patches=List(6){ index ->
                val out=Bitmap.createBitmap(300,196,Bitmap.Config.ARGB_8888);val c=Canvas(out)
                val matrix=Matrix().apply{setScale(scale,scale);postTranslate(384-278*scale-(index%3)*512*scale-244,249-294*scale-(index/3)*512*scale-148)}
                c.drawBitmap(atlas,matrix,Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG))
                val pixels=IntArray(300*196);out.getPixels(pixels,0,300,0,0,300,196)
                for(y in 0 until 196)for(x in 0 until 300){
                    fun area(l:Float,t:Float,r:Float,b:Float):Float = minOf((x-l)/10f,(r-x)/10f,(y-t)/10f,(b-y)/10f).coerceIn(0f,1f)
                    // Only eyes, brows and mouth. Hood/hair/cheeks always remain the original artwork.
                    val edge=maxOf(area(25f,22f,132f,145f),area(136f,22f,250f,145f),area(95f,116f,187f,186f))
                    val a=(255*edge*edge*(3-2*edge)).toInt();pixels[y*300+x]=(pixels[y*300+x] and 0xffffff) or (a shl 24)
                }
                out.setPixels(pixels,0,300,0,0,300,196);out
            }
            atlas.recycle()
        }
        fun blink(seconds:Float):Float {val t=seconds%5.7f;return if(t in 4.7f..5.04f)sin((t-4.7f)/.34f*Math.PI).toFloat().coerceIn(0f,1f) else 0f}
    }
}
