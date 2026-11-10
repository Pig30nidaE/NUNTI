#!/usr/bin/env python3
"""Pack already-rendered RGBA PNG frames into an atlas + JSON manifest.

Example:
  python3 tools/vfx_frames_to_atlas.py --input-dir renders/ocean \
      --output app/src/main/assets/vfx/ocean.png --cols 8 --frame-ms 33
This does NOT render Effekseer project files. Install Pillow in a venv.
"""
import argparse, json, math, re
from pathlib import Path
from PIL import Image


def numeric_sort_key(path: Path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', path.name)]


def run():
    p=argparse.ArgumentParser()
    p.add_argument('--input-dir', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--cols', type=int, default=8)
    p.add_argument('--frame-ms', type=int, default=33)
    p.add_argument('--max-edge', type=int, default=4096)
    args=p.parse_args()
    source=Path(args.input_dir)
    files=sorted(source.glob('*.png'),key=numeric_sort_key)
    if not files: raise SystemExit(f'No .png frames in {source}')
    if args.cols<1 or args.frame_ms<1: raise SystemExit('cols and frame-ms must be >0')
    images=[]; width=height=None; any_alpha=False
    for item in files:
        with Image.open(item) as original:
            if original.mode != 'RGBA':
                raise SystemExit(f'Not RGBA: {item.name} ({original.mode}); export TRUE transparent PNG frames first.')
            frame=original.copy()
        if width is None: width,height=frame.size
        if frame.size != (width,height):
            raise SystemExit(f'Frame dimension mismatch at {item.name}: {frame.size} != {(width,height)}')
        lo,hi=frame.getchannel('A').getextrema()
        if lo<255: any_alpha=True
        images.append(frame)
    if not any_alpha: raise SystemExit('All frames fully opaque; likely missing transparency, refusing atlas output.')
    cols=min(args.cols,len(images));rows=math.ceil(len(images)/cols)
    aw,ah=width*cols,height*rows
    if max(aw,ah)>args.max_edge:
        raise SystemExit(f'Atlas {aw}x{ah} exceeds max-edge={args.max_edge}; reduce cols/frame size/count or split atlases.')
    atlas=Image.new('RGBA',(aw,ah),(0,0,0,0))
    for i,frame in enumerate(images): atlas.alpha_composite(frame,((i%cols)*width,(i//cols)*height))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    atlas.save(output)
    manifest={'atlas':output.name,'frame_width':width,'frame_height':height,
       'columns':cols,'rows':rows,'frame_count':len(images),
       'frame_duration_ms':args.frame_ms,'duration_ms':len(images)*args.frame_ms,
       'source_frames':[x.name for x in files], 'mode':'RGBA'}
    meta=output.with_suffix('.json');meta.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{output} + {meta} | frames={len(images)} size={aw}x{ah} duration={manifest["duration_ms"]}ms')

if __name__=='__main__': run()
