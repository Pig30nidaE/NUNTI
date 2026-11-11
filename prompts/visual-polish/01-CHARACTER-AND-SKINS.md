# 01 — Actual character artwork (API-powered)

Use `$nunti-visual-polish`, `$nunti-identity`, `$nunti-route-variants`.

INPUT: approved existing Nunti ORIGINAL from repository, never a tiny screenshot. Read `docs/NUNTI_VISUAL_POLISH_OVERRIDE.md` and `references/ART_AND_MOTION_REFERENCES.md`.

Generate actual edited image assets using an available image tool / API, not prompt-only documents:
A) First small batch: `gpt-image-2.6-flare` 3 previews (COAST, CITY, MOUNTAIN), each with the original as image editing reference, not text-to-image from zero.
B) Review against original for lovable 3D-toy texture and face identity. Fix missing features; select best skin direction per theme without requiring user to draw.
C) Then `gpt-image-2.6-sunburst` final variants (at most 3 initial images), again reference-guided, with 3/4 camera angle and coherent lighting. If model access fails, use the available connected image generation facility; never substitute low-quality vector art.
D) Produce transparent RGBA characters if the current renderer uses transparency, and make compatible sizes and formats; derive thumbnails automatically.
E) Replace/update *only* the existing visual assets and skin-specific prompts/mapping needed to call them. Prefer existing mapping/renderer modules.
F) For dynamic route generation already implemented, adapt the existing generation prompt/API call to use canonical reference + positive/negative material and costume instructions, preserving the data/response contract. Do not create parallel backend.

Art direction:
- miniature premium collectible 3D soft-vinyl mascot, round head and chunky tiny body, subtly asymmetrical sprout, enormous glossy friendly eyes, peachy blush, high-quality studio lighting, soft shadows, tactile detailed clothing.
- Keep face/body identity extremely recognizable.
- Different complete outfits, accessories and shoes. Do NOT repeat the mint scarf + white sweater + generic bag for every skin.
- Soft pastel color harmony, rich material detail, toy-shop charm, tiny expressive poses.
- No flat 2D/vector, bland low-poly, generic human/anime replacement, realistic adult proportions, sticker UI mockups, words or extra characters.

Follow `docs/NUNTI_VISUAL_POLISH_OVERRIDE.md`. User values cuteness/collectibility, not maximum skin count.

Cost behavior: follow the Skin V2 verification and explicit approval gate before any actual generation API call. If approved, check model access and pricing first, use a small trial, and track each call. The kit's proposed model names and pricing have not been verified. No unbounded retries.

OUTPUT: actual assets in current app's expected folders + one small visual comparison image for selection; concise discussion of look and feel, no long architecture document.
