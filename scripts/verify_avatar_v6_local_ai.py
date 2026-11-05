#!/usr/bin/env python3
"""Generate/reuse three real offline AI counterparts of the v6 character grammar."""

import argparse
import json
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from nunti.avatar_studio.api import Settings
from nunti.avatar_studio.illustration import render_avatar
from nunti.avatar_studio.local_model import render_local_image
from nunti.avatar_studio.models import canonical, digest
from nunti.avatar_studio.voice_design import build_voice_design


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/avatar-v6/local-ai")
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    config = Settings(
        token="v6-offline-art-verification-local-only",
        workspace=folder,
        local_model_enabled=True,
        local_model_binary=ROOT
        / ".local/avatar-quality-v4/local-image/venv/bin/mflux-generate-flux2-edit",
        local_model_weights=ROOT / ".local/avatar-quality-v4/local-image/model",
    )
    cases = [
        ("seoul-business", "서울역", "중요한 고객 미팅 출장"),
        ("suwon-date", "수원역", "연인과 데이트"),
        ("eulwangri-swim", "을왕리 해수욕장", "친구들과 수영하고 물놀이"),
    ]
    records = []
    for name, destination, purpose in cases:
        out = folder / name
        out.mkdir(exist_ok=True)
        saved = out / "artifact.json"
        if saved.exists():
            records.append(json.loads(saved.read_text()))
            print(name, "RESTORED", flush=True)
            continue
        request_id = str(uuid5(NAMESPACE_URL, "nunti-v6-ai-1/" + name))
        value = {
            "requestId": request_id,
            "destination": {"name": destination, "traits": ""},
            "purpose": purpose,
            "renderMode": "LOCAL_MODEL",
            "route": {
                "points": [[0.1, 0.8], [0.3, 0.75], [0.4, 0.3], [0.7, 0.4], [0.8, 0.1]],
                "inputOrigin": "TEST_ROUTE",
                "sourceLabel": "v6 의미대조 합성 QA 경로",
                "confirmed": True,
            },
        }
        png, design = render_avatar(
            value["route"]["points"], destination, "", purpose, request_id
        )
        (out / "structure.png").write_bytes(png)
        (out / "input.json").write_text(canonical(value))
        attempt = len(list(out.glob("run*"))) + 1
        result = render_local_image(config, value, design, out / f"run-{attempt}")
        (out / "avatar.png").write_bytes(result.png)
        artifact = {
            **value,
            "characterId": "nunti-" + request_id,
            "displayName": design["displayName"],
            "mediaOrigin": "LOCAL_MODEL",
            "visual": {"path": str(out / "avatar.png"), "sha256": digest(result.png)},
            "design": {**design, "formation": result.formation},
            "provider": result.metadata,
            "voice": build_voice_design(value, design),
        }
        saved.write_text(json.dumps(artifact, ensure_ascii=False, indent=2))
        records.append(artifact)
        print(name, "GENERATED", result.metadata.get("elapsedSeconds"), flush=True)
    (folder / "results.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
