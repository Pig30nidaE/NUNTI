"""Validate freshly generated Kotlin wire outputs and persist their route/avatar pairs."""

import argparse
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker

from nunti.api import create_app
from nunti.config import Settings
from nunti.models import CONTRACTS

ROOT = Path(__file__).resolve().parents[2]
MODELS = {model.__name__: model for model in CONTRACTS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reports", type=Path, default=ROOT / "android/feature/avatar/build/reports"
    )
    args = parser.parse_args()
    values = {}
    for path in sorted(args.reports.glob("*.json")):
        model_name = path.stem.split(".")[-1]
        if model_name not in MODELS:
            continue
        value = json.loads(path.read_text())
        schema = json.loads((ROOT / "contracts/v1" / f"{model_name}.schema.json").read_text())
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
        MODELS[model_name].model_validate(value)
        values[path.name] = value
    if not values:
        raise SystemExit("No Kotlin outputs found. Run the AVATAR JVM test script first.")

    token = "synthetic-integration-check-token-00001"
    pairs = 0
    with tempfile.TemporaryDirectory(prefix="nunti-contract-check-") as directory:
        settings = Settings(
            db_path=Path(directory) / "test.sqlite3",
            tokens={token: "integration"},
            sync_enabled=True,
            require_https=False,
        )
        with TestClient(
            create_app(settings), headers={"Authorization": f"Bearer {token}"}
        ) as client:
            for name, avatar in values.items():
                if not name.endswith(".AvatarSpec.json"):
                    continue
                route = values[name.replace(".AvatarSpec.json", ".RouteSnapshot.json")]
                trip_id = f"trip-kotlin-{pairs}"
                response = client.post(
                    "/v1/trips",
                    json={
                        "schemaVersion": "1.0",
                        "tripId": trip_id,
                        "startedAt": route["collectedAt"],
                        "syncConsent": True,
                    },
                )
                response.raise_for_status()
                path = f"/v1/trips/{trip_id}"
                client.put(path + "/route", json=route).raise_for_status()
                client.put(path + "/avatar", json=avatar).raise_for_status()
                stored = client.get(path)
                stored.raise_for_status()
                assert stored.json()["data"]["avatar"]["value"] == avatar
                pairs += 1
    if pairs == 0:
        raise SystemExit("No corresponding route/avatar outputs found")
    print(f"PASS: {len(values)} Kotlin JSON contracts and {pairs} route/avatar API round trips")


if __name__ == "__main__":
    main()
