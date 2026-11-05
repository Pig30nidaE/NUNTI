#!/usr/bin/env bash
set -euo pipefail

journey_root="$(cd "$(dirname "$0")/../../../.." && pwd)"
journey_build="${JOURNEY_VISUAL_BUILD_DIR:-$journey_root/.local/journey-visual-check}"
journey_kotlinc="${KOTLINC:-kotlinc}"
if [[ -z "${JAVA_HOME:-}" || ! -x "$JAVA_HOME/bin/java" ]]; then
  echo 'Set JAVA_HOME to JDK 21.' >&2
  exit 2
fi
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p "$journey_build"
"$journey_kotlinc" \
  "$journey_root/android/feature/avatar/src/main/kotlin/ai/nunti/avatar/JourneyVisualSpec.kt" \
  "$journey_root/android/feature/avatar/src/test/kotlin/ai/nunti/avatar/JourneyVisualSpecTestMain.kt" \
  -jvm-target 17 -include-runtime -d "$journey_build/geometry-tests.jar"
java -cp "$journey_build/geometry-tests.jar" ai.nunti.avatar.JourneyVisualSpecTestMain
