from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from osteo_vision_core.io.content_probe import probe_file_signature, signature_matches_upload_suffix
from osteo_vision_core.preprocess.input_validation import detect_input_type, validate_input


def test_detects_supported_inputs(fixture_dir) -> None:
    assert detect_input_type(fixture_dir / "sample_image.png") == "2d_image"
    assert detect_input_type(fixture_dir / "sample_roi.npz") == "npz_roi"
    assert detect_input_type(fixture_dir / "sample_volume.nii.gz") == "nifti_volume"
    assert detect_input_type(fixture_dir / "dicom_series") == "dicom_series"
    assert detect_input_type(fixture_dir / "unknown.txt") == "unknown"


def test_detects_and_summarizes_mp4_video(tmp_path) -> None:
    video_path = tmp_path / "official_device_sample.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 48))
    for index in range(3):
        frame = np.full((48, 64, 3), index * 40, dtype=np.uint8)
        writer.write(frame)
    writer.release()

    assert detect_input_type(video_path) == "video_file"
    result = validate_input(video_path)
    assert result.accepted
    assert result.metadata["extension"] == ".mp4"
    assert result.metadata["width"] == 64
    assert result.metadata["height"] == 48
    assert result.metadata["official_target_resolution"] == "3840x2160"
    assert result.metadata["official_input_profile"]["target_resolution"] == [3840, 2160]
    assert result.metadata["official_input_profile"]["resolution_match"] is False
    assert any(warning["code"] == "official_video_resolution_mismatch" for warning in result.warnings)


def test_image_official_profile_flags_non_jpeg_non_4k(tmp_path) -> None:
    image_path = tmp_path / "proxy.png"

    Image.fromarray(np.zeros((48, 64, 3), dtype=np.uint8)).save(image_path)

    result = validate_input(image_path)

    assert result.accepted
    assert result.metadata["official_input_profile"]["target_format"] == "jpeg"
    assert result.metadata["official_input_profile"]["format_match"] is False
    assert result.metadata["official_input_profile"]["resolution_match"] is False
    assert {warning["code"] for warning in result.warnings} >= {
        "official_image_format_mismatch",
        "official_image_resolution_mismatch",
    }


def test_rejects_fake_mp4_payload(tmp_path) -> None:
    video_path = tmp_path / "fake.mp4"
    video_path.write_text("<html>captcha</html>", encoding="utf-8")

    result = validate_input(video_path)

    assert not result.accepted
    assert result.reason == "video capture could not be opened"


def test_content_probe_detects_upload_signature_mismatch(tmp_path) -> None:
    fake_image = tmp_path / "fake.jpg"
    fake_image.write_text("<html>captcha</html>", encoding="utf-8")

    probe = probe_file_signature(fake_image)
    ok, reason, _ = signature_matches_upload_suffix(fake_image, ".jpg")

    assert probe["detected_family"] == "html"
    assert not ok
    assert "image content" in reason


def test_unknown_input_is_rejected(fixture_dir) -> None:
    result = validate_input(fixture_dir / "unknown.txt")
    assert not result.accepted
    assert result.warnings[0]["code"] == "invalid_input"
