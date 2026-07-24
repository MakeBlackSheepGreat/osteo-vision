"""Validate public real-video inputs against the competition 4K JPEG/MP4 workflow.

The run keeps source-domain disclosures attached to every result. It benchmarks
selected-keyframe analysis and does not claim full-frame real-time inference.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from osteo_vision_core.core.config import load_yaml, runtime_config  # noqa: E402
from osteo_vision_core.core.paths import ensure_dir, resolve_path  # noqa: E402
from osteo_vision_core.core.schemas import AdapterRequest  # noqa: E402
from osteo_vision_core.models.adapters import build_adapter, model_spec_from_mapping  # noqa: E402
from osteo_vision_core.models.keyframe_segmenter import load_rgb_image  # noqa: E402
from osteo_vision_core.preprocess.video import extract_keyframes  # noqa: E402

DEFAULT_LIBRARY_MANIFEST = "research/literature/inventory/video_library_manifest_20260704.csv"
DEFAULT_OFD_MANIFEST = "research/literature/inventory/ofdvdnet_video_manifest_20260704.csv"
DEFAULT_CONFIG = "configs/inference/osteo_vision.yml"
OFFICIAL_SIZE = (3840, 2160)


def main() -> int:
    args = parse_args()
    output_dir = ensure_dir(
        resolve_path(args.output_dir)
        if args.output_dir
        else ROOT / "artifacts" / "platform_smoke" / f"public_video_4k_{timestamp()}"
    )
    source_rows = select_public_sources(args.library_manifest, args.ofdvdnet_manifest)
    source_records = [source_record(row) for row in source_rows]
    visual_reviews = [write_contact_sheet(row, output_dir / "visual_review") for row in source_rows]

    decode_samples: list[float] = []
    preprocessing_samples: list[float] = []
    extracted: list[dict[str, Any]] = []
    for row in source_rows:
        video_path = Path(str(row["local_path"]))
        started = time.perf_counter()
        report = extract_keyframes(
            video_path,
            output_dir / "keyframes" / str(row["record_id"]),
            max_frames=args.keyframes,
            sampling_strategy="quality_peak",
        )
        extraction_ms = (time.perf_counter() - started) * 1000.0
        per_frame_decode = extraction_ms / max(1, len(report.get("keyframes") or []))
        decode_samples.extend([per_frame_decode] * max(1, len(report.get("keyframes") or [])))
        extracted.append({"source": row, "report": report, "elapsed_ms": extraction_ms})

    fluor_source = next(item for item in extracted if item["source"]["record_id"].startswith("OFDVDNET_"))
    fluorescence_keyframes = make_fluorescence_keyframes(
        fluor_source["report"], output_dir / "derived" / "fluorescence_keyframes", preprocessing_samples
    )
    official_jpeg = derive_official_4k_jpeg(
        Path(fluorescence_keyframes[0]), output_dir / "derived" / "official_4k_public_proxy.jpg"
    )
    fps_variants = derive_fps_variants(
        Path(str(fluor_source["source"]["local_path"])),
        output_dir / "derived" / "fps_variants",
        frame_limit=args.variant_frames,
    )
    fps_variant_validation = validate_fps_variants(fps_variants, output_dir / "keyframes" / "fps_variants")

    primary_model_id = args.model_id or configured_segmentation_model_id(args.config)
    primary_mapping = configured_model_mapping(args.config, primary_model_id)
    primary_mapping["extra"] = {
        **dict(primary_mapping.get("extra") or {}),
        "output_dir": str(output_dir / "model_outputs"),
    }
    adapter = build_adapter(model_spec_from_mapping(primary_mapping))
    adapter_status = adapter.warmup().to_dict()
    inference_runs = benchmark_images(
        adapter,
        [Path(path) for path in fluorescence_keyframes],
        runs=args.native_runs,
        case_prefix="public_native",
        preprocessing_samples=preprocessing_samples,
    )

    tiled_mapping = dict(primary_mapping)
    tiled_mapping["extra"] = {
        **dict(primary_mapping["extra"]),
        "output_dir": str(output_dir / "tiled_outputs"),
        "force_tiled": True,
        "tile_size": args.tile_size,
        "tile_overlap": args.tile_overlap,
        "max_whole_pixels": 1,
    }
    tiled_adapter = build_adapter(model_spec_from_mapping(tiled_mapping))
    tiled_status = tiled_adapter.warmup().to_dict()
    tiled_runs = benchmark_images(
        tiled_adapter,
        [official_jpeg],
        runs=args.tiled_runs,
        case_prefix="public_4k_tiled",
        preprocessing_samples=preprocessing_samples,
    )

    memory_observation = sustained_memory_observation(
        adapter,
        Path(fluorescence_keyframes[-1]),
        iterations=args.memory_iterations,
    )
    abnormal = unreadable_source_check(args.ofdvdnet_manifest)
    fallback = fallback_check(primary_mapping, Path(fluorescence_keyframes[0]), output_dir / "fallback")
    all_runs = inference_runs + tiled_runs
    inference_ms = [float(item["inference_ms"]) for item in all_runs]
    end_to_end_ms = [float(item["end_to_end_ms"]) for item in all_runs]
    postprocess_estimates = [float(item["postprocess_estimate_ms"]) for item in all_runs]
    derived_manifest = write_derived_manifest(
        output_dir,
        source_records=source_records,
        official_jpeg=official_jpeg,
        fps_variants=fps_variants,
    )

    checks = {
        "public_sources_have_manifest_trace": all(item.get("source_page_original_link") for item in source_records),
        "visual_review_written": all(Path(item["contact_sheet_path"]).exists() for item in visual_reviews),
        "long_mp4_covered": any(float(item.get("duration_sec") or 0.0) >= 60.0 for item in source_records),
        "different_fps_covered": len({round(float(item.get("fps") or 0.0), 2) for item in source_records}) >= 2,
        "derived_fps_variants_decoded": all(item.get("keyframes_extracted", 0) >= 1 for item in fps_variant_validation),
        "official_4k_jpeg_covered": image_size(official_jpeg) == OFFICIAL_SIZE,
        "forced_tiling_covered": all(item.get("inference_mode") == "tiled" for item in tiled_runs),
        "unreadable_encoding_failure_recorded": abnormal.get("decode_opened") is False,
        "fallback_succeeded": fallback.get("fallback_available") is True,
        "memory_observation_completed": memory_observation.get("completed_iterations") == args.memory_iterations,
        "keyframe_analysis_disclosed": True,
        "target_domain_claim_blocked": True,
    }
    checks["pass"] = all(checks.values())
    summary = {
        "schema_version": "osteo-vision-public-video-4k-validation-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "official_device_boundary": {
            "resolution": [3840, 2160],
            "image_format": "JPEG",
            "video_format": "MP4",
            "analysis_mode": "keyframe-based playback analysis",
            "full_frame_4k_30fps_claim_allowed": False,
        },
        "source_records": source_records,
        "visual_reviews": visual_reviews,
        "derived_manifest_path": str(derived_manifest),
        "fps_variants": fps_variants,
        "fps_variant_validation": fps_variant_validation,
        "abnormal_encoding": abnormal,
        "fallback": fallback,
        "adapter_status": adapter_status,
        "tiled_adapter_status": tiled_status,
        "performance": {
            "decode_keyframe_ms": latency_summary(decode_samples),
            "preprocess_image_load_ms": latency_summary(preprocessing_samples),
            "model_inference_ms": latency_summary(inference_ms),
            "postprocess_estimate_ms": latency_summary(postprocess_estimates),
            "end_to_end_adapter_ms": latency_summary(end_to_end_ms),
            "measurement_note": (
                "Model inference is emitted by the adapter around probability inference. Preprocess is isolated RGB "
                "loading. Postprocess is the non-negative remainder of adapter end-to-end minus model inference and "
                "isolated image load, so it is an engineering estimate."
            ),
        },
        "native_runs": inference_runs,
        "forced_4k_tiled_runs": tiled_runs,
        "memory_observation": memory_observation,
        "checks": checks,
        "evidence_boundary": {
            "fluorescence_source": (
                "OFDVDnet Dryad mock chicken-thigh fluorescence-guided surgery proxy; ex vivo and outside the target domain."
            ),
            "osteomyelitis_source": (
                "PMC tibial osteomyelitis endoscopic debridement; clinical surgical video without fluorescence and "
                "outside jaw osteomyelitis."
            ),
            "medical_claim": (
                "Engineering input, decoding, tiling, fallback, and latency evidence only; physician review remains required."
            ),
        },
    }
    summary_path = output_dir / "public_video_4k_validation_summary.json"
    report_path = output_dir / "public_video_4k_validation_report.md"
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if checks["pass"] else 1


def select_public_sources(library_manifest: str | Path, ofd_manifest: str | Path) -> list[dict[str, Any]]:
    library_rows = read_csv(library_manifest)
    ofd_rows = read_csv(ofd_manifest)
    tibial = next(row for row in library_rows if row.get("record_id") == "PMC12350196_MMC1")
    ofd_archive = next(row for row in library_rows if row.get("record_id") == "DRYAD_OFDVDNET_DATA")
    readable_ofd = [
        row
        for row in ofd_rows
        if str(row.get("readable", "")).lower() == "true" and Path(str(row.get("video_path", ""))).exists()
    ]
    if not readable_ofd:
        raise RuntimeError("No readable OFDVDnet source video is available.")
    ofd = max(readable_ofd, key=lambda row: float(row.get("duration_sec") or 0.0))
    return [
        {
            **ofd,
            "record_id": str(ofd["record_id"]),
            "local_path": str(ofd["video_path"]),
            "fluorescence": "yes",
            "medical_scene": "mock chicken-thigh fluorescence-guided surgery",
            "source_kind": "public_ex_vivo_fluorescence_proxy",
            "direct_download_link": ofd_archive.get("direct_download_link"),
            "source_archive_path": ofd_archive.get("local_path"),
        },
        {**tibial, "source_kind": "public_clinical_nonfluorescence_osteomyelitis_video"},
    ]


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_record(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row["local_path"]))
    probe = probe_video(path)
    return {
        "record_id": row.get("record_id"),
        "title": row.get("title") or row.get("original_filename"),
        "source_kind": row.get("source_kind"),
        "source_page_original_link": row.get("source_page_original_link"),
        "direct_download_link": row.get("direct_download_link"),
        "local_path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "fluorescence": row.get("fluorescence"),
        "medical_scene": row.get("medical_scene"),
        "width": probe["width"],
        "height": probe["height"],
        "fps": probe["fps"],
        "frame_count": probe["frame_count"],
        "duration_sec": probe["duration_sec"],
        "codec_fourcc": probe["codec_fourcc"],
        "domain_boundary": row.get("domain_boundary") or row.get("notes"),
    }


def probe_video(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    opened = capture.isOpened()
    fourcc = int(capture.get(cv2.CAP_PROP_FOURCC)) if opened else 0
    fps = float(capture.get(cv2.CAP_PROP_FPS)) if opened else 0.0
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) if opened else 0
    payload = {
        "opened": opened,
        "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) if opened else 0,
        "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) if opened else 0,
        "fps": fps,
        "frame_count": frames,
        "duration_sec": float(frames / fps) if fps > 0 else None,
        "codec_fourcc": "".join(chr((fourcc >> (8 * index)) & 255) for index in range(4)).rstrip("\x00"),
    }
    capture.release()
    return payload


def write_contact_sheet(row: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    target_dir.mkdir(parents=True, exist_ok=True)
    source = Path(str(row["local_path"]))
    probe = probe_video(source)
    capture = cv2.VideoCapture(str(source))
    indexes = np.linspace(0, max(0, int(probe["frame_count"]) - 1), 9).astype(int).tolist()
    thumbs: list[np.ndarray] = []
    for index in indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        scale = 320 / frame.shape[1]
        thumb = cv2.resize(frame, (320, max(2, int(frame.shape[0] * scale))), interpolation=cv2.INTER_AREA)
        cv2.putText(thumb, str(index), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
        thumbs.append(thumb)
    capture.release()
    if not thumbs:
        raise RuntimeError(f"Could not sample contact sheet frames from {source}")
    cell_height = max(frame.shape[0] for frame in thumbs)
    canvas = np.zeros((cell_height * 3, 320 * 3, 3), dtype=np.uint8)
    for index, frame in enumerate(thumbs):
        y = (index // 3) * cell_height
        x = (index % 3) * 320
        canvas[y : y + frame.shape[0], x : x + frame.shape[1]] = frame
    output = target_dir / f"{row['record_id']}_contact_sheet.jpg"
    cv2.imwrite(str(output), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    assessment = (
        "Visible fluorescence-guided ex vivo operative field with reference, fluorescence, and overlay quadrants."
        if str(row.get("fluorescence")).lower() == "yes"
        else "Visible endoscopic tibial debridement and sclerotic-bone resection; title/teaching frames also occur."
    )
    return {
        "record_id": row["record_id"],
        "contact_sheet_path": str(output),
        "sampled_indexes": indexes,
        "assessment": assessment,
    }


def make_fluorescence_keyframes(
    report: dict[str, Any], target_dir: Path, preprocessing_samples: list[float]
) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for frame in report.get("keyframes") or []:
        started = time.perf_counter()
        image: Any = cv2.imread(str(frame["evidence_path"]), cv2.IMREAD_COLOR)
        if image is None:
            continue
        height, width = image.shape[:2]
        crop = image[0 : height // 2, width // 2 : width]
        output = target_dir / f"fluorescence_{int(frame['frame_index']):06d}.jpg"
        cv2.imwrite(str(output), crop, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        preprocessing_samples.append((time.perf_counter() - started) * 1000.0)
        outputs.append(str(output))
    if not outputs:
        raise RuntimeError("No fluorescence quadrant keyframes were derived.")
    return outputs


def derive_official_4k_jpeg(source: Path, output: Path) -> Path:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Could not read keyframe {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    derived = cv2.resize(image, OFFICIAL_SIZE, interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(output), derived, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return output


def derive_fps_variants(source: Path, target_dir: Path, *, frame_limit: int) -> list[dict[str, Any]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    frames: list[np.ndarray] = []
    while len(frames) < max(1, frame_limit):
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        frames.append(frame)
    capture.release()
    if not frames:
        raise RuntimeError(f"Could not decode source video for FPS variants: {source}")
    outputs: list[dict[str, Any]] = []
    for fps in (6.0, 29.97):
        output = target_dir / f"public_proxy_{str(fps).replace('.', '_')}fps.mp4"
        height, width = frames[0].shape[:2]
        fourcc = getattr(cv2, "VideoWriter_fourcc")(*"mp4v")
        writer = cv2.VideoWriter(str(output), fourcc, fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError(f"Could not open MP4 writer for {output}")
        for frame in frames:
            writer.write(frame)
        writer.release()
        probe = probe_video(output)
        outputs.append(
            {
                "path": str(output),
                "sha256": sha256_file(output),
                "derived_from": str(source),
                "source_fps": source_fps,
                "target_fps": fps,
                "frame_count": len(frames),
                "probe": probe,
                "derivation": "OpenCV MP4V transcode from the first decoded public-source frames",
            }
        )
    return outputs


def validate_fps_variants(variants: list[dict[str, Any]], target_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for variant in variants:
        started = time.perf_counter()
        report = extract_keyframes(
            variant["path"],
            target_dir / Path(str(variant["path"])).stem,
            max_frames=2,
            sampling_strategy="uniform",
        )
        results.append(
            {
                "path": variant["path"],
                "target_fps": variant["target_fps"],
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "keyframes_extracted": len(report.get("keyframes") or []),
                "keyframe_manifest_path": report.get("keyframe_manifest_path"),
            }
        )
    return results


def benchmark_images(
    adapter: Any,
    images: list[Path],
    *,
    runs: int,
    case_prefix: str,
    preprocessing_samples: list[float],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for index in range(max(1, runs)):
        image = images[index % len(images)]
        load_started = time.perf_counter()
        loaded = load_rgb_image(image)
        load_ms = (time.perf_counter() - load_started) * 1000.0
        preprocessing_samples.append(load_ms)
        started = time.perf_counter()
        result = adapter.predict(
            AdapterRequest(
                case_id=f"{case_prefix}_{index + 1:02d}",
                input_path=str(image),
                input_type="2d_image",
                task_type="segmentation",
                modality="surgical_keyframe",
                metadata={"roi_hints": []},
            )
        ).to_dict()
        end_to_end_ms = (time.perf_counter() - started) * 1000.0
        quantification = dict_field(result, "quantification")
        inference_value = quantification.get("inference")
        inference: dict[str, Any] = inference_value if isinstance(inference_value, dict) else {}
        segmentation_mask = dict_field(result, "segmentation_mask")
        inference_ms = float(inference.get("elapsed_ms") or 0.0)
        outputs.append(
            {
                "case_id": f"{case_prefix}_{index + 1:02d}",
                "input_path": str(image),
                "input_size": [int(loaded.shape[1]), int(loaded.shape[0])],
                "preprocess_image_load_ms": round(load_ms, 3),
                "inference_ms": round(inference_ms, 3),
                "postprocess_estimate_ms": round(max(0.0, end_to_end_ms - inference_ms - load_ms), 3),
                "end_to_end_ms": round(end_to_end_ms, 3),
                "inference_mode": inference.get("mode"),
                "tile_count": inference.get("tile_count"),
                "peak_gpu_memory_mb": inference.get("peak_gpu_memory_mb"),
                "mask_path": segmentation_mask.get("path"),
                "target_domain_flag": segmentation_mask.get("target_domain_flag"),
            }
        )
    return outputs


def sustained_memory_observation(adapter: Any, image: Path, *, iterations: int) -> dict[str, Any]:
    import psutil

    process = psutil.Process()
    samples: list[dict[str, Any]] = []
    for index in range(max(1, iterations)):
        started = time.perf_counter()
        result = adapter.predict(
            AdapterRequest(
                case_id=f"memory_observation_{index + 1:02d}",
                input_path=str(image),
                input_type="2d_image",
                task_type="segmentation",
                modality="surgical_keyframe",
                metadata={"roi_hints": []},
            )
        ).to_dict()
        samples.append(
            {
                "iteration": index + 1,
                "rss_mb": round(process.memory_info().rss / (1024**2), 3),
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "available": bool(dict_field(result, "prediction").get("segmentation_available")),
            }
        )
    rss = [float(item["rss_mb"]) for item in samples]
    return {
        "completed_iterations": len(samples),
        "samples": samples,
        "rss_first_mb": rss[0],
        "rss_last_mb": rss[-1],
        "rss_peak_mb": max(rss),
        "rss_growth_mb": round(rss[-1] - rss[0], 3),
        "interpretation": "Short sustained keyframe loop; retained CUDA allocator memory may remain after warmup.",
    }


def unreadable_source_check(ofd_manifest: str | Path) -> dict[str, Any]:
    unreadable = next(row for row in read_csv(ofd_manifest) if str(row.get("readable", "")).lower() == "false")
    path = Path(str(unreadable["video_path"]))
    probe = probe_video(path)
    return {
        "record_id": unreadable.get("record_id"),
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "sha256": sha256_file(path) if path.exists() else None,
        "manifest_probe_error": unreadable.get("probe_error"),
        "decode_opened": probe["opened"],
        "failure_policy": "Reject unreadable container and retain the failure record; select another traced source for analysis.",
    }


def fallback_check(primary_mapping: dict[str, Any], image: Path, output_dir: Path) -> dict[str, Any]:
    broken = dict(primary_mapping)
    broken["model_id"] = "validation_missing_checkpoint_primary"
    broken["checkpoint_path"] = str(output_dir / "missing.pt")
    primary = build_adapter(model_spec_from_mapping(broken))
    primary_status = primary.warmup().to_dict()
    fallback_mapping = configured_model_mapping(DEFAULT_CONFIG, "fluorescence_hotspot_2d_segmenter")
    fallback_mapping["extra"] = {**dict(fallback_mapping.get("extra") or {}), "output_dir": str(output_dir)}
    fallback = build_adapter(model_spec_from_mapping(fallback_mapping))
    fallback_status = fallback.warmup().to_dict()
    result = fallback.predict(
        AdapterRequest(
            case_id="public_video_fallback",
            input_path=str(image),
            input_type="2d_image",
            task_type="segmentation",
            modality="surgical_keyframe",
            metadata={"roi_hints": []},
        )
    ).to_dict()
    mask = dict_field(result, "segmentation_mask")
    return {
        "primary_available": primary_status.get("available"),
        "primary_reasons": primary_status.get("reasons"),
        "fallback_model_id": fallback_mapping["model_id"],
        "fallback_available": bool(
            fallback_status.get("available") and mask.get("path") and Path(str(mask["path"])).exists()
        ),
        "fallback_mask_path": mask.get("path"),
        "policy": "Traditional fluorescence hotspot segmentation remains available when the trainable checkpoint cannot warm up.",
    }


def configured_model_mapping(config_path: str | Path, model_id: str) -> dict[str, Any]:
    runtime = runtime_config(load_yaml(config_path))
    for item in runtime.get("models") or []:
        if str(item.get("model_id")) == model_id:
            return dict(item)
    raise ValueError(f"Model {model_id} is absent from {config_path}")


def dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def latency_summary(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if np.isfinite(float(value))]
    if not clean:
        return {"count": 0, "p50": None, "p95": None, "min": None, "max": None}
    return {
        "count": len(clean),
        "p50": round(float(statistics.median(clean)), 3),
        "p95": round(float(np.percentile(clean, 95)), 3),
        "min": round(min(clean), 3),
        "max": round(max(clean), 3),
    }


def write_derived_manifest(
    output_dir: Path,
    *,
    source_records: list[dict[str, Any]],
    official_jpeg: Path,
    fps_variants: list[dict[str, Any]],
) -> Path:
    payload = {
        "schema_version": "osteo-vision-public-video-derived-assets-v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_records": source_records,
        "derived_assets": [
            {
                "path": str(official_jpeg),
                "sha256": sha256_file(official_jpeg),
                "format": "JPEG",
                "resolution": list(image_size(official_jpeg)),
                "derived_from": source_records[0]["local_path"],
                "derivation": "Fluorescence quadrant keyframe resized to the official 3840x2160 input profile.",
            },
            *fps_variants,
        ],
        "boundary": "All derived assets retain their public non-target-domain source status.",
    }
    path = output_dir / "public_video_derived_assets_manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def render_report(summary: dict[str, Any]) -> str:
    perf = summary["performance"]
    sources = "\n".join(
        f"| {item['record_id']} | {item['medical_scene']} | {item['fluorescence']} | "
        f"{item['width']}x{item['height']} | {item['fps']:.2f} | {item['duration_sec']:.2f} | "
        f"[{item['source_page_original_link']}]({item['source_page_original_link']}) |"
        for item in summary["source_records"]
    )
    timing_rows = "\n".join(
        f"| {name} | {value['count']} | {value['p50']} | {value['p95']} | {value['min']} | {value['max']} |"
        for name, value in perf.items()
        if isinstance(value, dict) and "count" in value
    )
    checks = "\n".join(f"- {key}: `{value}`" for key, value in summary["checks"].items())
    return f"""# 公开真实视频与官方 4K 输入工程验证

## 结论

- 总体验证通过：`{summary['checks']['pass']}`
- 分析模式：`keyframe-based playback analysis`
- 4K 全帧 30 FPS AI 声明：`禁止`
- 本报告覆盖输入、解码、关键帧、强制 tiling、回退、短时持续内存和延迟证据。

## 数据来源

| 记录 | 场景 | 荧光 | 分辨率 | FPS | 时长秒 | 来源 |
|---|---|---|---:|---:|---:|---|
{sources}

OFDVDnet 数据展示离体鸡腿荧光引导手术代理画面，包含参考、荧光和叠加视图。PMC 视频展示胫骨骨髓炎内镜清创和硬化骨切除，同时包含标题及教学帧。两类数据均处于非目标域，不能支撑真实术中 ICG 颌骨骨髓炎临床性能结论。

## 性能

| 阶段 | 样本数 | P50 ms | P95 ms | 最小 ms | 最大 ms |
|---|---:|---:|---:|---:|---:|
{timing_rows}

测量说明：{perf['measurement_note']}

## 覆盖项

{checks}

## 异常与回退

- 不可读公开 MP4：`{summary['abnormal_encoding']['record_id']}`，OpenCV 打开结果 `{summary['abnormal_encoding']['decode_opened']}`。失败记录保留在 summary，分析选择有来源记录的可读样本继续执行。
- 缺失 checkpoint 主模型可用性：`{summary['fallback']['primary_available']}`。
- 传统荧光热点回退可用性：`{summary['fallback']['fallback_available']}`，输出 `{summary['fallback']['fallback_mask_path']}`。

## 持续内存观察

- 迭代：`{summary['memory_observation']['completed_iterations']}`
- RSS 起始/结束/峰值 MB：`{summary['memory_observation']['rss_first_mb']}` / `{summary['memory_observation']['rss_last_mb']}` / `{summary['memory_observation']['rss_peak_mb']}`
- RSS 增长 MB：`{summary['memory_observation']['rss_growth_mb']}`

## 证据边界

本结果用于公开异域视频的工程验证。输出涵盖荧光或灌注信号候选区、风险提示、不确定性和医生复核辅助。所有派生 4K JPEG 与转码 MP4 继续继承原始数据的非目标域属性。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-manifest", default=DEFAULT_LIBRARY_MANIFEST)
    parser.add_argument("--ofdvdnet-manifest", default=DEFAULT_OFD_MANIFEST)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--model-id", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--keyframes", type=int, default=3)
    parser.add_argument("--variant-frames", type=int, default=48)
    parser.add_argument("--native-runs", type=int, default=5)
    parser.add_argument("--tiled-runs", type=int, default=3)
    parser.add_argument("--memory-iterations", type=int, default=8)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--tile-overlap", type=int, default=64)
    return parser.parse_args()


def configured_segmentation_model_id(config_path: str | Path) -> str:
    runtime = runtime_config(load_yaml(config_path))
    tasks = runtime.get("tasks")
    segmentation = tasks.get("segmentation") if isinstance(tasks, dict) else None
    model_id = segmentation.get("model_id") if isinstance(segmentation, dict) else None
    selected = str(model_id or "").strip()
    if not selected:
        raise ValueError(f"No segmentation task model_id is configured in {config_path}")
    return selected


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
