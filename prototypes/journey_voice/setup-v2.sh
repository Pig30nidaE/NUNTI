#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd "$(dirname "$0")/../.." && pwd)"
task_tools="$task_root/.local/journey-voice"
export UV_CACHE_DIR="$task_tools/uv-cache"
export UV_PYTHON_INSTALL_DIR="$task_tools/python"
export PIP_CACHE_DIR="$task_tools/pip-cache"
bash "$task_root/prototypes/journey_voice/setup.sh"
if [ ! -x "$task_tools/venv-v2/bin/python" ]; then
  "$task_tools/uv/bin/uv" venv --python 3.12.12 --managed-python "$task_tools/venv-v2"
fi
"$task_tools/uv/bin/uv" pip install --only-binary=:all: --python "$task_tools/venv-v2/bin/python" --requirement "$task_root/prototypes/journey_voice/requirements-v2.lock.txt"
"$task_tools/venv-v2/bin/python" "$task_root/prototypes/journey_voice/download_models_v2.py"
