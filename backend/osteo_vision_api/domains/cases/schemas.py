from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.osteo_vision_api.core.disclaimers import DISCLAIMER_VERSION
from backend.osteo_vision_api.domains.cases.enums import (
    ArtifactKind,
    CaseStatus,
    InputChannel,
    QualityFlagCode,
    RegionSource,
    ReviewerRole,
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


class ReviewActorIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")
    role: ReviewerRole
    institution: str = Field(min_length=2, max_length=160)
    auth_source: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")

    @field_validator("actor_id", "institution", "auth_source", mode="before")
    @classmethod
    def strip_identity_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_identity_trust_boundary(self) -> ReviewActorIdentity:
        if self.role == ReviewerRole.LEGACY_UNVERIFIED:
            raise ValueError("legacy_unverified cannot be used for a new review identity")
        if self.role == ReviewerRole.PHYSICIAN and self.auth_source not in {
            "institution_sso",
            "signed_session",
            "verified_identity_token",
        }:
            raise ValueError("physician review requires a verified authentication source")
        return self


class ReviewIdentityStatus(ReviewActorIdentity):
    authenticated: bool


class ReviewEvent(BaseModel):
    event_id: str
    case_id: str
    actor: str = "legacy-reviewer"
    actor_id: str = "legacy-reviewer"
    role: ReviewerRole = ReviewerRole.LEGACY_UNVERIFIED
    institution: str = "unrecorded"
    auth_source: str = "legacy_event"
    action: str
    target_id: str
    before_state: str | None = None
    after_state: str | None = None
    timestamp: datetime = Field(default_factory=_utc_now)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_actor(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        legacy_actor = str(payload.get("actor") or "legacy-reviewer").strip() or "legacy-reviewer"
        payload.setdefault("actor", legacy_actor)
        payload.setdefault("actor_id", legacy_actor)
        payload.setdefault("role", ReviewerRole.LEGACY_UNVERIFIED)
        payload.setdefault("institution", "unrecorded")
        payload.setdefault("auth_source", "legacy_event")
        return payload


class EvidenceArtifact(BaseModel):
    artifact_id: str
    case_id: str
    run_id: str | None = None
    kind: ArtifactKind
    path: str
    checksum: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)


class HospitalIntakeMetadata(BaseModel):
    source_type: str = "institutional_handover"
    source_organization: str
    external_case_id: str
    batch_ids: list[str] = Field(default_factory=list)
    handover_ids: list[str] = Field(default_factory=list)
    authorization_status: str
    usage_scope: str
    deidentification_confirmed: bool
    deidentification_method: str | None = None
    mapping_held_by_institution: bool
    target_condition_confirmed: bool = False
    admission_status: str = "engineering_analysis_ready"
    report_paths: list[str] = Field(default_factory=list)


class ClinicalLabResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    value: float | str
    unit: str | None = Field(default=None, max_length=40)
    reference_range: str | None = Field(default=None, max_length=80)
    measured_at: datetime | None = None
    abnormal_flag: Literal["low", "normal", "high", "unknown"] = "unknown"


class ClinicalContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age_years: int | None = Field(default=None, ge=0, le=130)
    age_group: Literal["pediatric", "young_adult", "middle_aged", "older_adult", "unknown"] = "unknown"
    sex_at_birth: Literal["female", "male", "intersex", "unknown", "not_recorded"] = "not_recorded"
    comorbidities: list[str] = Field(default_factory=list)
    comorbidities_reviewed: bool = False
    medications: list[str] = Field(default_factory=list)
    medications_reviewed: bool = False
    labs: list[ClinicalLabResult] = Field(default_factory=list)
    source_organization: str | None = Field(default=None, max_length=160)
    recorded_by: str | None = Field(default=None, max_length=128)
    recorded_at: datetime | None = None
    review_status: Literal["unreviewed", "review_required", "verified"] = "unreviewed"
    deidentified: bool = True
    clinical_use_boundary: Literal[
        "risk_prior_and_calibration_only_no_spatial_boundary_effect",
        "restricted_spatial_conditioning_with_physician_review",
    ] = "risk_prior_and_calibration_only_no_spatial_boundary_effect"

    @model_validator(mode="after")
    def derive_age_group(self) -> ClinicalContextInput:
        if self.age_years is None:
            group = "unknown"
        elif self.age_years < 18:
            group = "pediatric"
        elif self.age_years < 40:
            group = "young_adult"
        elif self.age_years < 65:
            group = "middle_aged"
        else:
            group = "older_adult"
        if self.age_group != group:
            object.__setattr__(self, "age_group", group)
        return self


class ClinicalContext(ClinicalContextInput):
    verified_by: ReviewActorIdentity | None = None
    verified_at: datetime | None = None


class ClinicalContextUpdateRequest(ClinicalContext):
    pass


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
    intake_metadata: HospitalIntakeMetadata | None = None
    clinical_context: ClinicalContext = Field(default_factory=ClinicalContext)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    three_d_evidence: dict[str, Any] = Field(default_factory=dict)
    three_d_modeling: dict[str, Any] = Field(default_factory=dict)
    inputs: list[CaseInputAsset] = Field(default_factory=list)
    analysis_runs: list[AnalysisRun] = Field(default_factory=list)
    review_events: list[ReviewEvent] = Field(default_factory=list)
    artifacts: list[EvidenceArtifact] = Field(default_factory=list)
    rois: list[RegionOfInterest] = Field(default_factory=list)
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str | None = None


class ThreeDRuntimeModelAsset(BaseModel):
    """A controlled model asset exposed to the isolated 3D renderer."""

    asset_id: Literal["model"] = "model"
    url: str = Field(min_length=1)
    format: Literal["stl", "glb", "gltf"]
    file_name: str = Field(min_length=1, max_length=255)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    rendering_status: Literal["ready", "unsupported_format"] = "ready"
    rendering_failure_reason: str | None = Field(default=None, max_length=160)


class ThreeDRuntimeSafety(BaseModel):
    """Safety state available to the isolated renderer without patient context."""

    navigation_level: str = Field(min_length=1, max_length=32)
    navigation_ready: bool = False
    registration_status: str = Field(min_length=1, max_length=80)
    doctor_review_status: str = Field(min_length=1, max_length=80)
    fallback_mode: str = Field(min_length=1, max_length=120)
    failure_reasons: list[str] = Field(default_factory=list)
    boundary: str = Field(min_length=1, max_length=4000)


class ThreeDRuntimeSpatialMapping(BaseModel):
    """Checksum-bound coordinate contract for placing video candidates on a model."""

    schema_version: Literal["osteo-vision-three-d-runtime-spatial-mapping-v1"]
    model_coordinate_space: str | None = Field(default=None, max_length=160)
    transform_sha256: str | None = Field(default=None, min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    status: Literal["verified", "unavailable"] = "unavailable"
    failure_reasons: list[str] = Field(default_factory=list)


class ThreeDRuntimeSnapshot(BaseModel):
    """Versioned minimum scene contract for the standalone 3D runtime."""

    schema_version: Literal["osteo-vision-three-d-runtime-snapshot-v2"]
    case_id: str = Field(min_length=1, max_length=160)
    case_version: int = Field(ge=1)
    generated_at: datetime
    snapshot_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    mode_label: str = Field(min_length=1, max_length=160)
    candidate_regions: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    three_d_evidence: dict[str, Any] = Field(default_factory=dict)
    model_asset: ThreeDRuntimeModelAsset | None = None
    spatial_mapping: ThreeDRuntimeSpatialMapping
    safety: ThreeDRuntimeSafety


class CaseCreateRequest(BaseModel):
    title: str
    disclaimer_version: str = DISCLAIMER_VERSION
    metadata: dict[str, Any] = Field(default_factory=dict)


class InputCreateRequest(BaseModel):
    channel: InputChannel
    path: str
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HospitalIntakeFileRequest(BaseModel):
    external_case_id: str = Field(min_length=3, max_length=64)
    path: str
    channel: InputChannel
    acquisition_mode: Literal[
        "white_light",
        "fluorescence",
        "overlay",
        "mode_switching",
        "synchronized_dual_channel",
        "unknown",
    ]
    channel_relationship: Literal[
        "single_channel",
        "synchronized_pair",
        "mode_switch",
        "overlay_only",
        "unknown",
    ] = "unknown"
    pair_id: str | None = None
    original_filename: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


class HospitalIntakeBatchRequest(BaseModel):
    batch_id: str = Field(min_length=3, max_length=64)
    handover_id: str = Field(min_length=3, max_length=128)
    source_organization: str = Field(min_length=2, max_length=160)
    received_by: str = Field(min_length=2, max_length=80)
    received_at: datetime
    authorization_status: Literal["approved", "pending", "restricted", "denied"]
    usage_scope: str = Field(min_length=3, max_length=240)
    deidentification_confirmed: bool
    deidentification_method: str | None = None
    mapping_held_by_institution: bool
    target_condition_confirmed: bool = False
    files: list[HospitalIntakeFileRequest] = Field(min_length=1)


class AnalysisRunCreateRequest(BaseModel):
    selected_input_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    roi_hints: list[dict[str, Any]] = Field(default_factory=list)


class Task2PairedFrameReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_index: int = Field(ge=0)
    white_input_id: str = Field(min_length=1, max_length=160)
    fluorescence_input_id: str = Field(min_length=1, max_length=160)
    captured_at: datetime | None = None
    white_timestamp_ms: float | None = Field(default=None, ge=0.0)
    fluorescence_timestamp_ms: float | None = Field(default=None, ge=0.0)
    magnification: float | None = Field(default=None, ge=1.3, le=17.0)
    working_distance_mm: float | None = Field(default=None, ge=200.0, le=630.0)


class Task2PairedSequenceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["osteo-vision-task2-paired-sequence-v1"]
    sequence_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    frames: list[Task2PairedFrameReference] = Field(min_length=2, max_length=120)
    synchronization_tolerance_ms: float = Field(default=33.34, gt=0.0, le=1000.0)
    alpha: float = Field(default=0.45, ge=0.0, le=1.0)
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    colormap: Literal["green", "amber", "magenta"] = "green"
    prefer_gpu: bool = True

    @model_validator(mode="after")
    def validate_frame_order_and_unique_assets(self) -> Task2PairedSequenceManifest:
        indexes = [frame.frame_index for frame in self.frames]
        if indexes != sorted(indexes) or len(indexes) != len(set(indexes)):
            raise ValueError("paired sequence frame_index values must be unique and strictly increasing")
        white_ids = [frame.white_input_id for frame in self.frames]
        fluorescence_ids = [frame.fluorescence_input_id for frame in self.frames]
        if len(white_ids) != len(set(white_ids)) or len(fluorescence_ids) != len(set(fluorescence_ids)):
            raise ValueError("paired sequence input assets must be unique per frame")
        captured = [frame.captured_at for frame in self.frames if frame.captured_at is not None]
        if len(captured) > 1 and captured != sorted(captured):
            raise ValueError("paired sequence captured_at values must be chronological")
        return self


class ReviewMutationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegionUpdateRequest(ReviewMutationRequest):
    review_state: ReviewState
    geometry: dict[str, Any] | None = None
    label: str | None = Field(default=None, max_length=160)
    reviewer_notes: str | None = Field(default=None, max_length=2000)


class BoneGateMaskCreateRequest(ReviewMutationRequest):
    geometry: dict[str, Any] | None = None
    review_state: ReviewState = ReviewState.REVIEW_REQUIRED
    label: str | None = Field(default="exposed_bone", max_length=160)
    reviewer_notes: str | None = Field(default=None, max_length=2000)
    prompt_source: str = Field(default="frontend_bbox_prompt", min_length=2, max_length=80)


class BoneGateMaskEditRequest(ReviewMutationRequest):
    mask_png_base64: str = Field(min_length=1)
    review_state: ReviewState = ReviewState.MODIFIED
    label: str | None = Field(default="exposed_bone", max_length=160)
    reviewer_notes: str | None = Field(default=None, max_length=2000)


class ReviewEventCreateRequest(ReviewMutationRequest):
    action: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    target_id: str = Field(min_length=1, max_length=160)
    before_state: str | None = Field(default=None, max_length=80)
    after_state: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)


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
