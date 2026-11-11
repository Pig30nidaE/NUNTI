# Incremental Nunti redesign plan

## Decide what the next prototype should prove

Use the existing hooded-sprout sheet as the working identity reference. The score module identifies it as Nunti and the current local model reads it. Confirm the exact master and its approval record before making production assets. The working identity is a compact rounded hood and body, a small asymmetric forehead curl under the sprout, stable eye centers and proportions, a small signature mouth, and the blue badge. Keep the mint scarf and warm matte treatment as reference cues. Derive normalized face anchors from the chosen master before drawing variants. Check the silhouette at 64 px and the full face at 128 px against both display modes. Keep Nunti's own face and shape language.

| Direction | Parked presentation | What to compare |
| --- | --- | --- |
| A · Pocket companion | Keep the whole hooded figure in soft matte color. Put the destination in one attached keepsake, such as a wave charm, and the route in a restrained trail that disappears at settlement. Purpose can change the established wardrobe detail or gesture within the canonical silhouette. | The face and body read first at thumbnail size. The direction can reuse the v6 matte renderer and the current collection card. |
| B · Journey relief | Present the same face and body as a shallow, raised figure on a quiet matte plinth. Put the destination on a single embossed tag. The route traces briefly around the plinth before the figure becomes visible. Keep the figure separable so the restricted view can use the same still without the plinth. | The arrival and gallery have a stronger keepsake treatment. Check that the base does not shrink the face or wash out the hood on the narrow app window. |

I recommend A for the first proof. It keeps the travel companion as the focus in all four states and needs fewer layers to reach a readable still. Compare A and B on the same city, coast, and mountain fixtures before selecting one for production. Keep the studies separate from accepted assets and old collections. [Named reference](../design/avatar-v6/assets/nunti-base-character.png) · [Identity constraints](../NUNTI_DESIGN_CONTRACT.md)

## Keep the integration points and change the visual output

1. **Prototype with existing artifacts.** Use the current Studio stage and one existing saved local PNG in a fixture-only branch or prototype. Build the one-shot reveal around the saved image. Keep the approved master decision and new art separate so motion can be tested against existing images first.
2. **Add a versioned plan for future visuals.** Treat the draft `RouteContext` as an internal projection of the confirmed route, user inputs, and provenance. Derive the new visual plan alongside the existing `build_design_intent` and `build_character_plan` boundary. Reuse their route features, place parsing, and asset handling. Keep the v1 `AvatarSpec` and v3 request/response shape intact in the first proof. Resolve new fields or metadata changes as a separate contract review before enabling them for new records.
3. **Use deterministic layers for new approved visuals.** Store the master asset version, selected accent, pose, and seed with the accepted visual. Use a stable hash of the confirmed route ID or a hash of its canonical normalized snapshot, the mapping version, and the stored seed. Keep the existing UUID per explicit creation, so a new journey can still produce a new collectible. A retry reads the same stored result. A reroute or a restoration never recomputes a previously saved character.
4. **Keep existing ownership.** Preserve `StudioStore`, image and voice hashes, authenticated media, the Studio native bridge, navigation confirmation, `JourneyService`, `ScoreEngine`, and report persistence. Use one presentation token table in Figma to align the WebView and native View. Implement in the current hosts.
5. **Roll out by artifact version.** New records may use the chosen design after approval. Older records use their original image and binding. At first launch after an update, verify the same image and prepared audio hashes on reopened items. Store the owner, source prompt or illustration source, exact asset version, export settings, license note, and fallback for each accepted asset.

[Current pipeline](01-current-state-audit.md) · [Studio API](../../backend/nunti/avatar_studio/api.py) · [Journey media loader](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyRuntime.kt)

For the first prototype, a successful creation supplies the saved artifact and decoded bitmap to the reveal. A gallery selection supplies the same inputs and opens directly in the settled state. The Studio WebView owns the reveal phase (`WAITING`, `PLAYING`, or `SETTLED`) and its single frame request. Android owns display eligibility through the existing bridge. The renderer accepts progress and draws a frame. It has no dependency on the vehicle service or storage. Eligibility loss, Skip, and completion converge on the same settled frame for that artifact. A pending decode from a previous selection cannot start playback for the current selection.

## Map trip context without inventing trip facts

| Visual channel | Eligible input | Fallback |
| --- | --- | --- |
| One destination motif | Explicit or app-classified destination. Use a dotted charm for city, wave for coast, ridge for mountain. Record whether the category came from explicit input, app classification, or a fixture. | Use a neutral journey-star charm when category is unknown. |
| One route motif | Confirmed normalized geometry. Use a short arc or segmented trace derived from the shape. Mark screenshot, file, OSRM, or test provenance. | Use a short generic parked preview stroke for a design fixture, or show the saved still when the real route is absent. Preserve v3's valid-route requirement for new generation. |
| One mood expression | A future explicit mood choice, if added through an approved contract. Keep eye positions, scale, and mouth geometry anchored. The chosen expression changes eyelids, brows, or a small pose. | Neutral expression for unset or absent mood. Preserve existing purpose-based wardrobe and voice as separate creative inputs. Vehicle feedback remains a separate journey state. |

Use the following comparison with identical master geometry and a fixed seed per row. Use the same route motif within each row to isolate mood. Change the geometry in a separate pass to isolate route influence.

| Destination | Calm | Curious | Adventurous |
| --- | --- | --- | --- |
| City · warm lilac dot charm | Soft lids | Lifted brow | Focused brows, warm accent |
| Coast · blue-green wave charm | Soft lids | Lifted brow | Focused brows, warm accent |
| Mountain · moss ridge charm | Soft lids | Lifted brow | Focused brows, warm accent |

Verify that the eyes, forehead curl, badge, and number of limbs remain legible in all nine cells at 64 px and 128 px. If a dark accent disappears in the night theme, use the lighter semantic accent and keep the motif shape. Keep real coordinates local. The comparison uses synthetic inputs.

## Play one reveal with a stable final frame

Use the current WebView Canvas route and resize functions and keep the existing formation parser for compatible artifacts. Draw the original PNG as its own layer, with a separately drawn route, particles, and optional clipped silhouette. When the formation metadata is missing or incompatible, use the saved still or a short opacity reveal from an already loaded image. Never derive face keyframes from an unknown alpha contour. Transparent PNG/WebP can carry finished art. Use the existing Canvas renderer for the first implementation so the sequence needs no new player, inference, or image request once the still is loaded.

| Time | Visual | Easing and limits |
| --- | --- | --- |
| 0–0.7 s | Trace the normalized route into the stage. | Use arc-length progress and ease out near the destination. Show one leading point. |
| 0.7–1.5 s | Three to five soft points move from the trace into the reveal area. | Ease in and out. Fade the source route without redrawing a map on the body. |
| 1.5–2.5 s | A rounded outline forms and reaches the saved illustration's bounds. | Use smoothstep for scale and opacity. Limit silhouette clipping to verified geometry. |
| 2.5–3.5 s | The route and lights clear as the same character becomes fully visible. | Use a short eased mask or fade. Keep the baked face intact. Include a blink only if an approved layered expression is available. |
| 3.5–4.3 s | Show the name and a settled still. | Remove all particle layers. Draw the final still once and stop scheduling frames. |

Start only on an eligible foreground parked screen after the asset is ready. Loading uses a static status with immediate feedback. Skip and reduced motion show the final still immediately. When eligibility is lost, cancel animation and clear transient effects before drawing again. If the platform hides Studio, respect that and restore the still on the next eligible entry. Apply the same cancellation rule to native reactions even if the emotion is unchanged. Resizing, relaunching, leaving the app, or re-parking does not replay a completed or interrupted reveal. The reveal is proposed for pre-departure only in the first proof. A later post-arrival reveal can use the same gate. [Project timeline](../NUNTI_DESIGN_CONTRACT.md) · [Pleos driving safety](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline)

## Map the Figma frames to the existing app

Start with the official Pleos design and display kit. Create native components, auto layout, and semantic variables inside the official application area. Match the measured 1,682 × 1,210 dp app region first. Add narrow app-window, night, and keyboard-visible frames based on the kit and the actual emulator. Keep the Driving view, system status, and Global Navigation Bar in the reference frame as platform-owned areas. This audit produced a layout brief. No editable Figma file was requested for this stage. [Pleos display layout](https://document.pleos.ai/en/docs/connect/guide/docs-design/getting-started/layout) · [Multi-window behavior](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/app-structure-screen-model) · [Official design kit](https://document.pleos.ai/img/Pleos_Connect_design_assets_215.fig) · [Official display kit](https://document.pleos.ai/img/Pleos_Connect_display_guide_215.fig)

| State | App-owned hierarchy | Existing integration point |
| --- | --- | --- |
| `PRE_TRIP` | Destination and source, confirmed route preview, then one creation action with the missing prerequisite shown inline. Put import alternatives in a parked secondary area. | Studio form, `setRoute`, and `enableCreate` |
| `REVEAL_PARKED` | Character and Skip while playing. Character, name, and primary journey-start action after settling. Group voice, artifact details, and route receipt below. | Studio result section and `birthAnimation` with native parked gate |
| `DRIVING_RESTRICTED` | Where the app category permits display, use the still and one brief status. Keep actions limited to the approved category and restriction flags. Creation, collection, detailed score review, and decorative motion require parked eligibility. | `JourneyActivity`, `JourneyCompanionView`, and `CarUxRestrictions` binding |
| `POST_TRIP` | Lead with character, trip outcome, and coverage. Place report evidence in its own scroll region. Open the existing gallery as a separate parked destination, with no creation step strip. | Native report state and Studio collection |

| Variable group | Initial design rule |
| --- | --- |
| `surface`, `text.primary`, `text.secondary` | Use Pleos day/night roles. Verify app text and icon pairs at 4.5:1 or better. Pair status color with words or a symbol. |
| `type.title`, `type.body`, `type.label` | Use Pleos typography and Korean glyphs. Use 18 px actual rendered height as the initial supporting-text review target, then check physical size and reach in the vehicle layout. |
| `space`, `radius`, `touch.target` | Take spacing and shape from the imported components. Use the official button and spacing metrics at actual density. Measure hit regions and focus order in both window widths. |
| `character.accent`, `effect.opacity` | Map destination accents independently of text contrast. Set effect opacity to zero in the settled and restricted states. |

[Pleos color roles](https://document.pleos.ai/docs/connect/guide/docs-design/foundations/colors) · [Pleos typography](https://document.pleos.ai/en/docs/connect/guide/docs-design/foundations/typography)

## Stage 2 acceptance

- Use one saved synthetic route and the same PNG for both directions. Review actual paused frames at the trace, gathered light, silhouette, reveal, and final still. Compare the still against the direct rendering of the original PNG.
- Exercise completion, Skip, reduced motion including a setting change, backgrounding, app loss and return, viewport resize, and parked-to-restricted-to-parked transitions. Use the actual restriction feed and Virtual Console without relaxing policy. Confirm no frame scheduling after settlement, no ineligible start, and no animation restart on return. Test a native restriction change while the emotion stays constant.
- Exercise missing route, unknown destination, absent mood, local media available while offline, missing and corrupt media, provider artifacts without formation, pending and failed generation, and reroute. Confirm explicit status, neutral fallback where applicable, and unchanged stored character and voice hashes.
- Capture matching Figma and Pleos frames at wide and narrow bounds in day and night modes. Check Korean text, contrast, TalkBack or equivalent focus, touch regions, overflow, and keyboard overlap.
- Profile on Pleos with the current baseline as the comparison. Start with the contract's 30 FPS target during the reveal. Record frame times, CPU, bitmap memory, and allocation behavior during the reveal, at rest, and over repeated plays. Confirm the static state releases animation work.
- Update the navigation UI test harness to match the existing startup DOM before relying on it for regression coverage. Keep the historical LIVE and navigation movement checks separate from the redesign proof.

Start with a parked reveal proof using Direction A and the saved artifact pipeline. Compare both art directions against the same 64 px identity and wide/narrow frames, then choose the master and direction before changing the generation renderer.

