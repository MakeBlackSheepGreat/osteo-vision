from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from src.core.paths import ensure_dir

ACTIVE_JOB_STATUSES = {"queued", "running"}


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
    """Small persistent job tracker for local competition prototypes."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self.storage_path = Path(storage_path) if storage_path is not None else None
        self._load()

    def create(
        self,
        *,
        kind: str,
        payload: dict[str, Any] | None = None,
        max_active: int | None = None,
        singleton_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        now = _utc_now()
        job_id = f"job_{uuid4().hex[:12]}"
        job_payload = payload or {}
        job = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "payload": job_payload,
            "result": {},
            "error": None,
            "progress": _progress("queued", 0, "Job queued."),
            "created_at": now,
            "updated_at": now,
        }
        with self._lock:
            self._refresh_locked()
            active = self._active_jobs_locked(kind)
            if max_active is not None and len(active) >= max_active:
                raise JobCapacityError(kind=kind, max_active=max_active, active_count=len(active))
            if singleton_keys:
                for active_job in active:
                    raw_active_payload = active_job.get("payload")
                    active_payload = raw_active_payload if isinstance(raw_active_payload, dict) else {}
                    if all(active_payload.get(key) == job_payload.get(key) for key in singleton_keys):
                        raise JobConflictError(kind=kind, active_job=active_job, singleton_keys=singleton_keys)
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
            queued = [
                job
                for job in self._jobs.values()
                if job.get("status") == "queued" and (kind is None or job.get("kind") == kind)
            ]
            if not queued:
                return None
            job = sorted(queued, key=lambda item: str(item.get("created_at") or ""))[0]
            claimed = {
                **job,
                "status": "running",
                "progress": _progress("running", 5, "Job claimed by local worker."),
                "updated_at": _utc_now(),
            }
            self._jobs[str(job["job_id"])] = claimed
            self._save_locked()
            return dict(claimed)

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.get("status") == "canceled":
                return
        self._update(job_id, status="running", progress=_progress("running", 5, "Job started."))

    def mark_completed(self, job_id: str, result: dict[str, Any]) -> None:
        if self.is_canceled(job_id):
            return
        self._update(job_id, status="completed", result=result, error=None, progress=_progress("completed", 100, "Job completed."))

    def mark_failed(self, job_id: str, error: str, result: dict[str, Any] | None = None) -> None:
        if self.is_canceled(job_id):
            return
        self._update(job_id, status="failed", result=result or {}, error=error, progress=_progress("failed", 100, error))

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
        self._update(job_id, progress=_progress(phase, percent, message, details))

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
                "progress": _progress("canceled", _progress_percent(job), reason),
                "updated_at": _utc_now(),
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
            self._jobs[job_id] = {**self._jobs[job_id], **updates, "updated_at": _utc_now()}
            self._save_locked()

    def _active_jobs_locked(self, kind: str | None = None) -> list[dict[str, Any]]:
        return [
            dict(job)
            for job in self._jobs.values()
            if (kind is None or job.get("kind") == kind) and job.get("status") in ACTIVE_JOB_STATUSES
        ]

    def _load(self, *, fail_running_on_restart: bool = True) -> None:
        if self.storage_path is None or not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._jobs = {}
            return
        jobs = payload.get("jobs", {})
        if isinstance(jobs, dict):
            self._jobs = {str(job_id): dict(job) for job_id, job in jobs.items() if isinstance(job, dict)}
        changed = False
        for job_id, job in list(self._jobs.items()):
            if fail_running_on_restart and job.get("status") == "running":
                self._jobs[job_id] = {
                    **job,
                    "status": "failed",
                    "error": "Job did not complete before process restart.",
                    "progress": _progress("failed", _progress_percent(job), "Job did not complete before process restart."),
                    "updated_at": _utc_now(),
                }
                changed = True
        if changed:
            self._save_locked()

    def _refresh_locked(self) -> None:
        self._load(fail_running_on_restart=False)

    def _save_locked(self) -> None:
        if self.storage_path is None:
            return
        ensure_dir(self.storage_path.parent)
        tmp_path = self.storage_path.with_name(f"{self.storage_path.name}.{uuid4().hex[:8]}.tmp")
        payload = {"schema_version": "osteo-vision-job-registry-v1", "jobs": self._jobs}
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.storage_path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _progress(phase: str, percent: int, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "phase": phase,
        "percent": max(0, min(100, int(percent))),
        "message": message,
        "details": details or {},
    }


def _progress_percent(job: dict[str, Any]) -> int:
    progress = job.get("progress")
    if not isinstance(progress, dict):
        return 0
    percent = progress.get("percent")
    return int(percent) if isinstance(percent, (int, float)) else 0
