from __future__ import annotations

from typing import Any

STATUS_INVALID_INPUT = "invalid_input"
STATUS_QUALITY_BLOCKED = "quality_blocked"
STATUS_CHECKPOINT_MISSING = "checkpoint_missing"
STATUS_CLASSIFICATION_UNAVAILABLE = "classification_unavailable"
STATUS_SEGMENTATION_UNAVAILABLE = "segmentation_unavailable"
STATUS_METADATA_MISSING = "metadata_missing"
STATUS_FULL_VOLUME_REQUIRES_DETECTION = "full_volume_requires_detection"
STATUS_LOW_CONFIDENCE = "low_confidence"
STATUS_COMPLETED = "completed"

DISCLAIMER_TEXT = "Platform software for research and engineering validation. This result is not a clinical diagnosis and must not replace physician review."

KNOWN_STATUSES = {
    STATUS_INVALID_INPUT,
    STATUS_QUALITY_BLOCKED,
    STATUS_CHECKPOINT_MISSING,
    STATUS_CLASSIFICATION_UNAVAILABLE,
    STATUS_SEGMENTATION_UNAVAILABLE,
    STATUS_METADATA_MISSING,
    STATUS_FULL_VOLUME_REQUIRES_DETECTION,
    STATUS_LOW_CONFIDENCE,
    STATUS_COMPLETED,
}

DEFAULT_WARNING_MESSAGES = {
    STATUS_INVALID_INPUT: "Input is unsupported or cannot be read.",
    STATUS_QUALITY_BLOCKED: "Input quality is insufficient for this platform validation workflow.",
    STATUS_CHECKPOINT_MISSING: "Configured checkpoint is missing; fixture fallback is active.",
    STATUS_CLASSIFICATION_UNAVAILABLE: "Classification output is unavailable.",
    STATUS_SEGMENTATION_UNAVAILABLE: "Segmentation output is unavailable.",
    STATUS_METADATA_MISSING: "Medical-image metadata is missing or incomplete.",
    STATUS_FULL_VOLUME_REQUIRES_DETECTION: "Full-volume inputs require a detection or segmentation stage before direct classification.",
    STATUS_LOW_CONFIDENCE: "Prediction is close to the configured threshold and needs review.",
}


def warning(code: str, message: str | None = None, blocking: bool = False, **details: Any) -> dict[str, Any]:
    return {
        "code": code,
        "message": message or DEFAULT_WARNING_MESSAGES.get(code, code),
        "blocking": bool(blocking),
        "details": details,
    }
