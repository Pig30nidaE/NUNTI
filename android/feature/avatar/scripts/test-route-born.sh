#!/usr/bin/env bash
set -euo pipefail
route_born_root="$(cd "$(dirname "$0")/../../../.." && pwd)"
route_born_build="${ROUTE_BORN_BUILD_DIR:-$route_born_root/.local/route-born-avatar}"
route_born_kotlinc="${KOTLINC:-kotlinc}"
if [[ -z "${JAVA_HOME:-}" || ! -x "$JAVA_HOME/bin/java" ]]; then
  echo 'Set JAVA_HOME to JDK 21.' >&2
  exit 2
fi
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p "$route_born_build"
"$route_born_kotlinc" \
  "$route_born_root/android/feature/avatar/src/main/kotlin/ai/nunti/avatar/RouteBornSpec.kt" \
  "$route_born_root/android/feature/avatar/src/test/kotlin/ai/nunti/avatar/RouteBornGeometryTestMain.kt" \
  -jvm-target 17 -include-runtime -d "$route_born_build/geometry-tests.jar"
java -Djava.awt.headless=true -cp "$route_born_build/geometry-tests.jar" \
  ai.nunti.avatar.RouteBornGeometryTestMain "$route_born_build/design-variants.png"
