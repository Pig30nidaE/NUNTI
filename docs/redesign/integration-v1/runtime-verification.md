# Production integration runtime verification

The production Studio transformation and native journey flow were exercised on the connected Pleos emulator. The final APK passed generation failure/retry, motion interruption, reduced motion, final-pixel and image-fallback checks. Actual day/night and narrow-window captures and a real production video are saved. Two limits remain: Pleos visibly blocks the app while driving, and Android frame timing remains poor despite a steady 30 Hz animation controller. This is not production performance certification.

## Final build and device

| Item | Verified value |
|---|---|
| Installed APK SHA-256 | `fe8781a6b5643a213f0cce7ba18cbbfb360a0567ba5094cfee4315f0e339565a` |
| Install | `adb install -r`; installed `base.apk` SHA matches the built file |
| Package | `ai.nunti.avatar.demo`, existing debug build containing production activities |
| Device | `emulator-5554`, Android user 10 |
| Physical display / app bounds | 2560 × 1440 / `[853,90]–[2535,1300]`, 1682 × 1210 |
| Final WebView | DPR 1.375; CSS 1683 × 1210; visual viewport scale approximately 0.727312 |
| Narrow app window | 830 × 1210 physical pixels, calibrated to approximately 830 CSS pixels |

The one-pixel CSS-width difference is Chromium rounding. The host passes its measured window dimensions to the viewport calibration; no OS density or reserved platform area was changed. Ten packaged HTML/CSS/JavaScript/font files matched their source bytes. See [installed build](installed-build.json), [build and app test log](optimized-package-build.log), and [final device state](final-device-state.json).

All acceptance captures use production `AvatarStudioActivity` or `JourneyActivity`. Debug transformation previews are excluded from this report's acceptance evidence.

## Verification results

| Boundary | Result and evidence |
|---|---|
| Backend regression | 395 tests and 104 subtests passed; isolated fixtures, no live model calls. See [baseline](regression-baseline.md) and the final backend results recorded by the integration owner. |
| Score/session/live gate | 18 JVM tests passed in an actual rerun: 7 score, 8 journey, 3 gate. [Result](regression-baseline/score-results.json). |
| App build | Final build and app tests passed. [Log](optimized-package-build.log). |
| JavaScript | Seven suites passed; the production transformation controller has 14 checks. [Optimized source report](regression-js-optimized/report.json). |
| Calibrated production Studio | 31 distinct checks passed across a preserved interrupted run and its continuation on the same calibrated APK. [Aggregate](calibrated-studio-aggregate.json). |
| Final APK generation and motion | 12 checks passed, including controlled POST 503, same-request retry, elapsed bounds, complete/skip/reduced, actual D interruption and dialog closure. [Report](runtime-optimized-final/report.json). |
| Final APK nine endpoints | Nine exact browser-decoded pixel comparisons passed, reusing saved records without new generation. [Report](runtime-endpoints-final/report.json). |
| Final APK display/lifecycle/video | Seven checks passed: actual night mode, actual narrow window, background/foreground, system reduced motion and recording. [Report](runtime-display-optimized/report.json). |
| Native LIVE journey | Six checks passed: existing bridge/service, silent review, real mute, actual driving gate, parked finish, original report restoration. [Report](runtime-journey/report.json). |
| Final native image fallback | Approved base and its accessibility explanation remain present after periodic emotion updates; original report restored exactly. [Report](runtime-native-fallback-final/report.json). |

These counts cover different boundaries and are not summed into a single test total. The first Studio run's early `state.avatars.length` observation was taken before collection loading completed; it is not used as a preservation count. The runner now reads the collection API directly before starting.

## Production screens and video

| State | Actual artifact | Scope |
|---|---|---|
| PRE_TRIP | [Day](runtime-studio-calibrated/02-pre-trip-ready.png), [night](runtime-display-optimized/night-pre-trip.png), [narrow](runtime-display-optimized/compact-pre-trip.png) | Existing synthetic route input; no navigation destination change or route API request |
| REVEAL_PARKED | [Final day](runtime-display-optimized/final-wide-day.png), [night](runtime-display-optimized/night-reveal.png), [narrow](runtime-display-optimized/compact-reveal.png) | Approved A, real server AvatarSpec, production Canvas controller |
| DRIVING_RESTRICTED | [Final APK block](runtime-optimized-final/04-driving-restriction.png), [native LIVE block](runtime-journey/02-driving-actual.png) | Actual Console D/30 and CarUx restriction; app content visibly covered by Pleos |
| POST_TRIP | [Day](runtime-native-final/01-post-trip-day.png), [night](runtime-native-final/02-post-trip-night.png), [narrow night](runtime-native-final/03-post-trip-compact-night.png), [narrow day](runtime-native-final/04-post-trip-compact-day.png) | Reopened previously finished, owned LIVE review; font/subtitle correction verified |
| Native image failure | [Final fallback](runtime-native-fallback-final/05-native-image-fallback.png), [XML](runtime-native-fallback-final/05-native-image-fallback.xml) | Controlled missing local image path; approved base and explicit accessibility explanation |
| Generation failure | [Loading](runtime-optimized-final/01-generation-loading.png), [503 recovery](runtime-optimized-final/02-generation-failure.png), [successful retry](runtime-optimized-final/03-retry-completed.png) | Controlled HTTP 503 before backend; not a real outage |

The post-trip layout captures precede the final fallback-description-only native correction. The final fallback screenshot verifies that correction in the same native layout. The final optimized day/night/narrow Studio captures include the final Canvas changes.

[Actual production motion video](runtime-display-optimized/production-motion.mp4) is 6.990 seconds long and includes a complete approximately four-second replay. It is a 2560 × 1440 device recording, not a storyboard or debug preview. The video was decoded with macOS AVFoundation; [metadata and tracks](runtime-display-optimized/video-frames-final/decoded-frames.json) and a [0–5 second contact sheet](runtime-display-optimized/video-frames-final/contact-sheet.png) preserve the inspection. The character stays visible while the pattern/accessory changes precede expression change. The recorder's approximately 49.35 fps nominal stream rate is separate from the animation controller's measured 30 Hz update rate.

## Pixel and motion identity

The nine coast/mountain/city × calm/curious/adventurous results were generated with the real `LOCAL_LAYERS` API and persisted with their actual AvatarSpecs. The final APK reused these records. For every result, its 4000 ms production capture equals a PNG made by decoding that result in the same WebView and drawing it on an equal-size canvas. Server source SHA values also matched during the calibrated Studio run. This proves final-image identity, not equality between browser PNG encoding and original server file bytes.

At 0/1000/2200/3000/4000 ms, all RGBA channels in protected body, limb, sprout, bag and silhouette areas were unchanged. Only explicitly variable face/scarf/pocket regions were excluded. [Production pixel report](production-pixel-verification.json) and [repeatable verifier](../../../scripts/verify_nunti_integration_pixels.py). The final backing-resolution optimization does not change this offscreen capture function; all nine endpoints were checked again on the final APK.

The actual skip control settles immediately. User and Android system reduced-motion preferences prevent replay and never cause automatic replay when disabled again. An explicit background transition into the existing navigation app stops the sequence; returning foreground stays static. Actual D/30 stops the animation and closes open dialogs, and P/0 return remains static. No permission override or synthetic `CarUxRestrictions` was used.

## Failure and offline behavior

The controlled POST 503 is injected with CDP at the request stage before reaching the backend. The UI returns to input with the approved base visible, retains all form values and the pending request ID, and sends that same ID on an explicit retry. The retry reaches the unchanged local renderer and succeeds. Both observed POST bodies specify `LOCAL_LAYERS`; no model or voice generation was requested.

A separate absent `/v3/assets/` URL exercises final-image decode failure and hides replay while showing the approved base. Offline emulation preserves the current final image. Reloading offline loads the APK-bundled shell and approved base and shows recovery UI. [Calibrated continuation evidence](runtime-studio-calibrated-continuation/report.json). This was network fault injection in the actual WebView, not termination of the user's server.

The native fallback uses a copy of an already-finished owned review with a deliberately nonexistent image path. It renders the packaged base. Its fallback explanation initially disappeared during emotion updates; the implementation owner fixed the description's ownership, and the final XML retains it. No original image or report was modified.

## Performance

The two observations below used nine warmed variant layers and no simultaneous recording. CPU values are process percentages against one virtual core; this emulator exposes four virtual cores. They are not percentages of the entire host machine.

| Observation | Before final optimization | Final optimized APK |
|---|---:|---:|
| Controller drawings in four seconds | 121 | 121 |
| Mean interval / update rate | 33.333 ms / 30 Hz | 33.333 ms / 30 Hz |
| Interval p95 / maximum | 33.4 / 33.4 ms | 33.4 / 50 ms |
| App PSS | 152.19 MiB | 146.17 MiB |
| Active process CPU samples | 41–56% | 37–56% |
| Android modern jank | 71.90% | 75.21% |
| Android legacy jank | 47.93% | 47.11% |
| Android frame p50 / p95 | 18 / 32 ms | 17 / 34 ms |
| GPU p95 | 17 ms | 17 ms |

[Raw comparison](performance-comparison.json), [final CPU](runtime-display-optimized/performance-top.txt), [memory](runtime-display-optimized/performance-meminfo.txt), [gfxinfo](runtime-display-optimized/performance-gfxinfo-unrecorded.txt), and [controller intervals](runtime-display-optimized/performance-motion.json). Canvas backing resolution now accounts for the actual viewport scale, redundant status/accessibility writes are avoided, and progress uses a transform. This reduced measured PSS by about 6 MiB in this observation. It did not establish smoother Android frame timing or substantially lower CPU. A real Pleos device profile remains necessary; do not label these jank results as a performance pass.

## Findings corrected during verification

- The initial WebView used 1224 × 880 CSS pixels inside the 1682 × 1210 physical app window, clipping the character and controls. Measured-window viewport calibration corrected it without changing OS density or platform chrome.
- The initial native subtitle clipped and its variable font appeared too light. Font axis selection and intro height were corrected; day/night/narrow screenshots verified the result.
- A stale failed base load could overwrite a newer result, a malformed layer contract could throw, and first RAF timing could briefly report negative elapsed time. Controller tests now cover these cases.
- The CDP transport once reported `Promise was collected`; the app had no observed crash. Verification now retains its awaited Promise until completion and removes its temporary handle. Only the unfinished Studio cases were repeated.
- The initial system-reduced restoration wrote the literal string `null` for an originally absent setting. The verifier now restores the observed enabled default, then removes the key; actual reduced=false and key absence are verified. This was a verifier restoration defect, not a product failure.

Failed/interrupted records remain in their original directories. Final acceptance uses the corrected runs explicitly linked above.

## Preservation and remaining limits

[Final device state](final-device-state.json) confirms installed APK identity, P/0, accelerator/brake/steering 0, no Console browser client, climate power on, day mode, 1682 × 1210 app bounds, native permission true, and no persisted user reduced-motion preference. `animator_duration_scale` is back to its original absent-key state. The original `latest.json` is byte-identical, SHA-256 `a8aa8a5730f5278404b2317a5f871c6def568799f8a06faa408fe36193f99576`. The local Studio remains running.

The final collection has 118 records. [Eleven identified local integration records](owned-local-records.json) are retained: the nine variant examples, one viewport-verification result and one successful controlled-failure retry. Existing characters were not deleted or replaced. One owned LIVE review was finished; later native tests only reopened its saved report. Original latest bytes were restored after every temporary report operation.

Driving-screen visibility remains blocked by the platform on this emulator. The underlying native service receives D/speed and disables finish, but this does not prove a visible driving companion. Actual TalkBack speech, elevated Android font-scale behavior and real-vehicle performance were not exercised; native/WebView labels, actual XML and normal-scale screenshots were inspected. No paid API, local image-model inference, voice generation, route API call or server rewrite was performed by these verification scripts.

## Reproduction

Use a new output directory for every run; runtime helpers refuse to overwrite an existing original-state backup. The scripts require the connected emulator, installed debug APK, existing local Studio and original finished report. Do not run them concurrently against the same device.

- [Regression runner](../../../scripts/verify_nunti_integration_regression.py): backend, JavaScript and score checks with source hashes.
- [Studio suite](../../../scripts/verify_nunti_integration_studio.mjs): actual generation, nine endpoints, controls, restrictions, offline and image failure. `--reuse` avoids duplicate records.
- [Final focused suite](../../../scripts/verify_nunti_integration_final.mjs): controlled generation 503/retry and final motion gates.
- [Native LIVE suite](../../../scripts/verify_nunti_integration_journey.mjs) and [saved-report suite](../../../scripts/verify_nunti_integration_native_saved.mjs): native states and exact report restoration.
- [Display/performance/video suite](../../../scripts/verify_nunti_integration_display.mjs), [nine-endpoint verifier](../../../scripts/verify_nunti_integration_endpoints.mjs), [shared device helper](../../../scripts/nunti_integration_runtime_lib.mjs).
- [Native video decoder](../../../scripts/verify_nunti_video_frames.swift): built-in macOS AVFoundation, no dependency installation.
