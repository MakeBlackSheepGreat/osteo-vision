from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.src.domains.annotations.enums import (
    AnnotationCoordinateSpace,
    AnnotationLabel,
    AnnotationOperationMode,
    AnnotationReviewDecision,
    AnnotationSourceType,
    AnnotationStatus,
    AnnotationTool,
)
from backend.src.domains.cases.schemas import ReviewActorIdentity


class AnnotationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def finite_coordinate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("annotation coordinates must be finite")
        return value


class AnnotationOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: AnnotationTool
    points: list[AnnotationPoint] = Field(min_length=1, max_length=10000)
    radius: float | None = Field(default=None, gt=0, le=2048)
    mode: AnnotationOperationMode = AnnotationOperationMode.ADD

    @model_validator(mode="after")
    def validate_tool_shape(self) -> AnnotationOperation:
        if self.tool == AnnotationTool.POLYGON and len(self.points) < 3:
            raise ValueError("polygon operations require at least three points")
        if self.tool in {AnnotationTool.BRUSH, AnnotationTool.ERASER} and self.radius is None:
            raise ValueError("brush and eraser operations require a radius in source-image pixels")
        return self


class AnnotationGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coordinate_space: AnnotationCoordinateSpace = AnnotationCoordinateSpace.IMAGE_PIXELS
    operations: list[AnnotationOperation] = Field(default_factory=list, max_length=5000)


class AnnotationSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: AnnotationSourceType
    input_id: str | None = Field(default=None, min_length=1, max_length=160)
    run_id: str | None = Field(default=None, min_length=1, max_length=160)
    frame_index: int | None = Field(default=None, ge=0)
    timestamp_sec: float | None = Field(default=None, ge=0)
    candidate_id: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_source_selector(self) -> AnnotationSourceRequest:
        if self.source_type == AnnotationSourceType.CASE_JPEG and not self.input_id:
            raise ValueError("case_jpeg sources require input_id")
        if self.source_type == AnnotationSourceType.VIDEO_KEYFRAME and (not self.run_id or self.frame_index is None):
            raise ValueError("video_keyframe sources require run_id and frame_index")
        if self.source_type == AnnotationSourceType.MODEL_CANDIDATE and not self.candidate_id:
            raise ValueError("model_candidate sources require candidate_id")
        return self


class AnnotationSourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_key: str
    source_id: str | None = None
    title: str | None = None
    source_type: AnnotationSourceType
    input_id: str | None = None
    run_id: str | None = None
    frame_index: int | None = None
    timestamp_sec: float | None = None
    candidate_id: str | None = None
    label_hint: AnnotationLabel | None = None
    source_path: str
    source_video_path: str | None = None
    preview_path: str
    original_width: int = Field(gt=0)
    original_height: int = Field(gt=0)
    source_checksum: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnnotationVersionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_id: str
    version: int = Field(ge=1)
    geometry: AnnotationGeometry
    mask_path: str
    mask_checksum: str
    positive_pixel_count: int = Field(ge=0)
    positive_area_fraction: float = Field(ge=0, le=1)
    author: ReviewActorIdentity
    created_at: datetime
    notes: str | None = None


class ManualAnnotationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_id: str
    case_id: str
    label: AnnotationLabel
    status: AnnotationStatus = AnnotationStatus.DRAFT
    current_version: int = Field(ge=1)
    geometry: AnnotationGeometry
    source: AnnotationSourceDescriptor
    source_snapshot_path: str
    source_checksum: str
    original_width: int = Field(gt=0)
    original_height: int = Field(gt=0)
    mask_path: str
    mask_checksum: str
    positive_pixel_count: int = Field(ge=0)
    positive_area_fraction: float = Field(ge=0, le=1)
    created_by: ReviewActorIdentity
    latest_author: ReviewActorIdentity
    submitted_by: ReviewActorIdentity | None = None
    reviewed_by: ReviewActorIdentity | None = None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None
    review_notes: str | None = None
    training_eligible: bool = False
    sample_weight: float = Field(default=0.0, ge=0)
    training_exclusion_reason: str | None = None
    medical_boundary: str


class AnnotationSourceListResponse(BaseModel):
    case_id: str
    sources: list[AnnotationSourceDescriptor]


class AnnotationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: AnnotationSourceRequest
    label: AnnotationLabel
    geometry: AnnotationGeometry = Field(default_factory=AnnotationGeometry)
    notes: str | None = Field(default=None, max_length=2000)


class AnnotationVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    geometry: AnnotationGeometry
    notes: str | None = Field(default=None, max_length=2000)


class AnnotationSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    notes: str | None = Field(default=None, max_length=2000)


class AnnotationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    decision: AnnotationReviewDecision
    notes: str | None = Field(default=None, max_length=2000)


class AnnotationVersionHistoryResponse(BaseModel):
    annotation_id: str
    current_version: int
    versions: list[AnnotationVersionRecord]
    items: list[AnnotationVersionRecord]


class AnnotationDeleteResponse(BaseModel):
    deleted: bool
    annotation_id: str


class AnnotationTrainingManifestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_ids: list[str] = Field(default_factory=list, max_length=10000)
    include_ineligible: bool = False


class AnnotationTrainingManifestResponse(BaseModel):
    manifest_id: str
    schema_version: str
    created_at: datetime
    json_path: str
    manifest_path: str
    csv_path: str
    error_analysis_json_path: str
    error_analysis_csv_path: str
    sample_count: int
    eligible_count: int
    excluded_count: int
    records: list[dict[str, Any]]
    medical_boundary: str


class AnnotationTrainingManifestSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_id: str
    created_at: datetime
    created_by: ReviewActorIdentity
    case_ids: list[str] = Field(default_factory=list)
    json_path: str
    csv_path: str
    error_analysis_json_path: str
    error_analysis_csv_path: str
    eligible_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    manifest_checksum: str
    error_analysis_checksum: str


class AnnotationTrainingManifestListResponse(BaseModel):
    items: list[AnnotationTrainingManifestSummary]
