# Lightning Aura particle-follow masking v4

The production geometry API now accepts `ParticleLine` samples from the game's native white speed streaks.

- Native start/end positions are retained exactly.
- The filament direction and length follow the native streak.
- Only interior vertices are displaced into a sharp angular lightning profile.
- Native particle alpha and vehicle speed control brightness.
- The speed gate is 150 km/h, with full intensity at 500 km/h.
- Degenerate and non-finite samples are ignored.

## Integration contract

The game-side adapter must capture only the white high-speed streak draw data, convert endpoints to player-car-local meters using the same frame's vehicle transform, call `BuildParticleMaskVertices`, and submit the returned vertices with an additive yellow/gold material. It must suppress the original white line only when its yellow replacement is actually drawn.

## Verified boundary

This commit adds the geometry/masking API to the existing feature branch. It does not yet connect a native streak capture hook or a renderer draw pass. The current branch's game source documents the particle manager used for tyre smoke, sparks and crash debris, but that is not proof that the white speed streaks are emitted by the same draw path. No memory offsets or callbacks are guessed. Android APK integration remains pending the verified capture and render hooks.


## Renderer bridge added

The runtime now exposes a thread-safe `PublishNativeSpeedStreaks` / `CopyNativeSpeedStreaks` bridge. The existing foreground renderer no longer generates free-running bolts: it renders only when native streak samples are available, using the sampled endpoints as the mask source. The bridge accepts up to 256 valid samples and discards invalid/degenerate lines.

The capture hook itself is still not connected. This deliberately fails closed (no synthetic aura) until the native white speed-streak draw has been identified and its line endpoints can be converted into the player-car-local coordinate space.
