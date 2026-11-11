# Nunti current-state audit

2026-11-09 · Stage 1 · Working tree at `d42cefb` with in-progress journey integration changes

## Application and rendering paths

| Entry point | Implementation and ownership |
| --- | --- |
| App launcher | `MainActivity` opens the active native journey or the parked Avatar Studio. The source manifest declares the launcher and journey activity distraction optimized. The Studio activity has its own stricter parked gate. [Launcher](../../android/app/src/main/kotlin/ai/nunti/app/MainActivity.kt) · [Manifest](../../android/app/src/main/AndroidManifest.xml) |
| Creation, reveal, and collection | `AvatarStudioActivity` hosts the app UI in an Android WebView. The local Python service serves the HTML, CSS, JavaScript, authenticated avatar API, and media on `127.0.0.1:8768`. The WebView draws the route and reveal on Canvas 2D. The `prototypes/avatar_generator` directory supplies the shipped Studio UI through this server. [Activity](../../android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt) · [Studio UI](../../prototypes/avatar_generator/index.html) · [API](../../backend/nunti/avatar_studio/api.py) |
| Journey companion and report | The Studio bridge opens `JourneyActivity` and starts `JourneyService` with the selected character ID. The service owns the session, score, audio, and report. `JourneyAssets` reads the existing image and prepared audio, verifies hashes, and caches the files. The activity decodes the bitmap off the main thread and renders it in `JourneyCompanionView`, an Android View with a native Canvas. The image, name, and voice stay tied to the selected character. [Runtime and media](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyRuntime.kt) · [Service](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyService.kt) · [Native renderer](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyCompanionView.kt) |
| Older Compose paths | `NuntiAvatar` renders the v1 parts-based mock. Debug entries separately exercise `JourneyKeepsake`, `RouteBornCompanion`, and `GeneratedCompanion`. These are useful geometry and policy references. They are separate from the Studio-to-journey launcher path. [Avatar module](../../android/feature/avatar/README.md) · [Debug manifest](../../android/app/src/debug/AndroidManifest.xml) |

## How inputs affect the current avatar

| Input | Provenance | Current effect and fallback |
| --- | --- | --- |
| Destination name | User input, test preset, or directly imported from the NaviHelper 3.0.5 destination callback | The name is required. The app resolves known names first, then explicit place traits, place words, and a station-name suffix. The resulting place selects an accent and a destination keepsake. An unknown place gets a generic journey star. This classification is app-derived. |
| Destination traits | User-entered description or test preset | Text can supply a place hint and can affect the design theme. The app does not verify the presence of scenery on the driven route. |
| Route points | User-confirmed normalized 2D points. Origins are synthetic test route, route file, screenshot extraction, or an OSRM plan. | The current v3 request requires 2–512 finite points and explicit confirmation. Geometry such as flow, turns, and proportions drives design and motion. In the v6 illustration, route features feed the seed and influence ear lean and tail curl. Formation follows the route and lands on a contour derived from the final image. The current render keeps route ink off the character. Without a valid route, new generation is blocked and the UI can show a saved companion. |
| Route option, destination and location coordinates, route state, trip summaries, turn-by-turn | Direct NaviHelper callbacks and app bridge state | The adapter exposes snapshots and commands. It explicitly marks the full road polyline unavailable in its public SDK path. Trip route points are waypoint/destination summaries. Studio obtains independent geometry from OSRM when routing is enabled. OSRM distance and duration are provider fields shown in route review. The generator consumes normalized points, not those metrics or native route option. The Hyundai-selected route and OSRM line have unverified correspondence. |
| Destination category, road class, and scenery | Place labels are app-derived. Route road-class ratios and scenery are available as v1 mock fixture inputs. | Production v3 has no verified category field, road composition, or route scenery in the generation input. Normalized path shape cannot establish highway, mountain, or coastal road classification. Mock fixtures with “verified” in their IDs are internally verified synthetic data. |
| Visit purpose | User-entered free text or test preset | The app resolves an activity role, which sets wardrobe, props, actions, motion theme, and voice direction. Empty or unresolved text uses general travel styling. Purpose also feeds a separate design-intent field named `purposeMood`. The main v6 facial expression is seed-selected from five expressions, with some role-specific pose choices. |
| Explicit user mood | Absent in v3 `AvatarInput` and Studio controls | There is no calm/curious/adventurous selector. Purpose-derived art direction and the seeded expression are separate from explicit mood. |
| Vehicle events and driving feedback | `ScoreEngine` processes live Pleos input or a labeled demo scenario. `CarUxRestrictions` plus gear and speed control parked display eligibility. | The journey service maps scores/events to feedback states such as `NEUTRAL`, `WORRY`, `RELIEF`, and `JOY`. These change text and surrounding visual cues and may trigger prepared audio. They never enter the avatar-generation request. |

Source paths for the mapping are [v3 input model](../../backend/nunti/avatar_studio/models.py), [Studio request](../../prototypes/avatar_generator/studio.js), [native navigation adapter](../../android/app/src/main/kotlin/ai/nunti/app/navigation/PleosNavigationAdapter.kt), [OSRM route planner](../../backend/nunti/avatar_studio/route_api.py), [route design intent](../../backend/nunti/avatar_studio/design_intent.py), and [character planning](../../backend/nunti/avatar_studio/journey_art.py). Public API behavior and version caveats are documented by Pleos. [NaviHelper SDK 3.0.5](https://document.pleos.ai/en/api-reference/connect-sdk-pleos/NaviHelper/intro) · [NaviHelper events](https://document.pleos.ai/en/api-reference/connect-sdk-pleos/NaviHelper/event-listeners)

## Generation, storage, and reuse

1. Studio confirms a route and sends `POST /v3/avatars`. It reuses the pending UUID for the same unresolved submission. A deliberately new request gets a new UUID, so repeating a trip can yield a different character. The server claims the request, stores the response, and returns the same saved artifact for an exact retry.
2. `render_avatar` hashes the request UUID into its seed, then `build_design_intent` and `build_character_plan` apply the route and text. `render_character` draws the v6 Storybook PNG. The current metadata versions are `journey-character-3`, `purpose-wardrobe-storybook-4`, and `route-volume-2`.
3. `LOCAL_RENDER` outputs a 768 × 768 RGBA PNG. `LOCAL_MODEL` optionally sends a 512 px structure reference and a 256 px derivative of the base character sheet to a local FLUX model on the host. The backend validates and cuts out the result, then measures its alpha contour. `IMAGE_API` is separately approval- and configuration-gated. The server removes the local contour from those artifacts because it does not describe the provider image.
4. `StudioStore` stores owner-scoped JSON and content-addressed image bytes. Collection restoration reads the saved artifact. The journey receives that same image through its hash-verified cache. Voice preparation and playback have separate entry points and existing identities. The current Studio contract is v3. The repository's v1 `AvatarSpec` and v2 generation-job schemas document different paths.

Reuse the existing input confirmation and provenance, request reservation, `StudioStore`, authenticated media, collection restore, journey cache, score service, and voice bindings. The proposed redesign belongs at the visual-plan and presentation boundaries. [v3 endpoint](../../backend/nunti/avatar_studio/api.py) · [Storage](../../backend/nunti/avatar_studio/storage.py) · [Local renderer](../../backend/nunti/avatar_studio/illustration.py) · [Local model reference preparation](../../backend/nunti/avatar_studio/local_model.py) · [Journey integration](../architecture/integrated-journey.md)

## Character and variant inventory

| Group | Identified assets or variants |
| --- | --- |
| Current named reference | [`nunti-base-character.png`](../design/avatar-v6/assets/nunti-base-character.png) is a 1,254 × 1,254 RGB sheet of the hooded sprout character with a mint scarf, blue badge, and four poses. The score module calls it the base sheet and uses four expression crops. The active local-model code reads this same sheet as reference image 2. Formal master approval, editable layers, source/export record, and mascot asset licensing are unverified. [Score expression crops](../../android/feature/score/src/main/kotlin/ai/nunti/score/ui/NuntiFace.kt) |
| Studio defaults | The Studio opens with no route and an empty collection in a fresh store. Its three test routes are synthetic city, coast, and hills. They populate inputs and generate a new character on request. The native journey draws a placeholder while the selected image is missing or loading. [Test-route index](../../prototypes/avatar_generator/examples/index.json) · [Native placeholder](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyCompanionView.kt) |
| v1 procedural default | `nunti-v1`, `face-round-v1`, `body-bean-v1`, and `forehead-seed-v1`. Default `BASE` plus `CITY`, `JOURNEY`, `COASTAL`, and `MOUNTAIN` themes share fixed geometry. Four representative route fixtures show Seoul city, long journey, coast, and mountain. [Parts manifest](../../android/feature/avatar/src/main/resources/assets.properties) · [Contact sheet](../../android/feature/avatar/demo/nunti-contact-sheet.png) |
| Debug keepsake bundle | Eight named fixtures. 파도방울 (coast/rest), 이끼토리 (mountain/camping), 조각몽 (city/exhibition), 파도몽 (second coast trip), 숲토리 (forest/visit), 물빛콩 (lake/errand), 반짝별 (city/commute), and 보송몽 (unplanned). Its recipe library defines eight body families and sixteen shapes. [Packaged bundle](../../android/app/src/debug/assets/journey-mvp/bundle.json) · [Body shapes](../../android/feature/avatar/src/main/kotlin/ai/nunti/avatar/JourneyVisualSpec.kt) |
| Studio v6 procedural families | Bunny, bear, cat, otter, fox, pup, bird, seal, panda, deer, mouse, and penguin. These are generator families, with five facial expressions and thirteen activity roles. They do not represent twelve bundled default images. [Generator families and role choices](../../backend/nunti/avatar_studio/journey_art.py) |
| Studio collection before this audit | 107 saved characters in the readable local Studio database. All 107 PNG files match their stored size and SHA-256, and their hashes are distinct. Mode counts were 96 `LOCAL_RENDER` and 11 `LOCAL_MODEL`. Render-version counts were 23 `route-glass-local-1`, 28 `route-matte-local-2`, 30 `route-matte-clean-surface-3`, and 26 `purpose-wardrobe-storybook-4`. The `humanQualityApproved` flag was false on all 107 records. See the ID roster below. |
| Historical generated batches | v6 fast-render gallery has 200 illustrated cases, with ten separate same-input/new-journey controls. The local AI gallery has 30 selected cases from 37 actual matrix attempts. A separate beach reading case ran through the app. These are benchmark and integration sets with separate indexes. Their overlap with local saved collections has not been reconciled. [Local 200-case gallery](../../.local/avatar-v6/matrix/index.html) · [Ten controls](../../.local/avatar-v6/matrix/repeat-control/report.json) · [Local 30-case AI gallery](../../.local/avatar-v6/ai-matrix-selected/index.html) · [AI attempt selection](../../.local/avatar-v6/ai-matrix-selected/selection.json) · [Separate app case](../design/avatar-v6/RESULT.ko.md) |
| Historical experiments and art | The five procedural route-birth cases cover Sokcho coast, Daegwallyeong pasture, Seongsu Seoul Forest, North Seoul Dream Forest, and a separate hand-drawn UI trip. The earlier generated-PNG offline fixture reuses one coast image. The C luminous concept was selected as a direction. The v5 matte coast master was selected for implementation as a style reference. Approval of a canonical production rig remains unverified. [Route-birth cases](../design/route-birth/test-report.md) · [Generated fixture evidence](../design/generative-mvp/test-report.md) · [C art manifest](../design/journey-characters/asset-manifest.json) · [v5 style](../design/avatar-quality-v5/README.md) |

The local collection count covers the single accessible Studio database and excludes this audit's isolated test store. Local runs and saved stores on other machines are unknown. An inventory entry is a saved record or fixture, not a design approval.

## Existing animation

| Path | Current implementation |
| --- | --- |
| Waiting for an image | `waitingAnimation` in Studio loops an 1.8 s trace while the host allows display. Its 35% bar is fixed during this wait. The loop lacks a reduced-motion check. |
| v6 parked reveal | `NuntiFormation.prepare` validates formation metadata. `createRenderer` draws the traced route, deformation, expanding volume, masked image, and final PNG. `NuntiJourneyEffects` adds purpose-specific particles. The current reveal lasts 5.4 s and then continuously schedules a small idle float. Replay is present. Skip is absent. |
| Legacy and missing formation | The older 4.2 s route-fold/fade path is available for older or provider artifacts, and continues its idle loop at normal motion. Local-model artifacts without valid measured geometry show the original image directly. Valid measured geometry without a confirmed face anchor omits the intermediate face patch. |
| Parked policy | The native Studio gate checks foreground, gear P, speed near zero, and an unrestricted `CarUxRestrictions` reading. Loss of eligibility hides the WebView, cancels its frame loop, and stops Studio audio. Returning to an eligible result reopens the artifact as a still. Unknown vehicle state fails closed. |
| Native journey reaction | `JourneyCompanionView.setEmotion` can run an 850 ms animator when an active journey is parked. It retains the original image and uses cues around it and small pose offsets. The view checks Android animator settings and cancels on detach. The same-emotion early return can bypass cancellation when permission changes mid-reaction. See the [visual problems report](01-visual-problems.md). |

[Studio animation and gate callbacks](../../prototypes/avatar_generator/studio.js) · [Canvas formation](../../prototypes/avatar_generator/formation.js) · [Purpose effects](../../prototypes/avatar_generator/journey_effects.js) · [Native motion](../../android/app/src/main/kotlin/ai/nunti/app/journey/JourneyCompanionView.kt)

## Evidence and limits

Fresh captures use the installed Debug APK and a read-only Pleos AVD connected to a disposable localhost Studio store. The installed APK matched the cached build by SHA-256. Studio served the audited working-tree assets. See [the baseline record](baseline/README.md) for screenshots, build provenance, and the split between observed and unverified states.

The current Node formation, generation submission, and collection state suites passed. The navigation UI state suite stopped before its first assertion. Its mock `journey-button` has no `parentElement` for the current Studio startup code. This run cannot confirm navigation UI behavior. The 2026-11-05 historical integrated test also reports an overall failure. The demo report was saved, but LIVE timed out at the D/30 km/h condition before foreground navigation persistence could be checked. [Navigation test harness](../../scripts/test_navigation_ui_state.mjs) · [Historical integrated verification](../architecture/integrated-journey.md)

Figma parity, actual vehicle category and release approval, live restriction transitions, vehicle GPS movement, day/night, accessibility with assistive technology, and render/thermal performance remain unverified in this audit.

## Local Studio collection roster

The roster below comes from the read-only `characters` table in `.local/avatar-generator/studio.sqlite3`. It includes the generated display name, ID, render mode, and version. Trip text, location data, account data, and media contents are omitted.


<details>
<summary>107 saved Studio variants</summary>

| Render version | Mode | Generated name | Character ID |
| --- | --- | --- | --- |
| `purpose-wardrobe-storybook-4` | `LOCAL_MODEL` | 몽글방울 | `nunti-232697c0-0e92-435f-af34-b525dc7266ee` |
| `purpose-wardrobe-storybook-4` | `LOCAL_MODEL` | 몽글방울 | `nunti-30a9bb28-5578-474d-9519-6edfc5bf3d74` |
| `purpose-wardrobe-storybook-4` | `LOCAL_MODEL` | 몽글방울 | `nunti-bb48e374-03bd-4b14-b34c-733cc93f395b` |
| `purpose-wardrobe-storybook-4` | `LOCAL_MODEL` | 몽글콩 | `nunti-945833ab-63ed-4ce3-b4ba-83b8448f9d39` |
| `purpose-wardrobe-storybook-4` | `LOCAL_MODEL` | 몽글콩 | `nunti-d5451dd8-e6a1-4b8a-81bd-6c5e4463d0d6` |
| `purpose-wardrobe-storybook-4` | `LOCAL_MODEL` | 포말누리 | `nunti-3b02caf1-e363-40cc-bb99-a9a25e034e48` |
| `purpose-wardrobe-storybook-4` | `LOCAL_MODEL` | 포말포롱 | `nunti-fe640ad0-80b4-4ecc-9e82-dcf183bd1b81` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글누리 | `nunti-11995dab-f8fe-41d4-95b3-922890b52edc` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글누리 | `nunti-38a2d785-834b-4721-b63f-1b1d3b05beba` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글누리 | `nunti-56bd2ac4-3e54-4ec6-b13d-388271ce9926` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글누리 | `nunti-def59d34-1643-400e-89af-64498e9d06de` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글모리 | `nunti-400b49dc-a9a1-4120-b422-bbccf8841d0a` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글모리 | `nunti-b11d18c6-eb48-418d-8044-92cde3c32ab3` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글모리 | `nunti-d909400b-6d58-4085-af97-5a97309935a8` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글방울 | `nunti-596a9ebc-1f8b-4216-8ed3-bf3570a4749e` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글방울 | `nunti-f90330ab-dfb3-4217-8d96-de9ad111c084` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글콩 | `nunti-820fcc88-45a7-4aaa-a35f-3da675c98db6` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글콩 | `nunti-f6d2ba0b-73e1-483c-b33e-02218e21c977` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글포롱 | `nunti-4f16f483-27e8-4b10-b67d-b8d36c4a4c1a` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 몽글포롱 | `nunti-d9164893-7593-4a53-b817-751cad51f396` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 포말누리 | `nunti-158ef59f-3306-4d2b-ab38-8c23aa62d41b` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 포말모리 | `nunti-648568e2-e35f-4ddc-92a9-e76dc8f0c555` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 포말방울 | `nunti-422a4384-a09d-4a9f-a653-3f56596c0814` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 포말콩 | `nunti-6c423bb5-da66-4b37-bdb8-38be139772e2` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 포말콩 | `nunti-841fe469-29dc-403e-9022-5441fbf86136` |
| `purpose-wardrobe-storybook-4` | `LOCAL_RENDER` | 포말포롱 | `nunti-b4ce7f64-1dca-4cfe-8acd-2b3cf856d826` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬모찌 | `nunti-0650ea9c-2ba5-4afa-aefb-c5a061d9d78d` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬모찌 | `nunti-144893b3-b92d-4f5d-a311-e3bc0aeb1186` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬모찌 | `nunti-1eb2ac3e-e4ad-4e41-9f23-666d70f61a59` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬모찌 | `nunti-c3ffbe3f-b623-49b0-8b8f-c3f9ed708d4c` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬방울 | `nunti-0a965231-5bee-4706-9b4b-2c1baf357d11` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬방울 | `nunti-ab949aa7-9b6c-4346-9646-0890a964de07` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬콩 | `nunti-368cff0c-52a2-4814-8ace-6e55d12b2557` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬콩 | `nunti-9ad0b54c-5a69-41e5-a4ed-fbf90a16d401` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬토리 | `nunti-02a81cf1-4f72-4e2a-878f-1d0c5cd33d50` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬토리 | `nunti-094dc581-fdde-441e-b60a-ed9e45363e4f` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬토리 | `nunti-16e4f0a8-ae87-4cc1-81e2-84e6021bc7dc` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬토리 | `nunti-7a884710-f514-469d-a3ab-3b7ac1ad9c0e` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬토리 | `nunti-ae7a4f55-b503-4b0a-b600-23a44e01b6ea` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬토리 | `nunti-e5b3506d-dc8f-4f09-a660-8e8d96fb6986` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬포롱 | `nunti-28c1f611-a79c-4f64-8221-0826b4963efb` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬포롱 | `nunti-62e603c7-7e41-4aff-bf03-1cd6b300fd20` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬포롱 | `nunti-b0e29984-f9a7-4be5-998a-d090112ebaee` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬포롱 | `nunti-dcd59446-1aa7-4e2a-a5b3-281419c71a73` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬포롱 | `nunti-dd941243-7938-4313-bcce-838cebabd7bb` |
| `route-glass-local-1` | `LOCAL_RENDER` | 윤슬포롱 | `nunti-f8755548-847a-4ea5-b670-43e464f7289c` |
| `route-glass-local-1` | `LOCAL_RENDER` | 진주콩 | `nunti-a32ae5d9-447d-4d65-8ffe-2b1b3b8b004f` |
| `route-glass-local-1` | `LOCAL_RENDER` | 진주토리 | `nunti-bfc1bde9-0fae-4934-bace-e6774104d0b5` |
| `route-glass-local-1` | `LOCAL_RENDER` | 진주토리 | `nunti-e1ecfdec-9cc8-4349-ac89-0dda731b4a26` |
| `route-matte-clean-surface-3` | `LOCAL_MODEL` | 몽글모리 | `nunti-fe9822fc-98d6-4802-b135-24c4ec3c6718` |
| `route-matte-clean-surface-3` | `LOCAL_MODEL` | 포말누리 | `nunti-0a0ff413-987f-4aae-8c2f-a81e216824cb` |
| `route-matte-clean-surface-3` | `LOCAL_MODEL` | 포말포롱 | `nunti-aadf0cac-7a3f-56e3-8fd5-12c510eb969e` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 몽글모리 | `nunti-a0331552-0115-4f15-a853-57303be60af6` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 몽글모리 | `nunti-b49661b2-9f39-46d6-acd3-a2ba7a04f840` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 몽글콩 | `nunti-c238cc09-d62e-4c94-a431-625afae70931` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 몽글콩 | `nunti-d3539a72-4a5d-4c3b-8084-7c8d1452aa9f` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 몽글포롱 | `nunti-9a95bd5e-7b83-4d22-964f-81726cdf5e82` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 몽글포롱 | `nunti-b4867080-bf77-4b2d-be23-b44f1be80e12` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 새잎누리 | `nunti-7b3827b0-c4d5-402a-8f0f-acd6022c6d4f` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 진주누리 | `nunti-66249b92-28d8-4def-9cce-a5e76b11a5b3` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 진주누리 | `nunti-c188f7e9-1458-401b-9f62-4613d1de3763` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 진주모리 | `nunti-a6a71580-3b54-482c-894f-1e7c2495fc71` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 진주방울 | `nunti-4667ac76-d3be-4206-a817-3e338222000a` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 진주콩 | `nunti-17e9e38e-5889-4304-8fd5-cd503e2eb4a7` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 진주콩 | `nunti-eacdfdcb-1289-4a66-86ee-945941e34c22` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 진주포롱 | `nunti-3058ddc8-69d4-4199-9a6b-fd68fb77c668` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말누리 | `nunti-0cfa73a6-e552-45a0-b810-b6b0b056ca95` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말누리 | `nunti-c0a37f48-72af-46f3-8c7b-383d88601234` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말모리 | `nunti-741cf438-6dc5-45f6-8c92-60f8c7043d8e` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말모리 | `nunti-8325054c-c643-4657-9f24-85eaf65bb722` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말방울 | `nunti-29fbdd05-6b14-4e4e-8300-60b95512f6ed` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말방울 | `nunti-335b6dd2-5356-4326-aac0-e06cb1bd50fe` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말방울 | `nunti-47115160-1e42-4ec5-be0f-9e66caedaade` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말방울 | `nunti-bf1e4bc5-afec-46df-b8e0-a25bf5be1ea0` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말방울 | `nunti-c423b8aa-5baa-4a5e-bced-80b19cca02db` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말콩 | `nunti-473d0294-30f7-4413-b247-fd73964eed93` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말포롱 | `nunti-043362de-6167-461e-b47d-f0628ea95ccc` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말포롱 | `nunti-2f8e60a3-1549-44dc-88f4-fccd65788f85` |
| `route-matte-clean-surface-3` | `LOCAL_RENDER` | 포말포롱 | `nunti-bd513e07-e127-4aa3-bc98-63fe14f70b85` |
| `route-matte-local-2` | `LOCAL_MODEL` | 포말방울 | `nunti-c73d3ae5-e278-49ca-8cd3-5829676b14fe` |
| `route-matte-local-2` | `LOCAL_RENDER` | 새잎모리 | `nunti-0e67f3ed-b051-4024-8330-2a03c184712f` |
| `route-matte-local-2` | `LOCAL_RENDER` | 새잎콩 | `nunti-7c6e3350-afe1-4136-ae68-cf995a6d5ced` |
| `route-matte-local-2` | `LOCAL_RENDER` | 진주방울 | `nunti-4e4943f9-fbe8-438c-8fc8-862ccac3b296` |
| `route-matte-local-2` | `LOCAL_RENDER` | 진주방울 | `nunti-55534298-7980-4f5e-b431-8c04ceb9bb13` |
| `route-matte-local-2` | `LOCAL_RENDER` | 진주콩 | `nunti-4c243c7c-733d-49a1-a1f8-e894f45f0eac` |
| `route-matte-local-2` | `LOCAL_RENDER` | 진주포롱 | `nunti-bd0618c0-9914-4224-b102-3c55672343d2` |
| `route-matte-local-2` | `LOCAL_RENDER` | 진주포롱 | `nunti-be610dcc-2ca9-40ad-ae14-76335f117119` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말누리 | `nunti-0b7c5aa1-9321-43a4-bba8-8f475d2e4c02` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말누리 | `nunti-15eea28b-8fa4-462c-a139-de81e86e73a5` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말누리 | `nunti-4144cca6-4126-41e9-9796-81c9594c0676` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말누리 | `nunti-58ce9aa8-989e-48ce-bb81-8c89e6755112` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말누리 | `nunti-df95e79f-11b3-45ce-be8c-7ea0a914ac08` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말모리 | `nunti-34bb8d3a-6d3e-4e20-a90d-4d767774dedb` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말모리 | `nunti-45146faa-ddf1-43b3-b273-f7716513eb47` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말모리 | `nunti-60e43323-c039-4b6c-9e8c-6805aef85591` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말모리 | `nunti-6a9e3bfc-c0cc-4a7b-932d-0253cf9a22e3` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말모리 | `nunti-8a220927-3805-4163-9e33-3b6acaa615ac` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말모리 | `nunti-a091b5ff-c843-446f-90b3-c5a32fe0ce28` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말방울 | `nunti-98fe5c17-ad4b-4302-840c-a5103c4a112c` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말방울 | `nunti-9931e19c-451e-4b08-9d7e-641a4c756108` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말방울 | `nunti-e83c8654-275e-4357-bf93-76e04c743968` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말방울 | `nunti-f69b75bc-140c-48f6-aa8f-52f4461a66dd` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말콩 | `nunti-c9b62670-a8b0-4ef8-8c8d-09b59f0500fc` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말콩 | `nunti-cc69edac-ce3f-472f-89df-55bb9b19f54d` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말포롱 | `nunti-187491d5-d4a7-47ae-acac-87245cc75e99` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말포롱 | `nunti-c292c143-fc4a-45d8-8c07-4578a9d7e148` |
| `route-matte-local-2` | `LOCAL_RENDER` | 포말포롱 | `nunti-ea10a54c-b6cd-44b3-9aa2-c9525edf1e67` |

</details>
