#!/usr/bin/env python3
"""Reproduce the four synthetic recipe examples through fresh CLI processes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
EXAMPLES = ["coastal_rest.json", "mountain_camping.json", "city_exhibition.json", "coastal_rest_next.json"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "sample-output.json")
    args = parser.parse_args()
    recipes = []
    with tempfile.TemporaryDirectory(prefix="nunti-recipe-samples-") as directory:
        ledger = Path(directory) / "ledger.json"
        for filename in EXAMPLES:
            result = subprocess.run(
                [sys.executable, str(HERE / "recipe_cli.py"), "generate", "--input",
                 str(HERE / "examples" / filename), "--ledger", str(ledger)],
                check=True, capture_output=True, text=True, timeout=10)
            recipes.append(json.loads(result.stdout))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"syntheticOnly": True, "status": "RECIPE_ONLY", "recipes": recipes},
                                      ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for filename, recipe in zip(EXAMPLES, recipes):
        design = recipe["design"]
        print("{} -> {} / {} / {} / {}".format(filename, recipe["characterId"], design["bodyFamily"],
                                                design["shapeId"], recipe["voiceIntent"]["requested"]["affect"]))
    print("saved " + str(args.output))


if __name__ == "__main__":
    main()
