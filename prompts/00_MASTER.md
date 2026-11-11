# NUNTI — PROFESSIONAL GAME VFX EXECUTION

You are **Senior Game VFX Artist + Android rendering integration engineer** for an EXISTING Nunti/Pleos APK.

## Existing context
Core app functions, avatar creation, route/destination/mood mapping, skin images, animation flow and UI already exist. Some existing effects are better than before, but a thin orbit line, generic rings and simplistic image transition still look cheap. The goal is the *feel* of a premium collectible character gaining a new costume: cute, emotional, visually sophisticated, clearly themed.

## Skills and references — load these first
- `$nunti-game-vfx` (new), and its three reference docs.
- Already installed `$nunti-identity`, `$nunti-route-variants`, `$nunti-birth-motion`, `$nunti-pleos-ui` as needed. New VFX guidance takes priority if old skills insist on a light-born character or unchanged costume silhouette.
- pstack `principle-experience-first`, `principle-exhaust-the-design-space`, `principle-prove-it-works` if present.
- Official sources: https://effekseer.github.io/en/contribute.html ; https://effekseer.github.io/en/contributes/MAGICALxSPIRAL/index.html ; https://effekseer.github.io/Help_Tool/en/ToolReference/record.html ; https://kenney.nl/assets/particle-pack ; https://github.com/airbnb/lottie/blob/master/android-compose.md

## Non-negotiables
1. **Do not rebuild** app, avatar generator, server, navigation or skin collection. Change only VFX assets, existing effect renderer, timeline coupling, and minor character pose where useful.
2. **Real professionally authored effects first.** Actually find/download licensed effect originals, inspect content, choose usable effects, output/import the sprite frames. Do not simulate the entire effect with `drawCircle`/a single orbit stroke.
3. Use **Effekseer new CC0** examples (or explicitly licensed alternative); avoid Old License bundles unless precise permission for this export path is independently verified.
4. Preserve current Nunti 3D-toy face and existing skin costumes. No Rive free-tier opening splash, no random replacement characters.
5. Three effects must be **structurally different** (sea wave / city neon assembly / forest foliage growth), not recolored clones.
6. Keep production within currently existing Android screen. No separate VFX app or game engine if standard sprite compositing fits.
7. No hidden paid VFX purchases or API calls. Use public CC0 and current resources first; if any license/cost hurdle appears, propose a concrete free substitute.
8. Observe Pleos driving restrictions, reduce motion when restricted. Avoid harsh repeated full-screen strobes.

## Action plan — implement, not just summarize
A. Briefly inspect the existing animation code, asset folders, timeline and skin switching (do not produce a long architecture report). Identify precisely where current thin lines and image wipes are drawn.
B. Obtain **real assets**: new CC0 Effekseer collection samples; evaluate 2-3 authentic candidate effects for ONE Ocean transformation. Record actual downloaded filenames and author/license. When an Effekseer editor is required, install the Mac architecture-matched official version if possible; recognize that CLI conversion does not guarantee transparent Recorder output.
C. Use official Recorder to export transparent PNG frames / sprite sheet when interactive editor control is possible. Use `Generate alpha (Blend+Add)` for mixed blend modes, or verify `Original image` alpha. If you lack editor GUI automation, switch to licensed pre-exported animation assets rather than faking the result. If no suitable asset exists, tell me the *one* exact blocked action, not a large task list.
D. Make the Ocean effect irresistible: a 2.5D flow of luminous wave/pearls around Nunti, short charged buildup, wave-splash burst masking the costume change, drift-down iridescent sparkles and a small delighted character reaction. Match character scale and soft toy look; preserve face readability.
E. Integrate in the **existing** Android animation container. Match time and layer order; remove the old thin orbit line if it conflicts. Spot-check in the running existing app in parked state. Do not stop at an asset download and call the animation done.
F. Expand from the working approach to City (geometric neon assembly / spark) and Forest (wind / floating leaves / sunlight) with different authored effects, motion shapes, timing and climax patterns.
G. Finish with the actual changed files, links/credits/licenses for chosen VFX, and concise notes. No extra presentation/long report needed.

## Work quality before declaring success
- Visual: believable volumetric effect; no bare rings, obvious wipe or cheap alpha edges; skin is revealed with emotional peak.
- Themes: ocean/city/forest genuinely different and recognizable WITHOUT labels.
- Technical: effect plays in actual existing app; true transparent asset; starts/stops/reset with existing screen; safe when driving-restricted.
- Truthfulness: if you cannot render the effect or operate the editor, report that blocker and an alternate route. Never say you used an asset that you didn't actually obtain.

**Proceed with real edits and source acquisition NOW. Do not answer by drafting another plan.**
