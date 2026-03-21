# PDF Tools (Windows-first)

This repo now has two scripts:
- `merge_optimize_pdfs.py`: Merge per-folder PDFs and lightly optimize with pikepdf.
- `compress_max_pdfs.py`: Compress individual PDFs with lossless and aggressive (lossy) modes.

## Release

- GitHub release: [`PDF Tools GUI v1.0.0`](https://github.com/midhiman-dev/Utilities/releases/tag/pdftools-v1.0.0)
- Download binary: [`pdf_tools_gui.exe`](https://github.com/midhiman-dev/Utilities/releases/download/pdftools-v1.0.0/pdf_tools_gui.exe)

If you only want to use the Windows app, download the binary from the release above. Local source setup is only needed if you want to run from Python or build the executable yourself.

## GUI (MVP)
- A Windows desktop GUI wrapper implementation is under `src/pdf_gui/`.
- Launch it with:

```bash
python src/launch_gui.py
```

Run this command from the repository root (`pdfmerger`). You can also use `python -m src.pdf_gui`.

Current GUI capabilities:
- Quick actions for all existing CLI tools:
	- `merge_optimize_pdfs.py`
	- `compress_max_pdfs.py`
	- `xlsx_to_html.py`
	- `backlog_docx_to_excel.py`
- Form-based argument entry with validation for required fields and numeric types.
- Run/cancel support with live stdout/stderr log streaming.
- Persisted settings in `%APPDATA%\PdfMergerGUI\config\config.json`.
- Tool profiles in `%APPDATA%\PdfMergerGUI\profiles\<tool>\*.json` with import/export.

Notes:
- The GUI invokes tool logic in-process via shared callable CLI entry points.
- Source code follows a `src/` layout; launch GUI and CLI tools from the repository root with `python src/...`.
- CLI usage remains fully supported and unchanged.
- Cancellation is currently best-effort in GUI and not yet hard-stop for in-process runs.

## Packaging (Phase 3)

### Local Windows build (PyInstaller single-file EXE)

```powershell
./scripts/build_gui.ps1 -PythonExe .venv/Scripts/python.exe -Clean -BuildPath out/build -DistPath out/dist
```

Output:
- Single-file app: `out/dist/pdf_tools_gui.exe`
- Published binary is also available from `Releases/pdftools-v1.0.0`

Notes:
- Build script installs/updates packaging dependencies (`pyinstaller`) and project requirements from `requirements.txt`.
- The PyInstaller spec used by the script is `pdf_gui.spec`.

### CI build

- Workflow file: `.github/workflows/windows-gui-build.yml`
- Triggers: `workflow_dispatch`, pushes to `main`, pull requests.
- Artifacts uploaded:
	- `out/dist/pdf_tools_gui.exe`
	- `out/installer/*.exe`

## Installer (Phase 4)

Build installer from the existing GUI build output:

```powershell
./scripts/build_installer.ps1 -IsccExe iscc -DistPath out/dist -InstallerOutputDir out/installer
```

Installer notes:
- Inno Setup script: `installer/pdf_tools_gui.iss`
- Installer installs per-user at `%LOCALAPPDATA%\Programs\PdfToolsGUI` (no admin required).
- Uninstall preserves user config and logs (`%APPDATA%\PdfMergerGUI` and `%LOCALAPPDATA%\PdfMergerGUI`).

## Observability (Phase 5)

- Central rotating log file: `%LOCALAPPDATA%\PdfMergerGUI\logs\app.log` (with rollover backups).
- GUI menu actions:
	- `Help > Open Logs Folder`
	- `Help > Export Diagnostics...`
- Diagnostics ZIP includes:
	- Config and profiles from `%APPDATA%\PdfMergerGUI`
	- Logs from `%LOCALAPPDATA%\PdfMergerGUI\logs`
	- Environment metadata (`environment_info.json`)
- Global exception handling writes crash details to `app.log` and shows a user-facing error dialog.

## What merge_optimize_pdfs.py does
- Discovers subfolders under an input root (optionally recursive).
- Collects PDFs in each folder, merges them in a deterministic order, then tries to optimize/compress via `pikepdf`.
- Saves outputs to the chosen output directory using safe slugs based on folder names (lowercase, spaces to underscores, invalid filename characters removed).
- Falls back to the unoptimized merge if optimization does not reduce size or fails.

## Distribution & Transfer

To package this repo for transfer to another machine:

### Create clean source archive

From the repository root, run:

```powershell
./scripts/package_source_zip.ps1
```

This generates `pdfmerger_source_YYYYMMDD.zip` in the parent directory, which excludes:
- `.venv/` and `.vscode/` (local environment, regenerate on target)
- `out/` (build outputs, regenerate with `./scripts/build_gui.ps1`)
- `__pycache__/` and `.pyc` files (regenerated on import)
- `archive/generated/*` (pycache backups, not needed for transfer)

Included in the archive:
- Full source code (`src/`)
- Build scripts and specs (`scripts/`, `pdf_gui.spec`)
- Packaging config (`installer/`, CI workflows)
- Documentation and requirements

### Setup on target machine

After extracting the zip:

```powershell
cd pdfmerger_source_<date>

# Create fresh virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Test the GUI
python src/launch_gui.py

# Test CLI
python src/merge_optimize_pdfs.py --help

# (Optional) Build single-file PyInstaller package
./scripts/build_gui.ps1 -PythonExe .venv/Scripts/python.exe -Clean
```

## Setup (Local Development)
- Python 3.10+ recommended
- Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage: merge_optimize_pdfs.py (Windows examples)

```bash
python src/merge_optimize_pdfs.py --input "C:\\mydocs\\studymaterials" --output "C:\\mydocs\\studymaterials\\mergedpdfs"
```

Optional flags:
- `--recursive` Process all descendant folders instead of only immediate subfolders.
- `--sort {name,mtime}` Merge order for PDFs (default `name`, case-insensitive). `mtime` sorts by modification time.
- `--overwrite` Replace an existing output file (default: skip existing outputs).
- `--verbose` More detailed logs (DEBUG level).
- `--dry-run` Show planned work without writing files.

### Example commands
- Immediate subfolders, default name sort:

```bash
python src/merge_optimize_pdfs.py --input "C:\\mydocs\\studymaterials" --output "C:\\mydocs\\studymaterials\\mergedpdfs"
```

- Recursive, sort by modification time, overwrite existing outputs:

```bash
python src/merge_optimize_pdfs.py --input "C:\\mydocs\\studymaterials" --output "C:\\mydocs\\studymaterials\\mergedpdfs" --recursive --sort mtime --overwrite
```

- Dry run with verbose logs:

```bash
python src/merge_optimize_pdfs.py --input "C:\\mydocs\\studymaterials" --output "C:\\mydocs\\studymaterials\\mergedpdfs" --dry-run --verbose
```

## Behavior notes (merge)
- Optimization uses pure-Python `pikepdf` settings that enable stream and object stream compression. No external executables are called.
- If the optimized file is not smaller than the merged file, the tool keeps the original merged output instead (fallback).
- Each folder is processed independently; errors opening a particular PDF are logged and skipped without stopping the run.
- Safe writes: outputs are written to temp files and moved atomically to final filenames.

## Troubleshooting (merge)
- **Permissions**: Ensure you can read the input PDFs and write to the output directory.
- **Encrypted or corrupt PDFs**: These files will be skipped with a warning; the rest of the folder continues.
- **Existing outputs**: Use `--overwrite` to replace, or delete/rename the existing file.
- **Long or unusual paths**: Paths are handled with `pathlib`; wrap paths in quotes when they contain spaces.

---

## What compress_max_pdfs.py does
- Compresses each PDF in a folder (optionally recursive) into an output folder (`compressedfiles` by default).
- Modes:
	- `lossless` (pikepdf optimization only).
	- `aggressive` (rasterize pages to JPEG via PyMuPDF for maximum reduction; lossy and removes text searchability).
	- `auto` (default): try lossless; if not smaller or above `--target-mb`, fall back to aggressive.
- Per-file logging with original size, final size, percent saved, and mode used.
- Final summary of counts and total bytes saved.

### WARNING about aggressive mode
Aggressive mode rasterizes pages to images (JPEG). This is lossy and will likely remove selectable text/searchability. Use only when you need maximum size reduction.

## Usage: compress_max_pdfs.py (Windows examples)

Basic (default output to `<input>/compressedfiles`):

```bash
python src/compress_max_pdfs.py --input "C:\\yourpath\\pdffilestocompress"
```

Force aggressive mode with lower DPI/quality for smaller files:

```bash
python src/compress_max_pdfs.py --input "C:\\yourpath\\pdffilestocompress" --mode aggressive --dpi 120 --jpeg-quality 60 --grayscale
```

Auto mode with target size (run aggressive only if still above 2 MB after lossless):

```bash
python src/compress_max_pdfs.py --input "C:\\yourpath\\pdffilestocompress" --target-mb 2 --mode auto
```

Process subfolders and overwrite existing outputs:

```bash
python src/compress_max_pdfs.py --input "C:\\yourpath\\pdffilestocompress" --recursive --overwrite
```

Dry-run with verbose logs:

```bash
python src/compress_max_pdfs.py --input "C:\\yourpath\\pdffilestocompress" --dry-run --verbose
```

## Tuning guidance (aggressive mode)
- `--dpi`: Lower DPI reduces size; 150 is a good balance, 120/100 for smaller files, higher for better readability.
- `--jpeg-quality`: Lower quality shrinks size but increases artifacts. Stay between 40-85 (default 70).
- `--grayscale`: Reduces size further for mostly text/line-art PDFs.
- `--max-pages`: Limit pages during testing to gauge output quality/size quickly.

## Behavior notes (compression)
- Lossless stage uses pikepdf; aggressive stage uses PyMuPDF to render each page and rebuild the PDF.
- Outputs are written via temp files then atomically replaced.
- If both stages fail, the original PDF is copied to output and a warning is logged.
- Encrypted/corrupt PDFs are logged; processing continues for others.

## Troubleshooting (compression)
- **Encrypted PDFs**: If a PDF requires a password, the tool logs a failure and copies the original (no password prompt is provided).
- **Corrupt PDFs**: Logged and skipped/fallback copy is used; other files continue.
- **Huge files**: Reduce `--dpi` and `--jpeg-quality`, and consider `--grayscale`.
- **Existing outputs**: Use `--overwrite` or clear the output folder.
