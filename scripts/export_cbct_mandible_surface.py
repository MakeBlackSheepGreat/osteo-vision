from __future__ import annotations

import argparse
import hashlib
import json
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from skimage import measure

DEFAULT_INPUT = Path(
    "research/datasets/public-candidates/d024_dentvoxel/derived/nnunet/nnUNet_preprocessed/"
    "Dataset124_DentVoxelJawROI/gt_segmentations/d024_0001.nii.gz"
)
DEFAULT_OUTPUT = Path("frontend/public/models/local/mandible_d024_0001.stl")
DEFAULT_LABEL_VALUE = 2
SCHEMA_VERSION = "osteo-vision-cbct-surface-export-v1"
THREE_D_EVIDENCE_SCHEMA = "osteo-vision-three-d-evidence-v1"
DATA_BOUNDARY = (
    "D024 DentVoxel public CBCT-derived mandible surface; non-target-domain anatomy reference only. "
    "It is not a real jaw osteomyelitis intraoperative ICG case, not registered to video, and not surgical navigation."
)


def main() -> None:
    args = parse_args()
    result = export_mandible_surface(
        input_path=args.input,
        output_path=args.output,
        label_value=args.label_value,
        dataset_id=args.dataset_id,
        case_id=args.case_id,
        decimation_step=args.decimation_step,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a D024 CBCT mandible label surface to binary STL.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input label NIfTI path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output STL path.")
    parser.add_argument("--label-value", type=int, default=DEFAULT_LABEL_VALUE, help="Label value to extract.")
    parser.add_argument("--dataset-id", default="D024", help="Dataset identifier for the manifest.")
    parser.add_argument("--case-id", default="d024_0001", help="Source case identifier for the manifest.")
    parser.add_argument(
        "--decimation-step",
        type=int,
        default=1,
        help="Optional voxel downsampling step before marching cubes; keep 1 for maximum fidelity.",
    )
    return parser.parse_args()


def export_mandible_surface(
    *,
    input_path: Path,
    output_path: Path,
    label_value: int,
    dataset_id: str,
    case_id: str,
    decimation_step: int = 1,
) -> dict[str, Any]:
    if decimation_step < 1:
        raise ValueError("decimation_step must be >= 1")
    if not input_path.exists():
        raise FileNotFoundError(f"Input label volume does not exist: {input_path}")

    image = nib.load(str(input_path))
    data = np.asarray(image.dataobj)
    mask = data == label_value
    if decimation_step > 1:
        mask = mask[::decimation_step, ::decimation_step, ::decimation_step]
    if not np.any(mask):
        raise ValueError(f"Label {label_value} was not found in {input_path}")

    spacing = voxel_spacing_from_image(image, decimation_step=decimation_step)
    vertices, faces, normals, _ = measure.marching_cubes(mask.astype(np.uint8), level=0.5, spacing=spacing)
    if len(faces) == 0:
        raise ValueError(f"Label {label_value} did not produce a surface mesh")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_binary_stl(output_path, vertices=vertices, faces=faces, normals=normals)
    sha256 = sha256_for_file(output_path)
    manifest = build_manifest(
        input_path=input_path,
        output_path=output_path,
        label_value=label_value,
        dataset_id=dataset_id,
        case_id=case_id,
        spacing=spacing,
        vertices=vertices,
        faces=faces,
        sha256=sha256,
    )
    manifest_path = output_path.with_suffix(".three_d_evidence.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "stl_path": str(output_path),
        "manifest_path": str(manifest_path),
        "vertex_count": int(len(vertices)),
        "face_count": int(len(faces)),
        "sha256": sha256,
    }


def voxel_spacing_from_image(image: nib.spatialimages.SpatialImage, *, decimation_step: int) -> tuple[float, float, float]:
    zooms = image.header.get_zooms()[:3]
    spacing = tuple(float(value) * decimation_step for value in zooms)
    if len(spacing) != 3 or any(value <= 0 for value in spacing):
        return (1.0 * decimation_step, 1.0 * decimation_step, 1.0 * decimation_step)
    return spacing  # type: ignore[return-value]


def write_binary_stl(
    output_path: Path,
    *,
    vertices: np.ndarray,
    faces: np.ndarray,
    normals: np.ndarray | None = None,
) -> None:
    header = b"Osteo Vision D024 public CBCT mandible surface; unregistered non-navigation reference"
    header = header[:80].ljust(80, b" ")
    with output_path.open("wb") as handle:
        handle.write(header)
        handle.write(struct.pack("<I", int(len(faces))))
        for face in faces:
            tri_vertices = vertices[np.asarray(face, dtype=np.int64)]
            normal = triangle_normal(tri_vertices)
            handle.write(struct.pack("<3f", *normal))
            for vertex in tri_vertices:
                handle.write(struct.pack("<3f", float(vertex[0]), float(vertex[1]), float(vertex[2])))
            handle.write(struct.pack("<H", 0))


def triangle_normal(triangle: np.ndarray) -> tuple[float, float, float]:
    edge_a = triangle[1] - triangle[0]
    edge_b = triangle[2] - triangle[0]
    normal = np.cross(edge_a, edge_b)
    length = float(np.linalg.norm(normal))
    if length <= 0:
        return (0.0, 0.0, 0.0)
    normal = normal / length
    return (float(normal[0]), float(normal[1]), float(normal[2]))


def build_manifest(
    *,
    input_path: Path,
    output_path: Path,
    label_value: int,
    dataset_id: str,
    case_id: str,
    spacing: tuple[float, float, float],
    vertices: np.ndarray,
    faces: np.ndarray,
    sha256: str,
) -> dict[str, Any]:
    scene_manifest = build_scene_manifest(
        dataset_id=dataset_id,
        case_id=case_id,
        vertices=vertices,
        spacing=spacing,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "dataset_id": dataset_id,
            "case_id": case_id,
            "modality": "CBCT",
            "input_label_path": str(input_path),
            "label_value": label_value,
            "label_name": "mandible",
            "label_source": "D024 DentVoxel nnU-Net preprocessed jaw ROI labels",
            "target_domain": False,
        },
        "surface_model": {
            "path": str(output_path),
            "format": "stl",
            "file_name": output_path.name,
            "sha256": sha256,
            "vertex_count": int(len(vertices)),
            "face_count": int(len(faces)),
            "spacing_mm": [float(value) for value in spacing],
        },
        "three_d_evidence": {
            "schema_version": THREE_D_EVIDENCE_SCHEMA,
            "model_path": str(output_path),
            "model_format": "stl",
            "model_file_name": output_path.name,
            "model_source": "D024 DentVoxel public CBCT derived mandible label",
            "exported_from": "scripts/export_cbct_mandible_surface.py marching_cubes",
            "segmentation_source": "D024 DentVoxel label value 2 mandible",
            "segmentation_review_status": "public_dataset_annotation_not_case_reviewed",
            "registration_status": "unregistered",
            "registration_method": None,
            "registration_error_mm": None,
            "coordinate_space": "cbct_label_voxel_spacing_mm",
            "transform_path": None,
            "registration_markups": [],
            "transform_chain": [
                {
                    "name": "D024 label volume to STL surface",
                    "from_space": "cbct_label_voxel",
                    "to_space": "mandible_stl",
                    "path": str(output_path),
                    "status": "ready",
                },
                {
                    "name": "STL surface to video keyframe evidence",
                    "from_space": "mandible_stl",
                    "to_space": "video_keyframe_reference",
                    "path": None,
                    "status": "missing",
                },
            ],
            "doctor_review_status": "not_reviewed",
            "navigation_ready": False,
            "input_domain": "public_cbct_anatomy_reference",
            "data_boundary": DATA_BOUNDARY,
            "scene_manifest": scene_manifest,
            "boundary_note": DATA_BOUNDARY,
        },
    }


def build_scene_manifest(
    *,
    dataset_id: str,
    case_id: str,
    vertices: np.ndarray,
    spacing: tuple[float, float, float],
) -> dict[str, Any]:
    """Build a BRP-inspired, non-navigation scene manifest for frontend display."""
    bounds_min = vertices.min(axis=0)
    bounds_max = vertices.max(axis=0)
    center = (bounds_min + bounds_max) / 2.0
    size = np.maximum(bounds_max - bounds_min, 1e-6)
    curve_points = _mandibular_curve_points(bounds_min=bounds_min, bounds_max=bounds_max, center=center)
    return {
        "schema_version": "osteo-vision-three-d-scene-v1",
        "source_project": "SlicerBoneReconstructionPlanner-inspired scene semantics",
        "scene_id": f"{dataset_id.lower()}_{case_id}_mandible_reference_scene",
        "coordinate_space": "cbct_label_voxel_spacing_mm",
        "model_bounds_mm": {
            "min": _float_list(bounds_min),
            "max": _float_list(bounds_max),
            "center": _float_list(center),
            "size": _float_list(size),
            "spacing_mm": [float(value) for value in spacing],
        },
        "mandibular_curve": {
            "id": "d024_mandibular_reference_curve",
            "label": "D024 mandibular reference curve",
            "source": "derived from STL bounding box for display; not physician markups",
            "coordinate_space": "cbct_label_voxel_spacing_mm",
            "points_mm": [_float_list(point) for point in curve_points],
            "display_points": [
                [-1.9, 0.02, -0.08],
                [-1.42, -0.12, 0.16],
                [-0.72, -0.28, 0.34],
                [0.0, -0.36, 0.42],
                [0.72, -0.28, 0.34],
                [1.42, -0.12, 0.16],
                [1.9, 0.02, -0.08],
            ],
        },
        "review_planes": [
            {
                "id": "d024_review_plane_left",
                "label": "Reference review plane left",
                "source": "synthetic BRP-style review plane for display",
                "origin_mm": _float_list(curve_points[1]),
                "normal": [1.0, 0.0, 0.0],
                "display_position": [-0.95, 0.18, 0.12],
                "display_rotation": [0.0, 1.44, -0.16],
                "display_scale": [1.0, 1.85, 1.0],
                "status": "illustrative_unregistered",
            },
            {
                "id": "d024_review_plane_mid",
                "label": "Reference review plane middle",
                "source": "synthetic BRP-style review plane for display",
                "origin_mm": _float_list(curve_points[3]),
                "normal": [1.0, 0.0, 0.0],
                "display_position": [0.0, 0.21, 0.12],
                "display_rotation": [0.0, 1.57, 0.0],
                "display_scale": [1.0, 1.85, 1.0],
                "status": "illustrative_unregistered",
            },
            {
                "id": "d024_review_plane_right",
                "label": "Reference review plane right",
                "source": "synthetic BRP-style review plane for display",
                "origin_mm": _float_list(curve_points[5]),
                "normal": [1.0, 0.0, 0.0],
                "display_position": [0.95, 0.24, 0.12],
                "display_rotation": [0.0, 1.70, 0.16],
                "display_scale": [1.0, 1.85, 1.0],
                "status": "illustrative_unregistered",
            },
        ],
        "fibula_reference": {
            "label": "BRP fibula line and miter boxes reference",
            "display_curve": [
                [-1.92, -1.34, -0.26],
                [-0.72, -1.24, -0.18],
                [0.62, -1.28, -0.10],
                [1.84, -1.36, -0.20],
            ],
            "segment_lengths_mm": [29.49, 28.95],
            "miter_planes": [
                {"id": "miter_a", "display_position": [-0.64, -1.27, -0.10], "display_rotation": [0.0, 1.29, 0.08]},
                {"id": "miter_b", "display_position": [-0.12, -1.27, -0.10], "display_rotation": [0.0, 1.75, 0.08]},
                {"id": "miter_c", "display_position": [0.48, -1.27, -0.10], "display_rotation": [0.0, 1.37, 0.08]},
            ],
        },
        "slice_views": {
            "axial": {"axis": "Z", "base_mm": float(center[2]), "note": "示意 reslice；未加载真实 CBCT 体数据。"},
            "coronal": {"axis": "Y", "base_mm": float(center[1]), "note": "示意 reslice；未加载真实 CBCT 体数据。"},
            "sagittal": {"axis": "X", "base_mm": float(center[0]), "note": "示意 reslice；未加载真实 CBCT 体数据。"},
        },
        "migration_notes": [
            "Scene fields mirror Slicer BRP curve, plane, fibula line and miter box concepts.",
            "Generated planes are display references only; no registered surgical guide or navigation output is produced.",
        ],
    }


def _mandibular_curve_points(*, bounds_min: np.ndarray, bounds_max: np.ndarray, center: np.ndarray) -> list[np.ndarray]:
    xs = np.linspace(bounds_min[0], bounds_max[0], 7)
    width = max(float(bounds_max[0] - bounds_min[0]), 1e-6)
    points: list[np.ndarray] = []
    for x in xs:
        t = (float(x) - float(bounds_min[0])) / width
        arch = np.sin(t * np.pi)
        y = float(bounds_min[1]) + 0.58 * float(bounds_max[1] - bounds_min[1]) - 0.12 * arch * float(bounds_max[1] - bounds_min[1])
        z = float(bounds_min[2]) + 0.42 * float(bounds_max[2] - bounds_min[2]) + 0.08 * arch * float(bounds_max[2] - bounds_min[2])
        points.append(np.array([float(x), y, z], dtype=np.float32))
    if len(points) == 7:
        points[3][0] = center[0]
    return points


def _float_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in values.tolist()]


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
