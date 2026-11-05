#!/usr/bin/env python3
"""Check research documents and inventory citations; does not run models or validate taste."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs/research/avatar-art-direction-2026-11-03"


def main():
    documents = [
        FOLDER / name
        for name in (
            "README.md",
            "collectible-design.md",
            "image-generation.md",
            "formation-motion.md",
            "PROMPT-PACK.md",
        )
    ]
    checks, sources = [], {}
    quality = json.loads((ROOT / "docs/product/nunti-scope.json").read_text())[
        "ownedFeatureQualityReview"
    ]
    checks.append(
        {
            "check": "human-art-approval-is-not-functional-test-pass",
            "ok": quality["source"] == "USER_FEEDBACK"
            and quality["humanArtApproval"] is False
            and quality["nextDesignStep"]
            in {
                "VERIFY_LOCAL_AI_IMAGE_AND_FORMATION_WITH_USER",
                "REVIEW_CLEAN_SURFACE_AND_AURORA_FORMATION",
            },
        }
    )
    checks.append(
        {
            "check": "accepted-rendering-style-is-distinct-from-final-art-approval",
            "ok": quality["renderingStyleHumanApproved"] is True
            and quality["requestedRenderingStyle"]
            == "OPAQUE_MATTE_PASTEL_ILLUSTRATED_2_5D"
            and quality["finalCharacterSelected"] is False,
        }
    )
    for document in documents:
        content = document.read_text()
        checks.append(
            {
                "check": "dated-document:" + document.name,
                "ok": "2026-11-03" in content and len(content) > 500,
            }
        )
        content = re.sub(r"(?ms)^```.*?^```\s*$", "", content)
        for href in re.findall(r"!?\[[^\]\n]*\]\(([^\s)]+)", content):
            parsed = urlsplit(href.strip("<>"))
            if parsed.scheme in ("http", "https"):
                sources.setdefault(href, set()).add(document.name)
            elif not parsed.scheme and not parsed.netloc and parsed.path:
                target = (
                    document.parent / re.sub(r":\d+$", "", unquote(parsed.path))
                ).resolve()
                checks.append(
                    {
                        "check": "local-reference:" + document.name + ":" + href,
                        "ok": target.is_relative_to(ROOT) and target.exists(),
                    }
                )
    report = {
        "status": "PASS_RESEARCH_DOCUMENT_STRUCTURE"
        if all(c["ok"] for c in checks)
        else "FAIL",
        "scope": "Document presence, dates, local links, source inventory and source-code snapshot only. External links were read during research; this script does not fetch them or certify claims, image quality, taste or model performance.",
        "asOf": "2026-11-03",
        "documents": [str(d.relative_to(ROOT)) for d in documents],
        "checks": checks,
        "externalSourceCount": len(sources),
        "sources": [
            {"url": url, "citedIn": sorted(names)}
            for url, names in sorted(sources.items())
        ],
        "currentImplementationSnapshot": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "backend/nunti/avatar_studio/illustration.py",
                "backend/nunti/avatar_studio/image_api.py",
                "prototypes/avatar_generator/studio.js",
            )
        },
    }
    (FOLDER / "verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "documents": len(documents),
                "localAndStructureChecks": len(checks),
                "externalSourcesInventoried": len(sources),
            }
        )
    )
    return 0 if report["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
