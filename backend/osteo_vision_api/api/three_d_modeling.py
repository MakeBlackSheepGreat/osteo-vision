from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.osteo_vision_api.api.helpers import capacity_exceeded, conflict_from_active_job, require_case
from backend.osteo_vision_api.api.review_identity import TRUSTED_REVIEW_AUTH_SOURCES, resolve_review_actor
from backend.osteo_vision_api.core.settings import Settings
from backend.osteo_vision_api.domains.cases.enums import ReviewerRole
from backend.osteo_vision_api.domains.cases.repository import CaseRepository
from backend.osteo_vision_api.domains.cases.schemas import ReviewActorIdentity
from backend.osteo_vision_api.services.job_service import JobCapacityError, JobConflictError, JobRegistry
from backend.osteo_vision_api.services.job_tasks import (
    run_cbct_surface_modeling_job,
    run_l1_static_registration_job,
    run_l2_offline_pose_replay_job,
)


class ThreeDModelingRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    source_paths: list[str] | None = None
    source_role: Literal["volume", "label", "surface", "auto"] = "volume"
    source_original_filename: str | None = None
    label_value: int = Field(default=1, ge=0)
    case_id: str = Field(default="local_cbct", min_length=1)
    dataset_id: str = Field(default="local_import", min_length=1)
    decimation_step: int = Field(default=1, ge=1)


class L1StaticRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=128)
    input_mode: Literal["manual_metadata", "offline_manifest"] = "manual_metadata"
    registration_manifest_path: str | None = None
    registration_manifest_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    registration_method: Literal["rigid_points", "rigid_points_with_pnp"] = "rigid_points"
    model_path: str | None = None
    model_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    model_format: Literal["stl", "glb", "gltf"] | None = None
    point_correspondence_artifact_path: str | None = None
    point_correspondence_artifact_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    source_points: list[tuple[float, float, float]] | None = None
    target_points: list[tuple[float, float, float]] | None = None
    validation_source_points: list[tuple[float, float, float]] | None = None
    validation_target_points: list[tuple[float, float, float]] | None = None
    source_space: str | None = Field(default=None, max_length=128)
    target_space: str | None = Field(default=None, max_length=128)
    unit: Literal["mm"] = "mm"
    fre_threshold_mm: float | None = Field(default=None, gt=0)
    tre_threshold_mm: float | None = Field(default=None, gt=0)
    threshold_source: str | None = Field(default=None, max_length=240)
    camera_object_points: list[tuple[float, float, float]] | None = None
    camera_image_points: list[tuple[float, float]] | None = None
    validation_camera_object_points: list[tuple[float, float, float]] | None = None
    validation_camera_image_points: list[tuple[float, float]] | None = None
    camera_matrix: list[tuple[float, float, float]] | None = None
    distortion_coefficients: list[float] | None = None
    image_size_px: tuple[int, int] | None = None
    intrinsics_id: str | None = Field(default=None, max_length=128)
    camera_space: str = Field(default="camera_optical", max_length=128)
    reprojection_threshold_px: float | None = Field(default=None, gt=0)
    camera_calibration_evidence: dict[str, Any] = Field(default_factory=dict)
    threshold_approval: dict[str, Any] = Field(default_factory=dict)
    doctor_review_status: Literal["review_required", "accepted"] = "review_required"
    microscope_pose_evidence: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_input_mode(self) -> L1StaticRegistrationRequest:
        if self.input_mode == "offline_manifest":
            if not str(self.registration_manifest_path or "").strip():
                raise ValueError("registration_manifest_path is required for offline_manifest input")
            if not str(self.registration_manifest_sha256 or "").strip():
                raise ValueError("registration_manifest_sha256 is required for offline_manifest input")
            return self
        if str(self.point_correspondence_artifact_path or "").strip():
            return self
        required = {
            "source_points": self.source_points,
            "target_points": self.target_points,
            "validation_source_points": self.validation_source_points,
            "validation_target_points": self.validation_target_points,
            "source_space": self.source_space,
            "target_space": self.target_space,
            "fre_threshold_mm": self.fre_threshold_mm,
            "tre_threshold_mm": self.tre_threshold_mm,
            "threshold_source": self.threshold_source,
        }
        missing = [key for key, value in required.items() if value is None or value == [] or value == ""]
        if missing:
            raise ValueError(f"manual_metadata registration fields missing: {', '.join(missing)}")
        if self.registration_method == "rigid_points_with_pnp":
            pnp_required = {
                "camera_object_points": self.camera_object_points,
                "camera_image_points": self.camera_image_points,
                "validation_camera_object_points": self.validation_camera_object_points,
                "validation_camera_image_points": self.validation_camera_image_points,
                "camera_matrix": self.camera_matrix,
                "image_size_px": self.image_size_px,
                "intrinsics_id": self.intrinsics_id,
                "reprojection_threshold_px": self.reprojection_threshold_px,
            }
            pnp_missing = [key for key, value in pnp_required.items() if value is None or value == [] or value == ""]
            if pnp_missing:
                raise ValueError("manual_metadata PnP fields missing: " + ", ".join(pnp_missing))
        return self


class L2OfflinePoseReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=128)
    replay_mode: Literal["pose_only_engineering", "dynamic_ar_validation"] = "pose_only_engineering"
    input_mode: Literal["manual_metadata", "offline_manifest"] = "manual_metadata"
    pose_manifest_path: str | None = None
    pose_manifest_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    video_input_id: str | None = Field(default=None, min_length=1, max_length=128)
    frame_timestamps_s: list[float] | None = None
    poses: list[dict[str, Any]] | None = None
    calibration_table: list[dict[str, Any]] | None = None
    failure_injections: dict[int, list[str]] = Field(default_factory=dict)
    max_time_offset_ms: float = Field(default=50.0, gt=0)
    drift_threshold_mm: float = Field(default=1.0, gt=0)
    tre_proxy_threshold_mm: float = Field(default=2.0, gt=0)
    dynamic_target_error_threshold_mm: float = Field(default=2.0, gt=0)
    minimum_visible_projection_points: int = Field(default=4, ge=1)
    max_magnification_rate_per_s: float = Field(default=25.0, gt=0)
    max_working_distance_rate_mm_per_s: float = Field(default=600.0, gt=0)
    max_intrinsics_switch_rate_hz: float = Field(default=10.0, gt=0)
    calibration_ambiguity_margin: float = Field(default=0.05, ge=0, le=1)
    l2_threshold_approval: dict[str, Any] = Field(default_factory=dict)
    doctor_review_status: Literal["review_required", "accepted"] = "review_required"

    @model_validator(mode="after")
    def validate_input_mode(self) -> L2OfflinePoseReplayRequest:
        if self.replay_mode == "dynamic_ar_validation":
            required = {
                "pose_manifest_path": self.pose_manifest_path,
                "pose_manifest_sha256": self.pose_manifest_sha256,
                "video_input_id": self.video_input_id,
            }
            missing = [key for key, value in required.items() if value is None or value == "" or value == {}]
            if self.input_mode != "offline_manifest":
                raise ValueError("dynamic_ar_validation requires input_mode=offline_manifest")
            if missing:
                raise ValueError("dynamic AR validation fields missing: " + ", ".join(missing))
            manifest_bound_fields = {
                "frame_timestamps_s",
                "poses",
                "calibration_table",
                "failure_injections",
                "max_time_offset_ms",
                "drift_threshold_mm",
                "tre_proxy_threshold_mm",
                "dynamic_target_error_threshold_mm",
                "minimum_visible_projection_points",
                "max_magnification_rate_per_s",
                "max_working_distance_rate_mm_per_s",
                "max_intrinsics_switch_rate_hz",
                "calibration_ambiguity_margin",
                "l2_threshold_approval",
            }
            supplied_bound_fields = sorted(manifest_bound_fields.intersection(self.model_fields_set))
            if supplied_bound_fields:
                raise ValueError(
                    "dynamic AR safety fields must come from the checksum-bound pose manifest: "
                    + ", ".join(supplied_bound_fields)
                )
            return self
        if self.input_mode == "offline_manifest":
            if not str(self.pose_manifest_path or "").strip():
                raise ValueError("pose_manifest_path is required for offline_manifest input")
            if not str(self.pose_manifest_sha256 or "").strip():
                raise ValueError("pose_manifest_sha256 is required for offline_manifest input")
            return self
        manual_required: dict[str, Any] = {
            "frame_timestamps_s": self.frame_timestamps_s,
            "poses": self.poses,
            "calibration_table": self.calibration_table,
        }
        missing = [key for key, value in manual_required.items() if value is None]
        if missing:
            raise ValueError(f"manual_metadata pose replay fields missing: {', '.join(missing)}")
        return self


def router(
    settings: Settings,
    jobs: JobRegistry,
    repo: CaseRepository | None = None,
    *,
    max_active_jobs: int = 1,
    execution_mode: str = "background",
) -> APIRouter:
    api = APIRouter()

    @api.post("/three-d/modeling-jobs")
    def start_three_d_modeling_job(
        request: ThreeDModelingRequest,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        payload = request.model_dump()
        try:
            job = jobs.create(
                kind="cbct_surface_modeling",
                payload=payload,
                max_active=max_active_jobs,
                singleton_keys=["source_path"],
            )
        except JobConflictError as exc:
            raise conflict_from_active_job(
                exc,
                code="cbct_modeling_job_already_active",
                message="A CBCT/STL modeling job is already queued or running for this source.",
            ) from exc
        except JobCapacityError as exc:
            raise capacity_exceeded(
                exc,
                code="cbct_modeling_job_capacity_exceeded",
                message="Too many CBCT/STL modeling jobs are queued or running. Try again later.",
            ) from exc

        if execution_mode != "worker":
            background_tasks.add_task(
                _run_modeling_job,
                jobs,
                job["job_id"],
                settings,
                request,
                repo,
            )
        return job

    @api.get("/three-d/modeling-jobs/{job_id}")
    def get_three_d_modeling_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="3D modeling job not found")
        if job.get("kind") != "cbct_surface_modeling":
            raise HTTPException(status_code=400, detail="Job is not a CBCT/STL modeling job")
        return job

    @api.post("/three-d/modeling-jobs/{job_id}/cancel")
    def cancel_three_d_modeling_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="3D modeling job not found")
        if job.get("kind") != "cbct_surface_modeling":
            raise HTTPException(status_code=400, detail="Job is not a CBCT/STL modeling job")
        canceled = jobs.cancel(job_id)
        if canceled is None:
            raise HTTPException(status_code=404, detail="3D modeling job not found")
        return canceled

    @api.post("/three-d/registration-jobs")
    def start_l1_static_registration_job(
        request: L1StaticRegistrationRequest,
        background_tasks: BackgroundTasks,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> dict[str, Any]:
        if repo is None:
            raise HTTPException(status_code=503, detail="Case repository is unavailable")
        require_case(repo, request.case_id)
        if request.doctor_review_status == "accepted" and not (
            actor.role == ReviewerRole.PHYSICIAN and actor.auth_source in TRUSTED_REVIEW_AUTH_SOURCES
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "l1_registration_review_forbidden",
                    "message": "Accepted L1 registration review requires an authenticated physician.",
                },
            )
        payload = request.model_dump(exclude_none=True, exclude_unset=True)
        payload["review_actor"] = actor.model_dump(mode="json")
        try:
            job = jobs.create(
                kind="l1_static_registration",
                payload=payload,
                max_active=max_active_jobs,
                singleton_keys=["case_id"],
            )
        except JobConflictError as exc:
            raise conflict_from_active_job(
                exc,
                code="l1_registration_job_already_active",
                message="A navigation pipeline job is already queued or running for this case.",
            ) from exc
        except JobCapacityError as exc:
            raise capacity_exceeded(
                exc,
                code="l1_registration_job_capacity_exceeded",
                message="Too many L1 static registration jobs are active. Try again later.",
            ) from exc
        if execution_mode != "worker":
            background_tasks.add_task(
                run_l1_static_registration_job,
                jobs,
                job["job_id"],
                settings,
                repo,
                payload,
            )
        return job

    @api.get("/three-d/registration-jobs/{job_id}")
    def get_l1_static_registration_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="L1 registration job not found")
        if job.get("kind") != "l1_static_registration":
            raise HTTPException(status_code=400, detail="Job is not an L1 static registration job")
        return job

    @api.post("/three-d/registration-jobs/{job_id}/cancel")
    def cancel_l1_static_registration_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="L1 registration job not found")
        if job.get("kind") != "l1_static_registration":
            raise HTTPException(status_code=400, detail="Job is not an L1 static registration job")
        canceled = jobs.cancel(job_id)
        if canceled is None:
            raise HTTPException(status_code=404, detail="L1 registration job not found")
        return canceled

    @api.post("/three-d/pose-replay-jobs")
    def start_l2_offline_pose_replay_job(
        request: L2OfflinePoseReplayRequest,
        background_tasks: BackgroundTasks,
        actor: Annotated[ReviewActorIdentity, Depends(resolve_review_actor)],
    ) -> dict[str, Any]:
        if repo is None:
            raise HTTPException(status_code=503, detail="Case repository is unavailable")
        require_case(repo, request.case_id)
        if request.doctor_review_status == "accepted" and not (
            actor.role == ReviewerRole.PHYSICIAN and actor.auth_source in TRUSTED_REVIEW_AUTH_SOURCES
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "l2_pose_replay_review_forbidden",
                    "message": "Accepted L2 pose replay review requires an authenticated physician.",
                },
            )
        payload = request.model_dump(exclude_none=True, exclude_unset=True)
        payload["review_actor"] = actor.model_dump(mode="json")
        try:
            job = jobs.create(
                kind="l2_offline_pose_replay",
                payload=payload,
                max_active=max_active_jobs,
                singleton_keys=["case_id"],
            )
        except JobConflictError as exc:
            raise conflict_from_active_job(
                exc,
                code="l2_pose_replay_job_already_active",
                message="A navigation pipeline job is already queued or running for this case.",
            ) from exc
        except JobCapacityError as exc:
            raise capacity_exceeded(
                exc,
                code="l2_pose_replay_job_capacity_exceeded",
                message="Too many L2 offline pose replay jobs are active. Try again later.",
            ) from exc
        if execution_mode != "worker":
            background_tasks.add_task(
                run_l2_offline_pose_replay_job,
                jobs,
                job["job_id"],
                settings,
                repo,
                payload,
            )
        return job

    @api.get("/three-d/pose-replay-jobs/{job_id}")
    def get_l2_offline_pose_replay_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="L2 offline pose replay job not found")
        if job.get("kind") != "l2_offline_pose_replay":
            raise HTTPException(status_code=400, detail="Job is not an L2 offline pose replay job")
        return job

    @api.post("/three-d/pose-replay-jobs/{job_id}/cancel")
    def cancel_l2_offline_pose_replay_job(job_id: str) -> dict[str, Any]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="L2 offline pose replay job not found")
        if job.get("kind") != "l2_offline_pose_replay":
            raise HTTPException(status_code=400, detail="Job is not an L2 offline pose replay job")
        canceled = jobs.cancel(job_id)
        if canceled is None:
            raise HTTPException(status_code=404, detail="L2 offline pose replay job not found")
        return canceled

    return api


def _run_modeling_job(
    jobs: JobRegistry,
    job_id: str,
    settings: Settings,
    request: ThreeDModelingRequest,
    repo: CaseRepository | None,
) -> None:
    run_cbct_surface_modeling_job(
        jobs,
        job_id,
        settings,
        Path(request.source_path),
        repo=repo,
        source_paths=[Path(path) for path in request.source_paths] if request.source_paths else None,
        label_value=request.label_value,
        case_id=request.case_id,
        dataset_id=request.dataset_id,
        decimation_step=request.decimation_step,
        source_role=request.source_role,
        source_original_filename=request.source_original_filename,
        mark_running=True,
    )
