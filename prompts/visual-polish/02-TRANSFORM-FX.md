# 02 — Game-like transformation in THE EXISTING VIEW

Use `$nunti-visual-polish`, `$nunti-birth-motion`, plus Figma skills only if they genuinely improve motion quality and are connected. Read `references/ART_AND_MOTION_REFERENCES.md`.

Target: existing Nunti generation view. Same character remains on stage and equips new skin. 3.5–5 seconds while vehicle is parked / non-restricted.

Creative beats (improve artistry as needed):
0–0.6: default Nunti idly blinks, notices a glowing route ribbon.
0.6–1.5: colorful route ribbon swirls around Nunti with fireflies and sparkling dust, destination-colored halo expands softly.
1.5–2.8: clothes materialize/assemble as 2–3 distinct layers with cloth highlights; headwear/sprout ornament and shoes transform; cheeks/eyes react; do NOT replace whole character with one static fade.
2.8–3.6: joyful squish-stretch and bounce; bright star pop around the character; recognizable in-between costume state.
3.6–4.3: final mini pose and soft lingering glow, then still exact same final skin delivered by generation.

Look: premium game collectible skin unlock, soft magical brilliance, tasteful colorful sparkles, tactile 3D toy, fun small microexpressions. Avoid merely drawing a thin turquoise ellipse around the sprite, spinner, or quick image crossfade.

First inspect actual existing animation/render technology:
- If current Compose/Canvas layer motion exists, extend its assets and keyframes in place; use an existing Lottie layer if already present.
- If current implementation only swaps two flat images, add the MINIMUM local keyframe/overlay logic inside that existing view. No new app, navigation, standalone engine or Figma dependency.
- Figma Motion optional if connected and meaningful; `figma-use-motion` and `figma-implement-motion` for keyframe authoring / code translation when available.
- GPT Image 2.6 GIF optional to discover interesting in-between visuals; image GIF supports max 16 frames and does not automatically yield clean separate rigged layers. Do not use a full-screen raster GIF if it blurs the character or can't blend with the app.
- Optional image-to-video provider only after comparing visual benefits and identifying incremental cost; do not purchase new external services by default. OpenAI credits cannot pay for non-OpenAI APIs.

User should see actual transformed Nunti in existing app, not a separate demo or only still assets. Respect current parked/restricted logic, skip, reduced-motion and fallback without broad new testing scope. Show the user the in-app result and summarize visual changes; no long demo-film requirement.
