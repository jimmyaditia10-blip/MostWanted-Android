# Lightning Aura particle-follow masking v4

The production geometry API now accepts `ParticleLine` samples from the game's native white speed streaks.

- Native start/end positions are retained exactly.
- The filament direction and length follow the native streak.
- Only interior vertices are displaced into a sharp angular lightning profile.
- Native particle alpha and vehicle speed control brightness.
- The speed gate is 150 km/h; intensity ramps linearly to maximum at 250 km/h.
- From 250 through 500 km/h (and above), intensity remains clamped at maximum; it does not keep increasing.
- Degenerate and non-finite samples are ignored.

## Integration contract

The game-side adapter must capture only the white high-speed streak draw data, convert endpoints to player-car-local meters using the same frame's vehicle transform, call `BuildParticleMaskVertices`, and submit the returned vertices with an additive yellow/gold material. It must suppress the original white line only when its yellow replacement is actually drawn.

## Verified boundary

This commit adds the geometry/masking API to the existing feature branch. It does not yet connect a native streak capture hook or a renderer draw pass. The current branch's game source documents the particle manager used for tyre smoke, sparks and crash debris, but that is not proof that the white speed streaks are emitted by the same draw path. No memory offsets or callbacks are guessed. Android APK integration remains pending the verified capture and render hooks.


## Renderer bridge added

The runtime now exposes a thread-safe `PublishNativeSpeedStreaks` / `CopyNativeSpeedStreaks` bridge. The existing foreground renderer no longer generates free-running bolts: it renders only when native streak samples are available, using the sampled endpoints as the mask source. The bridge accepts up to 256 valid samples and discards invalid/degenerate lines.

The capture hook itself is still not connected. This deliberately fails closed (no synthetic aura) until the native white speed-streak draw has been identified and its line endpoints can be converted into the player-car-local coordinate space.

## D3D8 adapter progress

- Capture is wired into both DrawVerticesUP and DrawIndexedVertices.
- The adapter accepts white diffuse XYZ line pairs and paired-edge triangle-strip ribbons, validates finite endpoints/alpha, and rejects degenerate or implausibly long samples.
- The mask is submitted with the native draw's current transforms, viewport and depth state. The white source draw is skipped only when the gold/white replacement draw is submitted successfully.
- This remains a format-filtered capture candidate, not yet verified against a live game trace. If the native speed streak uses a different vertex declaration or draw path, the filter will fail closed and leave the original effect untouched.
- The vehicle-speed publisher is still not connected to a verified Xbox vehicle-velocity source. No PC-only address or guessed Xbox offset is used. Therefore the 150–250 km/h intensity ramp (held at maximum through 500 km/h) cannot activate reliably until that source is mapped.

## Verification status

No Android build or in-game capture has been run for this adapter commit. Source integration is committed; runtime correctness remains unverified.


## Reference wind-trail visual pass

The captured native streak mask now emits three tapered filaments per accepted source line. The center filament remains anchored to the exact native start/end coordinates; two outer filaments fan out only through the interior and converge at both endpoints. This creates a wider, jagged lightning ribbon without changing the native draw transform or moving the vehicle-relative source positions. The D3D8 replacement draw stacks additive orange, gold, and white-hot color passes. The speed gate remains 150 km/h with full intensity at 250 km/h and a clamped plateau through 500 km/h. Runtime appearance still requires an Android build and in-game capture; the source change alone does not prove the target visual has been reached.


## Live rear-lamp geometry probe (Build #120 diagnostic follow-up)

The indexed draw hook now emits bounded `lightning-lamp-probe` records without changing rendering:
- draw metadata: primitive index count, stream stride, vertex declaration/FVF, pixel-shader handle, first two texture handles, and current world translation;
- up to 12 sampled indexed vertices per draw, including raw local XYZ and packed diffuse ARGB;
- the probe is observational only. It does not guess left/right lamp anchors, alter the world matrix, suppress draws, or move the aura.

For a runtime capture, enable the existing verbose/trace logging and record a short segment with NOS switched off, then the same view with NOS held on. Compare the draw records and local XYZ/color samples to isolate the two rear-lamp vertices. Only after those two live vertices are identified should the marker dots and aura roots be attached to them. The probe is bounded to 4096 indexed draw calls per process.


## Live two-point marker test

A temporary debug overlay is now drawn by the D3D8 native-streak replacement path whenever the measured speed is at least 150 km/h and at least two current native streak lines are captured.

- **Magenta cross**: start endpoint with the smallest local X in the current captured batch.
- **Cyan cross**: start endpoint with the largest local X in the current captured batch.
- Both crosses use the exact same world transform and render path as the native streak replacement; depth testing is disabled only for the crosses so they remain visible over the car body.
- `lightning-marker-debug` log lines include the frame number and both selected start/end coordinates.
- The marker points are selected from the current `DrawLightningParticleMask` input, not from the shared replay overlay cache. This avoids reading a previously published batch for this diagnostic.
- Test with NOS active and inspect whether the two crosses sit on the rear brake lamps. If they do but the gold ribbon appears to start behind them, compare the logged `start -> end` endpoints and frame values. If the crosses themselves miss the lamps, the source point/transform mapping is wrong and must be corrected before changing shader geometry.

This is a temporary diagnostic build. Remove the cross draw and its log after the marker transform has been verified.


## Static XBE source mapping (default.xbe SHA-1 f636a16af04171089f879a4bed646e185c734233)

- `0x000CE8B0` is the native particle-manager draw routine.
- Inside that routine, the particle resource ID is read from `[[[esi + 0x7C] + 8] + 0x98]` and resolved by `0x000C5900`.
- The XBE name table starts at `0x004699D8`. Its `CARFX_NOS_BLOWOFF` string pointer is at `0x00469A40`; the resolved runtime handle is stored at `0x00469A44`.
- The D3D capture filter now accepts white native geometry only while the current particle resource ID matches that resolved NOS handle. It preserves the original vertex coordinates and the native draw transform.

The resource identity is established statically from the XBE. Build verification remains pending, and the speed publisher still needs a verified Xbox source before the 150–250 km/h gate can activate.
