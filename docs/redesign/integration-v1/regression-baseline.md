# Integration regression baseline

Observed on 2026-11-09 UTC / 2026-11-10 KST, on `codex/nunti-visual-integration`. These are automated regression results and a read-only device snapshot. They are not evidence that the new production UI has run on the emulator.

The initial [source snapshot](before-integration-source-state.json) records 45 file hashes. [Git status](before-integration-git-status.txt) preserves the pre-existing dirty and untracked state. Other agents began the authorized integration concurrently; subsequent reports record their own source hashes rather than treating this checkout as an immutable baseline.

| Check | Result | Evidence |
|---|---|---|
| Entire backend test suite | 395 passed; 104 subtests passed; one Starlette/httpx deprecation warning | [Log](regression-baseline/backend.log), [JUnit](regression-baseline/backend-junit.xml) |
| Score/session/live gate JVM tests | 18 passed in an actual rerun: 7 score, 8 journey, 3 gate | [Fresh Gradle log](regression-baseline/score-fresh.log), [Suite attributes](regression-baseline/score-results.json) |
| Original five Node UI suites | Four initially passed. Navigation failed during mock-DOM initialization, before a product assertion | [Initial results](regression-baseline/javascript-results.json), [Failure](regression-baseline/test_navigation_ui_state.log) |
| Navigation harness repair | Eight assertions pass after adding the existing parent node method and native parked callback | [Result](regression-baseline/navigation-after-harness-fix.log) |
| Integration JavaScript checks | Seven suites pass: five existing UI suites, production transformation controller, legacy formation | [Report](regression-js-pre-build/report.json) |

The score command first reported `UP-TO-DATE`; that log is retained, and the acceptance count uses the subsequent `--rerun` invocation. No Android app was installed for this baseline.

Harness changes preserve the existing behavior assertions. The native UI starts fail-closed, so the navigation fixture now explicitly reports its parked permission after initialization. The layer default assertion now reflects the user's approved A integration. Attribute-tolerant HTML matching permits the new accessibility attributes, while unavailable capabilities, missing route data, invalid rendering contracts and restriction cases remain checked. Existing collection/voice fixtures now include the DOM boundary used to close dialogs on permission loss.

The new [transformation state tests](../../../scripts/test_nunti_transformation_state.mjs) read all nine saved AvatarSpecs and verify actual packaged PNG bytes and SHA-256 checks. A deterministic clock covers timeline order, exact final-image identity, interruption, skip, reduced motion, deferred loading and capture permission. Canvas and image decoding are boundary stubs: pixel quality, GPU performance and actual Android permission delivery still require device verification. The tests exposed two issues corrected by the implementation owner: a stale base-loading failure could overwrite a newer result, and a malformed LOCAL_LAYERS object without `design` could throw instead of declining animation.

The repeatable runner is [verify_nunti_integration_regression.py](../../../scripts/verify_nunti_integration_regression.py). It runs isolated fixtures with offline SDK caches and strips provider API keys from child environments. It does not launch an app, restart a server, alter vehicle values or call generation services. Source snapshots before/after each run identify concurrent edits.

```sh
python3 scripts/verify_nunti_integration_regression.py
# --only backend|js|score selects one boundary.
```

## Read-only runtime observation

The connected device is `emulator-5554`, user 10, display 2560 × 1440 at 160 dpi. The app occupies `[853,90]–[2535,1300]`, 1682 × 1210. The initial foreground activity is the separate debug `TransformationPreviewActivity`; its [screenshot](baseline/before-integration-screen.png) must not be presented as production integration proof.

The official Console reports P, 0 km/h, accelerator/brake/steering 0, no browser session, and climate power on at 22°C. Actual CarUx is `DO: false UxR: 0`. The existing local Studio and Console both return HTTP 200; paid image generation, local image models and external route lookup are disabled. [Environment manifest](baseline/read-only-environment.json), [Console state](baseline/console-state.json), [Studio capabilities](baseline/studio-state.json) and [CarUx dump](baseline/car-ux.txt) retain the observations. No gear, activity, heartbeat, service or user preference was changed while collecting this snapshot.

## Pending acceptance

Production UI and animation must still be built and installed, then verified with actual CarUx callbacks, saved server assets, failure/offline conditions, day/night configuration, narrow app bounds, performance and final browser-decoded pixel comparisons. The earlier debug motion and Figma baseline results remain separate historical evidence.
