# NFS APK Texture Editor

Browser-based MVP to inspect APK archives and edit embedded PNG, JPG/JPEG and WebP assets.

## Features
- Scan APK ZIP entries and identify standard embedded images.
- Categorize images by filename heuristics and preview them.
- Replace an image; adjust brightness, contrast, sharpness and resolution.
- Apply a changed image to same-category assets with matching dimensions.
- Rebuild the APK archive while retaining untouched entries.

## Limitations
- Proprietary, encrypted or compressed NFS game archives such as ZZDATA16.BIN and ZDIR.BIN are detected only, not decoded or modified.
- Categories are heuristic and must be reviewed.
- APK rebuild invalidates the original signature. The output must be signed again before installation; signing is not implemented in this MVP.

## Run
Run `npm install`, `npm run dev`; create a production build with `npm run build`.
