#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/../../.." && pwd)"
task_tools="$task_root/.local/voice-audition-asr"
task_uv="${NUNTI_UV:-$task_root/.local/journey-voice/uv/bin/uv}"
task_python="${NUNTI_PYTHON:-$task_root/.local/journey-voice/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12}"
export UV_CACHE_DIR="$task_tools/uv-cache"
mkdir -p "$task_tools"
if [ ! -x "$task_tools/venv/bin/python" ]; then
  "$task_uv" venv --python "$task_python" "$task_tools/venv"
fi
"$task_uv" pip install --python "$task_tools/venv/bin/python" --requirement "$task_root/prototypes/voice_audition/asr/requirements.lock.txt"
"$task_tools/venv/bin/python" "$task_root/prototypes/voice_audition/asr/download.py"
