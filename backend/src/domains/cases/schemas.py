from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from backend.src.core.disclaimers import DISCLAIMER_VERSION
from backend.src.domains.cases.enums import (
    ArtifactKind,
    CaseStatus,
    InputChannel,
    QualityFlagCode,
    RegionSource,
    ReviewState,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QualityFlag(BaseModel):
    code: QualityFlagCode
    message: str
    blocking: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class CaseInputAsset(BaseModel):
    input_id: str
    channel: InputChannel
    path: str
    mime_type: str | None = None
    dimensions: list[int] = Field(default_factory=list)
    timestamps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    quality_flags: list[QualityFlag] = Field(default_factory=list)


class CandidateRegion(BaseModel):
    candidate_id: str
    run_id: str
    score: float | None = None
    risk_type: str = "candidate"
    confidence: float | None = None
    status: ReviewState = ReviewState.REVIEW_REQUIRED
    explanation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegionOfInterest(BaseModel):
    roi_id: str
    case_id: str
    source: RegionSource = RegionSource.MANUAL
    geometry: dict[str, Any] = Field(default_factory=dict)
    label: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    review_state: ReviewState = ReviewState.REVIEW_REQUIRED
    candidate_id: str | None = None


class ReviewEvent(BaseModel):
    event_id: str
    case_id: str
    actor: str
    action: str
    target_id: str
    before_state: str | None = None
    after_state: str | None = None
    timestamp: datetime = Field(default_factory=_utc_now)
    notes: str | None = None


class EvidenceArtifact(BaseModel):
    artifact_id: str
    case_id: str
    run_id: str | None = None
    kind: ArtifactKind
    path: str
    checksum: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)


class AnalysisRun(BaseModel):
    run_id: str
    case_id: str
    method_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: str = "queued"
    created_at: datetime = Field(default_factory=_utc_now)
    duration: float | None = None
    notes: str | None = None
    candidate_regions: list[CandidateRegion] = Field(default_factory=list)
    fused_outputs: dict[str, Any] = Field(default_factory=dict)
    quantitative_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class CaseRecord(BaseModel):
    case_id: str
    title: str
    status: CaseStatus = CaseStatus.DRAFT
    version: int = 1
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    disclaimer_version: str = DISCLAIMER_VERSION
    review_summary: dict[str, Any] = Field(default_factory=dict)
    inputs: list[CaseInputAsset] = Field(default_factory=list)
    analysis_runs: list[AnalysisRun] = Field(default_factory=list)
    review_events: list[ReviewEvent] = Field(default_factory=list)
    artifacts: list[EvidenceArtifact] = Field(default_factory=list)
    rois: list[RegionOfInterest] = Field(default_factory=list)
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str | None = None


class CaseCreateRequest(BaseModel):
    title: str
    disclaimer_version: str = DISCLAIMER_VERSION
    metadata: dict[str, Any] = Field(default_factory=dict)


class InputCreateRequest(BaseModel):
    channel: InputChannel
    path: str
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisRunCreateRequest(BaseModel):
    selected_input_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    roi_hints: list[dict[str, Any]] = Field(default_factory=list)


class RegionUpdateRequest(BaseModel):
    review_state: ReviewState
    geometry: dict[str, Any] | None = None
    label: str | None = None
    reviewer_notes: str | None = None


class BoneGateMaskCreateRequest(BaseModel):
    geometry: dict[str, Any] | None = None
    review_state: ReviewState = ReviewState.REVIEW_REQUIRED
    label: str | None = "exposed_bone"
    reviewer_notes: str | None = None
    prompt_source: str = "frontend_bbox_prompt"


class BoneGateMaskEditRequest(BaseModel):
    mask_png_base64: str
    review_state: ReviewState = ReviewState.MODIFIED
    label: str | None = "exposed_bone"
    reviewer_notes: str | None = None


class ReviewEventCreateRequest(BaseModel):
    action: str
    target_id: str
    before_state: str | None = None
    after_state: str | None = None
    notes: str | None = None


class ExportRequest(BaseModel):
    export_format: str = "bundle"
    selected_artifacts: list[str] = Field(default_factory=list)


class ExportResponse(BaseModel):
    bundle_path: str
    report_path: str
    manifest_path: str
    case_id: str
    dicom_path: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    artifact_entries: list[dict[str, Any]] = Field(default_factory=list)
