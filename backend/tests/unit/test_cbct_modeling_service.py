from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np

from backend.src.core.settings import Settings
from backend.src.services import cbct_modeling_service
from backend.src.services.cbct_modeling_service import CbctVolumeGeometry, build_cbct_surface_model


def test_build_cbct_surface_model_exports_nifti_label(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_dir = artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    source = source_dir / "case001_label.nii.gz"
    data = np.zeros((8, 8, 8), dtype=np.uint8)
    data[2:6, 2:6, 2:6] = 2
    nib.save(nib.Nifti1Image(data, affine=np.eye(4)), str(source))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        source_role="label",
        label_value=2,
        case_id="case001",
        dataset_id="unit",
    )

    assert result["modeling_status"] == "completed"
    assert Path(result["model_path"]).exists()
    assert Path(result["manifest_path"]).exists()
    evidence = result["three_d_evidence"]
    assert evidence["model_path"] == result["model_path"]
    assert evidence["model_source"] == "uploaded label volume surface"
    assert evidence["segmentation_source"] == "uploaded label volume value 2"
    assert evidence["registration_status"] == "unregistered"
    assert evidence["navigation_ready"] is False
    assert evidence["scene_manifest_v2"]["schema_version"] == "osteo-vision-three-d-scene-v2"
    assert evidence["scene_manifest_v2"]["nodes"][1]["type"] == "segmentation"
    assert evidence["scene_manifest_v2"]["nodes"][2]["type"] == "model"


def test_build_cbct_surface_model_routes_raw_nifti_to_proxy_not_label(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    source_dir = artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    source = source_dir / "case001_cbct_0000.nii.gz"
    raw = np.linspace(-500.5, 1600.25, num=12 * 12 * 12, dtype=np.float32).reshape((12, 12, 12))
    nib.save(nib.Nifti1Image(raw, affine=np.eye(4)), str(source))
    proxy_volume = np.zeros((12, 12, 12), dtype=np.float32)
    proxy_volume[3:9, 3:9, 3:9] = 1500
    monkeypatch.setattr(
        cbct_modeling_service, "_load_cbct_proxy_volume", lambda sources: (proxy_volume, (0.4, 0.4, 0.4))
    )

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        case_id="case001",
        dataset_id="unit",
    )

    evidence = result["three_d_evidence"]
    assert result["modeling_status"] == "completed"
    assert result["input_type"] == "nifti_volume"
    assert evidence["model_source"] == "uploaded CBCT balanced hard tissue proxy"
    assert evidence["surface_quality"]["method"] == "balanced_adaptive_hard_tissue_proxy"
    assert "label1_surface" not in Path(result["model_path"]).name


def test_build_cbct_surface_model_does_not_extract_label_from_raw_integer_nifti(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    source_dir = artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    source = source_dir / "upload_d024_0006_copy.nii.gz"
    raw = np.linspace(-1000, 3000, num=14 * 14 * 14, dtype=np.int32).reshape((14, 14, 14))
    raw[0, 0, 0] = 2
    nib.save(nib.Nifti1Image(raw, affine=np.diag([0.3, 0.3, 0.3, 1.0])), str(source))
    proxy_volume = np.zeros((14, 14, 14), dtype=np.float32)
    proxy_volume[4:10, 4:10, 4:10] = 1600
    monkeypatch.setattr(
        cbct_modeling_service, "_load_cbct_proxy_volume", lambda sources: (proxy_volume, (0.3, 0.3, 0.3))
    )

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        source_role="volume",
        label_value=2,
        case_id="case001",
        dataset_id="unit",
    )

    evidence = result["three_d_evidence"]
    assert result["modeling_status"] == "completed"
    assert evidence["model_source"] == "uploaded CBCT balanced hard tissue proxy"
    assert evidence["surface_quality"]["method"] == "balanced_adaptive_hard_tissue_proxy"
    assert "label2_surface" not in Path(result["model_path"]).name


def test_build_cbct_surface_model_rejects_label_like_nifti_when_role_is_volume(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_dir = artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    source = source_dir / "case001_label.nii.gz"
    data = np.zeros((8, 8, 8), dtype=np.uint8)
    data[2:6, 2:6, 2:6] = 2
    nib.save(nib.Nifti1Image(data, affine=np.eye(4)), str(source))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        source_role="volume",
        label_value=2,
        case_id="case001",
        dataset_id="unit",
    )

    assert result["modeling_status"] == "segmentation_required"
    assert result["model_path"] is None
    assert "更像分割标签体" in result["message"]


def test_build_cbct_surface_model_records_surface_model_without_generation(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    source_dir = artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    source = source_dir / "case001_mandible.stl"
    source.write_bytes(b"solid mandible\nendsolid mandible\n")

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        case_id="case001",
    )

    assert result["modeling_status"] == "surface_model_ready"
    assert result["three_d_evidence"]["model_path"] == str(source)
    assert result["three_d_evidence"]["navigation_ready"] is False
    assert result["three_d_evidence"]["scene_manifest_v2"]["nodes"][0]["type"] == "model"


def test_build_cbct_surface_model_exports_dicom_hard_tissue_proxy(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    source_dir = artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    first = source_dir / "case001_001.dcm"
    second = source_dir / "case001_002.dcm"
    first.write_bytes(b"DICM" + b"\0" * 512)
    second.write_bytes(b"DICM" + b"\0" * 512)
    volume = np.zeros((8, 8, 8), dtype=np.float32)
    volume[2:6, 2:6, 2:6] = 1200
    monkeypatch.setattr(cbct_modeling_service, "_load_cbct_proxy_volume", lambda sources: (volume, (0.4, 0.4, 0.4)))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=first,
        source_paths=[first, second],
        case_id="case001",
        dataset_id="unit",
    )

    assert result["modeling_status"] == "completed"
    assert result["input_type"] == "dicom_series"
    assert Path(result["model_path"]).exists()
    evidence = result["three_d_evidence"]
    assert evidence["model_source"] == "uploaded CBCT balanced hard tissue proxy"
    assert evidence["segmentation_review_status"] == "not_reviewed"
    assert evidence["coordinate_space"] == "cbct_physical_lps_mm_proxy"
    assert evidence["navigation_ready"] is False
    assert evidence["orientation_review_status"] == "pending_slicer_or_physician_review"
    assert evidence["view_space_mapping"]["display_up_axis"] == "physical_z"
    assert evidence["surface_quality"]["method"] == "balanced_adaptive_hard_tissue_proxy"
    assert evidence["scene_manifest_v2"]["nodes"][1]["role"] == "hard_tissue_proxy_surface"


def test_build_cbct_surface_model_exports_mha_hard_tissue_proxy(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "artifacts"
    source_dir = artifact_root / "uploads"
    source_dir.mkdir(parents=True)
    source = source_dir / "case001_cbct.mha"
    source.write_bytes(b"ObjectType = Image\nNDims = 3\n")
    volume = np.zeros((10, 10, 10), dtype=np.float32)
    volume[3:8, 3:8, 3:8] = 1600
    monkeypatch.setattr(cbct_modeling_service, "_load_cbct_proxy_volume", lambda sources: (volume, (0.5, 0.5, 0.5)))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        source_paths=[source],
        case_id="case001",
        dataset_id="unit",
    )

    assert result["modeling_status"] == "completed"
    assert result["input_type"] == "medical_volume"
    assert Path(result["model_path"]).exists()
    assert result["three_d_evidence"]["model_source"] == "uploaded CBCT balanced hard tissue proxy"
    assert result["three_d_evidence"]["navigation_ready"] is False
    assert result["three_d_evidence"]["orientation_review_status"] == "pending_slicer_or_physician_review"
    assert result["three_d_evidence"]["view_space_mapping"]["display_up_axis"] == "-physical_z"


def test_build_cbct_surface_model_prefers_d036_public_label_over_threshold_proxy(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    d036_root = (
        tmp_path / "research" / "datasets" / "public-candidates" / "d036_toothfairy2" / "raw" / "Dataset112_ToothFairy2"
    )
    images_dir = d036_root / "imagesTr"
    labels_dir = d036_root / "labelsTr"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    source = images_dir / "ToothFairy2F_001_0000.mha"
    label = labels_dir / "ToothFairy2F_001.mha"
    _write_sitk_volume(source, np.zeros((10, 10, 10), dtype=np.float32), spacing=(0.3, 0.3, 0.3))
    label_data = np.zeros((10, 10, 10), dtype=np.uint8)
    label_data[2:8, 3:7, 4:9] = 1
    label_data[1:4, 1:4, 1:4] = 2
    _write_sitk_volume(label, label_data, spacing=(0.3, 0.3, 0.3))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        case_id="local_cbct",
        dataset_id="local_import",
    )

    evidence = result["three_d_evidence"]
    assert result["modeling_status"] == "completed"
    assert Path(result["model_path"]).exists()
    assert evidence["model_source"] == "D036 ToothFairy2 public upper/lower jawbone segmentation labels"
    assert evidence["segmentation_source"] == "D036 ToothFairy2 label values 1 Lower Jawbone and 2 Upper Jawbone"
    assert evidence["surface_quality"]["method"] == "label_volume_marching_cubes"
    assert evidence["surface_quality"]["label_values"] == [1, 2]
    assert evidence["surface_quality"]["source_type"] == "public_dataset_label"
    assert evidence["navigation_ready"] is False
    assert evidence["orientation_review_status"] == "pending_slicer_or_physician_review"
    assert evidence["view_space_mapping"]["display_up_axis"] == "-physical_z"
    assert "公开上颌骨与下颌骨标签" in evidence["boundary_note"]


def test_build_cbct_surface_model_flags_sparse_d036_upper_jaw_label(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    d036_root = (
        tmp_path / "research" / "datasets" / "public-candidates" / "d036_toothfairy2" / "raw" / "Dataset112_ToothFairy2"
    )
    images_dir = d036_root / "imagesTr"
    labels_dir = d036_root / "labelsTr"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    source = images_dir / "ToothFairy2F_013_0000.mha"
    label = labels_dir / "ToothFairy2F_013.mha"
    _write_sitk_volume(source, np.zeros((16, 16, 16), dtype=np.float32), spacing=(0.3, 0.3, 0.3))
    label_data = np.zeros((16, 16, 16), dtype=np.uint8)
    label_data[4:14, 3:13, 3:13] = 1
    label_data[0:3, 5:11, 5:11] = 2
    _write_sitk_volume(label, label_data, spacing=(0.3, 0.3, 0.3))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        case_id="local_cbct",
        dataset_id="local_import",
    )

    quality = result["three_d_evidence"]["surface_quality"]
    upper = next(item for item in quality["per_label"] if item["label_value"] == 2)
    assert upper["label_name"] == "upper_jawbone"
    assert upper["coverage_status"] == "partial_or_crop_limited"
    assert "upper_jaw_label_sparse_or_crop_limited" in quality["quality_warnings"]


def test_build_cbct_surface_model_matches_renamed_d036_upload_by_fingerprint(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    d036_root = (
        tmp_path / "research" / "datasets" / "public-candidates" / "d036_toothfairy2" / "raw" / "Dataset112_ToothFairy2"
    )
    images_dir = d036_root / "imagesTr"
    labels_dir = d036_root / "labelsTr"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    source_image = images_dir / "ToothFairy2F_039_0000.mha"
    label = labels_dir / "ToothFairy2F_039.mha"
    _write_sitk_volume(source_image, np.ones((10, 10, 10), dtype=np.float32), spacing=(0.3, 0.3, 0.3))
    label_data = np.zeros((10, 10, 10), dtype=np.uint8)
    label_data[1:4, 1:7, 1:7] = 1
    label_data[5:9, 3:9, 3:9] = 2
    _write_sitk_volume(label, label_data, spacing=(0.3, 0.3, 0.3))
    upload_dir = artifact_root / "uploads"
    upload_dir.mkdir(parents=True)
    renamed_upload = upload_dir / "upload_8ef674fe46f0.mha"
    renamed_upload.write_bytes(source_image.read_bytes())

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=renamed_upload,
        case_id="frontend_local_cbct",
        dataset_id="frontend_local_import",
    )

    evidence = result["three_d_evidence"]
    assert result["modeling_status"] == "completed"
    assert evidence["model_source"] == "D036 ToothFairy2 public upper/lower jawbone segmentation labels"
    assert evidence["surface_quality"]["label_values"] == [1, 2]
    assert evidence["surface_quality"]["source_type"] == "public_dataset_label"
    assert "ToothFairy2F_039_d036_public_upper_lower_jaw_label_surface" in Path(result["model_path"]).name


def test_build_cbct_surface_model_uses_d024_public_label_from_uploaded_original_name(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    d024_root = (
        tmp_path
        / "research"
        / "datasets"
        / "public-candidates"
        / "d024_dentvoxel"
        / "derived"
        / "nnunet"
        / "nnUNet_raw"
        / "Dataset124_DentVoxelJawROI"
    )
    labels_dir = d024_root / "labelsTr"
    labels_dir.mkdir(parents=True)
    upload_dir = artifact_root / "uploads"
    upload_dir.mkdir(parents=True)
    source = upload_dir / "upload_abcd1234.nii.gz"
    _write_sitk_volume(source, np.zeros((10, 10, 10), dtype=np.float32), spacing=(0.3, 0.3, 0.3))
    label = labels_dir / "d024_0006.nii.gz"
    label_data = np.zeros((10, 10, 10), dtype=np.uint8)
    label_data[1:4, 1:6, 1:6] = 1
    label_data[5:9, 4:9, 4:9] = 2
    _write_sitk_volume(label, label_data, spacing=(0.3, 0.3, 0.3))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        source_role="volume",
        source_original_filename="d024_0006_0000.nii.gz",
        case_id="frontend_local_cbct",
        dataset_id="local_import",
    )

    evidence = result["three_d_evidence"]
    assert result["modeling_status"] == "completed"
    assert Path(result["model_path"]).exists()
    assert evidence["model_source"] == "D024 DentVoxel public maxilla/mandible segmentation labels"
    assert evidence["segmentation_source"] == "D024 DentVoxel label values 1 maxilla and 2 mandible"
    assert evidence["surface_quality"]["label_values"] == [1, 2]
    assert evidence["surface_quality"]["source_type"] == "public_dataset_label_d024"
    assert evidence["navigation_ready"] is False


def test_build_cbct_surface_model_prefers_d036_nnunet_prediction_when_available(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    upload_dir = artifact_root / "uploads"
    upload_dir.mkdir(parents=True)
    source = upload_dir / "ToothFairy2F_001_0000.mha"
    _write_sitk_volume(source, np.zeros((10, 10, 10), dtype=np.float32), spacing=(0.4, 0.4, 0.4))
    prediction_dir = (
        tmp_path
        / "research"
        / "datasets"
        / "public-candidates"
        / "d036_toothfairy2"
        / "derived"
        / "nnunet"
        / "predictions"
        / "jaw2"
    )
    prediction_dir.mkdir(parents=True)
    prediction = prediction_dir / "ToothFairy2F_001.nii.gz"
    label_data = np.zeros((10, 10, 10), dtype=np.uint8)
    label_data[2:8, 3:7, 4:9] = 1
    label_data[1:4, 1:4, 1:4] = 2
    _write_sitk_volume(prediction, label_data, spacing=(0.4, 0.4, 0.4))

    result = build_cbct_surface_model(
        settings=Settings(project_root=tmp_path, artifact_root=artifact_root),
        source_path=source,
        case_id="local_cbct",
        dataset_id="local_import",
    )

    evidence = result["three_d_evidence"]
    assert evidence["model_source"] == "D036-trained nnU-Net upper/lower jawbone prediction"
    assert evidence["segmentation_review_status"] == "model_inferred_not_physician_reviewed"
    assert evidence["surface_quality"]["source_type"] == "nnunet_prediction_jaw2"
    assert evidence["surface_quality"]["label_values"] == [1, 2]
    assert evidence["scene_manifest_v2"]["nodes"][1]["type"] == "segmentation"
    assert evidence["view_space_mapping"]["display_up_axis"] == "-physical_z"
    assert evidence["navigation_ready"] is False


def test_cbct_proxy_uses_balanced_threshold_and_physical_axis_order(tmp_path: Path) -> None:
    output_dir = tmp_path / "models"
    volume = np.zeros((12, 14, 16), dtype=np.float32)
    volume[:, :, :] = 80.0
    volume[2:7, 3:9, 4:12] = 1400.0
    geometry = CbctVolumeGeometry(
        spacing_xyz=(0.5, 1.0, 2.0),
        origin_xyz=(10.0, 20.0, 30.0),
        direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
    )

    result = cbct_modeling_service._cbct_proxy_surface_evidence(
        volume=volume,
        geometry=geometry,
        sources=[tmp_path / "case001.mha"],
        output_dir=output_dir,
        case_id="case001",
        dataset_id="unit",
        decimation_step=1,
        input_type="medical_volume",
    )

    evidence = result["three_d_evidence"]
    quality = evidence["surface_quality"]
    assert quality["threshold_value"] >= 1000
    assert quality["method"] == "balanced_adaptive_hard_tissue_proxy"
    assert quality["fill_ratio_after_components"] < 0.2
    assert evidence["coordinate_space"] == "cbct_physical_lps_mm_proxy"
    assert "物理坐标" in evidence["boundary_note"]
    assert evidence["orientation_review_status"] == "pending_slicer_or_physician_review"
    assert evidence["view_space_mapping"]["display_up_axis"] == "-physical_z"

    vertices = _read_stl_vertices(Path(result["model_path"]))
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    assert 11.0 <= mins[0] <= 12.1
    assert 22.0 <= mins[1] <= 23.1
    assert 32.0 <= mins[2] <= 34.0
    assert 15.5 <= maxs[0] <= 16.5
    assert 28.5 <= maxs[1] <= 29.5
    assert 42.0 <= maxs[2] <= 44.0


def _read_stl_vertices(path: Path) -> np.ndarray:
    import struct

    with path.open("rb") as handle:
        handle.seek(80)
        triangle_count = struct.unpack("<I", handle.read(4))[0]
        vertices: list[tuple[float, float, float]] = []
        for _ in range(triangle_count):
            handle.read(12)
            for _vertex_index in range(3):
                vertices.append(struct.unpack("<3f", handle.read(12)))
            handle.read(2)
    return np.asarray(vertices, dtype=np.float32)


def _write_sitk_volume(path: Path, data: np.ndarray, *, spacing: tuple[float, float, float]) -> None:
    import SimpleITK as sitk

    image = sitk.GetImageFromArray(data)
    image.SetSpacing(spacing)
    path.parent.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(image, str(path))
