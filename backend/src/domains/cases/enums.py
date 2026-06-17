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
    OVERLAY = "overlay"
    HEATMAP = "heatmap"
    NORMALIZED_FLUORESCENCE = "normalized_fluorescence"
    ROI_MASK = "roi_mask"
    QUANTIFICATION_CSV = "quantification_csv"
    REPORT_JSON = "report_json"
    REPORT_MD = "report_md"
    EVIDENCE_BUNDLE = "evidence_bundle"
