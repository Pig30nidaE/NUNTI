#!/usr/bin/env python3
"""Create the v2 listening page without altering the v1 page."""
import html
import json
from pathlib import Path
from render_listen import CARDS

HERE = Path(__file__).resolve().parent


def render():
    manifest = json.loads((HERE / "samples-v2/manifest.json").read_text(encoding="utf-8"))
    clips = {c["clipId"]: c for c in manifest["clips"]}
    raw = {c["clipId"]: c for c in manifest["comparisonClips"]}
    cards = []
    for slug, name, journey, trait in CARDS:
        common, greeting, original = clips[slug + "-common"], clips[slug + "-greeting"], raw[slug + "-raw"]
        cards.append(f'''<article><p class="journey">{journey}</p><h2>{name}</h2><p class="trait">{trait}</p><p class="label">작은 목소리로 같은 인사</p><p class="line">{html.escape(common["text"])}</p><audio controls preload="none" src="samples-v2/{common["audioPath"]}"></audio><details><summary>높이를 올리기 전 목소리와 비교</summary><audio controls preload="none" src="samples-v2/{original["audioPath"]}"></audio></details><div class="greeting"><p class="label">이 여정의 인사</p><p class="line">{html.escape(greeting["text"])}</p><audio controls preload="none" src="samples-v2/{greeting["audioPath"]}"></audio></div></article>''')
    source = (HERE / "listen.html").read_text(encoding="utf-8")
    style = source[source.index("<style>"):source.index("</style>") + len("</style>")]
    markup = '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>더 작은 목소리 · Nunti</title>''' + style + '''<style>details{margin-top:12px;font-size:12px;color:#82758a}summary{cursor:pointer;padding:8px 0}details audio{margin-top:8px}.greeting{margin-top:24px;padding-top:18px;border-top:1px solid #eee8e5}</style><header><p class="eyebrow">NUNTI · SMALL VOICE STUDY</p><h1>조금 더 작게, 조금 더 귀엽게.</h1><p class="intro">세 친구의 목소리를 새로 골랐어요. 부드럽게 높인 작은 목소리와 높이기 전 목소리를 비교하고, 각자의 인사도 들어보세요.</p></header><img class="board" src="../../docs/design/journey-characters/concepts/c-luminous-v2.png" alt="왼쪽부터 바다, 숲, 전시에서 태어난 반투명 캐릭터 세 친구"><main class="cards">''' + "".join(cards) + '''</main><footer>새 목소리를 골라 보는 두 번째 시안입니다. <a href="listen.html">첫 목소리와 비교</a></footer></html>'''
    (HERE / "listen-v2.html").write_text(markup, encoding="utf-8")


if __name__ == "__main__":
    render()
