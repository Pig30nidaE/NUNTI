# Integration fixture provenance

Captured 2026-11-01 from active SERVER/AVATAR sessions, with explicit collaboration authorization.
These are Mock/generated examples, not vehicle telemetry or production user data.

- server-speech.json: root `contracts/v1/examples/SpeechRequest.valid.json` after emotion linking correction.
- server-profile.json: root `contracts/v1/examples/VoiceProfile.valid.json`.
- server-emotion.json: root `contracts/v1/examples/EmotionSnapshot.valid.json` (CONCERNED/emotion-worried).
- avatar-profile.json: AVATAR `/private/tmp/nunti-avatar/android/feature/avatar/build/reports/VoiceProfile.json`.
- avatar-emotion.json: same report directory `EmotionSnapshot.json`.
- avatar-spec.json: same directory `mock-seoul-city.AvatarSpec.json`.

The generated AvatarSpec and EmotionSnapshot are independent samples with different avatar IDs.
Tests intentionally reject joining them; a separate synthetic approved request uses the actual snapshot's identity.
No source sample is rewritten to conceal this mismatch.
`verify.py` parses these JSON files and feeds lossless Base64 property projections into Kotlin boundary tests.
