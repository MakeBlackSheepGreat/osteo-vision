from __future__ import annotations

from enum import StrEnum


class AnnotationLabel(StrEnum):
    LESION = "lesion"
    EXPOSED_BONE = "exposed_bone"
    FLUORESCENCE_SIGNAL = "fluorescence_signal"
    BOUNDARY_RISK = "boundary_risk"
    UNCERTAIN = "uncertain"
    LOW_ACTIVITY = "low_activity"
    TRANSITION = "transition"
    HIGH_ACTIVITY = "high_activity"
    IGNORE = "ignore"


class AnnotationSourceType(StrEnum):
    CASE_JPEG = "case_jpeg"
    VIDEO_KEYFRAME = "video_keyframe"
    MODEL_CANDIDATE = "model_candidate"


class AnnotationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class AnnotationCoordinateSpace(StrEnum):
    IMAGE_PIXELS = "image_pixels"
    NORMALIZED = "normalized"


class AnnotationTool(StrEnum):
    BRUSH = "brush"
    ERASER = "eraser"
    POLYGON = "polygon"


class AnnotationOperationMode(StrEnum):
    ADD = "add"
    ERASE = "erase"


class AnnotationReviewDecision(StrEnum):
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
