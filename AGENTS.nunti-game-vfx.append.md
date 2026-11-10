## Nunti game VFX — non-destructive overlay rules

- Preserve the current Nunti app, backend, route-to-avatar mapping, skin assets, and UI navigation. Upgrade VFX only; reuse existing renderer/state machine.
- For visual-effects tasks, load `.agents/skills/nunti-game-vfx/SKILL.md` and its references, plus already-installed `$nunti-birth-motion`, `$nunti-identity`, `$nunti-route-variants`, `$nunti-pleos-ui` as applicable. Prefer pstack `principle-experience-first` and `principle-exhaust-the-design-space` if available.
- Use professionally authored, licensed effect sources first: Effekseer new CC0 samples, Kenney CC0, and compatible Lottie animations whose individual license has been checked.
- Do NOT treat an Effekseer `.efk` / `.efkefc` project conversion as a transparent sprite-sheet export. Recorder GUI may be needed; do not claim otherwise.
- No Rive free-tier splash. No extra game engine/new server/new app unless an actual blocker is demonstrated and approved.
- Different route themes must have different visual signatures, not a shared rotating ring recolored.
- Character's original 3D-toy charm and face remain clear. VFX must not replace character art or cover its face for sustained periods.
- Treat a real installed effect, playable within the existing APK, as the deliverable. Keep build/tests proportionate: a quick run and visual check, not a documentary/video pipeline.
- Respect Pleos driving restrictions; no attention-grabbing visual effects while driving, and use a static fallback where required.
