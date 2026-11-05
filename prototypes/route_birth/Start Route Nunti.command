#!/bin/zsh
set -euo pipefail
nunti_root="${0:A:h:h:h}"
cd "$nunti_root"
python3.12 scripts/run_route_birth.py "$@"
echo "\n이 창을 닫아도 PC 생성기와 앱은 계속 실행됩니다."
