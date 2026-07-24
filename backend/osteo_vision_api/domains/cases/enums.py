from __future__ import annotations

from enum import StrEnum


class CaseStatus(StrEnum):
    DRAFT = "draft"
    LOADED = "loaded"
    ANALYZED = "analyzed"
    REVIEWING = "reviewing"
    REVIEWED = "reviewed"
    EXPORTED = "exported"
    ARCHIVED = "archived"


class InputChannel(StrEnum):
    WHITE_LIGHT = "white_light"
    FLUORESCENCE = "fluorescence"
    DEVICE_OVERLAY = "device_overlay"
    SEQUENCE = "sequence"
    VIDEO = "video"


class QualityFlagCode(StrEnum):
    MISMATCHED = "mismatched"
    WEAK_SIGNAL = "weak_signal"
    OVEREXPOSED = "overexposed"
    UNDEREXPOSED = "underexposed"
    BLURRED = "blurred"
    OCCLUDED = "occluded"
    LOW_CONFIDENCE = "low_confidence"
    OFFICIAL_PROFILE_MISMATCH = "official_profile_mismatch"
    UNUSABLE = "unusable"


class ReviewState(StrEnum):
    REVIEW_REQUIRED = "review_required"
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"


class ReviewerRole(StrEnum):
    PHYSICIAN = "physician"
    PROJECT_REVIEWER = "project_reviewer"
    ENGINEERING_REVIEWER = "engineering_reviewer"
    LEGACY_UNVERIFIED = "legacy_unverified"


class RegionSource(StrEnum):
    MANUAL = "manual"
    AI = "ai"


class ArtifactKind(StrEnum):
    KEYFRAME = "keyframe"
    OVERLAY = "overlay"
    VIDEO_OVERLAY = "video_overlay"
    VIDEO_MASK = "video_mask"
    VIDEO_SEGMENTATION_MANIFEST = "video_segmentation_manifest"
    PROBABILITY_MAP = "probability_map"
    HEATMAP = "heatmap"
    NORMALIZED_FLUORESCENCE = "normalized_fluorescence"
    COLORBAR = "colorbar"
    ROI_MASK = "roi_mask"
    QUANTIFICATION_CSV = "quantification_csv"
    REVIEW_MANIFEST_JSON = "review_manifest_json"
    REVIEW_MANIFEST_CSV = "review_manifest_csv"
    ANNOTATION_AUDIT_JSON = "annotation_audit_json"
    ANNOTATION_AUDIT_CSV = "annotation_audit_csv"
    ANNOTATION_MANIFEST_REGISTRY = "annotation_manifest_registry"
    THREE_D_MODEL = "three_d_model"
    THREE_D_MODELING_MANIFEST = "three_d_modeling_manifest"
    THREE_D_REGISTRATION_TRANSFORM = "three_d_registration_transform"
    THREE_D_REGISTRATION_MANIFEST = "three_d_registration_manifest"
    THREE_D_POSE_REPLAY_MANIFEST = "three_d_pose_replay_manifest"
    THREE_D_POSE_REPLAY_FRAMES = "three_d_pose_replay_frames"
    THREE_D_AR_OVERLAY = "three_d_ar_overlay"
    THREE_D_SCENE_MANIFEST = "three_d_scene_manifest"
    REPORT_JSON = "report_json"
    REPORT_MD = "report_md"
    DICOM_SECONDARY_CAPTURE = "dicom_secondary_capture"
    EVIDENCE_BUNDLE = "evidence_bundle"
    HOSPITAL_INTAKE_MANIFEST = "hospital_intake_manifest"
    THREE_CHANNEL_QC_REPORT = "three_channel_qc_report"
    THREE_CHANNEL_DIFFERENCE_HEATMAP = "three_channel_difference_heatmap"
    BONE_ACTIVITY_CHECKPOINT_EVIDENCE = "bone_activity_checkpoint_evidence"
    BONE_ACTIVITY_RAW_ENGINEERING_OUTPUTS = "bone_activity_raw_engineering_outputs"
