#!/usr/bin/env bash
set -euo pipefail
generated_root="$(cd "$(dirname "$0")/../../../.." && pwd)"
generated_build="${GENERATED_AVATAR_BUILD_DIR:-$generated_root/.local/generated-avatar}"
generated_kotlinc="${KOTLINC:-kotlinc}"
generated_java_home="${JAVA_HOME:-$generated_root/.local/tts-tools/jdk/jdk-21.0.8+9/Contents/Home}"
if [[ ! -x "$generated_java_home/bin/java" ]]; then
  echo 'Set JAVA_HOME to the existing JDK.' >&2
  exit 2
fi
export PATH="$generated_java_home/bin:$PATH"
mkdir -p "$generated_build"
generated_sources=(
  "$generated_root/android/feature/avatar/src/main/kotlin/ai/nunti/avatar/GeneratedCompanionSpec.kt"
  "$generated_root/android/feature/avatar/src/main/kotlin/ai/nunti/avatar/GeneratedFormationSpec.kt"
  "$generated_root/android/feature/avatar/src/test/kotlin/ai/nunti/avatar/GeneratedCompanionTestMain.kt"
)
generated_runtime="$generated_build/contract-tests.jar"
if command -v "$generated_kotlinc" >/dev/null; then
  "$generated_kotlinc" "${generated_sources[@]}" -jvm-target 17 -include-runtime -d "$generated_runtime"
else
  # Reuse the restored compiler. No SDK install, network access, or dependency download.
  generated_artifacts="$generated_root/.local/tts-tools/artifacts"
  generated_stdlib="$generated_artifacts/kotlin-stdlib-2.2.20.jar"
  java -cp "$generated_artifacts/*" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler \
    "${generated_sources[@]}" -jvm-target 17 -no-stdlib -no-reflect \
    -classpath "$generated_stdlib:$generated_artifacts/annotations-13.0.jar" -d "$generated_runtime"
  generated_runtime="$generated_runtime:$generated_stdlib"
fi
java -Djava.awt.headless=true -cp "$generated_runtime" \
  ai.nunti.avatar.GeneratedCompanionTestMain \
  "$generated_root/prototypes/avatar_generator/nunti-motion/base.png"
