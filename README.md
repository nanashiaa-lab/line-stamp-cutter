# LINE Stamp Cutter

Windows desktop utility for splitting sprite sheets into transparent PNG stickers.

## Features

- Configurable grid splitting, manual crop adjustment, zoom, and background-aware auto-fit.
- Exports even-sized sticker PNGs (max 370 × 320 px), plus `main.png` (240 × 240) and `tab.png` (96 × 74).
- Creates `line_stickers.zip` with the images at the archive root.

## Run from source

Install Python 3.10+ on Windows, then run:

```powershell
py -3 -m pip install -r requirements.txt
py -3 line_stamp_cutter.py
```

## Build a standalone Windows app

Double-click `build_windows.bat`. It installs build dependencies and creates `dist\LINEStampCutter.exe`. The bundled app contains Python and Pillow, so end users do not need to install them.

## Notes

- Existing transparency is kept. Opaque flat or edge-connected checkerboard backgrounds are inferred and removed; unusual images should be checked after export.
- LINE's regular still stickers use 8, 16, 24, 32, or 40 images. PNG files must be even-sized, 72 dpi or higher, and at most 1 MB each. The ZIP must be at most 60 MB.
- Review the [LINE Creators Market sticker guidelines](https://creator.line.me/ja/guideline/sticker/) before submitting; requirements may change.

## License

MIT. See [LICENSE](LICENSE).
