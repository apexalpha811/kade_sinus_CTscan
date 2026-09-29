# CT Scan Viewer

Browser viewer for the CT scan (CAT Face w/o contrast, 09/25/2026). Replaces the Windows-only
Carestream disc viewer, so it runs on a Mac (Safari or Chrome), Windows, or a tablet.

## Use
Open the site. The Bone series loads first. Pick any series on the left.

- Scroll wheel or arrow keys: change slice. Space: play. Slider under the image.
- Toolbar: Window (drag for brightness/contrast), Pan, Zoom, Measure (drag, shows mm), presets, Invert, Reset.
- Ctrl (or Cmd) + scroll zooms. Middle-drag pans. Right-click (Mac: two-finger click or Ctrl-click) opens the browser menu to save or copy the image.

## Layout
- `index.html`: the whole viewer, no build step, no dependencies (fonts load from Google Fonts).
- `manifest.json`: series and image index, generated from the disc by `tools/build_manifest.py`.
- `data/`: the original DICOM files, byte-identical to the disc (1,744 files, 1.2 GB).
- `vercel.json`: long cache headers for `data/`.

## Deploy
Import the repo in Vercel. Framework preset: Other. No build command, output directory is the repo root.

## Rebuild the manifest
```
python tools/build_manifest.py
```
Assumes uncompressed DICOM (Explicit VR Little Endian), which is what this disc uses.

## Limits
Not a certified medical device. Reads uncompressed DICOM only. For clinical decisions use a diagnostic workstation.
