# Pleos emulator baseline

Captured on 2026-11-09 with Android `screencap -p`. The capture includes the full 2,560 × 1,440 display at 160 dpi. The Studio activity reported a 1,682 × 1,210 dp app area in multi-window mode, with bounds `(853, 90)–(2535, 1300)`. The Driving view, top status area, and bottom navigation belong to Pleos.

| Capture | Evidence |
| --- | --- |
| [Launch with Studio offline](2026-11-09-launch.png) | The launcher opened the installed app and the localhost connection failed. The screenshot shows the native fallback text. |
| [Pre-trip](2026-11-09-pre-trip.png) | Parked Studio opened against a fresh isolated store. No route was selected and generation was disabled. |
| [Parked reveal](2026-11-09-parked-reveal.png) | Mid-sequence frame of the actual WebView Canvas, after confirming a built-in synthetic city route. |
| [Parked result](2026-11-09-parked-result.png) | Same local-render character after the progress bar ended. The WebView still had an outstanding animation frame request. |
| [Collection](2026-11-09-collection.png) | The single synthetic character was present in the isolated collection. Opening it restored the original image SHA-256. |
| [Active demo journey](2026-11-09-demo-active.png) | Native journey view displaying the same character during the simulated recovery scenario. The emulator remained parked. |
| [Post-trip](2026-11-09-post-trip.png) | The native finish action completed the simulated journey. The saved report showed 75 points and 90% evaluated coverage. |

The initial ADB device list was empty. The captures use the saved `Nunti_Restore_2_1` AVD booted read-only with software graphics. The installed package was `ai.nunti.avatar.demo`, version `0.1.0-mock`, code 1. The installed and cached APKs matched at SHA-256 `318beecb49e4f50ee72b0e16a9fe55259aa3d753e9a2e0ff01c2aa0aa1613c49`. The APK was reused from the previous build. The WebView served the current checkout's Studio assets and backend code.

The audit ran Studio on localhost against a temporary store. The local renderer created one synthetic avatar for the captures. External image generation, local-model inference, external routing, and voice synthesis were unused. The saved AVD and original Studio collection were left intact.

The active and finished screenshots are DEMO evidence, not live-driving or simulator restriction-transition evidence. Narrow and night layouts, reduced-motion behavior on the actual platform, touch and accessibility, and timing and resource use remain unverified. For older restricted and narrow evidence, see the [archived runtime report](../../architecture/validation-evidence/pleos-runtime/manifest.json).

