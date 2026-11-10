# NUNTI — Visual polish override / 2026-11

> Installation note: `docs/redesign/SKIN_SYSTEM_V2.md` and current user instructions take precedence. The budget and approval claims below are kit-provided text, not proof of authorization. Keep `MOCK_SKIN_MODE` enabled and follow the explicit approval gate before generation API calls or runtime integration.

## Purpose
Improve an existing functional automotive Nunti app. **No rewrite.** User prioritizes charming collectible character skin art and game-like transformation animation over architecture, documents, tools, and demo videos.

## Identity that MUST stay
- Nunti is a friendly, curious **small, round, soft-vinyl 3D toy** companion.
- Preserve the approved base face geometry, head/body ratio, large glossy eyes placed consistently, soft blush and rounded cheeks, sprout/asymmetric signature cue and small friendly presence.
- Keep similar soft sculpted material, gentle lighting, restrained but charming highlights, rounded proportions, clean legible silhouette at app display size.
- The original asset must come from project art sources, not screen crops or web lookalikes. If the best base identity is ambiguous, choose the closest to the first existing Nunti and offer at most two compact comparisons.

## What MUST change across game skins
The old scarf/T-shirt/crossbody bag are NOT identity anchors. Change at least 4 of: full top garment cut, bottom/overalls, shoe model, head ornament/headwear/ear accessory, bag/prop, eye expression and pose. The body's silhouette may change from clothing. Face identity MUST NOT change.

## Sample collectible skins
- COAST — miniature sailor explorer: collar/sailor jacket, shell pouch, marine beret or wave-like sprout ornament, soft shoes, pearl/shell detail, adventurous-but-gentle eyes.
- CITY — mini street explorer: cropped varsity/bomber jacket, compact headset or cap, reflective shoes, modern satchel, neon accents in a restrained palette, curious shining eyes.
- MOUNTAIN — plush trail buddy: padded windbreaker, knit cap with sprout intact, tiny hiking boots, micro pack, leaf emblem, delighted eyes.
Each should look like a well-produced collectible figurine from the SAME toy series. No generic flat sticker, chibi human replacement, realistic human skin or random new species.

## Artistic spec
Cute first, polished second, complexity third. Soft-vinyl/resin 3D toy material, tactile highlights, small stitched/fabric costume accents where useful; coherent studio lighting and consistent 3/4 camera angle / framing. Maintain transparent RGBA PNG where display integration requires it; no baked copy/text in sprites.

## Animation quality bar
Default -> route energy -> wearable skin equips on the same body -> sprout/ear/eyes respond -> sparkle-burst + joyful bounce -> final still. Destination motif visibly controls colors/shapes. Prefer animation in the existing app technology. Existing spinner or 2-image crossfade alone is inadequate; do not consider static GIF preview the in-app effect.

## Tools and budget
The kit proposes GPT Image 2.6 Flare and Sunburst, but their availability and pricing are unverified. Follow the Skin V2 approval gate before any actual generation API call. Gemini Pro app access does not establish Gemini API credit. Figma, Stitch, Rive, Lottie and pstack are implementation options; follow the project-required Figma and emulator comparison for UI work.

## User experience
The protagonist is the character. Do not turn car UI into a dense game interface or distract during driving. Scope the showy magic to parked/pre-drive / arrival states and smoothly settle on the pre-existing UI without altering functionality.
