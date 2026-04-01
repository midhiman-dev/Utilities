from __future__ import annotations

import io
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"
RETRIABLE_STATUS = {403, 404, 429, 500, 503}
EXPORT_MIME_MAP: Dict[str, Tuple[str, str]] = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}


@dataclass
class DriveItem:
    id: str
    name: str
    mime_type: str
    size: Optional[int]

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME


def extract_folder_id(url_or_id: str) -> str:
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]+", url_or_id):
        return url_or_id
    raise ValueError("Could not extract folder ID from input")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name)
    cleaned = cleaned.rstrip(" .")
    return cleaned or "unnamed"


def is_google_doc(mime_type: str) -> bool:
    return mime_type.startswith("application/vnd.google-apps") and mime_type != FOLDER_MIME


def backoff_sleep(status: Optional[int], attempt: int = 1) -> None:
    delay = min(2 ** attempt, 30)
    logging.warning("Retrying after status %s (sleep %ss)", status, delay)
    time.sleep(delay)


def load_credentials(credentials_path: Path, token_path: Path) -> Credentials:
    creds: Optional[Credentials] = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return creds


class DriveService:
    def __init__(self, credentials_path: Path, token_path: Path, include_shared_drives: bool) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.include_shared_drives = include_shared_drives
        creds = load_credentials(credentials_path, token_path)
        self.service = build("drive", "v3", credentials=creds)
        self._folder_name_cache: Dict[str, str] = {}

    def get_item(self, item_id: str) -> DriveItem:
        params = {
            "fileId": item_id,
            "fields": "id,name,mimeType,size",
            "supportsAllDrives": self.include_shared_drives,
        }
        resp = self._execute_with_retry(lambda: self.service.files().get(**params).execute())
        return DriveItem(
            id=resp["id"],
            name=resp.get("name", ""),
            mime_type=resp.get("mimeType", ""),
            size=int(resp["size"]) if resp.get("size") is not None else None,
        )

    def get_folder_name(self, folder_id: str) -> str:
        resp = self._execute_with_retry(
            lambda: self.service.files()
            .get(fileId=folder_id, fields="id, name", supportsAllDrives=self.include_shared_drives)
            .execute()
        )
        return resp.get("name", folder_id)

    def list_children(self, folder_id: str) -> List[DriveItem]:
        q = f"'{folder_id}' in parents and trashed=false"
        params = {
            "q": q,
            "fields": "nextPageToken, files(id, name, mimeType, size)",
            "orderBy": "folder,name,modifiedTime desc",
        }
        if self.include_shared_drives:
            params.update(
                {
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True,
                    "corpora": "allDrives",
                }
            )
        results: List[DriveItem] = []
        page_token: Optional[str] = None
        while True:
            if page_token:
                params["pageToken"] = page_token
            resp = self._execute_with_retry(lambda: self.service.files().list(**params).execute())
            for f in resp.get("files", []):
                results.append(
                    DriveItem(
                        id=f["id"],
                        name=f.get("name", ""),
                        mime_type=f.get("mimeType", ""),
                        size=int(f["size"]) if f.get("size") is not None else None,
                    )
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        results.sort(key=lambda item: (0 if item.is_folder else 1, item.name.lower()))
        return results

    def search_files(self, query: str, page_token: Optional[str] = None, page_size: int = 50) -> Tuple[List[DriveItem], Optional[str]]:
        """Search for files by name across the entire Drive account."""
        # Escape single quotes in the query for Drive API
        escaped_query = query.replace("'", "\\'")
        q = f"name contains '{escaped_query}' and trashed=false"
        params = {
            "q": q,
            "fields": "nextPageToken, files(id, name, mimeType, size, parents)",
            "pageSize": page_size,
        }
        if page_token:
            params["pageToken"] = page_token
        if self.include_shared_drives:
            params.update(
                {
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True,
                    "corpora": "allDrives",
                }
            )
        resp = self._execute_with_retry(lambda: self.service.files().list(**params).execute())
        results: List[DriveItem] = []
        for f in resp.get("files", []):
            results.append(
                DriveItem(
                    id=f["id"],
                    name=f.get("name", ""),
                    mime_type=f.get("mimeType", ""),
                    size=int(f["size"]) if f.get("size") is not None else None,
                )
            )
        next_token = resp.get("nextPageToken")
        return results, next_token

    def resolve_path(self, file_id: str) -> str:
        """Resolve the full path of a file by walking up parent folders."""
        parts: List[str] = []
        current_id = file_id
        max_hops = 8
        
        for _ in range(max_hops):
            if current_id in self._folder_name_cache:
                parts.append(self._folder_name_cache[current_id])
                # Try to get parent from cache
                break
            
            try:
                params = {
                    "fileId": current_id,
                    "fields": "id, name, parents",
                    "supportsAllDrives": self.include_shared_drives,
                }
                resp = self._execute_with_retry(lambda: self.service.files().get(**params).execute())
                name = resp.get("name", "Unknown")
                parents = resp.get("parents", [])
                
                # Cache this folder name
                self._folder_name_cache[current_id] = name
                parts.append(name)
                
                if not parents:
                    # Reached root
                    break
                
                current_id = parents[0]
            except Exception:
                # Handle permission errors or missing files
                break
        
        if not parts:
            return "My Drive"
        
        # Reverse to get root-to-file order
        parts.reverse()
        # If we have more than 4 parts, show root/.../parent/file pattern
        if len(parts) > 4:
            return f"{parts[0]} / ... / {' / '.join(parts[-2:])}"
        return " / ".join(parts)

    def download_file(self, file_id: str, dest: Path, size: Optional[int]) -> None:
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=self.include_shared_drives)
        with dest.open("wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024 * 4)
            done = False
            while not done:
                try:
                    _, done = downloader.next_chunk()
                except HttpError as err:
                    if err.resp.status in RETRIABLE_STATUS:
                        backoff_sleep(err.resp.status)
                        continue
                    raise

    def download_file_stream(self, file_id: str, size: Optional[int]):
        """Stream file content for preview. Yields chunks of data."""
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=self.include_shared_drives)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request, chunksize=1024 * 256)
        done = False
        while not done:
            try:
                status, done = downloader.next_chunk()
                buffer.seek(0)
                chunk = buffer.read()
                if chunk:
                    yield chunk
                buffer.seek(0)
                buffer.truncate(0)
            except HttpError as err:
                if err.resp.status in RETRIABLE_STATUS:
                    backoff_sleep(err.resp.status)
                    continue
                raise

    def export_file(self, file_id: str, export_mime: str, dest: Path) -> None:
        request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
        with dest.open("wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024 * 4)
            done = False
            while not done:
                try:
                    _, done = downloader.next_chunk()
                except HttpError as err:
                    if err.resp.status in RETRIABLE_STATUS:
                        backoff_sleep(err.resp.status)
                        continue
                    raise

    def export_file_stream(self, file_id: str, export_mime: str):
        """Stream exported file content for preview. Yields chunks of data."""
        request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request, chunksize=1024 * 256)
        done = False
        while not done:
            try:
                status, done = downloader.next_chunk()
                buffer.seek(0)
                chunk = buffer.read()
                if chunk:
                    yield chunk
                buffer.seek(0)
                buffer.truncate(0)
            except HttpError as err:
                if err.resp.status in RETRIABLE_STATUS:
                    backoff_sleep(err.resp.status)
                    continue
                raise

    def enumerate_files(self, folder_id: str, base_prefix: Path) -> List[Tuple[DriveItem, Path]]:
        collected: List[Tuple[DriveItem, Path]] = []
        children = self.list_children(folder_id)
        for item in children:
            safe_name = sanitize_filename(item.name)
            rel_path = base_prefix / safe_name
            if item.is_folder:
                collected.extend(self.enumerate_files(item.id, rel_path))
            else:
                collected.append((item, rel_path))
        return collected

    def _execute_with_retry(self, func, max_attempts: int = 5):
        attempt = 0
        while True:
            attempt += 1
            try:
                return func()
            except HttpError as err:
                status = err.resp.status if err.resp else None
                if status in RETRIABLE_STATUS and attempt < max_attempts:
                    backoff_sleep(status, attempt)
                    continue
                raise
