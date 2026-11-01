package ai.nunti.avatar

import ai.nunti.navigation.RouteSnapshot
import ai.nunti.emotion.Emotion
import java.awt.BasicStroke
import java.awt.Color
import java.awt.Font
import java.awt.RenderingHints
import java.awt.geom.Ellipse2D
import java.awt.geom.Path2D
import java.awt.geom.RoundRectangle2D
import java.awt.image.BufferedImage
import javax.imageio.ImageIO
import java.io.File

/** Test-only raster backend, sharing the exact scene consumed by Compose and SVG. */
fun renderPng(scene: CharacterScene, width: Int, height: Int): BufferedImage {
    val image = BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB)
    val g = image.createGraphics()
    g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
    val scale = minOf(width, height) / 320.0
    g.translate((width - 320 * scale) / 2, (height - 320 * scale) / 2)
    g.scale(scale, scale)
    scene.primitives.forEach { p ->
        g.color = Color.decode(p.color)
        val b = p.bounds
        when (p.kind) {
            PrimitiveKind.ELLIPSE -> g.fill(Ellipse2D.Double(b.x, b.y, b.width, b.height))
            PrimitiveKind.RECT -> g.fill(RoundRectangle2D.Double(b.x, b.y, b.width, b.height, 10.0, 10.0))
            else -> {
                val path = Path2D.Double()
                p.points.forEachIndexed { i, point -> if (i == 0) path.moveTo(point.x, point.y) else path.lineTo(point.x, point.y) }
                g.stroke = BasicStroke(p.strokeWidth.toFloat(), BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND)
                g.draw(path)
            }
        }
    }
    g.dispose()
    return image
}

fun generateVisualDemo(engine: AvatarEngine, routes: List<RouteSnapshot>, renderer: CharacterRenderer,
    parked: PlatformDisplayPolicy, out: File) {
    val specs = routes.map { engine.generate(it, 42).avatar }
    val timeline = MockEmotionTimeline.run(specs[0].avatarId)
    val wire = V1WireAdapter(SourceRegistry(emptyMap(), true))
    File(out, "emotion-timeline.json").writeText(org.json.JSONArray(timeline.map {
        org.json.JSONObject(wire.emotion(it.snapshot, MockRoutes.EPOCH))
    }).toString(2))
    val sheet = BufferedImage(1280, 820, BufferedImage.TYPE_INT_RGB)
    val g = sheet.createGraphics()
    g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
    g.color = Color.decode("#F5F2E9"); g.fillRect(0, 0, 1280, 820)
    g.color = Color.decode("#283B3C"); g.font = Font("SansSerif", Font.BOLD, 30)
    g.drawString("NUNTI  /  ONE COMPANION, FOUR JOURNEYS", 36, 53)
    g.font = Font("SansSerif", Font.PLAIN, 16); g.drawString("MOCK ROUTES  ·  SHARED IDENTITY  ·  EVIDENCE-BASED PARTS  ·  STATIC MVP", 36, 84)
    val cards = specs.mapIndexed { i, spec ->
        val scene = renderer.scene(spec, RenderPolicy.resolve(TripPhase.PRE_DRIVE, Emotion.NEUTRAL, parked, 0))
        g.color = Color.WHITE; g.fillRoundRect(i * 312 + 20, 110, 300, 350, 22, 22)
        g.drawImage(renderPng(scene, 280, 280), i * 312 + 30, 120, null)
        g.color = Color.decode("#283B3C"); g.font = Font("SansSerif", Font.BOLD, 17)
        g.drawString(spec.journey.themeId.name, i * 312 + 43, 424)
        File(out, "${spec.routeId}.svg").writeText(scene.toSvg())
        "<article><span class=eyebrow>MOCK ${('A'.code + i).toChar()}</span>${scene.toSvg()}<h2>${spec.journey.themeId}</h2><p>${xmlEscape(spec.generationExplanation)}</p><details><summary>선택 근거와 후보 점수</summary><pre>${xmlEscape(spec.candidates.joinToString("\n") { "${it.journey.themeId}: ${it.score.total} · ${it.reason}" })}</pre></details></article>"
    }
    g.color = Color.decode("#283B3C"); g.font = Font("SansSerif", Font.BOLD, 22); g.drawString("EMOTION PARTS  /  INTERNAL STATE IS SEPARATE FROM DRIVING DISPLAY", 36, 516)
    val faces = Emotion.entries.mapIndexed { i, emotion ->
        val scene = renderer.scene(specs[0], RenderPolicy.resolve(TripPhase.POST_DRIVE, emotion, parked, 0))
        g.drawImage(renderPng(scene, 200, 200), 13 + i * 210, 537, null)
        g.color = Color.decode("#283B3C"); g.font = Font("SansSerif", Font.BOLD, 13); g.drawString(emotion.name, 53 + i * 210, 761)
        File(out, "emotion-${emotion.name.lowercase()}.svg").writeText(scene.toSvg())
        "<article>${scene.toSvg()}<h3>${emotion.name}</h3></article>"
    }
    g.dispose(); ImageIO.write(sheet, "png", File(out, "nunti-contact-sheet.png"))
    File(out, "demo.html").writeText("""<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nunti · 경로 생성 검증</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f5f2e9;color:#283b3c;font:16px/1.65 system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:36px}h1{font-size:clamp(28px,4vw,48px);margin:8px 0}h2{margin:0}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.14em;color:#657672}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}article{border:1px solid #deded3;border-radius:20px;padding:24px;background:white}article svg{display:block;width:100%;height:auto;max-height:280px}p{color:#536360}pre{font:12px/1.7 monospace;white-space:pre-wrap;overflow-wrap:anywhere}button{font:inherit;padding:9px 16px;border-radius:12px;border:1px solid #b8c3bd;background:white;cursor:pointer}button[aria-pressed=true]{background:#283b3c;color:white}.phase{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0}.notice{padding:20px;background:#e5ebdf;border-radius:15px;margin:20px 0}.faces{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}[hidden]{display:none!important}footer{font-size:13px;margin-top:30px}</style>
<main><span class="eyebrow">NUNTI / ALGORITHM WORKBENCH</span><h1>같은 눈티, 경로에 맞춘 준비.</h1><p>모든 경로는 합성 Mock입니다. 아래 그림은 실제 Kotlin 엔진의 AvatarSpec과 공통 렌더링 명령에서 생성했습니다.</p>
<div class="phase" aria-label="시연 단계"><button data-phase="pre" aria-pressed="true">출발 전</button><button data-phase="drive" aria-pressed="false">주행 중 · 제한</button><button data-phase="post" aria-pressed="false">주행 종료</button></div>
<div id="blocked" class="notice" hidden>플랫폼 표시 허가가 확인되지 않아 아바타 화면을 숨겼습니다. 감정은 내부 타임라인에만 기록합니다.</div>
<section id="pre"><div class="grid">${cards.joinToString("")}</div></section>
<section id="post" hidden><div class="notice">시연 D · 평온 → 놀람 → 안도 → 평온. 실제 reducer로 검증된 급제동과 회복 이벤트를 처리한 Mock 결과입니다.<ol>${timeline.joinToString("") { "<li>${it.now / 1000}초 · ${it.snapshot.emotion} · ${it.snapshot.reason}</li>" }}</ol><button id="replay">감정 흐름 재생</button><p id="replay-status" aria-live="polite"></p></div><div class="grid faces">${faces.joinToString("")}</div></section>
<footer>이 페이지는 로컬 검증용 정적 결과 뷰어입니다. 주행 허용 여부를 모의한 UI이며 차량 플랫폼 인증 또는 실도로 검증을 뜻하지 않습니다. 생성 규칙·가중치·감정 시간은 초기 실험 설정입니다.</footer></main>
<script>let timer;const cards=[...document.querySelectorAll('.faces article')];function stop(){clearInterval(timer);cards.forEach(x=>x.hidden=false)}document.querySelectorAll('[data-phase]').forEach(b=>b.addEventListener('click',()=>{stop();document.querySelectorAll('[data-phase]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.getElementById('pre').hidden=b.dataset.phase!=='pre';document.getElementById('post').hidden=b.dataset.phase!=='post';document.getElementById('blocked').hidden=b.dataset.phase!=='drive'}));document.getElementById('replay').onclick=()=>{stop();const frames=${org.json.JSONArray(timeline.map { it.snapshot.emotion.name })};let index=0;function step(){const current=frames[index];cards.forEach(c=>c.hidden=c.querySelector('h3').textContent!==current);document.getElementById('replay-status').textContent=(index*3)+'초 · '+current;index++;if(index===frames.length)clearInterval(timer)}step();timer=setInterval(step,3000)};</script></html>""")
}
