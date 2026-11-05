#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/../.." && pwd)"
task_tools="$task_root/.local/journey-voice-v3"
task_uv="${NUNTI_UV:-$task_root/.local/journey-voice/uv/bin/uv}"
task_python="${NUNTI_PYTHON:-$task_root/.local/journey-voice/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12}"
export UV_CACHE_DIR="$task_tools/uv-cache"
export HF_HOME="$task_tools/hf"
export HF_HUB_DISABLE_TELEMETRY=1
if [ ! -x "$task_uv" ] || [ ! -x "$task_python" ]; then
  echo 'Set NUNTI_UV to a uv executable and NUNTI_PYTHON to Python 3.12.12.' >&2
  exit 1
fi
mkdir -p "$task_tools"
if [ ! -x "$task_tools/venv/bin/python" ]; then
  "$task_uv" venv --python "$task_python" "$task_tools/venv"
fi
"$task_uv" pip install --python "$task_tools/venv/bin/python" --requirement "$task_root/prototypes/journey_voice_v3/requirements.lock.txt"
"$task_tools/venv/bin/python" "$task_root/prototypes/journey_voice_v3/download_model.py"
