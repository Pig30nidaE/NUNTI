#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/../.." && pwd)"
task_tools="$task_root/.local/journey-voice"
export UV_CACHE_DIR="$task_tools/uv-cache"
export UV_PYTHON_INSTALL_DIR="$task_tools/python"
export PIP_CACHE_DIR="$task_tools/pip-cache"
mkdir -p "$task_tools"
if [ ! -x "$task_tools/uv/bin/uv" ]; then
  python3 -m pip install --disable-pip-version-check --only-binary=:all: --target "$task_tools/uv" uv==0.9.7
fi
if [ ! -x "$task_tools/venv/bin/python" ]; then
  "$task_tools/uv/bin/uv" venv --python 3.12.12 --managed-python "$task_tools/venv"
fi
"$task_tools/uv/bin/uv" pip install --only-binary=:all: --python "$task_tools/venv/bin/python" --requirement "$task_root/prototypes/journey_voice/requirements.lock.txt"
"$task_tools/venv/bin/python" "$task_root/prototypes/journey_voice/download_models.py"
