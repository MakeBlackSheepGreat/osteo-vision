from __future__ import annotations

import json
import zipfile
from pathlib import Path

from tools.download_c3vd_l2_proxy import (
    C3VD_SAMPLE,
    direct_download_url,
    inspect_c3vd_archive,
    write_manifest,
)


def test_c3vd_proxy_source_is_fixed_to_official_sample() -> None:
    assert C3VD_SAMPLE["candidate_id"] == "D087"
    assert C3VD_SAMPLE["file_name"] == "sampledata.zip"
    assert C3VD_SAMPLE["size_bytes"] == 1_515_094_074
    assert C3VD_SAMPLE["license"] == "CC BY-NC-SA 4.0"
    assert "drive.usercontent.google.com" in direct_download_url(str(C3VD_SAMPLE["google_drive_file_id"]))


def test_c3vd_manifest_preserves_non_target_safety_boundary(tmp_path: Path) -> None:
    row = {
        "candidate_id": "D087",
        "size_bytes": 123,
        "target_domain_flag": False,
        "training_eligible": False,
        "navigation_claim_allowed": False,
        "data_boundary": "software engineering validation only",
    }
    write_manifest(tmp_path, [row])

    payload = json.loads((tmp_path / "c3vd_l2_proxy_manifest.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "osteo-vision-c3vd-l2-proxy-download-v3"
    assert payload["record_count"] == 1
    assert payload["records"][0]["navigation_claim_allowed"] is False
    assert "jaw-phantom" in payload["medical_boundary"]


def test_c3vd_archive_inventory_validates_paired_frames_and_pose_log(tmp_path: Path) -> None:
    archive_path = tmp_path / "sampledata.zip"
    matrix = ",".join(["1"] * 16)
    config = """; camera
width = 1350
height = 1080
cx = 678.5
cy = 543.0
a0 = 769.2
a1 = 0
a2 = -0.0008
a3 = 0.0000006
a4 = -0.000000001
c = 1
d = 0
e = 0
poseStartTime = 3.136
"""
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("sampledata/config.ini", config)
        archive.writestr("sampledata/mask.png", b"mask")
        archive.writestr("sampledata/model.mtl", b"material")
        archive.writestr("sampledata/model.obj", b"model")
        archive.writestr("sampledata/pose.txt", f"0,{matrix}\n0.016,{matrix}\n")
        for index in range(2):
            archive.writestr(f"sampledata/rgb/{index:04d}.png", b"rgb")
            archive.writestr(f"sampledata/depth/{index:04d}.png", b"depth")

    inventory = inspect_c3vd_archive(archive_path)

    assert inventory["zip_crc_verified"] is True
    assert inventory["paired_frame_count"] == 2
    assert inventory["pose_record_count"] == 2
    assert inventory["duplicate_pose_timestamp_count"] == 0
    assert inventory["runtime_pose_use_requires_deduplication"] is False
    assert inventory["camera_model"] == "scaramuzza_ocamcalib_polynomial_v1"
    assert inventory["runtime_projection_supported"] is True
