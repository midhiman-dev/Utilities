#!/usr/bin/env python3
"""Interactive Google Drive folder browser and downloader.

Usage:
    python drive_folder_downloader.py --root-url "<drive folder url>" --out "C:\\path\\to\\downloads"
"""
from __future__ import annotations

import argparse
import io
import logging
import os
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import questionary
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from tqdm import tqdm

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


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browse and download Google Drive folders")
    parser.add_argument("--root-url", required=True, help="Root Google Drive folder URL")
    parser.add_argument("--out", required=True, help="Output directory for downloads")
    parser.add_argument("--credentials", default="credentials.json", help="Path to OAuth client secrets")
    parser.add_argument("--token", default="token.json", help="Path to store OAuth tokens")
    parser.add_argument("--include-shared-drives", action="store_true", help="Include shared drives content")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing downloads/zips")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--dry-run", action="store_true", help="Only list what would download")
    parser.add_argument("--zip-name", help="Explicit zip filename (without path)")
    return parser.parse_args(argv)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def extract_folder_id(url: str) -> str:
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    # Fallback to share link like ?id=<id>
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]+", url):
        return url
    raise ValueError("Could not extract folder ID from URL")


@dataclass
class DriveItem:
    id: str
    name: str
    mime_type: str
    size: Optional[int]

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME


class DriveClient:
    def __init__(self, service, include_shared_drives: bool) -> None:
        self.service = service
        self.include_shared_drives = include_shared_drives

    @classmethod
    def from_credentials(cls, credentials_path: Path, token_path: Path, include_shared_drives: bool) -> "DriveClient":
        creds = load_credentials(credentials_path, token_path)
        service = build("drive", "v3", credentials=creds)
        return cls(service, include_shared_drives)

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

    def download_folder(
        self,
        folder_id: str,
        dest_root: Path,
        overwrite: bool,
        dry_run: bool,
    ) -> Dict[str, int]:
        summary = {"downloaded": 0, "exported": 0, "skipped": 0, "errors": 0}
        folder_name = sanitize_filename(self.get_folder_name(folder_id))
        target_dir = dest_root / folder_name

        if target_dir.exists() and overwrite:
            shutil.rmtree(target_dir)
        if target_dir.exists() and not overwrite:
            logging.warning("Destination already exists: %s", target_dir)
            return summary
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        self._download_folder_recursive(folder_id, target_dir, dry_run, summary)
        return summary

    def _download_folder_recursive(
        self, folder_id: str, current_path: Path, dry_run: bool, summary: Dict[str, int]
    ) -> None:
        items = self.list_children(folder_id)
        for item in items:
            safe_name = sanitize_filename(item.name)
            if item.is_folder:
                next_dir = current_path / safe_name
                if not dry_run:
                    next_dir.mkdir(exist_ok=True)
                self._download_folder_recursive(item.id, next_dir, dry_run, summary)
                continue
            try:
                if is_google_doc(item.mime_type):
                    export_mime, ext = EXPORT_MIME_MAP.get(item.mime_type, ("application/pdf", ".pdf"))
                    out_path = (current_path / safe_name).with_suffix(ext)
                    logging.info("Exporting %s -> %s", item.name, out_path)
                    if dry_run:
                        summary["exported"] += 1
                        continue
                    self._export_file(item.id, export_mime, out_path)
                    summary["exported"] += 1
                else:
                    out_path = current_path / safe_name
                    logging.info("Downloading %s -> %s", item.name, out_path)
                    if dry_run:
                        summary["downloaded"] += 1
                        continue
                    self._download_file(item.id, out_path, item.size)
                    summary["downloaded"] += 1
            except Exception as exc:  # noqa: BLE001
                logging.error("Failed %s: %s", item.name, exc)
                summary["errors"] += 1

    def _download_file(self, file_id: str, dest: Path, size: Optional[int]) -> None:
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=self.include_shared_drives)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024 * 4)
        with tqdm(total=size or 0, unit="B", unit_scale=True, desc=dest.name, leave=False) as bar:
            done = False
            while not done:
                try:
                    status, done = downloader.next_chunk()
                    if status:
                        bar.update(status.resumable_progress - bar.n)
                except HttpError as err:
                    if err.resp.status in RETRIABLE_STATUS:
                        backoff_sleep(err.resp.status)
                        continue
                    raise
        dest.write_bytes(fh.getvalue())

    def _export_file(self, file_id: str, export_mime: str, dest: Path) -> None:
        request = self.service.files().export_media(
            fileId=file_id, mimeType=export_mime, supportsAllDrives=self.include_shared_drives
        )
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024 * 4)
        done = False
        while not done:
            try:
                status, done = downloader.next_chunk()
            except HttpError as err:
                if err.resp.status in RETRIABLE_STATUS:
                    backoff_sleep(err.resp.status)
                    continue
                raise
        dest.write_bytes(fh.getvalue())

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


def is_google_doc(mime_type: str) -> bool:
    return mime_type.startswith("application/vnd.google-apps") and mime_type != FOLDER_MIME


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name)
    cleaned = cleaned.rstrip(" .")
    return cleaned or "unnamed"


def backoff_sleep(status: Optional[int], attempt: int = 1) -> None:
    delay = min(2 ** attempt, 30)
    logging.warning("Retrying after status %s (sleep %ss)", status, delay)
    time.sleep(delay)


def interactive_browser(client: DriveClient, root_id: str) -> Tuple[str, str]:
    stack: List[Tuple[str, str]] = [(root_id, client.get_folder_name(root_id))]
    while True:
        current_id, current_name = stack[-1]
        items = client.list_children(current_id)
        choices = []
        choices.append(questionary.Choice(title="[Download this folder]", value=("download", (current_id, current_name))))
        for item in items:
            label = f"[Folder] {item.name}" if item.is_folder else f"[File] {item.name}"
            if item.is_folder:
                choices.append(questionary.Choice(title=label, value=("open", item)))
            else:
                choices.append(questionary.Choice(title=label, value=("noop", item), disabled=True))
        if len(stack) > 1:
            choices.append(questionary.Choice(title="[Back]", value=("back", None)))
        choices.append(questionary.Choice(title="[Quit]", value=("quit", None)))

        selection = questionary.select(
            message=f"In folder: {' / '.join([s[1] for s in stack])}",
            choices=choices,
        ).ask()
        if selection is None:
            sys.exit(0)
        action, payload = selection
        if action == "open":
            item = payload
            stack.append((item.id, item.name))
            continue
        if action == "back":
            stack.pop()
            continue
        if action == "quit":
            sys.exit(0)
        if action == "download":
            return payload


def zip_directory(source_dir: Path, zip_path: Path, overwrite: bool) -> None:
    if zip_path.exists() and not overwrite:
        logging.warning("Zip already exists: %s", zip_path)
        return
    if zip_path.exists() and overwrite:
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            arcname = source_dir.name + "/" + str(file_path.relative_to(source_dir)).replace("\\", "/")
            if file_path.is_file():
                zf.write(file_path, arcname)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    root_id = extract_folder_id(args.root_url)
    out_dir = Path(args.out).expanduser().resolve()
    creds_path = Path(args.credentials).expanduser().resolve()
    token_path = Path(args.token).expanduser().resolve()

    logging.info("Using output directory: %s", out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = DriveClient.from_credentials(creds_path, token_path, args.include_shared_drives)
    target_id, target_name = interactive_browser(client, root_id)

    summary = client.download_folder(target_id, out_dir, overwrite=args.overwrite, dry_run=args.dry_run)

    if args.dry_run:
        logging.info("Dry-run complete. Summary: %s", summary)
        return

    zip_filename = args.zip_name or f"{sanitize_filename(target_name)}.zip"
    zip_path = out_dir / zip_filename
    source_dir = out_dir / sanitize_filename(target_name)
    zip_directory(source_dir, zip_path, overwrite=args.overwrite)

    logging.info(
        "Completed. Downloaded=%s Exported=%s Skipped=%s Errors=%s Zip=%s",
        summary["downloaded"],
        summary["exported"],
        summary["skipped"],
        summary["errors"],
        zip_path,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("Interrupted by user")
        sys.exit(1)
