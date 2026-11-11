#!/usr/bin/env python3
"""Small, opt-in test of reference-guided image edit. Not wired to app runtime.
Usage: python edit_reference_image.py --reference assets/original.png --prompt-file prompts/skin-coast.txt --output /tmp/coast.png --model gpt-image-2.6-flare --execute
"""
import argparse, base64
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--reference',type=Path,required=True)
p.add_argument('--prompt-file',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--model',choices=['gpt-image-2.6-flare','gpt-image-2.6-sunburst'],default='gpt-image-2.6-flare')
p.add_argument('--execute',action='store_true',help='Opt in to one billable API edit')
a=p.parse_args()
if not a.reference.exists() or not a.prompt_file.exists(): p.error('missing reference or prompt file')
print('Model:',a.model,'Reference:',a.reference,'Output:',a.output)
if not a.execute:
    print('DRY RUN. Add --execute to perform one billable image edit.')
    raise SystemExit(0)
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv('.env.local')
client=OpenAI()
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.reference.open('rb') as f:
    r=client.images.edit(model=a.model,image=f,prompt=a.prompt_file.read_text(encoding='utf-8'),output_format='png',background='transparent',quality='high',size='1024x1024')
if not r.data or not r.data[0].b64_json:
    raise RuntimeError('No base64 PNG output. Inspect response before claiming image generated.')
a.output.write_bytes(base64.b64decode(r.data[0].b64_json))
print('Saved:',a.output,'Usage:',getattr(r,'usage',None))
