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
    REPORT_JSON = "report_json"
    REPORT_MD = "report_md"
    DICOM_SECONDARY_CAPTURE = "dicom_secondary_capture"
    EVIDENCE_BUNDLE = "evidence_bundle"
