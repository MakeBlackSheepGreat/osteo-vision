from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.src.core.settings import Settings
from backend.src.domains.cases.repository import build_case_repository
from backend.src.domains.cases.schemas import AnalysisRunCreateRequest
from backend.src.services.analysis_service import AnalysisService
from backend.src.services.job_service import JobRegistry
from src.core.paths import ensure_dir
from src.preprocess.video import extract_keyframes


class LocalJobWorker:
    """Single-process durable queue worker for the local prototype.

    This is intentionally small: it drains jobs from the same persistent
    registry used by the FastAPI app, so interrupted queued jobs can be resumed
    without introducing Redis/Celery during the competition prototype stage.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs = JobRegistry(settings.job_store_path)
        self.repo = build_case_repository(settings.case_store_path, settings.case_store_backend)
        self.analysis_service = AnalysisService(self.repo)

    def run_once(self, *, limit: int = 1, kinds: list[str] | None = None) -> dict[str, Any]:
        processed: list[dict[str, Any]] = []
        for _ in range(max(1, limit)):
            job = self._claim_next(kinds)
            if job is None:
                break
            processed.append(self._process(job))
        return {
            "processed_count": len(processed),
            "processed": processed,
            "remaining_queued": len(self.jobs.list_jobs(status="queued")),
        }

    def _claim_next(self, kinds: list[str] | None) -> dict[str, Any] | None:
        if not kinds:
            return self.jobs.claim_next_queued()
        for kind in kinds:
            job = self.jobs.claim_next_queued(kind=kind)
            if job is not None:
                return job
        return None

    def _process(self, job: dict[str, Any]) -> dict[str, Any]:
        kind = str(job.get("kind") or "")
        if kind == "case_analysis":
            return self._process_case_analysis(job)
        if kind == "upload_keyframe_extraction":
            return self._process_upload_keyframes(job)
        self.jobs.mark_failed(str(job["job_id"]), f"Unsupported job kind: {kind}")
        return {"job_id": job["job_id"], "kind": kind, "status": "failed", "error": "unsupported kind"}

    def _process_case_analysis(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job["job_id"])
        payload = _payload(job)
        case_id = str(payload.get("case_id") or "")
        self.jobs.update_progress(job_id, phase="load_case", percent=15, message="Loading case inputs and analysis request.")
        case = self.repo.get(case_id)
        if case is None:
            self.jobs.mark_failed(job_id, "Case not found")
            return {"job_id": job_id, "kind": "case_analysis", "status": "failed", "error": "Case not found"}
        request = AnalysisRunCreateRequest(
            selected_input_ids=list(payload.get("selected_input_ids") or []),
            parameters=dict(payload.get("parameters") or {}),
            roi_hints=list(payload.get("roi_hints") or []),
        )
        try:
            self.jobs.update_progress(job_id, phase="analyze", percent=35, message="Running fluorescence and AI analysis.")
            updated = self.analysis_service.start_analysis(
                case,
                request.selected_input_ids,
                request.parameters,
                request.roi_hints,
            )
        except Exception as exc:
            self.jobs.mark_failed(job_id, str(exc))
            return {"job_id": job_id, "kind": "case_analysis", "status": "failed", "error": str(exc)}
        latest = updated.analysis_runs[-1] if updated.analysis_runs else None
        result = {
            "case_id": updated.case_id,
            "case_status": updated.status,
            "run_id": latest.run_id if latest else None,
            "run_status": latest.status if latest else None,
        }
        self.jobs.update_progress(job_id, phase="persist_results", percent=90, message="Persisting analysis results and artifacts.")
        if latest and latest.status == "failed":
            self.jobs.mark_failed(job_id, "Analysis run failed.", result)
        else:
            self.jobs.mark_completed(job_id, result)
        completed = self.jobs.get(job_id) or {}
        return {"job_id": job_id, "kind": "case_analysis", "status": completed.get("status"), "result": result}

    def _process_upload_keyframes(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job["job_id"])
        payload = _payload(job)
        source_path = Path(str(payload.get("source_path") or ""))
        output_dir = ensure_dir(str(payload.get("output_dir") or self.settings.artifact_root / "uploads" / "keyframes" / source_path.stem))
        max_frames = int(payload.get("max_frames") or 5)
        try:
            self.jobs.update_progress(job_id, phase="extract_keyframes", percent=20, message="Extracting representative MP4 keyframes.")
            report = extract_keyframes(source_path, output_dir, max_frames=max_frames)
        except Exception as exc:
            self.jobs.mark_failed(job_id, str(exc))
            return {"job_id": job_id, "kind": "upload_keyframe_extraction", "status": "failed", "error": str(exc)}
        self.jobs.update_progress(job_id, phase="write_keyframes", percent=90, message="Writing keyframe manifest and previews.")
        if report.get("keyframes"):
            self.jobs.mark_completed(job_id, report)
        else:
            warnings = report.get("warnings", [])
            message = str(warnings[0].get("message")) if warnings else "No keyframes were extracted."
            self.jobs.mark_failed(job_id, message, report)
        completed = self.jobs.get(job_id) or {}
        return {
            "job_id": job_id,
            "kind": "upload_keyframe_extraction",
            "status": completed.get("status"),
            "keyframes": len(report.get("keyframes") or []),
        }


def _payload(job: dict[str, Any]) -> dict[str, Any]:
    payload = job.get("payload")
    return payload if isinstance(payload, dict) else {}
