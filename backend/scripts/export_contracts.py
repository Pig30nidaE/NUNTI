"""Regenerate the reviewed wire artifacts. CI tests reject model/schema drift."""

import json
from pathlib import Path

from nunti.api import create_app
from nunti.config import Settings
from nunti.models import CONTRACTS

ROOT = Path(__file__).resolve().parents[2]


def schema_for(model):
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:nunti:contracts:v1:{model.__name__}",
        **model.model_json_schema(),
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main():
    for model in CONTRACTS:
        schema = schema_for(model)
        sample_path = ROOT / "contracts/v1/examples" / f"{model.__name__}.valid.json"
        if sample_path.exists():
            schema["examples"] = [json.loads(sample_path.read_text())]
        write_json(ROOT / "contracts/v1" / f"{model.__name__}.schema.json", schema)
    app = create_app(
        Settings(
            tokens={"documentation-only-not-a-valid-deployment-token": "docs"},
            enable_mocks=True,
        )
    )
    spec = app.openapi()
    write_json(ROOT / "contracts/v1/openapi.json", spec)


if __name__ == "__main__":
    main()
