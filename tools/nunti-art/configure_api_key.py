#!/usr/bin/env python3
"""Store an OpenAI key locally without printing it. Run from the existing project root."""
from pathlib import Path
from getpass import GetPassWarning, getpass
import os
import warnings

root=Path.cwd()
ignore=root/'.gitignore'
existing=ignore.read_text(encoding='utf-8') if ignore.exists() else ''
if '.env.local' not in existing.splitlines():
    ignore.write_text(existing.rstrip()+('\n' if existing.strip() else '')+'.env.local\n',encoding='utf-8')
with warnings.catch_warnings():
    warnings.simplefilter('error', GetPassWarning)
    try:
        secret = getpass('OpenAI API key (input hidden): ').strip()
    except GetPassWarning:
        raise SystemExit('Hidden input is unavailable. Run this script in a local terminal.') from None
if not secret.startswith('sk-'):
    raise SystemExit('API key does not look like a typical OpenAI key. No file saved.')
path=root/'.env.local'
lines=[]
if path.exists():
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('OPENAI_API_KEY='):
            lines.append(line)
lines.append('OPENAI_API_KEY='+secret)
fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w',encoding='utf-8') as f: f.write('\n'.join(lines)+'\n')
os.chmod(path,0o600)
print('Saved API key in ignored local file .env.local (0600). Do not commit this file.')
