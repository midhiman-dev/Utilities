# Local OCR CLI

An offline Windows-friendly command-line tool that extracts text from images using
[Tesseract OCR](https://github.com/tesseract-ocr/tesseract). It supports individual
images, batches of images in a folder, combined output, and multiple language packs.
No image data is sent to a cloud service.

## Requirements

The executable bundles Python and the Python packages, but **Tesseract itself is a
separate native dependency**. Install it before using the CLI:

- Windows: install a current build from the [UB Mannheim installer page](https://github.com/UB-Mannheim/tesseract/wiki), then add its install directory to `PATH`.
- macOS: `brew install tesseract`
- Debian/Ubuntu: `sudo apt install tesseract-ocr`

Install additional language packs if required. On Windows, these are `.traineddata`
files in Tesseract's `tessdata` directory.

## Use the executable

After building, run `dist\ocr-utility.exe` from PowerShell or Command Prompt:

```powershell
# Print text from one image
.\dist\ocr-utility.exe .\receipt.png

# Save one image's text
.\dist\ocr-utility.exe .\receipt.png --output .\receipt.txt

# Process every supported image directly in a folder
.\dist\ocr-utility.exe .\scans --output .\scans-text

# Combine a folder into one text file
.\dist\ocr-utility.exe .\scans --combine --output .\all-scans.txt

# Use installed English and Hindi language packs
.\dist\ocr-utility.exe .\receipt.png --lang eng+hin

# Inspect available language packs
.\dist\ocr-utility.exe --list-langs
```

If Tesseract is not on `PATH`, provide its exact executable location:

```powershell
.\dist\ocr-utility.exe .\receipt.png --tesseract-cmd 'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

`OCR_TESSERACT_CMD` can be set to the same value to avoid repeating the option.

## Develop locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
ocr-utility --help
pytest
```

## Build a distributable `.exe`

On Windows, after installing the development dependencies, run:

```powershell
.\scripts\build-exe.ps1
```

The single-file executable is written to `dist\ocr-utility.exe`. The build script
cleans only its own temporary PyInstaller work directories. Test the `.exe` on a
machine with Tesseract installed before releasing it.

## Supported image formats

`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`, `.gif`, and `.webp`.

Folder processing is non-recursive and uses deterministic filename ordering.

## Repository layout

```text
src/ocr_utility/     Application package (CLI and OCR domain logic)
tests/               Automated tests
scripts/             Release/build automation
pyproject.toml       Dependencies, package metadata, and command entry point
```

## Exit codes

- `0`: all requested OCR work completed.
- `1`: invalid invocation, missing input, unavailable Tesseract, or no usable images.
- `2`: one or more images could not be processed.

