from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import io

from .drive_service import EXPORT_MIME_MAP, DriveService, extract_folder_id, is_google_doc, sanitize_filename
from .zip_jobs import ZipJobManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

ROOT_FOLDER_URL = os.getenv("ROOT_FOLDER_URL")
CREDENTIALS_PATH = Path(os.getenv("CREDENTIALS_PATH", "credentials.json")).expanduser().resolve()
TOKEN_PATH = Path(os.getenv("TOKEN_PATH", "token.json")).expanduser().resolve()
INCLUDE_SHARED = os.getenv("INCLUDE_SHARED_DRIVES", "false").lower() == "true"
DATA_DIR = Path(os.getenv("APP_DATA_DIR", ".web_downloads")).expanduser().resolve()

DEFAULT_ROOT_ID: Optional[str] = None
DEFAULT_ROOT_URL: str = ROOT_FOLDER_URL or ""
if ROOT_FOLDER_URL:
    try:
        DEFAULT_ROOT_ID = extract_folder_id(ROOT_FOLDER_URL)
    except Exception:
        DEFAULT_ROOT_ID = None

app = FastAPI(title="Study Materials Downloader", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

drive_service = DriveService(CREDENTIALS_PATH, TOKEN_PATH, include_shared_drives=INCLUDE_SHARED)
job_manager = ZipJobManager(drive_service, DATA_DIR)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "default_root_url": DEFAULT_ROOT_URL,
            "error": error,
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


def _error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/?error={quote(message)}")


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        logging.exception("Failed to cleanup temp file: %s", path)


@app.get("/download-file")
async def download_file_direct(root_url: Optional[str] = None, item_id: Optional[str] = None):
    target_id = item_id
    if not target_id and root_url:
        try:
            target_id = extract_folder_id(root_url)
        except ValueError:
            return _error_redirect("Please paste a valid Google Drive file URL/ID or folder URL/ID.")

    if not target_id:
        return _error_redirect("Please provide a Google Drive file URL/ID.")

    try:
        item = drive_service.get_item(target_id)
    except Exception:
        return _error_redirect("Unable to access that Drive link. Please check permissions and try again.")

    if item.is_folder:
        return RedirectResponse(url=f"/browse?folder_id={item.id}")

    temp_dir = (DATA_DIR / "single_file_downloads")
    temp_dir.mkdir(parents=True, exist_ok=True)

    download_name = sanitize_filename(item.name)
    temp_suffix = Path(download_name).suffix
    media_type = "application/octet-stream"

    if is_google_doc(item.mime_type):
        mapping = EXPORT_MIME_MAP.get(item.mime_type)
        if not mapping:
            return _error_redirect("This Google file type is not supported for direct download.")
        export_mime, extension = mapping
        media_type = export_mime
        if not download_name.lower().endswith(extension):
            download_name = f"{download_name}{extension}"
        temp_suffix = extension

    temp_path = temp_dir / f"{uuid4().hex}{temp_suffix}"

    try:
        if is_google_doc(item.mime_type):
            export_mime, _ = EXPORT_MIME_MAP[item.mime_type]
            drive_service.export_file(item.id, export_mime, temp_path)
        else:
            drive_service.download_file(item.id, temp_path, item.size)
    except Exception:
        _safe_unlink(temp_path)
        return _error_redirect("Failed to download this file. Please try again.")

    from starlette.background import BackgroundTask

    return FileResponse(
        temp_path,
        media_type=media_type,
        filename=download_name,
        background=BackgroundTask(_safe_unlink, temp_path),
    )


@app.get("/browse", response_class=HTMLResponse)
async def browse(request: Request, folder_id: Optional[str] = None, path: Optional[str] = None, root_url: Optional[str] = None):
    target_id: Optional[str] = folder_id
    if not target_id and root_url:
        try:
            target_id = extract_folder_id(root_url)
        except ValueError:
            msg = quote("Please paste a valid Google Drive folder URL or folder ID.")
            return RedirectResponse(url=f"/?error={msg}")
    if not target_id:
        target_id = DEFAULT_ROOT_ID
    if not target_id:
        return RedirectResponse(url="/")

    try:
        target_item = drive_service.get_item(target_id)
    except Exception:
        msg = quote("Unable to access that Drive link. Please check permissions and try again.")
        return RedirectResponse(url=f"/?error={msg}")

    if not target_item.is_folder:
        msg = quote("This link points to a file. Use 'Download Single File' on the home page, or paste a folder link.")
        return RedirectResponse(url=f"/?error={msg}")

    folder_name = target_item.name or drive_service.get_folder_name(target_id)
    breadcrumbs = path.split("|") if path else [folder_name]
    try:
        children = drive_service.list_children(target_id)
    except Exception:
        msg = quote("Unable to list this folder. Please check access and try again.")
        return RedirectResponse(url=f"/?error={msg}")
    return templates.TemplateResponse(
        "browse.html",
        {
            "request": request,
            "folder_id": target_id,
            "folder_name": folder_name,
            "breadcrumbs": breadcrumbs,
            "children": children,
            "path": path or "|".join(breadcrumbs),
        },
    )


@app.get("/api/list")
async def api_list(folder_id: str):
    items = drive_service.list_children(folder_id)
    data = [
        {
            "id": i.id,
            "name": i.name,
            "mimeType": i.mime_type,
            "size": i.size,
            "isFolder": i.is_folder,
        }
        for i in items
    ]
    return JSONResponse(data)


@app.get("/api/search")
async def api_search(q: str, page_token: Optional[str] = None):
    """Search for files by name across the entire Drive account."""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    try:
        items, next_token = drive_service.search_files(q, page_token)
    except Exception as exc:
        logging.exception("Search API failed for query=%r", q)
        raise HTTPException(status_code=500, detail="Search failed. Please try again.") from exc

    results = []
    for item in items:
        try:
            path = drive_service.resolve_path(item.id)
        except Exception:
            path = "My Drive"
        results.append({
            "id": item.id,
            "name": item.name,
            "mimeType": item.mime_type,
            "size": item.size,
            "isFolder": item.is_folder,
            "path": path,
        })

    return JSONResponse({
        "results": results,
        "nextPageToken": next_token,
    })


@app.get("/api/preview/{file_id}")
async def api_preview(file_id: str):
    """Stream file for preview. Supports images, PDFs, and Google Docs (exported to PDF)."""
    try:
        item = drive_service.get_item(file_id)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found or inaccessible.")

    if item.is_folder:
        raise HTTPException(status_code=400, detail="Cannot preview a folder.")

    # Determine content type and handle Google Docs exports
    content_type = item.mime_type
    is_export = False

    if is_google_doc(item.mime_type):
        # Export Google Docs to PDF/XLSX
        mapping = EXPORT_MIME_MAP.get(item.mime_type)
        if not mapping:
            raise HTTPException(status_code=400, detail="This Google Docs type cannot be previewed.")
        content_type, _ = mapping
        is_export = True

    # For PDFs and images, stream directly
    # For videos and other types, we'll return the file type info
    # so frontend can decide to use Drive viewer
    supportable_preview_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
    }

    # For non-previewable types (like videos), return a redirect or info
    if content_type not in supportable_preview_types:
        # Video or unsupported: return 406 and let frontend handle it
        raise HTTPException(
            status_code=406,
            detail=f"Preview not supported for {content_type}. Use Drive link instead."
        )

    # Stream the file from Drive
    def file_generator():
        try:
            if is_export:
                export_mime, _ = EXPORT_MIME_MAP[item.mime_type]
                for chunk in drive_service.export_file_stream(item.id, export_mime):
                    yield chunk
            else:
                for chunk in drive_service.download_file_stream(item.id, item.size):
                    yield chunk
        except Exception as exc:
            logging.exception("Preview stream failed for file_id=%s", file_id)
            raise HTTPException(status_code=500, detail="Failed to stream file.")

    return StreamingResponse(file_generator(), media_type=content_type)


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: Optional[str] = None):
    """Search page for finding files by name."""
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "q": q or "",
            "root_url": DEFAULT_ROOT_URL,
            "default_root_id": DEFAULT_ROOT_ID,
        },
    )


@app.post("/api/download-zip")
async def api_download_zip(request: Request):
    payload = await request.json()
    folder_id = payload.get("folder_id")
    folder_name = payload.get("folder_name")
    if not folder_id:
        raise HTTPException(status_code=400, detail="folder_id is required")
    job = job_manager.start_job(folder_id, folder_name)
    download_url = request.url_for("download_zip", job_id=job.job_id)
    status_url = request.url_for("job_status", job_id=job.job_id)
    return {"job_id": job.job_id, "download_url": str(download_url), "status_url": str(status_url)}


@app.post("/api/download-zip-selected")
async def api_download_zip_selected(request: Request):
    payload = await request.json()
    current_folder_id = payload.get("current_folder_id")
    items = payload.get("items") or []
    zip_name = payload.get("zip_name")
    folder_name = payload.get("current_folder_name")
    if not current_folder_id:
        raise HTTPException(status_code=400, detail="current_folder_id is required")
    if not items:
        raise HTTPException(status_code=400, detail="No items selected")

    normalized: list[tuple[str, str]] = []
    for entry in items:
        item_id = entry.get("id")
        item_type = entry.get("type")
        if not item_id or item_type not in {"file", "folder"}:
            continue
        normalized.append((item_id, item_type))

    if not normalized:
        raise HTTPException(status_code=400, detail="No valid items to download")

    job = job_manager.start_selected_job(
        current_folder_id=current_folder_id,
        items=normalized,
        zip_name=zip_name,
        current_folder_name=folder_name,
    )
    download_url = request.url_for("download_zip", job_id=job.job_id)
    status_url = request.url_for("job_status", job_id=job.job_id)
    return {"job_id": job.job_id, "download_url": str(download_url), "status_url": str(status_url)}


@app.get("/api/job/{job_id}")
async def job_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": job.message,
        "total": job.total,
        "completed": job.completed,
        "current_file": job.current_file,
        "downloaded": job.downloaded,
        "exported": job.exported,
        "skipped": job.skipped,
        "errors": job.errors,
    }


@app.get("/download/{job_id}.zip")
async def download_zip(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != "ready" or not job.zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP not ready yet")
    filename = f"{sanitize_filename(job.folder_name)}.zip"
    return FileResponse(job.zip_path, media_type="application/zip", filename=filename)
