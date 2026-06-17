from __future__ import annotations

from src.preprocess.input_validation import detect_input_type, validate_input


def test_detects_supported_inputs(fixture_dir) -> None:
    assert detect_input_type(fixture_dir / "sample_image.png") == "2d_image"
    assert detect_input_type(fixture_dir / "sample_roi.npz") == "npz_roi"
    assert detect_input_type(fixture_dir / "sample_volume.nii.gz") == "nifti_volume"
    assert detect_input_type(fixture_dir / "dicom_series") == "dicom_series"
    assert detect_input_type(fixture_dir / "unknown.txt") == "unknown"


def test_unknown_input_is_rejected(fixture_dir) -> None:
    result = validate_input(fixture_dir / "unknown.txt")
    assert not result.accepted
    assert result.warnings[0]["code"] == "invalid_input"

