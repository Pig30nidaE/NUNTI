"""Inventory the integration deliverables without attributing older edits to this task."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/redesign/integration-v1"
OUTPUT = REPORT / "files-manifest.json"
SOURCE_FILES = (
    "android/app/build.gradle.kts",
    "android/app/src/main/AndroidManifest.xml",
    "android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt",
    "android/app/src/main/kotlin/ai/nunti/app/journey/JourneyActivity.kt",
    "android/app/src/main/kotlin/ai/nunti/app/journey/JourneyCompanionView.kt",
    "android/app/src/main/kotlin/ai/nunti/app/journey/NuntiTheme.kt",
    "prototypes/avatar_generator/index.html",
    "prototypes/avatar_generator/studio.css",
    "prototypes/avatar_generator/ui-redesign.js",
    "prototypes/avatar_generator/studio.js",
    "prototypes/avatar_generator/nunti-transformation.js",
    "backend/nunti/avatar_studio/api.py",
    "scripts/test_avatar_layers_ui_state.mjs",
    "scripts/test_navigation_ui_state.mjs",
    "scripts/package_nunti_production_assets.py",
    "scripts/test_nunti_transformation_state.mjs",
    "scripts/build_nunti_integration_comparison.py",
    "scripts/nunti_integration_runtime_lib.mjs",
    "scripts/verify_nunti_video_frames.swift",
    "scripts/write_nunti_integration_manifest.py",
)


def main() -> None:
    before = json.loads((REPORT / "before-integration-source-state.json").read_text())["files"]
    paths = {ROOT / name for name in SOURCE_FILES}
    paths.update((ROOT / "scripts").glob("verify_nunti_integration*"))
    for folder in (
        "prototypes/avatar_generator/nunti-motion",
        "prototypes/avatar_generator/assets",
        "docs/redesign/integration-v1",
        "docs/redesign/pleos-ui-v1/integration",
    ):
        paths.update((ROOT / folder).rglob("*"))
    files = []
    for path in sorted(paths):
        if not path.is_file() or path == OUTPUT or "__pycache__" in path.parts or path.name == ".DS_Store":
            continue
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        initial = before.get(relative)
        files.append({
            "path": relative,
            "bytes": len(data),
            "sha256": digest,
            "beforeIntegrationSha256": initial["sha256"] if initial else None,
            "comparedWithCapturedStart": (
                "UNCHANGED" if initial["sha256"] == digest else "CHANGED"
            ) if initial else "NOT_IN_SELECTED_START_HASH_CAPTURE",
        })
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "Integration source, verification tools, bundled assets, and evidence. Not a git diff or claim that all inventoried files are newly created.",
        "startState": "docs/redesign/integration-v1/before-integration-source-state.json",
        "preexistingGitChanges": "docs/redesign/integration-v1/before-integration-git-status.txt",
        "excludes": ["this manifest itself", "build outputs (APK hash is in installed-build.json)", "Python caches"],
        "count": len(files),
        "files": files,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"Recorded {len(files)} paths in {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
