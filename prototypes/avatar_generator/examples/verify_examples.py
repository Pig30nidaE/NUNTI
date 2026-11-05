"""Run the actual extractor and produce review overlays, keeping all original PNGs unchanged."""

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[2] / "backend"))
from nunti.avatar_studio.navigation import extract_route

if __name__ == "__main__":
    results = []
    entries = json.loads((ROOT / "index.json").read_text())
    for entry in entries:
        original = ROOT / entry["imageFile"]
        raw = original.read_bytes()
        extracted = extract_route(raw, "blue")
        image = Image.open(original).convert("RGB")
        d = ImageDraw.Draw(image)
        points = [(x * image.width, y * image.height) for x, y in extracted["points"]]
        d.line(points, fill="#e72f5a", width=3)
        for x, y in (points[0], points[-1]):
            d.ellipse((x - 5, y - 5, x + 5, y + 5), outline="#e72f5a", width=2)
        d.rectangle((235, 550, 925, 582), fill="white")
        d.text(
            (245, 560),
            "PINK = extracted line. Check the ORIGINAL route before confirming.",
            fill="#a31d3c",
        )
        overlay = ROOT / f"{entry['id']}.overlay.png"
        image.save(overlay, optimize=True)
        results.append(
            {
                "id": entry["id"],
                "sourceSha256": hashlib.sha256(raw).hexdigest(),
                "overlayFile": overlay.name,
                "overlaySha256": hashlib.sha256(overlay.read_bytes()).hexdigest(),
                "extraction": extracted,
                "reviewStatus": "SYNTHETIC_ROUNDTRIP_ONLY_USER_CONFIRMATION_STILL_REQUIRED",
            }
        )
        print(
            f"{entry['id']}: {len(points)} points, confidence={extracted['confidence']}, confirmation required"
        )
    (ROOT / "extraction-checks.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    )
