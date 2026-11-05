"""Export v2 contracts only. Never rewrites the historical v1 wire artifacts."""

import json
from pathlib import Path

from nunti.api import create_app
from nunti.characters.models import (
    CharacterArtifact,
    Concept,
    DesignedVoiceSource,
    GenerationInput,
    JobView,
    SpeechInput,
    VoiceManifest3,
)
from nunti.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def main():
    destination = ROOT / "contracts/v2"
    destination.mkdir(parents=True, exist_ok=True)
    for model in (
        GenerationInput,
        SpeechInput,
        Concept,
        DesignedVoiceSource,
        VoiceManifest3,
        CharacterArtifact,
        JobView,
    ):
        value = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:nunti:contracts:v2:" + model.__name__,
            **model.model_json_schema(),
        }
        (destination / (model.__name__ + ".schema.json")).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    app = create_app(Settings(tokens={"documentation-only-not-a-deployment-token": "docs"}))
    spec = app.openapi()
    spec["paths"] = {
        path: value for path, value in spec["paths"].items() if path.startswith("/v2/")
    }
    spec["info"] = spec["info"] | {
        "title": "Nunti Character Generation API",
        "version": "2.0-draft",
    }
    (destination / "openapi.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
