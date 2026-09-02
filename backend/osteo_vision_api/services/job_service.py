from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from backend.osteo_vision_api.services.job_state import (
    ACTIVE_JOB_STATUSES,
    progress,
    progress_percent,
    restart_failed_job,
    utc_now,
)
from osteo_vision_core.core.paths import ensure_dir

NAVIGATION_PIPELINE_JOB_KINDS = frozenset({"l1_static_registration", "l2_offline_pose_replay"})


def _job_family(kind: str) -> str:
    if kind in NAVIGATION_PIPELINE_JOB_KINDS:
        return "navigation_pipeline"
    return kind


def _job_progress_details(job: dict[str, Any]) -> dict[str, Any]:
    progress_payload = job.get("progress")
    if not isinstance(progress_payload, dict):
        return {}
    details = progress_payload.get("details")
    return dict(details) if isinstance(details, dict) else {}


class JobCapacityError(RuntimeError):
    def __init__(self, *, kind: str, max_active: int, active_count: int) -> None:
        super().__init__(f"Too many active {kind} jobs: {active_count}/{max_active}")
        self.kind = kind
        self.max_active = max_active
        self.active_count = active_count


class JobConflictError(RuntimeError):
    def __init__(self, *, kind: str, active_job: dict[str, Any], singleton_keys: list[str]) -> None:
        super().__init__(f"Active {kind} job already exists for {', '.join(singleton_keys)}")
        self.kind = kind
        self.active_job = dict(active_job)
        self.singleton_keys = list(singleton_keys)


class JobRegistry:
    """Small persistent job tracker for local platform software workflows."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self._storage_signature: tuple[int, int, int, int] | None = None
        self._load()

    def create(
        self,
        *,
        kind: str,
        payload: dict[str, Any] | None = None,
        max_active: int | None = None,
        singleton_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        job_id = f"job_{uuid4().hex[:12]}"
        job_payload = payload or {}
        job = {
            "job_id": job_id,
            "kind": kind,
            "family": _job_family(kind),
            "status": "queued",
            "payload": job_payload,
            "result": {},
            "error": None,
            "progress": progress("queued", 0, "Job queued."),
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._refresh_locked()
            active = self._active_jobs_locked(kind)
            if max_active is not None and len(active) >= max_active:
                raise JobCapacityError(kind=kind, max_active=max_active, active_count=len(active))
            if singleton_keys:
                family = _job_family(kind)
                family_active = [
                    active_job
                    for active_job in self._active_jobs_locked()
                    if _job_family(str(active_job.get("kind") or "")) == family
                ]
                for active_job in family_active:
                    raw_active_payload = active_job.get("payload")
                    active_payload = raw_active_payload if isinstance(raw_active_payload, dict) else {}
                    if all(active_payload.get(key) == job_payload.get(key) for key in singleton_keys):
                        raise JobConflictError(
                            kind=kind,
                            active_job=active_job,
                            singleton_keys=singleton_keys,
                        )
            self._jobs[job_id] = job
            self._save_locked()
        return dict(job)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._refresh_locked()
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self, *, status: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            self._refresh_locked()
            jobs = [
                dict(job)
                for job in self._jobs.values()
                if (status is None or job.get("status") == status) and (kind is None or job.get("kind") == kind)
            ]
        return sorted(jobs, key=lambda item: str(item.get("created_at") or ""))

    def claim_next_queued(self, *, kind: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            self._refresh_locked()
            job = min(
                (
                    candidate
                    for candidate in self._jobs.values()
                    if candidate.get("status") == "queued" and (kind is None or candidate.get("kind") == kind)
                ),
                key=lambda item: str(item.get("created_at") or ""),
                default=None,
            )
            if job is None:
                return None
            claimed = {
                **job,
                "status": "running",
                "progress": progress("running", 5, "Job claimed by local worker."),
                "updated_at": utc_now(),
            }
            self._jobs[str(job["job_id"])] = claimed
            self._save_locked()
            return dict(claimed)

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.get("status") == "canceled":
                return
        self._update(job_id, status="running", progress=progress("running", 5, "Job started."))

    def mark_completed(self, job_id: str, result: dict[str, Any]) -> None:
        if self.is_canceled(job_id):
            return
        current = self.get(job_id) or {}
        self._update(
            job_id,
            status="completed",
            result=result,
            error=None,
            progress=progress("completed", 100, "Job completed.", _job_progress_details(current)),
        )

    def mark_failed(self, job_id: str, error: str, result: dict[str, Any] | None = None) -> None:
        if self.is_canceled(job_id):
            return
        current = self.get(job_id) or {}
        self._update(
            job_id,
            status="failed",
            result=result or {},
            error=error,
            progress=progress("failed", progress_percent(current), error, _job_progress_details(current)),
        )

    def update_progress(
        self,
        job_id: str,
        *,
        phase: str,
        percent: int,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if self.is_canceled(job_id):
            return
        self._update(job_id, progress=progress(phase, percent, message, details))

    def cancel(self, job_id: str, reason: str = "Job canceled by user.") -> dict[str, Any] | None:
        with self._lock:
            self._refresh_locked()
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.get("status") in {"completed", "failed", "canceled"}:
                return dict(job)
            canceled = {
                **job,
                "status": "canceled",
                "error": reason,
                "progress": progress("canceled", progress_percent(job), reason, _job_progress_details(job)),
                "updated_at": utc_now(),
            }
            self._jobs[job_id] = canceled
            self._save_locked()
            return dict(canceled)

    def is_canceled(self, job_id: str) -> bool:
        with self._lock:
            self._refresh_locked()
            job = self._jobs.get(job_id)
            return bool(job and job.get("status") == "canceled")

    def active_count(self, kind: str | None = None) -> int:
        with self._lock:
            self._refresh_locked()
            return len(self._active_jobs_locked(kind))

    def _update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            self._refresh_locked()
            if job_id not in self._jobs:
                return
            self._jobs[job_id] = {
                **self._jobs[job_id],
                **updates,
                "updated_at": utc_now(),
            }
            self._save_locked()

    def _active_jobs_locked(self, kind: str | None = None) -> list[dict[str, Any]]:
        return [
            dict(job)
            for job in self._jobs.values()
            if (kind is None or job.get("kind") == kind) and job.get("status") in ACTIVE_JOB_STATUSES
        ]

    def _load(self, *, fail_running_on_restart: bool = True, force: bool = True) -> None:
        if self.storage_path is None:
            return
        signature = _file_signature(self.storage_path)
        if not force and signature == self._storage_signature:
            return
        if signature is None:
            self._jobs = {}
            self._storage_signature = None
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._jobs = {}
            self._storage_signature = signature
            return
        jobs = payload.get("jobs", {})
        if isinstance(jobs, dict):
            self._jobs = {str(job_id): dict(job) for job_id, job in jobs.items() if isinstance(job, dict)}
        changed = False
        for job_id, job in list(self._jobs.items()):
            if fail_running_on_restart and job.get("status") == "running":
                self._jobs[job_id] = restart_failed_job(job)
                changed = True
        if changed:
            self._save_locked()
        else:
            self._storage_signature = signature

    def _refresh_locked(self) -> None:
        self._load(fail_running_on_restart=False, force=False)

    def _save_locked(self) -> None:
        if self.storage_path is None:
            return
        ensure_dir(self.storage_path.parent)
        tmp_path = self.storage_path.with_name(f"{self.storage_path.name}.{uuid4().hex[:8]}.tmp")
        payload = {"schema_version": "osteo-vision-job-registry-v1", "jobs": self._jobs}
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(5):
            try:
                tmp_path.replace(self.storage_path)
                self._storage_signature = _file_signature(self.storage_path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))


def _file_signature(path: Path) -> tuple[int, int, int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_ctime_ns), int(stat.st_size), int(stat.st_ino)
