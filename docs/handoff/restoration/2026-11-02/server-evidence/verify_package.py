"""Check the built wheel directly, outside the backend source import path."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[5]
WHEEL = ROOT / ".local/dist/nunti_backend-0.1.0-py3-none-any.whl"


def main():
    with tempfile.TemporaryDirectory(prefix="nunti-wheel-") as directory:
        unpacked = Path(directory).resolve() / "wheel"
        with zipfile.ZipFile(WHEEL) as archive:
            fixtures = [name for name in archive.namelist() if name.startswith("nunti/mock_data/") and name.endswith(".json")]
            assert len(fixtures) == 10, fixtures
            archive.extractall(unpacked)
        sys.path.insert(0, str(unpacked))
        import nunti
        from fastapi.testclient import TestClient
        from nunti.api import create_app
        from nunti.config import Settings

        assert Path(nunti.__file__).resolve().is_relative_to(unpacked)
        settings = Settings(
            db_path=Path(directory) / "wheel.sqlite3",
            tokens={"synthetic-wheel-check-token-00000001": "wheel-check"},
            sync_enabled=True,
            enable_mocks=True,
            require_https=False,
        )
        with TestClient(create_app(settings), headers={"Authorization": "Bearer synthetic-wheel-check-token-00000001"}) as client:
            assert client.get("/health").status_code == 200
            response = client.get("/v1/mock/scenarios")
            response.raise_for_status()
            scenarios = response.json()["data"]["scenarios"]
            assert len(scenarios) == 10
            for scenario in scenarios:
                client.get(f"/v1/mock/scenarios/{scenario}").raise_for_status()
            openapi = client.get("/openapi.json")
            openapi.raise_for_status()
            assert "/v1/trips" in openapi.json()["paths"]
        print(json.dumps({"ok": True, "wheel": str(WHEEL), "sha256": hashlib.sha256(WHEEL.read_bytes()).hexdigest(), "mockJsonCount": len(fixtures), "checked": ["isolated wheel import", "health", "10 authenticated Mock endpoints", "OpenAPI"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
