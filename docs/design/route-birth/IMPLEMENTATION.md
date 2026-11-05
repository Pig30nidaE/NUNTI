# Route-born companion implementation contract

2026-11-03. User intent: enter a destination and route, watch the actual route become a new companion, then continue with matching TTS. No external APIs/accounts/model downloads. Prior eight cases remain historical fixtures, not the new entry point.

## Chosen shape and alternatives

1. New APK per generated bundle: existing implementation, rejected because user cannot create a trip within the app.
2. Android inference: no compatible local engine is currently verified; not selected for this runnable iteration.
3. Native Android input/rendering plus a loopback PC worker: selected. Model remains offline on this Mac. ADB reverse connects the emulator to localhost. APK is installed once; each new trip fetches a generated artifact at runtime.

This is procedural continuous geometry derived from the entered polyline, not generative-image inference. Unique identity is guaranteed by request UUID and immutable storage. Different visible geometry is checked for real samples, not claimed mathematically unique across every possible trip. No road route/geocoding is fabricated. User draws the intended route in this version.

## Ownership

- PC: `prototypes/route_birth/` generator, HTTP loopback bridge, immutable input+artifact+WAV persistence, local Sohee model. No writes to previous journey_mvp or journey_voice_dynamic states.
- AVATAR: new `RouteBornSpec.kt` domain parser-independent geometry and `RouteBornCompanion.kt` Compose route-to-body animation. No edits to previous JourneyKeepsake.
- PM: `android/app/src/debug/kotlin/ai/nunti/app/routebirth/` input/job/client/storage/voice host, launcher/manifest integration, runner and delivery.
- QA: `prototypes/route_birth/verify_*`, independent actual runtime checks, no worker or host edits without coordination.

## Request and bridge

Listen only on 127.0.0.1:8766. `POST /v1/journeys` receives exactly `{requestId, destination:{name,traits}, purpose, route:{points:[[x,y],...]}}`. requestId UUID, name 1..60 UTF-16 units, traits 0..240, purpose 0..120; route 2..512 finite normalized [0,1] points, nonzero path. Android draws a route in normalized coordinates. Retry same requestId and same canonical input returns the same result, conflicting input returns 409. New trip allocates a new UUID. Coordinates are local drawing coordinates, not GPS, verified road facts, or geocoded routing.

Response: `{requestId,state,error?,artifact?}`, state `GENERATING|READY|FAILED`. `GET /v1/journeys/<requestId>` returns same shape. `GET /health` returns `{status:"ok",version:"route-born-1"}`. `GET /v1/journeys/<requestId>/audio/<audioPath>` only returns that committed manifest clip's WAV, no arbitrary paths. Error is a plain bounded string. A GENERATING response may include an artifact with visual/identity but no voiceManifest. READY includes the final voiceManifest. Single worker executes model work; HTTP remains responsive. Restart resumes incomplete jobs using committed raw input and exact validated clip hashes; corrupt committed data fails closed. Same request never changes identity/audio. No silent backend fallback.

## Artifact shape

`{schemaVersion:1, characterId:"route-<24 hex>", journeyId:<UUID>, inputSha256:<64 hex>, inputCanonical:<canonical normalized request JSON string>, displayName:<Korean name>, destinationName:<input name>, purpose:<input purpose>, visual:{version:"route-born-1",outline:[[x,y] x72],route:[[x,y] x72],palette:["#RRGGBB" x3],face:{cx:0.5,cy:0.43,scale:1.0,eyeSpacing:1.0}}, voice:{description:<Korean user facing description>,direction:<English model instruction>,bindingId:<id>,profileId:<id>,speaker:"Sohee"}, voiceManifest:<existing LocalVoiceManifest schema2>}`.

All visual coordinates normalized 0..1; closed radial body uses exactly72 ordered outline points, route resampled to72 ordered points, outline within .05.. .95. face.cx .5, face.cy .43, scale .8..1.1, eyeSpacing .85..1.15. Face ellipse bounds are kept within body. Continuous route length/turning/aspect signals and per-journey noise shape the silhouette, palette and ornaments. No bodyFamily/shapeId or lookup among the previous16 outlines. Voice direction derives from the actual generated body's roundness/tallness/palette warmth plus purpose/traits. One Sohee speaker with delivery variations, not a newly cloned speaker. Three clips: greeting, arrival, common. They reference the artifact's exact characterId/profileId and a sealed DirectedSohee source. Existing voice runtime is reused.

## Native experience

Destination + traits/purpose text and a gesture-drawn path. Create sends input once and shows that route tracing, morphing into its actual generated outline, then face and internal keepsake glow. It does not replay stored fixtures as new generation. Result includes listen greeting/common, arrive/listen arrival, stop and local collection. UI distinguishes voice preparing/ready/failed; never fake readiness. Foreground/P/known UX + quiet confirmation policies apply; all animation/interaction/speech hidden or cancelled when blocked. No auto speech. Input and created results persist locally; app restart restores selected companion/collection without changing identity and without automatic speech. Raw routes/destination are not written to public diagnostic logs.

## Proof required

Real new user inputs with visibly different routes and no APK rebuild; route points/outline/WAV identity joined. Fresh submission, repeated same request, conflicting retry, changed route same destination, missing route, worker failure/restart, app restart identity/collection, foreground/stop policies. Actual local model runs and emulator playback. Native screenshots at route draw/morph/result. Cuteness, collectibility and naturalness remain human review, not numerical approval. Preserve every previous report and app namespace.

Input join correction: artifact.inputCanonical is exactly the PC canonical normalized input JSON string. Android hashes that UTF-8 string, compares to inputSha256, parses it and compares every field/number/array with the app-private submitted input. Destination/purpose are also checked. Pending-to-ready may only add voiceManifest; all prior identity/visual/voice/name fields stay equal. This avoids Python/Java floating point serialization discrepancies.
