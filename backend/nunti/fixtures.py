"""Synthetic fixtures only. These are not captures from Pleos or a real vehicle."""

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "mock_data"


def scenario_names() -> list[str]:
    return sorted(path.stem for path in FIXTURE_DIR.glob("*.json"))


def load_scenario(name: str) -> dict:
    if name not in scenario_names():
        raise ValueError("Unknown mock scenario")
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text())
