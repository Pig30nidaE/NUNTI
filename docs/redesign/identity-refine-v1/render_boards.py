"""Build local review layouts from unchanged source PNGs; no raster retouching.

Run with Python 3. Render the emitted HTML with a browser at the sizes below.
SVG viewports crop only the document presentation; PNG source bytes are embedded intact.
"""

from pathlib import Path
import base64

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT.parents[1] / "design/avatar-v6/assets/nunti-base-character.png"
FILES = {
    "original": REFERENCE,
    "a": ROOT / "nunti-a-sheet-v3.png",
    "b": ROOT / "nunti-b-sheet-v4.png",
    "a-cutout": ROOT / "nunti-a-front-transparent-v1.png",
    "b-cutout": ROOT / "nunti-b-front-transparent-v1.png",
}
SIZES = {"original": (1254, 1254), "a": (1254, 1254), "b": (1254, 1254),
         "a-cutout": (1208, 1302), "b-cutout": (1086, 1448)}
DATA = {key: "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
        for key, p in FILES.items()}
FRONT = {"original": (260, 0, 650, 750), "a": (128, 72, 304, 466), "b": (132, 62, 304, 462)}
CUTOUT = {"a-cutout": (228, 17, 744, 1258), "b-cutout": (132, 13, 802, 1394)}


def crop(key, box, width, height, cls="", label=""):
    vb = " ".join(map(str, box))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="{vb}" class="{cls}" role="img" aria-label="{label or key}">'
            f'<use href="#asset-{key}"/></svg>')


def image_definitions(keys):
    items = ''.join(f'<image id="asset-{key}" href="{DATA[key]}" width="{SIZES[key][0]}" height="{SIZES[key][1]}"/>' for key in keys)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0" style="position:absolute"><defs>{items}</defs></svg>'


STYLE = """
*{box-sizing:border-box}body{margin:0;color:#283e38;font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;background:#f5f4ef}
h1,h2,h3,p{margin:0}h1{font-weight:680;font-size:54px;letter-spacing:-2px}h2{font-size:32px;letter-spacing:-1px}h3{font-size:24px}
.kicker{font-size:18px;letter-spacing:3px;font-weight:650;color:#5f7c70}.muted{color:#62756d}.pill{display:inline-block;font-size:16px;padding:8px 14px;border-radius:40px;background:#d8e8dd;color:#35584b;font-weight:650}
.board{width:2600px;height:2200px;padding:54px 68px 40px}.header{height:142px;display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #cdd6cc}
.header p{font-size:22px;line-height:1.5;margin-top:14px}.meta{text-align:right;font-size:18px;line-height:1.7}.columns{display:grid;grid-template-columns:repeat(3,800px);gap:32px;margin-top:28px}
.column-head{height:74px;display:flex;align-items:flex-start;justify-content:space-between}.column-head small{display:block;font-size:18px;margin-top:7px;color:#667a70}
.hero{height:418px;border-radius:22px;background:#fff;display:flex;align-items:center;justify-content:center;border:1px solid #e0e5de;overflow:hidden}.hero.original{background:#c9e7fa}.hero.a{box-shadow:inset 0 0 0 2px #8cac96}
.intro{height:94px;padding:18px 5px 0;font-size:22px;line-height:1.45}.sheet{width:800px;height:800px;border-radius:18px;border:1px solid #e1e6de;overflow:hidden;background:white}.sheet img{display:block;width:100%;height:100%}
.sheet-caption{height:64px;font-size:18px;line-height:1.45;padding:13px 4px 0}.mini{height:236px;padding:18px 24px;background:#e9ede5;border-radius:18px}.mini h3{font-size:20px}.mini-grid{display:flex;gap:24px;align-items:flex-end;height:168px}.sample{display:flex;align-items:center;flex-direction:column;gap:9px;min-width:102px;font-size:14px;color:#52695b}.tile{background:#fff;border-radius:8px;padding:6px;display:flex;align-items:center;justify-content:center}.tile.dark{background:#293d3a}.silhouette{filter:brightness(0)}
.footer{margin-top:30px;padding:24px 28px;border:1px solid #cad8ca;border-radius:18px;display:grid;grid-template-columns:1.45fr 1fr;gap:56px;background:#edf1e9}.footer strong{font-size:27px}.footer p{font-size:20px;line-height:1.5;margin-top:8px}.footnote{margin-top:16px;display:flex;justify-content:space-between;font-size:15px;color:#6d7c72}
.qa{width:1200px;height:1050px;padding:32px;background:#f4f4ee}.qa h1{font-size:32px;letter-spacing:-1px}.qa .sub{font-size:15px;line-height:1.6;margin-top:9px;color:#5b7065}.qrow{display:flex;gap:24px;align-items:center;background:#e7ece3;border-radius:14px;margin-top:18px;padding:16px;height:204px}.qrow h2{width:95px;font-size:22px}.qrow .sample{min-width:110px;font-size:13px}.expressions{background:#fff;margin-top:20px;border-radius:14px;padding:16px;display:flex;align-items:center;gap:20px;height:136px}.expressions h2{width:140px;font-size:19px}.expr{display:flex;align-items:center;flex-direction:column;gap:7px;font-size:12px;width:100px}.qa-note{margin-top:20px;font-size:16px;line-height:1.65;padding:18px;border:1px solid #c9d5c6;border-radius:12px}
"""


def sample(key, height, text, *, cutout=False, silhouette=False, dark=False):
    box = CUTOUT[key] if cutout else FRONT[key]
    width = round(height * box[2] / box[3])
    art = crop(key, box, width, height, "silhouette" if silhouette else "")
    return f'<div class="sample"><div class="tile {"dark" if dark else ""}">{art}</div><span>{text}</span></div>'


titles = {"original": ("00 / 고정 원화", "기존 기본 눈티 · 원본 이미지 유지"),
          "a": ("A / Matte Form", "매트한 입체감 · 추천 방향"),
          "b": ("B / Soft Graphic", "색면과 유색 윤곽 · 비교 방향")}
intros = {"original": "둥근 후드, 두 새싹, 크림색 앞머리.<br>스카프·가방·파란 경로 배지가 정체성의 기준입니다.",
          "a": "직물 무늬와 주름을 줄이고 부피감을 남겼습니다.<br>원화의 따뜻함과 재질의 정돈이 가장 자연스럽습니다.",
          "b": "넓은 색면과 얇은 윤곽선으로 형태를 정리했습니다.<br>작은 표시에서 외곽과 표정의 경계가 더 또렷합니다."}
captions = {"original": "원본 전체. 상단 전신을 기준으로 고정했습니다. 아래 포즈의 장식 좌우 차이는 새 시안의 기준으로 사용하지 않았습니다.",
            "a": "A v3 · 정면 / 3/4 / 측면 + 기본 / 차분함 / 호기심 / 걱정 / 놀람 / 안도 / 기쁨",
            "b": "B v4 · 3/4 회전, 안도·호기심 표정과 배지 곡선을 보정했습니다. 각도는 제작용 정투영 도면이 아닙니다."}
cols = []
for key in ("original", "a", "b"):
    name, subtitle = titles[key]
    badge = '<span class="pill">RECOMMENDED</span>' if key == "a" else ""
    box = FRONT[key]
    hero = crop(key, box, round(396*box[2]/box[3]), 396)
    crop_label = "원본 크롭" if key == "original" else "시트 크롭"
    minis = sample(key, 128, crop_label + " · 높이 128 px") + sample(key, 64, crop_label + " · 높이 64 px")
    if key != "original":
        minis += sample(key+"-cutout", 64, "추출 시안 · 어두운 배경", cutout=True, dark=True)
        minis += sample(key+"-cutout", 64, "추출 시안 · 실루엣", cutout=True, silhouette=True)
    else:
        minis += '<p class="muted" style="font-size:16px;line-height:1.5;width:220px;margin-bottom:30px">높이를 맞춘 원본 크롭.<br>배경·자세는 원화 그대로입니다.</p>'
    cols.append(f'''<section><div class="column-head"><div><h2>{name}</h2><small>{subtitle}</small></div>{badge}</div>
      <div class="hero {key}">{hero}</div><p class="intro">{intros[key]}</p>
      <div class="sheet">{crop(key,(0,0,1254,1254),800,800,label=name+' 전체 시트')}</div><p class="sheet-caption">{captions[key]}</p>
      <div class="mini"><h3>Small-size check · 실제 픽셀 크기</h3><div class="mini-grid">{minis}</div></div></section>''')

board = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>Nunti identity refinement comparison</title><style>{STYLE}</style>{image_definitions(FILES)}
<main class="board"><header class="header"><div><div class="kicker">NUNTI · IDENTITY REFINEMENT 01</div><h1>같은 눈티, 더 정돈된 인상</h1><p>고정 원화와 두 가지 리파인 방향 · 정면 / 3/4 / 측면 · 기본 표정 + 감정 6종</p></div>
<div class="meta">2026.11.09<br>CONCEPT REVIEW · 선택 전 시안<br>기준 파일 SHA-256<br><span style="font-family:monospace">d655e819c2f8…47c293f</span></div></header>
<div class="columns">{''.join(cols)}</div><footer class="footer"><div><strong>A를 추천합니다.</strong><p>둥근 후드의 두께와 눈의 깊이가 원화와 이어지고, 질감을 덜어낸 만큼 얼굴이 먼저 보입니다.<br>B는 작은 아이콘의 윤곽 표현을 검토할 때 참고할 가치가 있습니다.</p></div>
<div><strong>64 px에서는 정체성, 표정은 별도 검토</strong><p>새싹·후드·갈색 눈은 유지됩니다. 배지의 내부 선과 미세한 감정 차이는 충분히 읽히지 않습니다.<br>투명 추출물은 외곽 정리가 필요하며, 모두 승인 전 래스터 시안입니다.</p></div></footer>
<div class="footnote"><span>원본·시트 이미지를 그대로 배치한 비교 문서 · 이미지 생성 9회 · 별도 API 키 기반 호출 0회</span><span>100% 확대에서 px 크기 비교 · 브라우저 배치용 HTML 함께 저장</span></div></main></html>'''
(ROOT / "comparison-board.html").write_text(board)

qrows = []
for key in ("a", "b"):
    samples = sample(key, 128, "시트 크롭 H128") + sample(key, 64, "시트 크롭 H64")
    samples += sample(key+"-cutout", 128, "추출물 H128 · 밝음", cutout=True)
    samples += sample(key+"-cutout", 128, "추출물 H128 · 어두움", cutout=True, dark=True)
    samples += sample(key+"-cutout", 64, "추출물 H64", cutout=True, dark=True)
    samples += sample(key+"-cutout", 64, "실루엣 H64", cutout=True, silhouette=True)
    qrows.append(f'<section class="qrow"><h2>{key.upper()}</h2>{samples}</section>')

expressions = {
    "a": [(84,596,234,242),(373,596,234,242),(651,596,234,242),(927,596,238,242),
          (196,883,240,242),(508,883,236,242),(815,883,240,242)],
    "b": [(69,587,245,252),(359,587,249,252),(639,587,246,252),(928,587,250,252),
          (195,878,251,258),(505,878,251,258),(816,878,254,258)],
}
names = ["기본", "차분함", "호기심", "걱정", "놀람", "안도", "기쁨"]
erows = []
for key, boxes in expressions.items():
    cells = ''.join(f'<div class="expr">{crop(key,box,64,64)}<span>{name}</span></div>' for box,name in zip(boxes,names))
    erows.append(f'<section class="expressions"><h2>{key.upper()} 표정<br><span class="muted">64 × 64 px</span></h2>{cells}</section>')
qa = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>Nunti 64 and 128 pixel review</title><style>{STYLE}</style>{image_definitions(['a','b','a-cutout','b-cutout'])}
<main class="qa"><h1>눈티 A/B · 64 px / 128 px 확인</h1><p class="sub">PNG를 100% 배율로 확인합니다. H64는 전신 표시 영역의 높이 64px입니다. 표정은 64×64px 뷰포트입니다.<br>시트 크롭은 생성 시트의 실제 픽셀을 표시하고, 투명 추출물은 별도로 생성한 파생 시안입니다. 화면 배율·전시 환경의 영향은 미검증입니다.</p>
{''.join(qrows)}{''.join(erows)}<p class="qa-note"><strong>관찰 기준</strong> · 새싹 두 갈래 / 후드와 얼굴 경계 / 눈·입의 구분 / 밝고 어두운 배경의 외곽 / 표정 간 차이<br>A v3 / B v4 · 호기심의 눈썹·시선을 보강하고 B 안도를 닫힌 미소로 바꿨습니다. 표정의 의미 전달은 사용자 검증이 필요합니다.<br>실루엣은 투명 파생 PNG에 브라우저의 검정색 표시 필터를 적용했습니다. PNG 원본 데이터는 수정하지 않았습니다.</p></main></html>'''
(ROOT / "small-size-review.html").write_text(qa)
print("Wrote comparison-board.html (2600×2200) and small-size-review.html (1200×1050)")
