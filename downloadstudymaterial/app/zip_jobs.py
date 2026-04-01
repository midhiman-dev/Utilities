from __future__ import annotations

import logging
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .drive_service import DriveItem, DriveService, EXPORT_MIME_MAP, is_google_doc, sanitize_filename


@dataclass
class ZipJob:
    job_id: str
    folder_id: str
    folder_name: str
    zip_path: Path
    temp_dir: Path
    total: int = 0
    completed: int = 0
    status: str = "running"  # running | ready | error
    message: str = ""
    current_file: Optional[str] = None
    downloaded: int = 0
    exported: int = 0
    skipped: int = 0
    errors: int = 0
    mode: str = "full"  # full | selected


class ZipJobManager:
    def __init__(self, drive: DriveService, base_dir: Path) -> None:
        self.drive = drive
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, ZipJob] = {}
        self.lock = threading.Lock()

    def start_job(self, folder_id: str, folder_name: Optional[str] = None) -> ZipJob:
        job_id = uuid.uuid4().hex
        temp_dir = self.base_dir / job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        resolved_name = folder_name or self.drive.get_folder_name(folder_id)
        safe_name = sanitize_filename(resolved_name)
        zip_path = temp_dir / f"{safe_name}.zip"
        job = ZipJob(
            job_id=job_id,
            folder_id=folder_id,
            folder_name=resolved_name,
            zip_path=zip_path,
            temp_dir=temp_dir,
            mode="full",
        )
        with self.lock:
            self.jobs[job_id] = job
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def start_selected_job(
        self,
        current_folder_id: str,
        items: Sequence[Tuple[str, str]],
        zip_name: Optional[str] = None,
        current_folder_name: Optional[str] = None,
    ) -> ZipJob:
        job_id = uuid.uuid4().hex
        temp_dir = self.base_dir / job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        resolved_root_name = current_folder_name or self.drive.get_folder_name(current_folder_id)
        safe_root = sanitize_filename(resolved_root_name)
        zip_path = temp_dir / (zip_name or f"{safe_root}.zip")
        job = ZipJob(
            job_id=job_id,
            folder_id=current_folder_id,
            folder_name=resolved_root_name,
            zip_path=zip_path,
            temp_dir=temp_dir,
            mode="selected",
        )
        with self.lock:
            self.jobs[job_id] = job
        thread = threading.Thread(target=self._run_selected_job, args=(job, items), daemon=True)
        thread.start()
        return job

    def get_job(self, job_id: str) -> Optional[ZipJob]:
        with self.lock:
            return self.jobs.get(job_id)

    def _run_job(self, job: ZipJob) -> None:
        try:
            base_prefix = Path(sanitize_filename(job.folder_name))
            files = self.drive.enumerate_files(job.folder_id, base_prefix=base_prefix)
            job.total = len(files)
            used_arcnames: set[str] = set()
            with zipfile.ZipFile(job.zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for drive_item, rel_path in files:
                    local_path = job.temp_dir / "files" / rel_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    arcname_path = rel_path
                    if is_google_doc(drive_item.mime_type):
                        export_mime, ext = EXPORT_MIME_MAP.get(drive_item.mime_type, ("application/pdf", ".pdf"))
                        local_path = local_path.with_suffix(ext)
                        arcname_path = arcname_path.with_suffix(ext)
                        self.drive.export_file(drive_item.id, export_mime, local_path)
                        job.exported += 1
                    else:
                        self.drive.download_file(drive_item.id, local_path, drive_item.size)
                        job.downloaded += 1
                    arcname_path = self._ensure_unique_path(arcname_path, used_arcnames)
                    job.current_file = arcname_path.as_posix()
                    zf.write(local_path, arcname_path.as_posix())
                    job.completed += 1
            job.status = "ready"
            job.message = "ZIP ready"
            job.current_file = None
        except Exception as exc:  # noqa: BLE001
            logging.exception("Job %s failed", job.job_id)
            job.status = "error"
            job.message = str(exc)
            job.errors += 1
        finally:
            job.current_file = None

    def _run_selected_job(self, job: ZipJob, items: Sequence[Tuple[str, str]]) -> None:
        try:
            base_prefix = Path(sanitize_filename(job.folder_name))
            collected: List[Tuple[DriveItem, Path]] = []

            for item_id, item_type in items:
                try:
                    drive_item = self.drive.get_item(item_id)
                    if item_type == "folder" and drive_item.is_folder:
                        sub_prefix = base_prefix / sanitize_filename(drive_item.name)
                        collected.extend(self.drive.enumerate_files(drive_item.id, base_prefix=sub_prefix))
                    elif item_type == "file" and not drive_item.is_folder:
                        rel_path = base_prefix / sanitize_filename(drive_item.name)
                        collected.append((drive_item, rel_path))
                    else:
                        job.skipped += 1
                        continue
                except Exception as exc:  # noqa: BLE001
                    logging.warning("Skip item %s: %s", item_id, exc)
                    job.skipped += 1
                    continue

            job.total = len(collected)
            used_arcnames: set[str] = set()
            with zipfile.ZipFile(job.zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for drive_item, rel_path in collected:
                    local_path = job.temp_dir / "files" / rel_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    arcname_path = rel_path
                    try:
                        if is_google_doc(drive_item.mime_type):
                            export_mime, ext = EXPORT_MIME_MAP.get(drive_item.mime_type, ("application/pdf", ".pdf"))
                            local_path = local_path.with_suffix(ext)
                            arcname_path = arcname_path.with_suffix(ext)
                            self.drive.export_file(drive_item.id, export_mime, local_path)
                            job.exported += 1
                        else:
                            self.drive.download_file(drive_item.id, local_path, drive_item.size)
                            job.downloaded += 1
                        arcname_path = self._ensure_unique_path(arcname_path, used_arcnames)
                        job.current_file = arcname_path.as_posix()
                        zf.write(local_path, arcname_path.as_posix())
                        job.completed += 1
                    except Exception as exc:  # noqa: BLE001
                        logging.warning("Skip item %s: %s", drive_item.id, exc)
                        job.skipped += 1
                        job.errors += 1
                        continue
            job.status = "ready"
            job.message = "ZIP ready"
            job.current_file = None
        except Exception as exc:  # noqa: BLE001
            logging.exception("Job %s failed", job.job_id)
            job.status = "error"
            job.message = str(exc)
            job.errors += 1
        finally:
            job.current_file = None

    def _ensure_unique_path(self, rel_path: Path, used: set[str]) -> Path:
        candidate = rel_path
        stem = rel_path.stem
        suffix = rel_path.suffix
        parent = rel_path.parent
        counter = 1
        while candidate.as_posix() in used:
            new_name = f"{stem} ({counter}){suffix}"
            candidate = parent / new_name
            counter += 1
        used.add(candidate.as_posix())
        return candidate
