from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/materialize_kits23_patient_conditioning_proxy.py"
SPEC = importlib.util.spec_from_file_location("materialize_kits23_patient_conditioning_proxy", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_materializes_five_patient_ras_proxy_with_closed_runtime_gate(
    tmp_path: Path,
) -> None:
    source_manifest = build_source_fixture(tmp_path / "source")
    output = tmp_path / "output"

    result = MODULE.materialize_kits23_patient_conditioning_proxy(
        source_manifest=source_manifest,
        output_dir=output,
    )

    assert result["status"] == "engineering_validation_passed"
    assert result["sample_count"] == 50
    assert result["split_sample_counts"] == {"train": 30, "val": 10, "test": 10}
    assert result["split_group_counts"] == {"train": 3, "val": 1, "test": 1}
    assert result["patient_leakage_checks"]["leakage_detected"] is False
    assert result["checks"]["affine_and_in_plane_spacing_provenance_emitted"] is True
    training_eligibility = result["training_eligibility"]
    assert training_eligibility["training_eligible"] is True
    assert training_eligibility["scope"] == "proxy_pretraining_only"
    assert training_eligibility["training_scope"] == "non_target_proxy_pretraining"
    assert training_eligibility["source_manifest_training_eligible"] is False
    assert training_eligibility["target_domain"] is False
    assert training_eligibility["runtime_replacement_allowed"] is False
    assert training_eligibility["independent_test_set"] is False
    assert training_eligibility["physician_reviewed"] is False
    assert result["channel_contract"]["fluorescence_path"] == ("non_fluorescence_ct_proxy")
    assert all(
        evidence["canonical_ct_axcodes"] == ["R", "A", "S"] and evidence["canonical_mask_axcodes"] == ["R", "A", "S"]
        for evidence in result["orientation_evidence"]
    )

    csv_path = output / "patient_conditioned_kits23_proxy_samples.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 50
    assert {row["patient_group_id"] for row in rows if row["split"] == "train"} == {
        "case_00000",
        "case_00002",
        "case_00003",
    }
    assert {row["patient_group_id"] for row in rows if row["split"] == "val"} == {"case_00001"}
    assert {row["patient_group_id"] for row in rows if row["split"] == "test"} == {"case_00004"}
    assert all(row["target_domain"] == "false" for row in rows)
    assert all(row["training_eligible"] == "true" for row in rows)
    assert all(row["training_scope"] == "non_target_proxy_pretraining" for row in rows)
    assert all(row["runtime_replacement_allowed"] == "false" for row in rows)
    assert all(row["channel_semantics"] == "non_fluorescence_ct_proxy" for row in rows)
    assert all(
        sum(row["slice_role"] == "foreground" for row in rows if row["patient_group_id"] == case_id) == 8
        for case_id in MODULE.CASE_SPLITS
    )

    first = rows[0]
    with Image.open(output / first["white_path"]) as image:
        assert image.mode == "RGB"
        assert image.size == (16, 16)
    with Image.open(output / first["fluorescence_path"]) as image:
        assert image.mode == "L"
    with Image.open(output / first["mask_path"]) as image:
        assert set(np.unique(np.asarray(image))) <= {0, 255}
    values = json.loads(first["clinical_values_json"])
    present = json.loads(first["clinical_present_json"])
    mapping = json.loads(first["clinical_mapping_json"])
    assert tuple(sorted(values)) == tuple(sorted(MODULE.FEATURE_NAMES))
    assert tuple(sorted(mapping)) == tuple(sorted(MODULE.FEATURE_NAMES))
    assert all(isinstance(mapping[name], str) and mapping[name].strip() for name in MODULE.FEATURE_NAMES)
    assert present["age_years"] is True
    source_affine_json = first["source_ct_affine_json"]
    canonical_affine_json = first["canonical_ct_affine_json"]
    assert hashlib.sha256(source_affine_json.encode("utf-8")).hexdigest() == first["source_ct_affine_sha256"]
    assert hashlib.sha256(canonical_affine_json.encode("utf-8")).hexdigest() == first["canonical_ct_affine_sha256"]
    canonical_affine = np.asarray(json.loads(canonical_affine_json), dtype=np.float64)
    assert float(first["canonical_axis0_spacing_mm"]) == pytest.approx(np.linalg.norm(canonical_affine[:3, 0]))
    assert float(first["canonical_axis1_spacing_mm"]) == pytest.approx(np.linalg.norm(canonical_affine[:3, 1]))
    assert first["spacing_unit"] == "mm"
    assert first["spacing_axis_contract"] == "array_axis0_rows;array_axis1_columns"


def test_rejects_registered_source_size_or_hash_drift(tmp_path: Path) -> None:
    source_manifest = build_source_fixture(tmp_path / "source")
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    ct_record = next(
        record
        for record in payload["records"]
        if record.get("case_id") == "case_00000" and record["file_role"] == "sample_ct_image"
    )
    ct_path = source_manifest.parent / ct_record["relative_path"]
    with ct_path.open("ab") as handle:
        handle.write(b"drift")

    with pytest.raises(ValueError, match="Source size mismatch"):
        MODULE.materialize_kits23_patient_conditioning_proxy(
            source_manifest=source_manifest,
            output_dir=tmp_path / "output",
        )


def test_rejects_duplicate_clinical_case_ids(tmp_path: Path) -> None:
    clinical_path = tmp_path / "kits23.json"
    clinical_path.write_text(
        json.dumps([{"case_id": "case_00000"}, {"case_id": "case_00000"}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate KiTS23 clinical case_id"):
        MODULE.load_one_to_one_clinical_records(clinical_path, selected_cases=("case_00000",))


def test_slice_selection_is_deterministic_and_uses_background_when_available() -> None:
    mask = np.zeros((8, 8, 12), dtype=np.uint8)
    mask[2:6, 2:6, 1:11] = 1

    first = MODULE.select_axial_slices(mask, foreground_count=8, background_count=2)
    second = MODULE.select_axial_slices(mask, foreground_count=8, background_count=2)

    assert first == second
    assert len(first) == 10
    assert sum(item["slice_role"] == "foreground" for item in first) == 8
    assert {item["canonical_slice_index"] for item in first if item["slice_role"] == "adjacent_background"} == {0, 11}


def build_source_fixture(root: Path) -> Path:
    records: list[dict[str, object]] = []
    clinical_rows: list[dict[str, object]] = []
    clinical_path = root / "metadata" / "kits23.json"
    clinical_path.parent.mkdir(parents=True, exist_ok=True)
    for index, case_id in enumerate(MODULE.CASE_SPLITS):
        case_dir = root / "raw" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        shape = (12, 16, 16)
        ct = np.linspace(-1000.0, 1000.0, num=np.prod(shape), dtype=np.float32).reshape(shape)
        mask = np.zeros(shape, dtype=np.uint8)
        for slice_index in range(1, 11):
            mask[slice_index, 4:12, 4:12] = 1 + (slice_index % 3)
        affine = np.asarray(
            [
                [0.0, 0.0, -1.0, 0.0],
                [0.0, -1.0, 0.0, 0.0],
                [-1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
        ct_path = case_dir / "imaging.nii.gz"
        mask_path = case_dir / "segmentation.nii.gz"
        nib.save(nib.Nifti1Image(ct, affine), ct_path)
        nib.save(nib.Nifti1Image(mask, affine), mask_path)
        records.extend(
            [
                source_record(
                    root,
                    ct_path,
                    role="sample_ct_image",
                    case_id=case_id,
                ),
                source_record(
                    root,
                    mask_path,
                    role="sample_pixel_mask",
                    case_id=case_id,
                ),
            ]
        )
        clinical_rows.append(
            {
                "case_id": case_id,
                "age_at_nephrectomy": 40 + index,
                "gender": "female" if index % 2 else "male",
                "comorbidities": {
                    "uncomplicated_diabetes_mellitus": bool(index % 2),
                    "diabetes_mellitus_with_end_organ_damage": False,
                    "chronic_kidney_disease": bool(index == 2),
                },
                "last_preop_egfr": {"value": None if index == 4 else 80.0 - index},
            }
        )
    clinical_path.write_text(json.dumps(clinical_rows), encoding="utf-8")
    records.insert(
        0,
        source_record(root, clinical_path, role="clinical_context_table", case_id=None),
    )
    manifest_path = root / "patient_conditioning_starter_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "osteo-vision-patient-conditioning-starter-v1",
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def source_record(root: Path, path: Path, *, role: str, case_id: str | None) -> dict[str, object]:
    size = path.stat().st_size
    record: dict[str, object] = {
        "dataset_id": "D071",
        "dataset_name": "KiTS23 patient conditioning starter",
        "file_role": role,
        "relative_path": path.relative_to(root).as_posix(),
        "expected_size": size,
        "size_bytes": size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "download_status": "verified",
        "license": "CC BY-NC-SA 4.0",
        "source_page_url": "https://github.com/neheller/kits23",
        "target_domain_flag": False,
        "training_eligible": False,
    }
    if case_id is not None:
        record["case_id"] = case_id
    return record
