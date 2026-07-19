from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
from skimage import measure, morphology

from backend.src.core.settings import Settings
from scripts.export_cbct_mandible_surface import sha256_for_file, write_binary_stl
from src.preprocess.input_validation import detect_input_type


@dataclass(frozen=True)
class CbctVolumeGeometry:
    spacing_xyz: tuple[float, float, float]
    origin_xyz: tuple[float, float, float]
    direction: tuple[float, ...]


@dataclass(frozen=True)
class CbctSegmentationSurfaceSource:
    label_path: Path
    label_value: int
    label_values: tuple[int, ...]
    label_name: str
    case_id: str
    dataset_id: str
    model_source: str
    segmentation_source: str
    segmentation_review_status: str
    coordinate_space: str
    input_domain: str
    data_boundary: str
    boundary_note: str
    output_suffix: str
    source_type: str


@dataclass(frozen=True)
class CbctPredictionLabelSource:
    label_path: Path
    label_value: int
    label_values: tuple[int, ...]
    label_name: str
    segmentation_source: str
    output_suffix: str
    source_type: str


def build_cbct_surface_model(
    *,
    settings: Settings,
    source_path: str | Path,
    source_paths: list[str | Path] | None = None,
    label_value: int = 1,
    case_id: str = "local_cbct",
    dataset_id: str = "local_import",
    decimation_step: int = 1,
    source_role: str = "volume",
    source_original_filename: str | None = None,
) -> dict[str, Any]:
    source = _resolve_modeling_source(settings, source_path)
    sources = _resolve_modeling_sources(settings, source_paths) if source_paths else [source]
    input_type = detect_input_type(source)
    normalized_source_role = _normalize_source_role(source_role)
    output_dir = settings.artifact_root / "three_d_models" / _safe_stem(source)
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_type == "surface_model":
        return _surface_model_evidence(source, output_dir=output_dir, case_id=case_id)

    if input_type in {"dicom_series", "medical_volume", "nifti_volume"}:
        if normalized_source_role == "label":
            return _direct_label_surface_evidence(
                source=source,
                output_dir=output_dir,
                label_value=label_value,
                case_id=case_id,
                dataset_id=dataset_id,
                input_type=input_type,
                decimation_step=decimation_step,
            )
        if normalized_source_role == "volume" and input_type in {"medical_volume", "nifti_volume"}:
            if _volume_looks_like_label(source):
                manifest = _source_role_mismatch_manifest(
                    source,
                    output_dir=output_dir,
                    input_type=input_type,
                    case_id=case_id,
                    requested_source_role=normalized_source_role,
                )
                return {
                    "model_path": None,
                    "manifest_path": str(manifest),
                    "input_type": input_type,
                    "modeling_status": "segmentation_required",
                    "source_role": normalized_source_role,
                    "message": (
                        "检测到该 NIfTI/MHA 更像分割标签体，不按原始 CBCT 灰度体建模。"
                        "请明确选择标签建模，或上传原始 CBCT 强度体。"
                    ),
                }
        segmented = _try_cbct_segmentation_surface(
            settings=settings,
            source=source,
            output_dir=output_dir,
            requested_case_id=case_id,
            decimation_step=decimation_step,
            input_type=input_type,
            source_role=normalized_source_role,
            source_original_filename=source_original_filename,
        )
        if segmented is not None:
            return segmented
        proxy = _try_cbct_proxy_surface(
            sources=sources,
            output_dir=output_dir,
            case_id=case_id,
            dataset_id=dataset_id,
            decimation_step=decimation_step,
            input_type=input_type,
        )
        if proxy is not None:
            return proxy

    manifest = _unsupported_volume_manifest(source, output_dir=output_dir, input_type=input_type, case_id=case_id)
    return {
        "model_path": None,
        "manifest_path": str(manifest),
        "input_type": input_type,
        "modeling_status": "segmentation_required",
        "message": "当前文件已进入 CBCT 检查，但浏览器/后端尚未从该格式自动生成上下颌骨表面。",
    }


def _normalize_source_role(source_role: str | None) -> str:
    normalized = str(source_role or "volume").strip().lower()
    if normalized in {"volume", "cbct", "raw", "raw_volume"}:
        return "volume"
    if normalized in {"label", "segmentation", "label_volume"}:
        return "label"
    if normalized in {"surface", "surface_model", "stl", "glb", "gltf"}:
        return "surface"
    if normalized == "auto":
        return "auto"
    return "volume"


def _direct_label_surface_evidence(
    *,
    source: Path,
    output_dir: Path,
    label_value: int,
    case_id: str,
    dataset_id: str,
    input_type: str,
    decimation_step: int,
) -> dict[str, Any]:
    if not _volume_looks_like_label(source):
        manifest = _source_role_mismatch_manifest(
            source,
            output_dir=output_dir,
            input_type=input_type,
            case_id=case_id,
            requested_source_role="label",
        )
        return {
            "model_path": None,
            "manifest_path": str(manifest),
            "input_type": input_type,
            "modeling_status": "segmentation_required",
            "source_role": "label",
            "message": "已选择标签建模，但该文件更像原始 CBCT 强度体；未按 label_value 直接抽取表面。",
        }
    source_info = CbctSegmentationSurfaceSource(
        label_path=source,
        label_value=label_value,
        label_values=(label_value,),
        label_name=f"label_{label_value}",
        case_id=case_id,
        dataset_id=dataset_id,
        model_source="uploaded label volume surface",
        segmentation_source=f"uploaded label volume value {label_value}",
        segmentation_review_status="not_reviewed",
        coordinate_space="uploaded_label_physical_lps_mm",
        input_domain="uploaded_label_volume",
        data_boundary=(
            "Uploaded segmentation label volume converted to a surface for platform validation. "
            "It is not automatically verified as jawbone anatomy, not registered to fluorescence video and not navigation-ready."
        ),
        boundary_note=(
            "该表面来自用户明确选择的标签体 value "
            f"{label_value}；仍需确认标签语义、医生复核、跨模态配准和导航误差记录。"
        ),
        output_suffix=f"label{label_value}_surface",
        source_type="uploaded_label_volume",
    )
    return _cbct_label_surface_evidence(
        source_info=source_info,
        source_volume_path=source,
        output_dir=output_dir,
        decimation_step=decimation_step,
        input_type=input_type,
    )


def _volume_looks_like_label(source: Path) -> bool:
    try:
        import SimpleITK as sitk
    except ImportError:
        return False
    try:
        image = sitk.ReadImage(str(source))
        array = sitk.GetArrayFromImage(image)
    except Exception:
        return False
    if array.size == 0:
        return False
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return False
    if finite.size > 1_000_000:
        finite = finite[:: max(1, finite.size // 1_000_000)]
    rounded = np.rint(finite)
    integer_like = bool(np.all(np.abs(finite - rounded) < 1e-3))
    if not integer_like:
        return False
    unique = np.unique(rounded.astype(np.int64))
    if unique.size > 32:
        return False
    return bool(unique.size >= 2 and unique.min() >= 0 and unique.max() <= 255)


def _try_cbct_segmentation_surface(
    *,
    settings: Settings,
    source: Path,
    output_dir: Path,
    requested_case_id: str,
    decimation_step: int,
    input_type: str,
    source_role: str,
    source_original_filename: str | None,
) -> dict[str, Any] | None:
    source_info = _find_cbct_segmentation_source(
        settings=settings,
        source=source,
        requested_case_id=requested_case_id,
        source_role=source_role,
        source_original_filename=source_original_filename,
    )
    if source_info is None:
        return None
    try:
        return _cbct_label_surface_evidence(
            source_info=source_info,
            source_volume_path=source,
            output_dir=output_dir,
            decimation_step=decimation_step,
            input_type=input_type,
        )
    except Exception:
        return None


def _find_cbct_segmentation_source(
    *,
    settings: Settings,
    source: Path,
    requested_case_id: str,
    source_role: str,
    source_original_filename: str | None,
) -> CbctSegmentationSurfaceSource | None:
    if source_role == "surface":
        return None
    d036_root = settings.project_root / "research" / "datasets" / "public-candidates" / "d036_toothfairy2"
    case_id = (
        _d036_case_id_from_path(source)
        or _d036_case_id_from_name(source_original_filename)
        or _find_d036_case_id_by_file_fingerprint(d036_root, source=source)
        or requested_case_id
    )
    prediction = _find_d036_nnunet_prediction(d036_root, case_id=case_id)
    if prediction is not None:
        return CbctSegmentationSurfaceSource(
            label_path=prediction.label_path,
            label_value=prediction.label_value,
            label_values=prediction.label_values,
            label_name=prediction.label_name,
            case_id=case_id,
            dataset_id="D036",
            model_source="D036-trained nnU-Net upper/lower jawbone prediction",
            segmentation_source=prediction.segmentation_source,
            segmentation_review_status="model_inferred_not_physician_reviewed",
            coordinate_space="cbct_physical_lps_mm_nnunet_prediction",
            input_domain="public_cbct_anatomy_nnunet_prediction",
            data_boundary=(
                "D036 ToothFairy2-trained nnU-Net prediction for CBCT anatomical upper/lower jawbone surface. "
                "It is public non-target-domain anatomy evidence, not jaw osteomyelitis ICG evidence and not navigation-ready."
            ),
            boundary_note=(
                "该表面来自 D036 ToothFairy2 训练链路的 nnU-Net 上下颌骨预测标签；"
                "仍未完成本病例医生复核、跨模态配准和导航误差记录。"
            ),
            output_suffix=prediction.output_suffix,
            source_type=prediction.source_type,
        )

    public_label = _find_d036_public_label(d036_root, case_id=case_id, source=source)
    if public_label is not None:
        return CbctSegmentationSurfaceSource(
            label_path=public_label,
            label_value=1,
            label_values=(1, 2),
            label_name="maxilla_and_mandible_jawbones",
            case_id=case_id,
            dataset_id="D036",
            model_source="D036 ToothFairy2 public upper/lower jawbone segmentation labels",
            segmentation_source="D036 ToothFairy2 label values 1 Lower Jawbone and 2 Upper Jawbone",
            segmentation_review_status="public_dataset_annotation_not_case_reviewed",
            coordinate_space="cbct_physical_lps_mm_public_label",
            input_domain="public_cbct_anatomy_label_reference",
            data_boundary=(
                "D036 ToothFairy2 public CBCT upper/lower jawbone label surface for platform validation. "
                "It is not a jaw osteomyelitis case, not registered to ICG video and not surgical navigation."
            ),
            boundary_note=(
                "该表面直接来自 D036 ToothFairy2 公开上颌骨与下颌骨标签，比灰度阈值代理干净；"
                "但它只是公开解剖标注参考，仍不是本项目病例医生复核导航边界。"
            ),
            output_suffix="d036_public_upper_lower_jaw_label_surface",
            source_type="public_dataset_label",
        )

    d024_case_id = (
        _d024_case_id_from_path(source)
        or _d024_case_id_from_name(source_original_filename)
        or _d024_case_id_from_name(requested_case_id)
    )
    if d024_case_id:
        d024_root = (
            settings.project_root
            / "research"
            / "datasets"
            / "public-candidates"
            / "d024_dentvoxel"
            / "derived"
            / "nnunet"
            / "nnUNet_raw"
            / "Dataset124_DentVoxelJawROI"
        )
        public_d024_label = _find_d024_public_label(d024_root, case_id=d024_case_id, source=source)
        if public_d024_label is not None:
            return CbctSegmentationSurfaceSource(
                label_path=public_d024_label,
                label_value=1,
                label_values=(1, 2),
                label_name="maxilla_and_mandible_jawbones",
                case_id=d024_case_id,
                dataset_id="D024",
                model_source="D024 DentVoxel public maxilla/mandible segmentation labels",
                segmentation_source="D024 DentVoxel label values 1 maxilla and 2 mandible",
                segmentation_review_status="public_dataset_annotation_not_case_reviewed",
                coordinate_space="cbct_physical_lps_mm_public_label",
                input_domain="public_cbct_anatomy_label_reference",
                data_boundary=(
                    "D024 DentVoxel public CBCT maxilla/mandible label surface for platform validation. "
                    "It is not a jaw osteomyelitis case, not registered to ICG video and not surgical navigation."
                ),
                boundary_note=(
                    "该表面来自 D024 DentVoxel 公开上颌骨 label=1 与下颌骨 label=2，"
                    "比原始灰度阈值代理稳定；仍不是本项目病例医生复核导航边界。"
                ),
                output_suffix="d024_public_upper_lower_jaw_label_surface",
                source_type="public_dataset_label_d024",
            )
    return None


def _find_d036_nnunet_prediction(d036_root: Path, *, case_id: str) -> CbctPredictionLabelSource | None:
    predictions_root = d036_root / "derived" / "nnunet" / "predictions"
    if not predictions_root.exists():
        return None
    candidates: list[tuple[Path, tuple[int, ...], str, str, str]] = []
    for folder, values, name, suffix in [
        ("jaw2", (1, 2), "maxilla_and_mandible_jawbones", "d036_nnunet_upper_lower_jaw_surface"),
        ("anatomy4", (1, 2), "maxilla_and_mandible_jawbones", "d036_nnunet_anatomy4_upper_lower_jaw_surface"),
        ("jawbone_binary", (1,), "maxilla_and_mandible_jawbones", "d036_nnunet_jawbone_binary_surface"),
        ("maxilla_mandible", (1, 2), "maxilla_and_mandible_jawbones", "d036_nnunet_upper_lower_jaw_surface"),
        ("mandible_binary", (1,), "mandible_or_lower_jawbone", "d036_nnunet_mandible_surface"),
    ]:
        for extension in [".nii.gz", ".mha"]:
            candidates.append((predictions_root / folder / f"{case_id}{extension}", values, name, suffix, folder))
    for extension in [".nii.gz", ".mha"]:
        candidates.append(
            (
                predictions_root / f"{case_id}{extension}",
                (1, 2),
                "maxilla_and_mandible_jawbones",
                "d036_nnunet_upper_lower_jaw_surface",
                "predictions_root",
            )
        )
    for candidate, values, name, suffix, source_type in candidates:
        if candidate.exists():
            return CbctPredictionLabelSource(
                label_path=candidate,
                label_value=values[0],
                label_values=values,
                label_name=name,
                segmentation_source=_prediction_segmentation_source(values=values, source_type=source_type),
                output_suffix=suffix,
                source_type=f"nnunet_prediction_{source_type}",
            )
    for candidate in predictions_root.rglob(f"{case_id}*"):
        if candidate.suffix.lower() in {".mha", ".nii"} or candidate.name.lower().endswith(".nii.gz"):
            return CbctPredictionLabelSource(
                label_path=candidate,
                label_value=1,
                label_values=(1, 2),
                label_name="maxilla_and_mandible_jawbones",
                segmentation_source="nnU-Net prediction label values 1 and 2 upper/lower jawbones",
                output_suffix="d036_nnunet_upper_lower_jaw_surface",
                source_type="nnunet_prediction_unclassified",
            )
    return None


def _prediction_segmentation_source(*, values: tuple[int, ...], source_type: str) -> str:
    joined = ", ".join(str(value) for value in values)
    if source_type == "mandible_binary":
        return f"nnU-Net prediction label value {joined} mandible_or_lower_jawbone"
    if len(values) == 1:
        return f"nnU-Net prediction label value {joined} combined upper/lower jawbone"
    return f"nnU-Net prediction label values {joined} upper/lower jawbones"


def _find_d036_public_label(d036_root: Path, *, case_id: str, source: Path) -> Path | None:
    if not case_id.startswith("ToothFairy2"):
        return None
    if source.parent.name == "labelsTr" and source.exists():
        return source
    label_path = d036_root / "raw" / "Dataset112_ToothFairy2" / "labelsTr" / f"{case_id}.mha"
    return label_path if label_path.exists() else None


def _d036_case_id_from_path(path: Path) -> str | None:
    match = re.search(r"(ToothFairy2[FP]_\d{3})", path.name)
    return match.group(1) if match else None


def _d036_case_id_from_name(name: str | None) -> str | None:
    if not name:
        return None
    match = re.search(r"(ToothFairy2[FP]_\d{3})", str(name))
    return match.group(1) if match else None


def _find_d036_case_id_by_file_fingerprint(d036_root: Path, *, source: Path) -> str | None:
    images_dir = d036_root / "raw" / "Dataset112_ToothFairy2" / "imagesTr"
    if not images_dir.exists() or not source.exists() or source.suffix.lower() not in {".mha", ".mhd"}:
        return None
    try:
        source_size = source.stat().st_size
    except OSError:
        return None
    size_matches = [
        candidate for candidate in images_dir.glob("ToothFairy2*_0000.mha") if candidate.stat().st_size == source_size
    ]
    if not size_matches:
        return None
    try:
        source_hash = sha256_for_file(source)
    except OSError:
        return None
    for candidate in size_matches:
        try:
            if sha256_for_file(candidate) == source_hash:
                return _d036_case_id_from_path(candidate)
        except OSError:
            continue
    return None


def _find_d024_public_label(d024_root: Path, *, case_id: str, source: Path) -> Path | None:
    if not case_id.startswith("d024_"):
        return None
    if source.parent.name in {"labelsTr", "gt_segmentations"} and source.exists():
        return source
    raw_label = d024_root / "labelsTr" / f"{case_id}.nii.gz"
    if raw_label.exists():
        return raw_label
    preprocessed_label = (
        d024_root.parent.parent
        / "nnUNet_preprocessed"
        / "Dataset124_DentVoxelJawROI"
        / "gt_segmentations"
        / f"{case_id}.nii.gz"
    )
    return preprocessed_label if preprocessed_label.exists() else None


def _d024_case_id_from_path(path: Path) -> str | None:
    return _d024_case_id_from_name(path.name)


def _d024_case_id_from_name(name: str | None) -> str | None:
    if not name:
        return None
    match = re.search(r"(d024_\d{4})(?:_0000)?", str(name), flags=re.IGNORECASE)
    return match.group(1).lower() if match else None


def _cbct_label_surface_evidence(
    *,
    source_info: CbctSegmentationSurfaceSource,
    source_volume_path: Path,
    output_dir: Path,
    decimation_step: int,
    input_type: str,
) -> dict[str, Any]:
    if decimation_step < 1:
        raise ValueError("decimation_step must be >= 1")
    mask, geometry = _load_label_mask_volume(source_info.label_path, label_values=source_info.label_values)
    if decimation_step > 1:
        mask = mask[::decimation_step, ::decimation_step, ::decimation_step]
    if not np.any(mask):
        raise ValueError(f"Labels {source_info.label_values} were not found in {source_info.label_path}")
    mask, pad_offset = _pad_for_marching_cubes(mask)
    vertices_zyx, faces, normals, _ = measure.marching_cubes(mask.astype(np.uint8), level=0.5, spacing=(1.0, 1.0, 1.0))
    vertices_zyx = vertices_zyx - np.asarray(pad_offset, dtype=np.float32)
    vertices = _array_zyx_vertices_to_physical_xyz(vertices_zyx, geometry=geometry, decimation_step=decimation_step)
    if len(faces) == 0:
        raise ValueError(f"Label {source_info.label_value} did not produce a surface mesh")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_info.case_id}_{source_info.output_suffix}.stl"
    write_binary_stl(output_path, vertices=vertices, faces=faces, normals=normals)
    sha256 = sha256_for_file(output_path)
    quality: dict[str, Any] = {
        "method": "label_volume_marching_cubes",
        "source_type": source_info.source_type,
        "label_value": source_info.label_value,
        "label_values": [int(value) for value in source_info.label_values],
        "label_name": source_info.label_name,
        "foreground_voxels": int(np.count_nonzero(mask)),
        "fill_ratio": float(np.count_nonzero(mask)) / float(mask.size),
        "quality_warnings": [
            "public_or_model_segmentation_not_target_domain",
            "physician_case_review_required_before_navigation_claims",
            "cross_modal_registration_missing",
        ],
    }
    label_quality = _label_value_quality_summary(
        source_info.label_path,
        label_values=source_info.label_values,
        source_type=source_info.source_type,
    )
    quality["per_label"] = label_quality["per_label"]
    quality["quality_warnings"].extend(label_quality["quality_warnings"])
    scene_manifest_v2 = _label_surface_scene_manifest_v2(
        source_info=source_info,
        source_volume_path=source_volume_path,
        output_path=output_path,
        vertex_count=len(vertices),
        face_count=len(faces),
        spacing=(
            float(geometry.spacing_xyz[0]) * decimation_step,
            float(geometry.spacing_xyz[1]) * decimation_step,
            float(geometry.spacing_xyz[2]) * decimation_step,
        ),
        sha256=sha256,
        quality=quality,
        geometry=geometry,
        orientation=_orientation_display_payload(
            geometry=geometry,
            source_paths=[source_volume_path, source_info.label_path],
            source_type=source_info.source_type,
        ),
    )
    orientation = scene_manifest_v2["scene"]
    evidence = {
        "schema_version": "osteo-vision-three-d-evidence-v1",
        "model_path": str(output_path),
        "model_format": "stl",
        "model_file_name": output_path.name,
        "model_source": source_info.model_source,
        "exported_from": "label volume + SimpleITK physical geometry + marching_cubes",
        "segmentation_source": source_info.segmentation_source,
        "segmentation_review_status": source_info.segmentation_review_status,
        "registration_status": "unregistered",
        "registration_method": None,
        "registration_error_mm": None,
        "coordinate_space": source_info.coordinate_space,
        "transform_path": None,
        "registration_markups": [],
        "transform_chain": [
            {
                "name": "CBCT segmentation label to jawbone STL",
                "from_space": "cbct_label_volume",
                "to_space": "jawbone_surface_stl",
                "path": str(output_path),
                "status": "ready",
            },
            {
                "name": "Jawbone STL to fluorescence keyframe reference",
                "from_space": "jawbone_surface_stl",
                "to_space": "video_keyframe_reference",
                "path": None,
                "status": "missing",
            },
        ],
        "doctor_review_status": "not_reviewed",
        "navigation_ready": False,
        "input_domain": source_info.input_domain,
        "orientation_review_status": orientation["orientation_review_status"],
        "display_orientation_status": orientation["display_orientation_status"],
        "view_space_mapping": orientation["view_space_mapping"],
        "surface_quality": quality,
        "data_boundary": source_info.data_boundary,
        "scene_manifest_v2": scene_manifest_v2,
        "boundary_note": source_info.boundary_note,
    }
    manifest_path = output_path.with_suffix(".three_d_evidence.json")
    manifest = {
        "schema_version": "osteo-vision-cbct-modeling-result-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_id": source_info.case_id,
        "modeling_status": "completed",
        "source_path": str(source_volume_path),
        "label_path": str(source_info.label_path),
        "input_type": input_type,
        "segmentation_surface_source": source_info.source_type,
        "decimation_step": decimation_step,
        "volume_geometry": _geometry_payload(geometry),
        "surface_model": {
            "path": str(output_path),
            "format": "stl",
            "file_name": output_path.name,
            "sha256": sha256,
            "vertex_count": int(len(vertices)),
            "face_count": int(len(faces)),
            "spacing_mm": [float(value) * decimation_step for value in geometry.spacing_xyz],
            "surface_quality": quality,
        },
        "three_d_evidence": evidence,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "model_path": str(output_path),
        "manifest_path": str(manifest_path),
        "input_type": input_type,
        "modeling_status": "completed",
        "three_d_evidence": evidence,
        "vertex_count": int(len(vertices)),
        "face_count": int(len(faces)),
        "sha256": sha256,
        "message": "已从上下颌骨分割标签生成三维表面；该结果仍未配准、未完成本病例医生复核、非导航。",
    }


def _load_label_mask_volume(
    label_path: Path, *, label_values: tuple[int, ...]
) -> tuple[np.ndarray, CbctVolumeGeometry]:
    try:
        import SimpleITK as sitk
    except ImportError as exc:  # pragma: no cover - project environment should include SimpleITK
        raise RuntimeError("SimpleITK is required for CBCT label surface generation") from exc

    image = sitk.ReadImage(str(label_path))
    array = sitk.GetArrayFromImage(image)
    if array.ndim == 2:
        array = array[np.newaxis, :, :]
    if array.ndim != 3:
        raise ValueError(f"Label volume must be 3D after loading, got shape {array.shape}")
    spacing_xyz = image.GetSpacing()
    spacing = tuple(max(float(spacing_xyz[index]) if len(spacing_xyz) > index else 1.0, 1e-3) for index in range(3))
    origin_raw = image.GetOrigin()
    origin = tuple(float(origin_raw[index]) if len(origin_raw) > index else 0.0 for index in range(3))
    direction_raw = tuple(float(value) for value in image.GetDirection())
    direction = direction_raw if len(direction_raw) == 9 else (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    return np.isin(array, label_values), CbctVolumeGeometry(
        spacing_xyz=spacing,  # type: ignore[arg-type]
        origin_xyz=origin,  # type: ignore[arg-type]
        direction=direction,
    )


def _label_value_quality_summary(
    label_path: Path,
    *,
    label_values: tuple[int, ...],
    source_type: str,
) -> dict[str, Any]:
    try:
        import SimpleITK as sitk
    except ImportError:
        return {"per_label": [], "quality_warnings": ["label_quality_unavailable_simpleitk_missing"]}

    try:
        image = sitk.ReadImage(str(label_path))
        array = sitk.GetArrayFromImage(image)
    except Exception:
        return {"per_label": [], "quality_warnings": ["label_quality_unavailable_read_failed"]}

    per_label: list[dict[str, Any]] = []
    warnings: list[str] = []
    total_voxels = max(int(array.size), 1)
    label_counts: dict[int, int] = {}
    for label_value in label_values:
        value = int(label_value)
        mask = array == value
        voxel_count = int(np.count_nonzero(mask))
        label_counts[value] = voxel_count
        entry: dict[str, Any] = {
            "label_value": value,
            "label_name": _jaw_label_display_name(source_type=source_type, label_value=value),
            "voxel_count": voxel_count,
            "foreground_ratio": float(voxel_count) / float(total_voxels),
            "coverage_status": "missing" if voxel_count == 0 else "recorded",
        }
        if voxel_count:
            coords = np.argwhere(mask)
            min_zyx = coords.min(axis=0)
            max_zyx = coords.max(axis=0)
            bbox_size = max_zyx - min_zyx + 1
            components = measure.label(mask, connectivity=1)
            counts = np.bincount(components.ravel())
            counts[0] = 0
            entry.update(
                {
                    "bbox_min_zyx": [int(value) for value in min_zyx],
                    "bbox_max_zyx": [int(value) for value in max_zyx],
                    "bbox_size_zyx": [int(value) for value in bbox_size],
                    "touches_volume_min_zyx": [bool(value) for value in (min_zyx == 0)],
                    "touches_volume_max_zyx": [bool(value) for value in (max_zyx == np.asarray(array.shape) - 1)],
                    "component_count": int(components.max()),
                    "largest_component_voxels": int(counts.max()) if counts.size else 0,
                }
            )
        per_label.append(entry)

    upper_value = _upper_jaw_label_value_for_source(source_type)
    lower_value = _lower_jaw_label_value_for_source(source_type)
    if upper_value in label_counts and lower_value in label_counts and label_counts[lower_value] > 0:
        upper = next((item for item in per_label if item["label_value"] == upper_value), None)
        ratio = float(label_counts[upper_value]) / float(label_counts[lower_value])
        if upper is not None:
            upper["relative_to_lower_jaw_voxel_ratio"] = ratio
            bbox_size = upper.get("bbox_size_zyx")
            z_size = int(bbox_size[0]) if isinstance(bbox_size, list) and bbox_size else 0
            touches_min_z = bool((upper.get("touches_volume_min_zyx") or [False])[0])
            if label_counts[upper_value] == 0:
                upper["coverage_status"] = "missing"
                warnings.append("upper_jaw_label_missing")
            elif ratio < 0.18 or z_size < 45:
                upper["coverage_status"] = "partial_or_crop_limited"
                warnings.append("upper_jaw_label_sparse_or_crop_limited")
            elif touches_min_z:
                upper["coverage_status"] = "crop_boundary_touching"
                warnings.append("upper_jaw_label_touches_crop_boundary")

    return {"per_label": per_label, "quality_warnings": warnings}


def _jaw_label_display_name(*, source_type: str, label_value: int) -> str:
    if source_type == "public_dataset_label_d024":
        return {1: "maxilla", 2: "mandible"}.get(label_value, f"label_{label_value}")
    if source_type == "public_dataset_label":
        return {1: "lower_jawbone", 2: "upper_jawbone"}.get(label_value, f"label_{label_value}")
    return f"label_{label_value}"


def _upper_jaw_label_value_for_source(source_type: str) -> int:
    return 1 if source_type == "public_dataset_label_d024" else 2


def _lower_jaw_label_value_for_source(source_type: str) -> int:
    return 2 if source_type == "public_dataset_label_d024" else 1


def _label_surface_scene_manifest_v2(
    *,
    source_info: CbctSegmentationSurfaceSource,
    source_volume_path: Path,
    output_path: Path,
    vertex_count: int,
    face_count: int,
    spacing: tuple[float, float, float],
    sha256: str,
    quality: dict[str, Any],
    geometry: CbctVolumeGeometry,
    orientation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "osteo-vision-three-d-scene-v2",
        "source_project": "D036 ToothFairy2 / nnU-Net upper-lower jawbone segmentation evidence scene",
        "case_id": source_info.case_id,
        "dataset_id": source_info.dataset_id,
        "scene_id": f"{source_info.case_id}_{source_info.source_type}_jawbone_scene",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "scene": {
            "coordinate_space": source_info.coordinate_space,
            "registration_status": "unregistered",
            "registration_error_mm": None,
            "navigation_ready": False,
            "doctor_review_status": "not_reviewed",
            "volume_geometry": _geometry_payload(geometry),
            "orientation_review_status": orientation["orientation_review_status"],
            "display_orientation_status": orientation["display_orientation_status"],
            "view_space_mapping": orientation["view_space_mapping"],
        },
        "subject_hierarchy": [
            {"id": "case_root", "name": "病例 / 体数据", "children": ["source_cbct_volume"]},
            {
                "id": "segmentation_models",
                "name": "分割 / 模型",
                "children": ["jawbone_segmentation", "jawbone_surface_model"],
            },
            {
                "id": "markups_review",
                "name": "标注 / 平面",
                "children": ["review_curve_pending", "review_plane_pending"],
            },
            {"id": "geometry_jobs", "name": "几何任务", "children": ["label_surface_export_job"]},
        ],
        "nodes": [
            {
                "id": "source_cbct_volume",
                "type": "volume",
                "role": "source_cbct_volume",
                "name": source_volume_path.name,
                "path": str(source_volume_path),
                "source": "D036 CBCT volume or uploaded CBCT file",
                "review_status": "recorded",
            },
            {
                "id": "jawbone_segmentation",
                "type": "segmentation",
                "role": "upper_lower_jawbone_label",
                "name": source_info.label_name,
                "path": str(source_info.label_path),
                "source": source_info.segmentation_source,
                "label_value": source_info.label_value,
                "label_name": source_info.label_name,
                "review_status": source_info.segmentation_review_status,
                "display": {"visible": True, "color": "#d9c4a8"},
            },
            {
                "id": "jawbone_surface_model",
                "type": "model",
                "role": "cbct_derived_upper_lower_jawbone_surface",
                "name": output_path.name,
                "path": str(output_path),
                "format": "stl",
                "source": "marching_cubes from upper/lower jawbone segmentation label",
                "derived_from": ["jawbone_segmentation"],
                "sha256": sha256,
                "vertex_count": int(vertex_count),
                "face_count": int(face_count),
                "spacing_mm": [float(value) for value in spacing],
                "review_status": source_info.segmentation_review_status,
                "display": {"visible": True, "color": "#d8c5ad", "opacity": 1.0},
                "metadata": {"surface_quality": quality},
            },
        ],
        "markups": [
            {
                "id": "review_curve_pending",
                "type": "curve",
                "role": "mandibular_reference_curve",
                "name": "待医生复核下颌曲线",
                "review_status": "not_available",
                "source": "not recorded",
            },
            {
                "id": "review_plane_pending",
                "type": "plane",
                "role": "review_plane",
                "name": "待医生复核平面",
                "review_status": "not_available",
                "source": "not recorded",
            },
        ],
        "geometry_jobs": [
            {
                "id": "label_surface_export_job",
                "type": "segmentation_label_to_surface",
                "status": "completed",
                "inputs": ["jawbone_segmentation"],
                "outputs": ["jawbone_surface_model"],
                "parameters": {
                    "label_values": [int(value) for value in source_info.label_values],
                    "coordinate_output": "physical_xyz_lps",
                },
            }
        ],
        "review_state": {
            "segmentation": source_info.segmentation_review_status,
            "model": "not_reviewed",
            "markups": "not_available",
            "fluorescence_video_mapping": "missing_registration",
        },
        "data_boundary": source_info.data_boundary,
    }


def _resolve_modeling_source(settings: Settings, source_path: str | Path) -> Path:
    requested = Path(source_path)
    if not requested.is_absolute():
        requested = settings.project_root / requested
    resolved = requested.resolve(strict=True)
    allowed_roots = [
        settings.artifact_root.resolve(),
        (settings.project_root / "artifacts").resolve(),
        (settings.project_root / "research" / "datasets").resolve(),
    ]
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise ValueError("CBCT modeling source is outside allowed project data roots")
    return resolved


def _resolve_modeling_sources(settings: Settings, source_paths: list[str | Path] | None) -> list[Path]:
    if not source_paths:
        return []
    resolved: list[Path] = []
    for source_path in source_paths:
        source = _resolve_modeling_source(settings, source_path)
        if source not in resolved:
            resolved.append(source)
    return resolved


def _try_cbct_proxy_surface(
    *,
    sources: list[Path],
    output_dir: Path,
    case_id: str,
    dataset_id: str,
    decimation_step: int,
    input_type: str,
) -> dict[str, Any] | None:
    try:
        volume, geometry = _load_cbct_proxy_volume(sources)
        return _cbct_proxy_surface_evidence(
            volume=volume,
            geometry=geometry,
            sources=sources,
            output_dir=output_dir,
            case_id=case_id,
            dataset_id=dataset_id,
            decimation_step=decimation_step,
            input_type=input_type,
        )
    except Exception:
        return None


def _load_cbct_proxy_volume(sources: list[Path]) -> tuple[np.ndarray, CbctVolumeGeometry]:
    try:
        import SimpleITK as sitk
    except ImportError as exc:  # pragma: no cover - project environment should include SimpleITK
        raise RuntimeError("SimpleITK is required for CBCT DICOM proxy surface generation") from exc

    if not sources:
        raise ValueError("No DICOM files were provided")
    file_names = [str(path) for path in sources]
    first_suffix = sources[0].suffix.lower()
    if len(file_names) > 1 and first_suffix in {".dcm", ".dicom"}:
        reader = sitk.ImageSeriesReader()
        reader.SetFileNames(file_names)
        image = reader.Execute()
    else:
        image = sitk.ReadImage(file_names[0])
    array = sitk.GetArrayFromImage(image).astype(np.float32)
    if array.ndim == 2:
        array = array[np.newaxis, :, :]
    if array.ndim != 3:
        raise ValueError(f"DICOM volume must be 3D after loading, got shape {array.shape}")
    spacing_xyz = image.GetSpacing()
    spacing = tuple(max(float(spacing_xyz[index]) if len(spacing_xyz) > index else 1.0, 1e-3) for index in range(3))
    origin_raw = image.GetOrigin()
    origin = tuple(float(origin_raw[index]) if len(origin_raw) > index else 0.0 for index in range(3))
    direction_raw = tuple(float(value) for value in image.GetDirection())
    direction = direction_raw if len(direction_raw) == 9 else (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    return array, CbctVolumeGeometry(
        spacing_xyz=spacing,  # type: ignore[arg-type]
        origin_xyz=origin,  # type: ignore[arg-type]
        direction=direction,
    )


def _cbct_proxy_surface_evidence(
    *,
    volume: np.ndarray,
    geometry: CbctVolumeGeometry | tuple[float, float, float],
    sources: list[Path],
    output_dir: Path,
    case_id: str,
    dataset_id: str,
    decimation_step: int,
    input_type: str,
) -> dict[str, Any]:
    if decimation_step < 1:
        raise ValueError("decimation_step must be >= 1")
    geometry = _coerce_cbct_geometry(geometry)
    data = np.asarray(volume, dtype=np.float32)
    effective_step = max(decimation_step, _auto_proxy_decimation_step(data))
    if effective_step > 1:
        data = data[::effective_step, ::effective_step, ::effective_step]
    mask, quality = _hard_tissue_proxy_mask_with_summary(data)
    if not np.any(mask):
        raise ValueError("DICOM CBCT proxy threshold produced an empty mask")
    mask, pad_offset = _pad_for_marching_cubes(mask)
    vertices_zyx, faces, normals, _ = measure.marching_cubes(mask.astype(np.uint8), level=0.5, spacing=(1.0, 1.0, 1.0))
    vertices_zyx = vertices_zyx - np.asarray(pad_offset, dtype=np.float32)
    vertices = _array_zyx_vertices_to_physical_xyz(vertices_zyx, geometry=geometry, decimation_step=effective_step)
    if len(faces) == 0:
        raise ValueError("DICOM CBCT proxy mask did not produce a surface mesh")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{case_id}_cbct_balanced_hard_tissue_proxy.stl"
    write_binary_stl(output_path, vertices=vertices, faces=faces, normals=normals)
    sha256 = sha256_for_file(output_path)
    source_names = [source.name for source in sources]
    orientation = _orientation_display_payload(
        geometry=geometry,
        source_paths=sources,
        source_type="balanced_hard_tissue_proxy",
    )
    scene_manifest_v2 = _dicom_proxy_scene_manifest_v2(
        case_id=case_id,
        dataset_id=dataset_id,
        source_names=source_names,
        output_path=output_path,
        vertex_count=len(vertices),
        face_count=len(faces),
        spacing=(
            float(geometry.spacing_xyz[0]) * effective_step,
            float(geometry.spacing_xyz[1]) * effective_step,
            float(geometry.spacing_xyz[2]) * effective_step,
        ),
        sha256=sha256,
        quality=quality,
        geometry=geometry,
        decimation_step=effective_step,
        orientation=orientation,
    )
    evidence = {
        "schema_version": "osteo-vision-three-d-evidence-v1",
        "model_path": str(output_path),
        "model_format": "stl",
        "model_file_name": output_path.name,
        "model_source": "uploaded CBCT balanced hard tissue proxy",
        "exported_from": "SimpleITK physical geometry + adaptive bone-window threshold + morphology + marching_cubes",
        "segmentation_source": "automatic balanced hard tissue proxy from raw CBCT; not jawbone-specific",
        "segmentation_review_status": "not_reviewed",
        "registration_status": "unregistered",
        "registration_method": None,
        "registration_error_mm": None,
        "coordinate_space": "cbct_physical_lps_mm_proxy",
        "transform_path": None,
        "registration_markups": [],
        "transform_chain": [
            {
                "name": "CBCT DICOM voxels to physical hard tissue proxy STL",
                "from_space": "dicom_voxel_space",
                "to_space": "cbct_physical_hard_tissue_proxy_stl",
                "path": str(output_path),
                "status": "ready",
            },
            {
                "name": "Proxy STL to video keyframe reference",
                "from_space": "cbct_hard_tissue_proxy_stl",
                "to_space": "video_keyframe_reference",
                "path": None,
                "status": "missing",
            },
        ],
        "doctor_review_status": "not_reviewed",
        "navigation_ready": False,
        "input_domain": "uploaded_cbct_proxy_surface",
        "orientation_review_status": orientation["orientation_review_status"],
        "display_orientation_status": orientation["display_orientation_status"],
        "view_space_mapping": orientation["view_space_mapping"],
        "surface_quality": quality,
        "data_boundary": (
            "Raw CBCT balanced hard tissue proxy generated for platform workflow validation. "
            "It uses ITK physical geometry but is not a jawbone-specific physician-reviewed segmentation and not navigation-ready."
        ),
        "scene_manifest_v2": scene_manifest_v2,
        "boundary_note": (
            "该表面由原始 CBCT 自适应骨窗阈值和形态学清理自动生成，并按 ITK 物理坐标写出，只用于让三维任务跑通和工程检查；"
            "它不是医生复核的上下颌骨分割，不能作为真实术中定位或手术边界。"
        ),
    }
    manifest_path = output_path.with_suffix(".three_d_evidence.json")
    manifest = {
        "schema_version": "osteo-vision-cbct-modeling-result-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_id": case_id,
        "modeling_status": "completed",
        "source_paths": [str(source) for source in sources],
        "input_type": input_type,
        "proxy_method": "balanced_hard_tissue_adaptive_threshold_physical_axes",
        "decimation_step": effective_step,
        "volume_geometry": _geometry_payload(geometry),
        "surface_model": {
            "path": str(output_path),
            "format": "stl",
            "file_name": output_path.name,
            "sha256": sha256,
            "vertex_count": int(len(vertices)),
            "face_count": int(len(faces)),
            "spacing_mm": [float(value) * effective_step for value in geometry.spacing_xyz],
            "surface_quality": quality,
        },
        "three_d_evidence": evidence,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "model_path": str(output_path),
        "manifest_path": str(manifest_path),
        "input_type": input_type,
        "modeling_status": "completed",
        "three_d_evidence": evidence,
        "vertex_count": int(len(vertices)),
        "face_count": int(len(faces)),
        "sha256": sha256,
        "message": "已从原始 CBCT/体数据生成自适应硬组织代理表面；该结果按物理坐标写出，但仍未分割上下颌骨、未配准、非导航。",
    }


def _auto_proxy_decimation_step(data: np.ndarray) -> int:
    voxel_count = int(np.prod(data.shape))
    if voxel_count > 250_000_000:
        return 4
    if voxel_count > 100_000_000:
        return 3
    if voxel_count > 30_000_000:
        return 2
    return 1


def _hard_tissue_proxy_mask(data: np.ndarray) -> np.ndarray:
    mask, _ = _hard_tissue_proxy_mask_with_summary(data)
    return mask


def _hard_tissue_proxy_mask_with_summary(data: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise ValueError("DICOM volume contains no finite voxel values")
    spread = float(np.max(finite) - np.min(finite))
    if spread <= 1e-6:
        raise ValueError("DICOM volume has no usable intensity contrast")
    p90 = float(np.percentile(finite, 90))
    p92 = float(np.percentile(finite, 92))
    p95 = float(np.percentile(finite, 95))
    p98 = float(np.percentile(finite, 98))
    p99 = float(np.percentile(finite, 99))
    hu_like = float(np.max(finite)) > 1000.0 and float(np.min(finite)) < -500.0
    lower_bound = 320.0 if hu_like else max(p90, float(np.mean(finite) + 0.75 * np.std(finite)))
    threshold = float(np.clip(p95, lower_bound, p98))
    mask, fill_ratio = _mask_at_threshold(data, threshold)
    if fill_ratio < 0.015:
        threshold = float(np.clip(p92, 260.0 if hu_like else p90, p95))
        mask, fill_ratio = _mask_at_threshold(data, threshold)
    elif fill_ratio > 0.09:
        threshold = float(np.clip(p98, p95, p99))
        mask, fill_ratio = _mask_at_threshold(data, threshold)

    closed_mask = _close_proxy_mask(mask)
    mask, component_summary = _keep_major_components(closed_mask)
    kept_fill_ratio = float(np.count_nonzero(mask)) / float(mask.size)
    quality = {
        "method": "balanced_adaptive_hard_tissue_proxy",
        "threshold_policy": "p95 clipped to a CBCT bone-window floor, with p92/p98 fallback by fill ratio",
        "threshold_value": float(threshold),
        "percentile_90": p90,
        "percentile_92": p92,
        "percentile_95": p95,
        "percentile_98": p98,
        "percentile_99": p99,
        "fill_ratio_before_components": fill_ratio,
        "fill_ratio_after_components": kept_fill_ratio,
        "component_count": component_summary["component_count"],
        "kept_component_count": component_summary["kept_component_count"],
        "kept_component_voxels": component_summary["kept_component_voxels"],
        "quality_warnings": [
            "raw_cbct_threshold_proxy_not_jawbone_segmentation",
            "metal_artifact_and_teeth_may_dominate_surface",
            "balanced_proxy_can_still_include_maxilla_or_other_hard_tissue",
            "physician_reviewed_segmentation_required_for_reference_jawbone",
        ],
    }
    return mask, quality


def _mask_at_threshold(data: np.ndarray, threshold: float) -> tuple[np.ndarray, float]:
    mask = data >= threshold
    fill_ratio = float(np.count_nonzero(mask)) / float(mask.size)
    return mask, fill_ratio


def _close_proxy_mask(mask: np.ndarray) -> np.ndarray:
    if min(mask.shape) < 3:
        return mask
    footprint = morphology.ball(1)
    return morphology.closing(mask, footprint=footprint)


def _keep_major_components(mask: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    labels = measure.label(mask, connectivity=1)
    if labels.max() == 0:
        return mask, {"component_count": 0, "kept_component_count": 0, "kept_component_voxels": []}
    counts = np.bincount(labels.ravel())
    counts[0] = 0
    largest = int(counts.max())
    min_size = max(96, int(mask.size * 0.00002), int(largest * 0.025))
    ranked_labels = sorted(
        (label for label in range(1, len(counts)) if counts[label] >= min_size),
        key=lambda label: int(counts[label]),
        reverse=True,
    )[:10]
    if not ranked_labels:
        ranked_labels = [int(np.argmax(counts))]
    kept = np.isin(labels, ranked_labels)
    return kept, {
        "component_count": int(labels.max()),
        "kept_component_count": int(len(ranked_labels)),
        "kept_component_voxels": [int(counts[label]) for label in ranked_labels],
    }


def _pad_for_marching_cubes(mask: np.ndarray) -> tuple[np.ndarray, tuple[float, float, float]]:
    padded = mask
    pad_width: list[tuple[int, int]] = []
    for size in padded.shape:
        pad_width.append((1, 1) if size < 2 else (0, 0))
    padded = np.pad(padded, pad_width, mode="constant", constant_values=False)
    final_pad = [(before + 1, after + 1) for before, after in pad_width]
    offsets = cast(tuple[float, float, float], tuple(float(before) for before, _ in final_pad))
    return np.pad(mask, final_pad, mode="constant", constant_values=False), offsets


def _coerce_cbct_geometry(geometry: CbctVolumeGeometry | tuple[float, float, float]) -> CbctVolumeGeometry:
    if isinstance(geometry, CbctVolumeGeometry):
        return geometry
    spacing_values = tuple(max(float(value), 1e-3) for value in geometry[:3])
    spacing = (spacing_values[0], spacing_values[1], spacing_values[2]) if len(spacing_values) == 3 else (1.0, 1.0, 1.0)
    return CbctVolumeGeometry(
        spacing_xyz=spacing,
        origin_xyz=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
    )


def _array_zyx_vertices_to_physical_xyz(
    vertices_zyx: np.ndarray,
    *,
    geometry: CbctVolumeGeometry,
    decimation_step: int,
) -> np.ndarray:
    index_xyz = np.column_stack(
        [
            vertices_zyx[:, 2] * float(decimation_step),
            vertices_zyx[:, 1] * float(decimation_step),
            vertices_zyx[:, 0] * float(decimation_step),
        ]
    ).astype(np.float64)
    spacing = np.asarray(geometry.spacing_xyz, dtype=np.float64)
    origin = np.asarray(geometry.origin_xyz, dtype=np.float64)
    direction = np.asarray(geometry.direction, dtype=np.float64).reshape(3, 3)
    physical = origin + (index_xyz * spacing) @ direction.T
    return physical.astype(np.float32)


def _geometry_payload(geometry: CbctVolumeGeometry) -> dict[str, Any]:
    return {
        "spacing_xyz_mm": [float(value) for value in geometry.spacing_xyz],
        "origin_xyz_mm": [float(value) for value in geometry.origin_xyz],
        "direction": [float(value) for value in geometry.direction],
        "array_axis_order": "zyx",
        "stl_vertex_order": "physical_xyz_lps",
    }


def _direction_is_identity(direction: tuple[float, ...]) -> bool:
    if len(direction) != 9:
        return False
    identity = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    return all(abs(float(value) - expected) < 1e-6 for value, expected in zip(direction, identity, strict=True))


def _orientation_display_payload(
    *,
    geometry: CbctVolumeGeometry,
    source_paths: list[Path],
    source_type: str,
) -> dict[str, Any]:
    suffixes = {path.suffix.lower() for path in source_paths}
    identity_direction = _direction_is_identity(geometry.direction)
    identity_mha_like = identity_direction and bool(suffixes & {".mha", ".mhd"})
    toothfairy_like = source_type.lower().startswith(("public_dataset_label", "nnunet_prediction"))
    use_inferior_z_display = identity_mha_like or toothfairy_like
    display_up_axis = "-physical_z" if use_inferior_z_display else "physical_z"
    rotation_x_degrees = 90 if use_inferior_z_display else -90
    reason = (
        "MHA/ToothFairy2 jaw volumes in this project use identity direction metadata while array z increases from upper jaw toward lower jaw; "
        "the frontend flips z for review display so maxilla appears above mandible."
        if use_inferior_z_display
        else "SimpleITK physical LPS geometry is used directly; frontend maps physical Z to the display up axis."
    )
    return {
        "orientation_review_status": "pending_slicer_or_physician_review",
        "display_orientation_status": "axis_mapping_inferred_not_physician_reviewed",
        "view_space_mapping": {
            "source_vertex_order": "physical_xyz_lps",
            "display_up_axis": display_up_axis,
            "frontend_rotation_x_degrees": rotation_x_degrees,
            "identity_direction": identity_direction,
            "requires_review": True,
            "reason": reason,
        },
    }


def _dicom_proxy_scene_manifest_v2(
    *,
    case_id: str,
    dataset_id: str,
    source_names: list[str],
    output_path: Path,
    vertex_count: int,
    face_count: int,
    spacing: tuple[float, float, float],
    sha256: str,
    quality: dict[str, Any],
    geometry: CbctVolumeGeometry,
    decimation_step: int,
    orientation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "osteo-vision-three-d-scene-v2",
        "source_project": "Osteo Vision CBCT hard tissue proxy workflow",
        "case_id": case_id,
        "dataset_id": dataset_id,
        "scene_id": f"{case_id}_cbct_proxy_scene",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "scene": {
            "coordinate_space": "cbct_physical_lps_mm_proxy",
            "registration_status": "unregistered",
            "registration_error_mm": None,
            "navigation_ready": False,
            "doctor_review_status": "not_reviewed",
            "volume_geometry": _geometry_payload(geometry),
            "orientation_review_status": orientation["orientation_review_status"],
            "display_orientation_status": orientation["display_orientation_status"],
            "view_space_mapping": orientation["view_space_mapping"],
        },
        "subject_hierarchy": [
            {"id": "case_root", "name": "病例 / 体数据", "children": ["uploaded_cbct_volume"]},
            {"id": "segmentation_models", "name": "分割 / 模型", "children": ["hard_tissue_proxy_model"]},
            {
                "id": "markups_review",
                "name": "标注 / 平面",
                "children": ["review_curve_pending", "review_plane_pending"],
            },
            {"id": "geometry_jobs", "name": "几何任务", "children": ["cbct_proxy_surface_job"]},
        ],
        "nodes": [
            {
                "id": "uploaded_cbct_volume",
                "type": "volume",
                "role": "source_cbct_volume",
                "name": ", ".join(source_names[:3]) if source_names else "uploaded CBCT series",
                "source": "browser uploaded CBCT DICOM series",
                "review_status": "recorded",
            },
            {
                "id": "hard_tissue_proxy_model",
                "type": "model",
                "role": "hard_tissue_proxy_surface",
                "name": output_path.name,
                "path": str(output_path),
                "format": "stl",
                "source": "automatic balanced hard tissue proxy from raw CBCT",
                "review_status": "not_reviewed",
                "display": {"visible": True, "color": "#d8c5ad", "opacity": 1.0},
                "metadata": {
                    "vertex_count": int(vertex_count),
                    "face_count": int(face_count),
                    "spacing_mm": [float(value) for value in spacing],
                    "sha256": sha256,
                    "decimation_step": int(decimation_step),
                    "surface_quality": quality,
                },
            },
        ],
        "markups": [
            {
                "id": "review_curve_pending",
                "type": "curve",
                "role": "mandibular_reference_curve",
                "name": "待医生复核下颌曲线",
                "review_status": "not_available",
                "source": "not recorded",
            },
            {
                "id": "review_plane_pending",
                "type": "plane",
                "role": "review_plane",
                "name": "待医生复核平面",
                "review_status": "not_available",
                "source": "not recorded",
            },
        ],
        "geometry_jobs": [
            {
                "id": "cbct_proxy_surface_job",
                "type": "cbct_balanced_hard_tissue_proxy_surface",
                "status": "completed",
                "inputs": source_names,
                "outputs": ["hard_tissue_proxy_model"],
                "parameters": {
                    "threshold_value": quality.get("threshold_value"),
                    "decimation_step": int(decimation_step),
                    "coordinate_output": "physical_xyz_lps",
                },
            }
        ],
        "review_state": {
            "segmentation": "hard_tissue_proxy_not_jawbone_specific",
            "model": "not_reviewed",
            "markups": "not_available",
            "fluorescence_video_mapping": "missing_registration",
        },
        "data_boundary": (
            "Raw CBCT proxy surface only. Not a physician-reviewed jawbone segmentation and not navigation-ready."
        ),
    }


def _surface_model_evidence(source: Path, *, output_dir: Path, case_id: str) -> dict[str, Any]:
    manifest_path = output_dir / f"{source.stem}.three_d_evidence.json"
    scene_manifest_v2 = _surface_model_scene_manifest_v2(source=source, case_id=case_id)
    evidence = {
        "schema_version": "osteo-vision-three-d-evidence-v1",
        "model_path": str(source),
        "model_format": source.suffix.lower().lstrip("."),
        "model_file_name": source.name,
        "model_source": "uploaded local surface model",
        "exported_from": "user uploaded STL/GLB/GLTF; no surface generation was run",
        "segmentation_source": "surface model supplied directly",
        "segmentation_review_status": "not_reviewed",
        "registration_status": "unregistered",
        "registration_method": None,
        "registration_error_mm": None,
        "coordinate_space": "uploaded_surface_file_space",
        "transform_path": None,
        "registration_markups": [],
        "transform_chain": [
            {
                "name": "Uploaded surface to 3D reference panel",
                "from_space": "uploaded_surface_file_space",
                "to_space": "three_d_reference_panel",
                "path": str(source),
                "status": "ready",
            },
            {
                "name": "3D reference to video keyframe evidence",
                "from_space": "three_d_reference_panel",
                "to_space": "video_keyframe_reference",
                "path": None,
                "status": "missing",
            },
        ],
        "doctor_review_status": "not_reviewed",
        "navigation_ready": False,
        "input_domain": "uploaded_surface_reference",
        "data_boundary": "Uploaded surface model is unregistered and not navigation-ready.",
        "scene_manifest_v2": scene_manifest_v2,
        "boundary_note": "该表面模型只用于三维检查和术前证据参考；未完成配准误差记录和医生复核前不得作为术中定位。",
    }
    manifest = {
        "schema_version": "osteo-vision-cbct-modeling-result-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_id": case_id,
        "modeling_status": "surface_model_ready",
        "source_path": str(source),
        "three_d_evidence": evidence,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "model_path": str(source),
        "manifest_path": str(manifest_path),
        "input_type": "surface_model",
        "modeling_status": "surface_model_ready",
        "three_d_evidence": evidence,
    }


def _surface_model_scene_manifest_v2(*, source: Path, case_id: str) -> dict[str, Any]:
    return {
        "schema_version": "osteo-vision-three-d-scene-v2",
        "source_project": "3D Slicer MRML and SlicerBoneReconstructionPlanner-inspired evidence scene",
        "case_id": case_id,
        "dataset_id": "local_upload",
        "scene_id": f"{case_id}_uploaded_surface_scene",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "scene": {
            "coordinate_space": "uploaded_surface_file_space",
            "registration_status": "unregistered",
            "registration_error_mm": None,
            "navigation_ready": False,
            "doctor_review_status": "not_reviewed",
        },
        "subject_hierarchy": [
            {"id": "case_root", "name": "病例 / 体数据", "children": []},
            {"id": "segmentation_models", "name": "分割 / 模型", "children": ["uploaded_surface_model"]},
            {
                "id": "markups_review",
                "name": "标注 / 平面",
                "children": ["review_curve_pending", "review_plane_pending"],
            },
            {"id": "geometry_jobs", "name": "几何任务", "children": ["surface_import_job"]},
        ],
        "nodes": [
            {
                "id": "uploaded_surface_model",
                "type": "model",
                "role": "uploaded_surface_reference",
                "name": source.name,
                "path": str(source),
                "format": source.suffix.lower().lstrip("."),
                "source": "user uploaded surface model",
                "derived_from": [],
                "review_status": "not_reviewed",
                "display": {"visible": True, "color": "#d8c5ad", "opacity": 1.0},
            }
        ],
        "markups": [
            {
                "id": "review_curve_pending",
                "type": "curve",
                "role": "mandibular_reference_curve",
                "name": "待医生复核下颌曲线",
                "review_status": "not_available",
                "source": "not recorded",
            },
            {
                "id": "review_plane_pending",
                "type": "plane",
                "role": "review_plane",
                "name": "待医生复核平面",
                "review_status": "not_available",
                "source": "not recorded",
            },
        ],
        "transforms": [
            {
                "id": "surface_to_video",
                "type": "cross_modal_registration",
                "from_node": "uploaded_surface_model",
                "to_node": "fluorescence_video_keyframes",
                "from_space": "uploaded_surface_file_space",
                "to_space": "video_keyframe_reference",
                "status": "missing",
                "error_mm": None,
            }
        ],
        "geometry_jobs": [
            {
                "id": "surface_import_job",
                "type": "surface_import",
                "status": "completed",
                "inputs": [str(source)],
                "outputs": ["uploaded_surface_model"],
            }
        ],
        "review_state": {
            "segmentation": "surface_supplied_directly",
            "model": "not_reviewed",
            "markups": "not_available",
            "fluorescence_video_mapping": "missing_registration",
        },
        "data_boundary": "Uploaded surface model is unregistered and not navigation-ready.",
    }


def _unsupported_volume_manifest(source: Path, *, output_dir: Path, input_type: str, case_id: str) -> Path:
    manifest_path = output_dir / f"{source.stem}.cbct_modeling_check.json"
    manifest = {
        "schema_version": "osteo-vision-cbct-modeling-result-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_id": case_id,
        "modeling_status": "segmentation_required",
        "source_path": str(source),
        "input_type": input_type,
        "boundary_note": (
            "该体数据已保存并完成基础检查，但需要 Slicer Segment Editor、医生复核标签或后端分割结果后，"
            "才能生成上下颌骨表面模型。"
        ),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _source_role_mismatch_manifest(
    source: Path,
    *,
    output_dir: Path,
    input_type: str,
    case_id: str,
    requested_source_role: str,
) -> Path:
    manifest_path = output_dir / f"{source.stem}.cbct_modeling_check.json"
    manifest = {
        "schema_version": "osteo-vision-cbct-modeling-result-v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "case_id": case_id,
        "modeling_status": "segmentation_required",
        "source_path": str(source),
        "input_type": input_type,
        "requested_source_role": requested_source_role,
        "boundary_note": (
            "建模入口已区分原始 CBCT 强度体和分割标签体；角色不匹配时不会按 label_value "
            "直接抽取表面，避免把灰度值误作上下颌标签。"
        ),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _safe_stem(path: Path) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in path.stem)[:80] or "cbct_import"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
