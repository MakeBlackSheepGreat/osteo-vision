from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest
from PIL import Image
from scipy.io import savemat

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/materialize_d074_bone_activity_proxy.py"
SPEC = importlib.util.spec_from_file_location("materialize_d074_bone_activity_proxy", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_materializes_real_image_proxy_with_patient_group_isolation(tmp_path: Path) -> None:
    source_manifest = _build_source_fixture(tmp_path / "source")
    output = tmp_path / "output"

    result = MODULE.materialize_d074_bone_activity_proxy(
        source_manifest=source_manifest,
        output_dir=output,
    )

    assert result["status"] == "engineering_validation_passed"
    assert result["sample_count"] == 5
    assert result["patient_group_count"] == 3
    assert result["split_sample_counts"] == {"test": 2, "train": 1, "val": 2}
    assert result["patient_group_leakage_detected"] is False
    assert result["training_eligibility"] == {
        "training_eligible": True,
        "scope": "proxy_pretraining_only",
        "training_scope": "non_target_proxy_pretraining",
        "source_manifest_training_eligible": False,
        "target_domain": False,
        "physician_reviewed_bone_gate": False,
        "runtime_replacement_allowed": False,
        "clinical_claim_allowed": False,
    }

    csv_path = output / "d074_bone_activity_proxy_samples.csv"
    rows = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 6
    parsed_rows = list(csv.DictReader(rows))
    assert all(len(row["source_asset_sha256"]) == 64 for row in parsed_rows)
    assert all(len(row["source_mask_asset_sha256"]) == 64 for row in parsed_rows)
    assert len({row["source_asset_sha256"] for row in parsed_rows}) == 5
    first = result["derived_files"][0]
    assert len(first["sha256"]) == 64
    class_paths = [item for item in result["derived_files"] if item["role"] == "class_target"]
    assert len(class_paths) == 5
    for item in class_paths:
        with Image.open(output / item["relative_path"]) as image:
            assert set(np.unique(np.asarray(image))).issubset({0, 1, 2, 255})


def test_rejects_source_archive_hash_drift(tmp_path: Path) -> None:
    source_manifest = _build_source_fixture(tmp_path / "source")
    payload = json.loads(source_manifest.read_text(encoding="utf-8"))
    image_record = next(
        record for record in payload["records"] if record["original_file_name"] == MODULE.IMAGE_ARCHIVE_NAME
    )
    with Path(image_record["local_path"]).open("ab") as handle:
        handle.write(b"drift")

    with pytest.raises(ValueError, match="size mismatch"):
        MODULE.materialize_d074_bone_activity_proxy(
            source_manifest=source_manifest,
            output_dir=tmp_path / "output",
        )


def test_rejects_unsafe_zip_member(tmp_path: Path) -> None:
    source_manifest = _build_source_fixture(tmp_path / "source", unsafe_member=True)

    with pytest.raises(ValueError, match="Unsafe D074 ZIP member"):
        MODULE.materialize_d074_bone_activity_proxy(
            source_manifest=source_manifest,
            output_dir=tmp_path / "output",
        )


def _build_source_fixture(root: Path, *, unsafe_member: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    image_archive = root / MODULE.IMAGE_ARCHIVE_NAME
    mask_archive = root / MODULE.MASK_ARCHIVE_NAME
    samples = (("001", 1), ("002", 1), ("002", 2), ("003", 1), ("003", 4))
    height, width = 12, 16
    x = np.linspace(0, 255, width, dtype=np.uint8)[None, :]
    red = np.repeat(x, height, axis=0)
    rgb = np.stack([red, np.flip(red, axis=1), np.full_like(red, 24)], axis=2)
    gate = np.zeros((height, width), dtype=np.uint8)
    gate[2:10, 2:14] = 1

    with ZipFile(image_archive, "w") as archive:
        if unsafe_member:
            archive.writestr("../unsafe.txt", b"unsafe")
        for index, (patient, frame) in enumerate(samples):
            encoded = BytesIO()
            sample_rgb = rgb.copy()
            sample_rgb[:, :, 2] = 24 + index
            Image.fromarray(sample_rgb).save(encoded, format="PNG")
            archive.writestr(
                f"Fluorescence Guided GBM Resection/Patient{patient}/P{patient} ({frame}).png",
                encoded.getvalue(),
            )
    with ZipFile(mask_archive, "w") as archive:
        for index, (patient, frame) in enumerate(samples):
            encoded = BytesIO()
            sample_gate = np.roll(gate, shift=index % 3, axis=1)
            savemat(encoded, {f"P{patient}_{frame}_mask": sample_gate})
            archive.writestr(f"Annotation Masks/masks ala/P{patient}_{frame}_mask.mat", encoded.getvalue())

    records = [
        _source_record(image_archive, MODULE.IMAGE_ARCHIVE_NAME),
        _source_record(mask_archive, MODULE.MASK_ARCHIVE_NAME),
    ]
    manifest = root / "three_priority_zenodo_manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": "test", "records": records}),
        encoding="utf-8",
    )
    return manifest


def _source_record(path: Path, name: str) -> dict[str, object]:
    return {
        "candidate_id": "D074",
        "record_id": "15260349",
        "original_file_name": name,
        "local_path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "license": "cc-by-4.0",
        "download_status": "verified",
        "source_page_url": "https://zenodo.org/records/15260349",
        "direct_download_url": "https://example.invalid/source.zip",
        "training_eligible": False,
        "target_domain_flag": False,
    }
