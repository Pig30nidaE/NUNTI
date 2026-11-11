#!/usr/bin/env python3
"""Register generated cutouts, preserve alpha, split local animation plates, and hash every export.

This is asset packaging only. It does not generate, recolor, repair or redraw the artwork.
"""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/nunti-atelier-v3/sources'
OUTPUT = ROOT / 'prototypes/avatar_generator/skin-v2/atelier'


def package(skin: str) -> dict:
    path = SOURCE / f'{skin}.png'
    with Image.open(path) as source:
        if source.mode != 'RGBA':
            raise ValueError(f'{skin}: genuine alpha required')
        # Measure the solid silhouette only; the source alpha itself remains untouched.
        bounds = source.getchannel('A').point(lambda value: 255 if value >= 128 else 0).getbbox()
        if bounds is None or source.getchannel('A').getextrema() != (0, 255):
            raise ValueError(f'{skin}: missing transparent cutout')
        x0, y0, x1, y1 = bounds
        scale = min(674 / (y1 - y0), 580 / (x1 - x0))
        # Uniform scale preserves facial/body proportions, with all feet at y=721.
        width, height = round(source.width * scale), round(source.height * scale)
        registered = Image.new('RGBA', (768, 768))
        resized = source.resize((width, height), Image.Resampling.LANCZOS)
        left = round(384 - (x0 + x1) * scale / 2)
        top = round(721 - y1 * scale)
        registered.alpha_composite(resized, (left, top))
    head = Image.new('L', (768, 768)); ImageDraw.Draw(head).rectangle((0, 0, 767, 369), fill=255)
    face = Image.new('L', (768, 768)); ImageDraw.Draw(face).rectangle((250, 180, 520, 339), fill=255)
    head = ImageChops.subtract(head, face)
    body = ImageChops.invert(ImageChops.lighter(head, face))
    accessory = Image.new('L', (768, 768))
    # Independent local costume plate. No hidden limbs or 3D geometry are invented.
    ImageDraw.Draw(accessory).rectangle((295, 465, 470, 570), fill=255)
    accessory = ImageChops.multiply(accessory, body)
    masks = {'head': head, 'eyes': face, 'outfit': ImageChops.subtract(body, accessory), 'accessory': accessory}
    transparent = Image.new('RGBA', (768, 768))
    plates = {name: Image.composite(registered, transparent, mask) for name, mask in masks.items()}
    assembled = Image.new('RGBA', (768, 768))
    for plate in plates.values():
        assembled.alpha_composite(plate)
    if assembled.tobytes() != registered.tobytes():
        raise ValueError(f'{skin}: animation plates must reconstruct the final image exactly')
    directory = OUTPUT / skin; directory.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for name, image in {'final': registered, **plates}.items():
        target = directory / f'{name}.png'; image.save(target, optimize=True)
        raw = target.read_bytes()
        metadata[name] = {'path': str(target.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return {'source': str(path.relative_to(ROOT)), 'sourceSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'sourceBounds': bounds, 'scale': scale, 'offset': [left, top], 'files': metadata}


def main():
    manifest = {'version': 'skin-v2.2', 'owner': 'NUNTI', 'status': 'IMPLEMENTATION_CANDIDATE',
        'tool': 'OpenAI built-in imagegen', 'generation': 'offline development assets, no per-drive generation',
        'identityReference': 'docs/redesign/identity-refine-v1/nunti-a-front-transparent-v1.png',
        'directionReference': 'artifacts/nunti-atelier-v3/concepts/directions.png',
        'licensingNote': 'Original Nunti reference-guided generated artwork. No third-party mascot assets.',
        'export': '768x768 RGBA PNG, uniform Lanczos scaling, source alpha preserved, binary local plate partition',
        'fallback': '/skin-v2/default/final.png', 'skins': {skin: package(skin) for skin in ['sea', 'city', 'mountain']}}
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'version': manifest['version'], 'skins': list(manifest['skins']), 'exactPlateRecomposition': True}))


if __name__ == '__main__':
    main()
