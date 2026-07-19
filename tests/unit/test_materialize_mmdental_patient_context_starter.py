from __future__ import annotations

import gzip
import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path

from tools.materialize_mmdental_patient_context_starter import (
    BytesRangeReader,
    _binary_stl_geometry_summary,
    _central_members,
    _csv_summary,
    _extract_member,
    _find_member,
    _nifti_gzip_header_summary,
    _paired_context_summary,
    _validated_modeling_artifacts,
    _zip64_values,
)


def _sample_zip(compression: int) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        archive.writestr(
            "MMDental/medical_records.csv",
            "filename,sex,age\n0001,female,42\n",
        )
        archive.writestr("MMDental/0001.nii.gz", b"proxy-volume")
    return stream.getvalue()


def test_range_parser_extracts_only_requested_deflated_member() -> None:
    reader = BytesRangeReader(_sample_zip(zipfile.ZIP_DEFLATED))

    directory, members = _central_members(reader)
    member = _find_member(members, "medical_records.csv")
    payload = _extract_member(reader, member)

    assert directory.entry_count == 2
    assert directory.zip64 is False
    assert payload == b"filename,sex,age\n0001,female,42\n"
    assert member.name == "MMDental/medical_records.csv"


def test_range_parser_supports_stored_member() -> None:
    reader = BytesRangeReader(_sample_zip(zipfile.ZIP_STORED))
    _, members = _central_members(reader)

    payload = _extract_member(reader, _find_member(members, "medical_records.csv"))

    assert payload.startswith(b"filename,sex,age")


def test_zip64_extra_values_follow_overflow_field_order() -> None:
    values = struct.pack("<QQQI", 123, 100, 4_500_000_000, 0)
    extra = struct.pack("<HH", 0x0001, len(values)) + values

    parsed = _zip64_values(
        extra,
        uncompressed_size=0xFFFFFFFF,
        compressed_size=0xFFFFFFFF,
        local_header_offset=0xFFFFFFFF,
        disk_start=0xFFFF,
    )

    assert parsed == (123, 100, 4_500_000_000, 0)


def test_member_lookup_rejects_ambiguous_suffix() -> None:
    reader = BytesRangeReader(_sample_zip(zipfile.ZIP_DEFLATED))
    _, members = _central_members(reader)
    duplicate = [*members, members[0]]

    try:
        _find_member(duplicate, "medical_records.csv")
    except RuntimeError as exc:
        assert "found 2" in str(exc)
    else:
        raise AssertionError("Ambiguous member lookup must fail closed")


def test_nifti_gzip_header_summary_validates_shape_and_spacing(tmp_path: Path) -> None:
    header = bytearray(348)
    struct.pack_into("<I", header, 0, 348)
    struct.pack_into("<8h", header, 40, 3, 16, 24, 32, 1, 1, 1, 1)
    struct.pack_into("<h", header, 70, 4)
    struct.pack_into("<h", header, 72, 16)
    struct.pack_into("<8f", header, 76, 1.0, 0.3, 0.3, 0.3, 0.0, 0.0, 0.0, 0.0)
    struct.pack_into("<f", header, 108, 352.0)
    header[123] = 2
    header[344:348] = b"n+1\x00"
    path = tmp_path / "case.nii.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(header)

    summary = _nifti_gzip_header_summary(path)

    assert summary["shape"] == [16, 24, 32]
    assert summary["voxel_spacing"] == [0.30000001192092896] * 3
    assert summary["spatial_unit"] == "millimeter"
    assert summary["magic"] == "n+1"


def test_paired_context_summary_checks_only_structural_presence(tmp_path: Path) -> None:
    path = tmp_path / "medical_records.csv"
    path.write_text(
        "Filename,Sex,Age,Diagnosis,Present medical history,Past medical history\n"
        "492,female,42,diagnosis text,history text,\n",
        encoding="utf-8-sig",
    )

    summary = _paired_context_summary(path, "492")

    assert summary == {
        "case_id": "492",
        "visit_record_count": 1,
        "age_present": True,
        "sex_present": True,
        "diagnosis_present": True,
        "medical_history_present": True,
    }


def test_csv_summary_reports_patient_level_conflicts_and_missingness(
    tmp_path: Path,
) -> None:
    path = tmp_path / "medical_records.csv"
    path.write_text(
        "Filename,Sex,Age,Present medical history,Past medical history,Diagnosis\n"
        "A,female,40,present history,,diagnosis A\n"
        "A,female,41,,past history,\n"
        "B,male,,,,\n",
        encoding="utf-8-sig",
    )

    summary = _csv_summary(path)

    assert summary["row_count"] == 3
    assert summary["unique_filename_count"] == 2
    assert summary["repeated_visit_record_count"] == 1
    assert summary["patients_with_multiple_visit_records"] == 1
    assert summary["patient_level_sex_counts"] == {"female": 1, "male": 1}
    assert summary["sex_conflict_patient_count"] == 0
    assert summary["age_conflict_patient_count"] == 1
    assert summary["patients_with_present_medical_history"] == 1
    assert summary["patients_with_past_medical_history"] == 1
    assert summary["patients_with_diagnosis"] == 1
    assert summary["column_non_missing_counts"]["Age"] == 2
    assert summary["column_missing_counts"]["Age"] == 1


def test_modeling_artifact_binding_requires_closed_navigation_state(
    tmp_path: Path,
) -> None:
    source = tmp_path / "492.nii.gz"
    source.write_bytes(b"source-cbct")
    surface = tmp_path / "proxy.stl"
    surface.write_bytes(
        b"\x00" * 80
        + struct.pack("<I", 1)
        + struct.pack(
            "<12fH",
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0,
        )
    )
    surface_sha256 = hashlib.sha256(surface.read_bytes()).hexdigest()
    manifest_path = tmp_path / "modeling.json"
    manifest_path.write_text(
        json.dumps(
            {
                "modeling_status": "completed",
                "source_paths": [str(source)],
                "proxy_method": "bounded-test-proxy",
                "decimation_step": 4,
                "surface_model": {
                    "path": str(surface),
                    "sha256": surface_sha256,
                    "vertex_count": 10,
                    "face_count": 1,
                    "surface_quality": {"method": "test"},
                },
                "three_d_evidence": {
                    "navigation_ready": False,
                    "registration_status": "unregistered",
                    "doctor_review_status": "not_reviewed",
                    "segmentation_review_status": "not_reviewed",
                    "orientation_review_status": "pending_review",
                    "data_boundary": "Engineering proxy only.",
                },
            }
        ),
        encoding="utf-8",
    )

    summary, paths = _validated_modeling_artifacts(
        source_cbct_path=source,
        modeling_manifest_path=manifest_path,
    )

    assert summary is not None
    assert summary["source_cbct_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert summary["navigation_ready"] is False
    assert paths == [manifest_path, surface]


def test_binary_stl_summary_rejects_empty_geometry(tmp_path: Path) -> None:
    path = tmp_path / "empty.stl"
    path.write_bytes(b"\x00" * 80 + struct.pack("<I", 0))

    try:
        _binary_stl_geometry_summary(path)
    except RuntimeError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("Empty STL geometry must fail closed")
