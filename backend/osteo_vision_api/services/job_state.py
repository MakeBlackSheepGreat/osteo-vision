from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ACTIVE_JOB_STATUSES = {"queued", "running"}
RESTART_FAILURE_MESSAGE = "Job did not complete before process restart."


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def progress(phase: str, percent: int, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "phase": phase,
        "percent": max(0, min(100, int(percent))),
        "message": message,
        "details": details or {},
    }


def progress_percent(job: dict[str, Any]) -> int:
    progress_payload = job.get("progress")
    if not isinstance(progress_payload, dict):
        return 0
    percent = progress_payload.get("percent")
    return int(percent) if isinstance(percent, (int, float)) else 0


def restart_failed_job(job: dict[str, Any]) -> dict[str, Any]:
    # 本地 worker 中断后不能让 running 永久挂起；重启时统一落到 failed，前端可提示重新运行。
    return {
        **job,
        "status": "failed",
        "error": RESTART_FAILURE_MESSAGE,
        "progress": progress("failed", progress_percent(job), RESTART_FAILURE_MESSAGE),
        "updated_at": utc_now(),
    }
