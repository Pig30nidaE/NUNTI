#!/usr/bin/env python3
"""Build a file:// friendly listening page from the actual audio manifest."""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARDS = [("coast", "파도빛", "바다를 만나러 떠나는 날", "차분한 동행"), ("mountain", "이끼별", "숲으로 떠나는 날", "작은 탐험가"), ("city", "조각빛", "전시를 만나러 떠나는 날", "색을 발견하는 친구")]


def render(manifest_path=HERE / "samples/manifest.json", output=HERE / "listen.html"):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    clips = {clip["clipId"]: clip for clip in manifest["clips"]}
    cards = []
    for slug, name, journey, trait in CARDS:
        tracks = []
        for category, label in (("common", "같은 문장으로 비교"), ("greeting", "이 여정의 인사")):
            clip = clips[slug + "-" + category]
            relative = str(Path(manifest_path).parent.relative_to(Path(output).parent) / clip["audioPath"])
            tracks.append(f'<div class="track"><p class="label">{label}</p><p class="line">{html.escape(clip["text"])}</p><audio controls preload="none" src="{html.escape(relative, quote=True)}"></audio></div>')
        cards.append(f'<article><p class="journey">{journey}</p><h2>{name}</h2><p class="trait">{trait}</p>{"".join(tracks)}</article>')
    markup = '''<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>여정의 작은 목소리 · Nunti</title>
<style>
:root{color-scheme:light;font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;background:#f7f4ef;color:#302d3b}body{margin:0 auto;max-width:1140px;padding:42px 24px 64px}header{max-width:710px}h1{font-size:32px;line-height:1.35;margin:8px 0 14px;font-weight:750;letter-spacing:-1.3px}p{line-height:1.7}.intro{color:#67616e}.eyebrow{font-size:12px;letter-spacing:2px;color:#82758a}.board{width:100%;border-radius:24px;display:block;margin:28px 0}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}article{background:#fffdfa;border:1px solid #e8e0e2;border-radius:22px;padding:24px 20px}.journey{color:#82758a;font-size:13px;margin:0}h2{margin:10px 0 2px;font-size:23px}.trait{margin:0 0 22px;color:#82758a;font-size:14px}.track+.track{margin-top:25px;padding-top:20px;border-top:1px solid #eee8e5}.label{font-size:12px;font-weight:650;color:#62526e;margin:0 0 8px}.line{font-size:14px;min-height:70px;margin:0 0 10px}audio{width:100%;height:42px}footer{font-size:13px;color:#82758a;margin-top:25px}@media(max-width:760px){.cards{grid-template-columns:1fr}h1{font-size:28px}.line{min-height:0}body{padding:26px 16px}}
</style>
<header><p class="eyebrow">NUNTI · JOURNEY KEEPSAKES</p><h1>여정마다, 다른 작은 목소리.</h1><p class="intro">바다와 숲, 전시로 향하는 세 친구의 목소리를 들어보세요. 먼저 같은 문장으로 비교하고, 각자의 인사를 이어서 들을 수 있어요.</p></header>
<img class="board" src="../../docs/design/journey-characters/concepts/c-luminous-v2.png" alt="왼쪽부터 바다, 숲, 전시에서 태어난 반투명 캐릭터 세 친구">
<main class="cards">''' + "".join(cards) + '''</main><footer>목소리를 골라 보는 첫 시안입니다. 출발 전에 편안한 음량으로 비교해주세요.</footer></html>'''
    Path(output).write_text(markup, encoding="utf-8")


if __name__ == "__main__":
    render()
