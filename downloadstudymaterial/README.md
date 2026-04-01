# Study Materials Downloader (Web + CLI)

Interactive tools (web app and CLI) to browse a Google Drive folder tree and download any folder as a ZIP using the official Drive API v3 (read-only scope).

## Features
- OAuth2 installed-app/local-server flow with least-privilege `drive.readonly` scope
- Web app with kid-friendly UI (breadcrumbs, big folder cards, download buttons)
- **Global file search** - search for files by name across your entire Drive account with live results, type filtering, and batch download
- **File preview** - preview images (JPEG, PNG, GIF, WebP, SVG) and PDFs inline in a modal; Google Docs/Slides/Drawings auto-exported to PDF for preview; videos open in Google Drive's native viewer
- Direct single-file download from a Google Drive file URL/ID (including Docs/Sheets/Slides export)
- Download entire folder or only selected items (files and/or subfolders)
- Background ZIP jobs on disk (no in-memory ZIPs) with optional progress polling
- Google Docs export mapping (Docs/Sheets/Slides/Drawings → PDF/XLSX/PDF)
- CLI still available for terminal use (dry-run, overwrite, shared drives)

## Installation
1. Create/activate a virtual environment (recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Enable Drive API and create OAuth credentials
1. Google Cloud Console → APIs & Services → Library → enable **Google Drive API**.
2. APIs & Services → Credentials → **Create Credentials** → **OAuth client ID** → **Desktop app**.
3. Download the client JSON (e.g., `client_secret_423218255220-0iki1pqhi7t97gm6jhjq6k99qhab7h1m.apps.googleusercontent.com.json`).
4. Either rename it to `credentials.json` **or** pass the filename via `--credentials <path>` (CLI) or env `CREDENTIALS_PATH` (web app).
5. First run opens a browser for consent; refresh token is stored in `token.json` (configurable via `--token` or env `TOKEN_PATH`).

## Run the web app (FastAPI)
From the project root (`downloadmaterial`):
```
uvicorn app.main:app --reload
```
If you are already inside the `app` folder, run:
```
uvicorn main:app --reload
```
Env vars (optional):
- `ROOT_FOLDER_URL` – prefill the home page with a Drive folder URL/ID
- `CREDENTIALS_PATH` – path to OAuth client JSON (default `credentials.json`)
- `TOKEN_PATH` – path to token store (default `token.json`)
- `INCLUDE_SHARED_DRIVES` – `true` to include shared drives
- `APP_DATA_DIR` – where temp zips/files are written (default `.web_downloads`)

## Create a transfer ZIP (for another machine)
From the project root, create a clean development package that excludes secrets and machine-specific artifacts:

```powershell
.\package_transfer.ps1
```

Options:
- Extended package (default): includes README, templates, static assets, and `.gitignore`
- Minimal package:

```powershell
.\package_transfer.ps1 -Mode minimal
```

- Custom output folder/name:

```powershell
.\package_transfer.ps1 -Mode extended -OutputDir dist -ZipName study-materials-transfer.zip
```

The ZIP is written to `dist/` by default.

Steps for kids:
1. Open http://127.0.0.1:8000
2. Paste a Drive link (folder or file)
3. Choose one on the home page:
  - **Connect Folder** to browse and download folder content as ZIP
  - **Download Single File** to download one file directly
4. In folder browse view, choose one:
  - Press **Download this folder as ZIP** (whole folder)
  - OR tick checkboxes for files/subfolders, then **Download selected as ZIP** (only those)
  - OR click **� Preview** next to any image or PDF to view it without downloading
  - OR click **�🔍 Search** to find files by name across your entire Drive, filter by type (All/Files/Folders), select any results, and download them as a ZIP
5. Wait for the status message; the ZIP downloads automatically when ready

## CLI usage (still works)
```
python drive_folder_downloader.py \
  --root-url "https://drive.google.com/drive/folders/1-Gq6-6Xtuy1oa6aYUHBFUjANzo45tht6" \
  --out "C:\path\to\downloads" \
  [--credentials "credentials.json"] [--token "token.json"] \
  [--include-shared-drives] [--overwrite] [--verbose] [--dry-run] \
  [--zip-name "myfolder.zip"]
```

## File Preview

A **👁 Preview** button appears next to each previewable file in the browse and search views.

| File type | Preview method |
|-----------|----------------|
| JPEG, PNG, GIF, WebP, SVG | Inline image viewer in modal |
| PDF | Embedded PDF.js viewer with page navigation and zoom |
| Google Docs / Slides / Drawings | Auto-exported to PDF and shown in the PDF viewer |
| Videos (MP4, etc.) | Opens Google Drive's native viewer in a new tab |
| Other types | "Open in Google Drive" link shown in modal |

- Press **ESC** or click **Close** / the background overlay to dismiss the modal.
- The preview API endpoint `/api/preview/{file_id}` streams file content directly from Google Drive — nothing is cached on disk.

## Export behavior for Google Docs types
- Docs → PDF
- Sheets → XLSX
- Slides → PDF
- Drawings → PDF

## Public vs private folders
- Drive API still requires an OAuth client; sign-in may be skipped only if resources are public and the token already has access.
- If the folder requires permissions, ensure the signed-in Google account has access (add as tester if app is in Testing mode).

## Troubleshooting
- **Access blocked / verification**: In OAuth consent screen (Testing), add your account as a Test user or publish the app.
- **Auth popup not opening**: rerun and ensure a browser is available; delete `token.json` to re-consent.
- **403/404/429 or rate limits**: the tool retries with backoff; wait and retry.
- **Permission denied**: share the folder/file with the signed-in account or request access.
- **Windows path issues**: filenames are sanitized; use `--overwrite` or delete old outputs when rerunning.

## Notes
- Uses only the official Google Drive API; no HTML scraping.
- Scope is read-only; no writes to Drive.

## Publish to GitHub (safe setup)
1. Ensure secret files are **not committed**:
  - `credentials.json`
  - `token.json`
  - any `client_secret_*.json`
2. This repo includes a `.gitignore` that excludes secrets, virtual env, and generated downloads.
3. Initialize and push:

```bash
git init
git add .
git commit -m "Initial commit: Study Materials Downloader"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

If credentials were ever committed by mistake, rotate OAuth client secrets and remove them from history before publishing.
