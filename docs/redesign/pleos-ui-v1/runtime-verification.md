# Pleos UI baseline verification

Captured on 2026-11-09 UTC, crossing into 2026-11-10 KST. These are screenshots of the existing installed app, before the Pleos UI redesign. They do not demonstrate an implemented redesign APK.

The production journey service receives actual D/30 km/h values and disables finishing, but the emulator visibly covers the app with "주행 중에는 사용할 수 없습니다." The same result remained after waiting for the compositor. A proposed Figma driving companion must therefore be labeled as a conditional design, separate from this observed platform block. No restriction was removed or overridden.

## Device and build

| Item | Observed value |
|---|---|
| Emulator | `emulator-5554`, existing `Nunti_Restore_2_1` AVD |
| Android user | 10 |
| Display | 2560 × 1440, 160 dpi |
| App bounds | `[853,90]–[2535,1300]`, 1682 × 1210 |
| Platform areas | Driving view left of x=853; top status area y=0–90; bottom navigation/climate area y=1300–1440 |
| Package | `ai.nunti.avatar.demo`, version `0.1.0-mock`, code 1 |
| Build | Existing debug APK, containing both production-source activities and separately labeled debug previews |
| APK SHA-256 | `05ae6bce7f2a0b6772346e5e81a2c2ab62bdfa0da4f221b851a8d79c5be6a567` |

The installed APK hash matches `android/build/app/outputs/apk/debug/app-debug.apk`. No rebuild or install was needed for this baseline. The previous birth-motion build had 10 passing unit tests; that result is historical build evidence, not a new UI regression suite. See [installed build evidence](baseline/installed-build.json) and [previous build report](../birth-motion-v1/runtime/build-report.json).

## Screen inventory

Every PNG below is a complete 2560 × 1440 emulator capture. Its matching XML records the actual Android UI hierarchy. The platform areas remain visible as reference and are not app-owned controls.

| State | Actual evidence | Meaning and limit |
|---|---|---|
| PRE_TRIP | [Production input](baseline/production-pre-trip.png), [XML](baseline/production-pre-trip.xml) | `AvatarStudioActivity` WebView, existing synthetic input, 107 stored characters. No generation submitted. |
| REVEAL_PARKED | [Production saved result](baseline/production-reveal-settled.png), [XML](baseline/production-reveal-settled.xml) | Existing 몽글콩 result rendered through `showArtifact(artifact, false)`. This is the settled result, not a fresh reveal or new character. |
| Result actions | [Scrolled production result](baseline/production-result-actions.png), [XML](baseline/production-result-actions.xml) | Shows the actual journey/voice controls below the first viewport. No voice preparation button was pressed. |
| REVEAL_PARKED debug reference | [Native motion at 2200 ms](baseline/debug-reveal-2200.png), [state](baseline/debug-reveal-2200.json), [XML](baseline/debug-reveal-2200.xml) | Separate `TransformationPreviewActivity`, approved A coast-curious layers. Actual parked gate allowed a deterministic seek. It is not integrated into the production Studio flow. |
| Active, parked | [Production companion](baseline/production-active-parked.png), [XML](baseline/production-active-parked.xml), [state](baseline/production-active-parked.json) | A temporary LIVE review journey with saved 몽글방울 image and no prepared audio. Muted through the real UI. |
| DRIVING_RESTRICTED | [Visible production block](baseline/production-driving-active.png), [XML](baseline/production-driving-active.xml), [state](baseline/production-driving-active.json) | Actual D, 30.000002 km/h, ACTIVE/LIVE, muted=true, canFinish=false. The screenshot shows the platform block; the hierarchy still contains the underlying Journey view. |
| POST_TRIP existing | [Original saved report](baseline/production-post-trip.png), [XML](baseline/production-post-trip.xml) | Existing 38-second LIVE report reopened without mutation. |
| POST_TRIP review | [New review report](baseline/production-post-trip-review.png), [XML](baseline/production-post-trip-review.xml), [state](baseline/production-post-trip-review.json) | The temporary review journey was finished after returning to P/0. Original latest report restored afterwards. |
| Connection failure | [Existing offline failure](baseline/production-connection-failure.png), [XML](baseline/production-connection-failure.xml) | The initially absent localhost Studio caused the existing recovery instructions to appear. |

Additional restriction captures, `production-driving-restricted-saved-report.*` and `production-driving-studio-blocked.*`, preserve the saved-report and Studio cases. Their screenshots also show the external block. Underlying Studio XML contains the app's parked-only instruction. Do not present those hidden nodes as visible driving UI.

## Actual restrictions

Parked `CarUxRestrictionsManagerService` reports `DO: false UxR: 0`. D/30 reports `DO: true UxR: 80`, hexadecimal `0x50`. [Driving CarUx dump](baseline/production-driving-active-car-ux.txt) and [final parked dump](baseline/final-car-ux.txt) retain the actual values.

The resumed activity during driving is `JourneyActivity`; its service continues receiving signals. The screenshot nevertheless shows the blocking overlay. The source manifest's `distractionOptimized` declaration did not prove visible availability in this device configuration. The exact platform eligibility cause was not diagnosed or changed. See [activity evidence](baseline/production-driving-active-activity.txt).

The first D screenshot was initially suspected to precede compositor settlement. A second limited run read the UI hierarchy first, waited another 1.2 seconds, and captured the same visible block. Original evidence remains in [first-transition](baseline/first-transition/). There is no claim that the companion is visible while driving on this emulator.

This preserves the policy described in the official [Pleos driving safety guide](https://document.pleos.ai/en/docs/pleos-only/vehicle-app-planning-guide/driver-distraction-guideline). App layouts must fit the application window and keep system status, driving view and GNB separate, as described in the official [display layout guide](https://document.pleos.ai/en/docs/connect/guide/docs-design/getting-started/layout).

## Visual observations for the redesign

- The Studio input screen puts navigation integration, API testing, route import and rendering mode controls alongside the main creation flow. The route preview and later controls extend below the first viewport.
- The saved-result screen gives the character a clear area, but the journey-start controls require scrolling. The native journey then changes typography and spacing substantially.
- The native companion and report use small labels and narrow information columns inside a large app window. The report's score, unavailable-signal rows and event list need stronger grouping and a more readable scale.
- Historical production characters differ from the approved A mascot used by the new debug motion. The redesign must distinguish migration of stored artwork from canonical assets; these captures do not authorize replacing saved images.
- The connection-failure screen exposes a developer command to the end user. A product recovery screen should communicate connection status and a clear retry action while keeping implementation instructions in diagnostics.
- Day mode was observed for the existing production screens. Production night styling, narrow-window layout, TalkBack behavior, measured contrast and the redesigned screens' runtime behavior are unverified here. Prior native motion night/resize tests apply only to that separate debug prototype.

## Reuse and data preservation

The verification reused the real launcher, Studio authentication, saved-artifact renderer, native bridge, `JourneyAssets.prepare`, `JourneyService`, actual mute/finish buttons and official Virtual Console. `JourneyAssets.prepare` performs GET requests for saved media and available feedback voice; it does not invoke generation.

The initial localhost server was absent and the ADB reverse tunnel was missing. The existing `run_avatar_generator.py` server function was started with paid images, local image model and external route API disabled, then the local tunnel was connected. The first reload exposed the connection-code dialog; reopening Studio let its existing native authentication complete. No server source was changed and no pre-existing server was terminated. The newly started offline Studio remains available for follow-up at localhost:8768, with PID 32423 at capture time. See [capabilities](baseline/studio-capabilities.json).

The temporary LIVE character was already saved as `nunti-bb48e374-03bd-4b14-b34c-733cc93f395b`. Its greeting audio was absent and each feedback-voice GET returned 404. The review began silently, then the real "음성 끄기" button set muted=true. No image/model generation, voice generation, paid API, route lookup, GPS replay or navigation destination change was requested. Review metadata and image identity are recorded in [review-character.json](baseline/review-character.json).

Two short review sessions are retained separately in the app's session files: `9301da92-ea2f-4403-921e-6f1f82abb214` and `58ce9660-2269-44a5-9b0e-8606c027946a`. The second exists only to resolve the screenshot timing concern. No existing collection item or report was deleted. Both review sessions were finished while parked. The app process was restarted only after its owned review ended, so an in-memory review snapshot could not shadow the restored original report.

The original `files/journeys/latest.json` was restored byte for byte, SHA-256 `a8aa8a5730f5278404b2317a5f871c6def568799f8a06faa408fe36193f99576`. [Exact original bytes](baseline/existing-last-journey-original.json) and [restoration proof](baseline/active-review-restoration.json) are saved.

## Final state and remaining verification

The emulator is back at P, 0 km/h, accelerator/brake/steering 0. All owned Console sessions are closed. Console activation also changed the climate power from the initial screenshot's on state to off; it was restored through the official HVAC endpoint, with both sides at 22°C and A/C on. [HVAC restoration](baseline/hvac-restoration.json) and the [final screenshot](baseline/restored-debug-final.png) show this restoration. Subsequent capture-script runs now preserve the observed HVAC power too.

The app window remains 1682 × 1210. The initial debug coast-curious LIGHT_TRAIL day screen is foreground at 4000 ms with readOnlyCapture=false, reducedMotion=false and actual gateAllowed=true. See [final native state](baseline/restored-debug-state.json), [window evidence](baseline/restored-activity.txt) and [Console evidence](baseline/final-console.json).

The repeatable active-state capture is [capture_active_review.py](baseline/capture_active_review.py). It requires the existing saved character, original report backup, installed debug APK and offline Studio; it does not build or modify production code. For this design task, compare Figma frames against these actual dimensions and baseline screenshots. Implemented-redesign parity, production driving eligibility and resource performance remain separate acceptance work. No fresh CPU or memory benchmark was run for this baseline.
