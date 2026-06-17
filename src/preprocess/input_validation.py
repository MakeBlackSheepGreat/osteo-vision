from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.schemas import InputSummary
from src.core.warnings import STATUS_INVALID_INPUT, warning
from src.io.dicom_io import dicom_summary, is_dicom_path
from src.io.image_io import image_metadata, is_image_path
from src.io.nifti_io import is_nifti_path
from src.preprocess.image_quality import assess_basic_quality


def detect_input_type(path: str | Path) -> str:
    p = Path(path)
    if p.is_dir() and is_dicom_path(p):
        return "dicom_series"
    if is_image_path(p):
        return "2d_image"
    if p.suffix.lower() == ".npz":
        return "npz_roi"
    if is_dicom_path(p):
        return "dicom_series"
    if is_nifti_path(p):
        return "nifti_volume"
    return "unknown"


def validate_input(path: str | Path) -> InputSummary:
    p = Path(path)
    input_type = detect_input_type(p)
    accepted, reason = assess_basic_quality(p, input_type)
    warnings = []
    metadata: dict[str, Any] = {}
    if input_type == "2d_image" and p.exists():
        metadata.update(image_metadata(p))
    elif input_type == "dicom_series" and p.exists():
        metadata.update(dicom_summary(p))
    elif input_type == "npz_roi":
        metadata.update({"extension": ".npz", "metadata_status": "not_loaded"})
    elif input_type == "nifti_volume":
        metadata.update({"extension": ".nii.gz" if p.name.lower().endswith(".nii.gz") else ".nii"})
    if not accepted:
        warnings.append(warning(STATUS_INVALID_INPUT, reason, True))
    return InputSummary(path=str(p), input_type=input_type, accepted=accepted, reason=reason, metadata=metadata, warnings=warnings)

