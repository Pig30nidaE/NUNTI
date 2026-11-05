#!/bin/zsh
set -euo pipefail
nunti_root="${0:A:h:h:h}"
cd "$nunti_root"
python3.12 scripts/run_journey_mvp.py "$@"
echo "\n이 창은 닫아도 앱은 계속 실행됩니다."
