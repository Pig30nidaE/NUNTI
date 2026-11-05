#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
CACHE="$ROOT/.local/chatterbox-audition"
mkdir -p "$CACHE"
python3.12 "$ROOT/prototypes/chatterbox_audition/bootstrap.py" source
python3.12 -m venv "$CACHE/venv"
UV_CACHE_DIR="$CACHE/uv-cache" "$ROOT/.local/journey-voice/uv/bin/uv" pip install \
  --python "$CACHE/venv/bin/python" \
  --overrides "$ROOT/prototypes/chatterbox_audition/overrides.txt" "$CACHE/source"
"$ROOT/.local/journey-voice/uv/bin/uv" pip freeze --python "$CACHE/venv/bin/python" \
  > "$ROOT/prototypes/chatterbox_audition/requirements.lock.txt"
