# NOSFX Lightning Replacement — Research Record

## Correct target

The red NOS ribbon in the tested Pustaka APK is **not a DDS/PNG texture**. It is produced by the custom `nosfx::kShader` HLSL source embedded in `lib/arm64-v8a/libmain.so`. The original shader declares no `Texture2D` or `SamplerState`; it computes the red core, glow, coverage and cutout procedurally. Replacing an unrelated XBE texture through Mod Loader will therefore not replace this effect.

Verified source:
- APK SHA-256: `222da4e42a2c14bba5adf44df1539964b9809a0a4f44c8b688f944503f8d49bc`
- `libmain.so` SHA-256: `9cea9cc3767d8cb0a72cad33a44edf68a66daecd75104ddd1032a17b55e9c906`
- `nosfx::kShader` pointer object VA: `0x1D5C0A0`
- Source string VA/file offset: `0x53CF5E`
- Original shader source length: 2,343 bytes

The source string is loaded by `host::VulkanGpuLoad` and compiled by the app's Vulkan shader compiler with vertex entry `vs` and pixel entry `ps`.

## Verified rendering chain

1. `streetlight::UpdateNosTrail` obtains the active player's current car transform.
2. It transforms two runtime model-space vectors (global fields at `0x1D7DD08` and `0x1D7DD68`) through that car matrix.
3. Those two world-space endpoints are passed to `nosfx::History::Update` with the NOS-active state.
4. `nosfx::History::Mesh` converts the history into the ribbon mesh.
5. `streetlight::BuildNosTrail` gates the custom trail option and builds the mesh.
6. `d3d::DrawNosTrail` submits the custom mesh through the Vulkan backend using `nosfx::kShader`.

The two endpoint values are runtime state, not a verified constant pair in the XBE. Preserve them for a visual-only replacement. Do not hardcode approximate offsets such as `(-0.85, 0.65, -2.10)` without a separate live marker check. Static analysis alone does not prove that the two points numerically coincide with the vehicle's brake-lamp markers.

## Safe replacement strategy

Change only the pixel-shader body in `nosfx::kShader`:
- Keep the existing vertex shader, `ATTR0/ATTR1` inputs, `SV_Position` and `TEXCOORD0` interface.
- Keep the existing ribbon mesh, two endpoints, history sampling, NOS activation and Vulkan draw path.
- Keep the existing width/taper/age coordinate contract and `ONE / ONE_MINUS_SRC_ALPHA` blend semantics.
- Replace the red core/halo/cutout with a narrow bright yellow-white jagged core, branching yellow filaments and a warm additive glow.
- Do not touch the global Vulkan shader pipeline, other particles, motion blur, NOS drain or vehicle physics.

A procedural shader is the lowest-risk option because the current pipeline has no NOS texture sampler. Using the exact external PNG would require adding a texture resource, binding it to the NOS draw state and changing descriptor/resource handling; simply adding a DDS to a Mod Loader pack is insufficient. No lightning image/texture asset is tracked in the relevant repository branches.

## Candidate validation completed

The candidate keeps the same vertex/pixel entry points and descriptor-free interface. The patch validator pins the exact source APK and native library hashes, checks the `nosfx::kShader` relocation, writes the shorter candidate into the existing 2,343-byte source slot, NUL-pads the remainder, and verifies every other `libmain.so` byte is unchanged.

A prior CI validation using glslang 16.2.0 and SPIR-V Tools passed:
- Original and candidate vertex shaders compile and validate.
- Candidate pixel shader compiles and validates.
- Vertex SPIR-V is byte-for-byte identical.
- Pixel shader input/output location and built-in decorations match.
- Candidate adds no image, sampler or descriptor binding.

An exact glslang 16.0.0 build/validation is being checked separately. These are static/compiler checks, not proof of the final in-game appearance. Final visual confirmation still requires running the patched APK in-game.

## Incorrect path to avoid

The earlier `feature/lightning-particle-mask-v4` / `lightning_aura.cpp` path intercepts `NativeSpeedStreak` / `CARFX_NOS_BLOWOFF` (the separate white/green aerodynamic streak). It is not the red custom `nosfx` ribbon. Do not use that path for this replacement.

## Installation/signature blocker

The Pustaka APK signer fingerprint is:
`ef83e4343cc57796523af29d250438fdfb0a26997771a61f4e99da8e52d8a5df`

The Windows build runner debug-key fingerprint is:
`cd575f9cbb440b0c3d3a005fc5437922d195c27b79bfe98c087c3ad5a15ddd22`

They do not match. No keystore/private-key file is tracked in the repository and the release-keystore secrets are unavailable. A patched APK signed by the current runner cannot update the installed Pustaka APK; it requires the original signing key or uninstall/reinstall. Do not publish it as an in-place update.

## Release gate

Do not call the implementation complete until:
1. Exact glslang 16.0.0 shader validation passes.
2. The patched native library passes ELF/symbol/relocation checks.
3. The final APK preserves every Pustaka DEX/asset entry except the intended native shader bytes, passes ZIP alignment and APK signature verification.
4. The user is warned about the signing mismatch before installation.
5. In-game screenshot confirms yellow lightning replaces the red ribbon and other effects remain unchanged.
