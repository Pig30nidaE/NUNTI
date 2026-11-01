#!/usr/bin/env bash
set -euo pipefail
avatar_root="$(cd "$(dirname "$0")/../../../.." && pwd)"
avatar_module="$avatar_root/android/feature/avatar"
avatar_build="${AVATAR_BUILD_DIR:-$avatar_module/build}"
avatar_kotlinc="${KOTLINC:-kotlinc}"
avatar_json="${JSON_JAR:-$avatar_build/deps/json-20250517.jar}"
mkdir -p "$avatar_build/deps" "$avatar_build/reports"
if ! command -v "$avatar_kotlinc" >/dev/null; then
  echo 'Kotlin 2.2.21+ compiler required. Set KOTLINC to the official kotlinc executable.' >&2
  exit 2
fi
if [[ ! -f "$avatar_json" ]]; then
  curl --fail --location --retry 2 https://repo.maven.apache.org/maven2/org/json/json/20250517/json-20250517.jar -o "$avatar_json"
fi
"$avatar_kotlinc" "$avatar_root/android/feature/navigation/src/main/kotlin" \
  "$avatar_root/android/feature/emotion/src/main/kotlin" "$avatar_module/src/main/kotlin" \
  "$avatar_module/src/test/kotlin" -jvm-target 17 -classpath "$avatar_json" -include-runtime -d "$avatar_build/avatar-tests.jar"
jar uf "$avatar_build/avatar-tests.jar" -C "$avatar_module/src/main/resources" .
java -Djava.awt.headless=true -cp "$avatar_build/avatar-tests.jar:$avatar_json" ai.nunti.avatar.AvatarTestMainKt "$avatar_build/reports" "${CONTRACT_ROOT:-$avatar_root/contracts/v1}"
