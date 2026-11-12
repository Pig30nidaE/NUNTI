"""Versioned, owner-scoped source textures for a bounded frontal mesh, not inferred 3D anatomy."""

import io
import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .models import canonical, png_bytes
from .storage import StudioError

VERSION = "nunti-rig-1"
ROOT = Path(__file__).resolve().parents[3]
DEFINITION = ROOT / "prototypes/avatar_generator/companion-rig/manifest.json"


def prepare(store, owner, content):
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format != "PNG" or source.size != (768, 768) or source.mode != "RGBA":
                raise StudioError("COMPANION_RIG_ALIGNMENT", 502)
            source.load()
            image = source.copy()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        if isinstance(error, StudioError):
            raise
        raise StudioError("COMPANION_RIG_ALIGNMENT", 502) from error
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None or not (145 <= bounds[0] <= 230 and 10 <= bounds[1] <= 90):
        raise StudioError("COMPANION_RIG_ALIGNMENT", 502)
    if not (540 <= bounds[2] <= 625 and 690 <= bounds[3] <= 750):
        raise StudioError("COMPANION_RIG_ALIGNMENT", 502)
    for region, minimum in (
        ((290, 200, 475, 355), 0.85),
        ((310, 440, 460, 550), 0.8),
        ((225, 445, 275, 520), 0.2),
        ((490, 445, 540, 520), 0.2),
        ((290, 660, 355, 710), 0.5),
        ((410, 660, 475, 710), 0.5),
    ):
        histogram = alpha.crop(region).histogram()
        if sum(histogram[128:]) / sum(histogram) < minimum:
            raise StudioError("COMPANION_RIG_ALIGNMENT", 502)
    definition = json.loads(DEFINITION.read_text(encoding="utf-8"))
    rgb = image.convert("RGB")
    for name in ("leftEye", "rightEye"):
        left, top, right, bottom = definition["regions"][name]
        points = []
        for y in range(top, bottom):
            for x in range(left, right):
                r, g, b = rgb.getpixel((x, y))
                if r < 150 and g < 110 and b < 95:
                    points.append((x, y))
        if len(points) < 500:
            raise StudioError("COMPANION_RIG_ALIGNMENT", 502)
        center_x = sum(x for x, _ in points) / len(points)
        center_y = sum(y for _, y in points) / len(points)
        if abs(center_x - (left + right) / 2) > 15 or abs(center_y - 274) > 16:
            raise StudioError("COMPANION_RIG_ALIGNMENT", 502)
    texture_sha = store.put_asset(owner, content, "image/png")
    parts = {}
    for name, region in definition["regions"].items():
        patch = png_bytes(image.crop(region))
        sha = store.put_asset(owner, patch, "image/png")
        parts[name] = {"path": "/v3/assets/" + sha, "sha256": sha, "sourceRect": region}
    definition.update(
        textureSha256=texture_sha,
        parts=parts,
        registration={
            "checks": [
                "RGBA_CANVAS",
                "ALPHA_BOUNDS",
                "JOINT_REGION_COVERAGE",
                "EYE_DARK_REGION_CENTERS",
            ],
            "anatomyVerified": False,
            "bounds": list(bounds),
        },
    )
    payload = canonical(definition).encode()
    sha = store.put_asset(owner, payload, "application/json")
    return {
        "version": VERSION,
        "kind": definition["kind"],
        "textureSha256": texture_sha,
        "manifest": {"path": "/v3/assets/" + sha, "sha256": sha},
        "parts": parts,
        "humanQualityApproved": False,
    }
