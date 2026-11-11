# Nunti Visual Data Contract — draft v0.2

**Status:** Design proposal, not a statement that Pleos SDK returns every field below. Confirm API support and permissions before implementation.

**Skin V2 scope:** [Skin System V2](redesign/SKIN_SYSTEM_V2.md) governs full outfits, head contours, facial features, accessories, and the in-app skin transformation. The v0.2 accent rules and timeline below describe the legacy variant system. Keep the RouteContext provenance and existing API compatibility rules for both systems.

**v0.2 direction:** The existing base Nunti transforms in response to the route, destination and explicitly selected mood. Nunti is present before, during and after the transformation. The base character must not disappear and be replaced by another character. This revision specifies future design work; it does not change existing implementation, stored assets, APIs or behavior. The example schema versions below remain `0.1` and do not prescribe an API migration.

## 1. Canonical character invariants

| Element | Rule |
|---|---|
| Identity | Same round compact body, recognizable asymmetric feature, fixed face anchors and eye-to-face proportions, and signature mouth |
| May vary by route/destination | Accent ornaments, tail or ear contour within the approved silhouette, route-inspired pattern, accent palette, and a small collectible badge |
| May vary by explicit mood | Expression within the fixed face geometry, eye highlights, restrained pose, and secondary accent color |
| Must not vary | Character identity, core body and silhouette family, asymmetric signature feature, face anchors, eye-to-face proportions, signature mouth identity, brand mark, and limb count |

Use the approved master character reference if available. Record its repository-relative path before implementing a variant. If no master is approved, label the reference or placeholder as provisional and do not treat it as an approved production asset. Do not auto-generate a new canonical character each run. Variants must remain recognizable as the same Nunti at small display sizes.

Transformation starts with the visible base character and changes permitted elements on that same character. Keep its body and face identifiable throughout every frame; effects must not fully cover them. Do not use disappearance, complete occlusion, a cut, or a dissolve to substitute a different character. Driving restrictions and safety take precedence over the animation: stop it when required and show an allowed static frame.

## 2. RouteContext — fields and provenance

```json
{
  "schemaVersion": "0.1",
  "routeId": "demo-route-001",
  "distanceKm": 32.0,
  "estimatedDurationMin": 46,
  "roadType": "mixed",
  "destinationCategory": "coast",
  "sceneryTags": ["water", "open-sky"],
  "userSelectedMood": "curious",
  "state": "parked",
  "provenance": {
    "distanceKm": "mock",
    "roadType": "mock",
    "destinationCategory": "mock",
    "sceneryTags": "mock",
    "userSelectedMood": "explicit-user-choice"
  }
}
```

- `destinationCategory`: `city | mountain | coast | nature | general | unknown`. This is an app-side category, NOT guaranteed NaviHelper SDK output.
- `roadType`: `urban | highway | rural | mixed | unknown`. Verify data availability. Don't hallucinate from destination text.
- `userSelectedMood`: `calm | curious | adventurous | bright | unset`. **Not** inferred from driving telemetry.
- `state`: `parked | driving | restricted | unknown`. Enforce platform restrictions, not merely a freeform app flag.
- Route coordinates can be sensitive; use sampled/reduced/anonymous data for external model calls or keep mapping local.

## 3. Deterministic mapping

For the same normalized inputs, mapping version and versioned seed, reproduce the same variant. A stable hash of (`schemaVersion`, `routeId`, `paletteVersion`) can supply the seed for ornaments and small variation. Include all mapping inputs and the mapping version in the reproducibility record. Prefer explicit values over inference; fall back to `general/unknown` without breaking composition. Example:

- destination `coast` → wave arc accent and blue-green detail
- destination `mountain` → gentle ridge accent and moss-teal detail
- destination `city` → dotted grid accent and warm lilac detail
- mood `calm` → relaxed eyelids, low-contrast secondary highlight
- mood `curious` → raised brow or ear, attentive expression within fixed eye geometry
- mood `adventurous` → determined yet friendly eyes, slightly bolder accent

Combine at most 1 destination motif + 1 route motif + 1 mood expression. Never clutter all three into the body.

## 4. AvatarSpec — runtime-ready output

```json
{
  "schemaVersion": "0.1",
  "characterId": "nunti-v1",
  "variantId": "nunti-v1-coast-curious-01",
  "seed": "a1b2c3",
  "baseAsset": "assets/avatar/master.png",
  "ornamentAsset": "assets/avatar/ornaments/wave.png",
  "expression": "curious",
  "palette": {
    "body": "#F1EEE8",
    "accent": "#77BED4",
    "highlight": "#F3DCA6"
  },
  "motion": "transform-coast-01",
  "accessibilityLabel": "여행의 푸른 물결을 담은 호기심 많은 눈티"
}
```

Assets and motion identifiers are design examples only: no files or runtime support are assumed to exist. They do not rename existing runtime values. A future renderer must use an approved static variant when available, or the base Nunti as a neutral fallback when a variant asset is missing.

## 5. Transformation timeline (design target; not an official Pleos specification)

| Interval | Event | Visual |
|---|---|---|
| 0.0–0.7 s | Start | Base Nunti is visible; a subtle route line approaches |
| 0.7–1.5 s | Apply route | Route-inspired accent develops on the same visible Nunti |
| 1.5–2.5 s | Apply destination | A destination ornament and accent color appear without covering the face or body |
| 2.5–3.5 s | Apply mood | An explicitly selected mood changes the expression within the fixed face geometry |
| 3.5–4.3 s | Settle | The same Nunti rests in the final static variant |

- Play once only when the current vehicle UX restrictions allow it and the state is parked/pre-departure/post-arrival.
- A Skip action must immediately show the final static variant if ready; otherwise show the base Nunti.
- Reduced-motion mode shows the final static variant immediately if ready, otherwise the base Nunti, with no decorative animation.
- When driving restrictions begin mid-animation, stop immediately and safely show an allowed static variant if ready, otherwise the base Nunti. Never relax platform restrictions to display it.
- Offline, loading, missing-asset and failure states retain an allowed static base Nunti when a variant is unavailable.
- Suggested frame rate: test 30 FPS baseline on Pleos emulator; tune to device actual resource/performance results.

## 6. Acceptance criteria

- Base, intermediate and final frames visibly retain the same canonical character; no character replacement or full concealment occurs.
- The same canonical character remains visually recognizable across a route × destination × mood comparison sheet.
- The same RouteContext + version seed reproduces the same AvatarSpec.
- No invalid SDK assumption masquerades as an available route field.
- Animation works offline with cached/local assets and can be skipped.
- Driving UI is non-animated while restrictions apply.
- For UI implementation, compare Figma screenshots with the emulator and check parked/driving transitions, loading and failure fallbacks, accessibility, contrast, visual scale, memory, CPU and smoothness.
