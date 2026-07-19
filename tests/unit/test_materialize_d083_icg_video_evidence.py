from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/materialize_d083_icg_video_evidence.py"
SPEC = importlib.util.spec_from_file_location("materialize_d083_icg_video_evidence", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_loads_registered_d083_archive_asset() -> None:
    record = MODULE.load_dataset_record(MODULE.DEFAULT_SOURCE_MANIFEST, candidate_id="D083")
    asset = MODULE.dataset_archive_asset(record, member_name="Video1.mpeg")
    archive_path = MODULE.resolve_dataset_asset_path(MODULE.DEFAULT_SOURCE_MANIFEST, asset["local_path"])

    assert record["target_domain_flag"] is False
    assert record["training_eligible"] is False
    assert archive_path.is_file()
    assert archive_path.stat().st_size == asset["size_bytes"]
    assert MODULE.sha256_file(archive_path) == asset["sha256"]


def test_extract_validated_member_records_crc_and_hash(tmp_path: Path) -> None:
    archive_path = tmp_path / "source.zip"
    payload = b"registered-video-payload"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("Video1.mpeg", payload)
    archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    output_path = tmp_path / "output" / "Video1.mpeg"

    result = MODULE.extract_validated_member(
        archive_path,
        member_name="Video1.mpeg",
        output_path=output_path,
        expected_archive_sha256=archive_hash,
    )

    assert output_path.read_bytes() == payload
    assert result["zip_test_status"] == "passed"
    assert result["member_size_bytes"] == len(payload)
    assert result["extracted_sha256"] == hashlib.sha256(payload).hexdigest()
    assert len(result["member_crc32"]) == 8


def test_rejects_unsafe_zip_member_even_when_requested_video_is_safe(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("Video1.mpeg", b"video")
        archive.writestr("../outside.txt", b"unsafe")

    with pytest.raises(ValueError, match="Unsafe ZIP member path"):
        MODULE.extract_validated_member(
            archive_path,
            member_name="Video1.mpeg",
            output_path=tmp_path / "Video1.mpeg",
            expected_archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        )


def test_rejects_zip_symlink_member() -> None:
    regular = ZipInfo("Video1.mpeg")
    symlink = ZipInfo("link.mpeg")
    symlink.create_system = 3
    symlink.external_attr = 0o120777 << 16

    with pytest.raises(ValueError, match="symlink"):
        MODULE.validate_zip_members([regular, symlink])


def test_rendered_report_keeps_target_domain_and_training_claims_closed() -> None:
    summary = {
        "status": "engineering_validation_passed",
        "dataset": {
            "domain_tier": MODULE.DOMAIN_TIER,
            "source_page_url": "https://example.test/d083",
            "doi": "10.0/example",
            "license": "CC BY 4.0",
            "data_boundary": MODULE.DATA_BOUNDARY,
        },
        "analysis": {
            "selected_keyframe_count": 2,
            "fluorescence_dynamics": {"available": True},
            "engineering_qc": {
                "dark_baseline_frame_count": 1,
                "dark_baseline_nonempty_mask": True,
            },
            "model": {"model_id": "proxy-model"},
            "keyframe_manifest_path": "keyframes.json",
            "video_segmentation_manifest_path": "segmentation.json",
            "frame_details_manifest_path": "details.json",
            "contact_sheet_path": "contact.jpg",
        },
        "checks": {"source_archive_integrity_verified": True, "pass": True},
        "source_archive": {"path": "source.zip"},
        "extracted_mpeg": {"path": "Video1.mpeg"},
        "derived_mp4": {"path": "Video1.mp4"},
    }

    report = MODULE.render_report(summary)

    assert "训练准入：`false`" in report
    assert "目标域标记：`false`" in report
    assert "禁止用于颌骨骨髓炎诊断" in report


def test_uniform_timestamps_cover_baseline_and_last_decodable_frame() -> None:
    timestamps = MODULE.uniform_timestamps(10.0, count=3, fps=2.0)

    assert timestamps == [0.0, 4.75, 9.5]


def test_engineering_qc_flags_nonempty_dark_baseline_mask() -> None:
    details = [
        {
            "frame_index": 0,
            "timestamp_sec": 0.0,
            "p95_intensity": 0.01,
            "positive_area_fraction": 0.15,
        },
        {
            "frame_index": 30,
            "timestamp_sec": 1.0,
            "p95_intensity": 0.8,
            "positive_area_fraction": 0.2,
        },
    ]

    result = MODULE.build_engineering_qc(details)

    assert result["dark_baseline_frame_count"] == 1
    assert result["dark_baseline_nonempty_frame_count"] == 1
    assert result["dark_baseline_nonempty_mask"] is True
    assert result["mean_dark_baseline_positive_area_fraction"] == 0.15
    assert details[0]["engineering_qc"]["dark_baseline"] is True


def test_dataset_manifest_fixture_is_valid_json() -> None:
    payload = json.loads(MODULE.DEFAULT_SOURCE_MANIFEST.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "osteo-vision-bone-activity-gap-v1"
