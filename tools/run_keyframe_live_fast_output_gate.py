from __future__ import annotations

import argparse
import gc
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import cv2
import numpy as np
import torch
import yaml
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.osteo_vision_api.services.live_frame_service import LiveFrameAnalysisService  # noqa: E402
from osteo_vision_core.models.keyframe_segmenter import select_torch_device  # noqa: E402

BROWSER_MAX_LONG_SIDE = 960
BROWSER_JPEG_QUALITY = 85
MIN_TIMED_FRAMES = 5


def prepare_browser_profile_jpeg(
    source_path: str | Path,
    output_path: str | Path,
    *,
    max_long_side: int = BROWSER_MAX_LONG_SIDE,
    jpeg_quality: int = BROWSER_JPEG_QUALITY,
) -> dict[str, Any]:
    source = Path(source_path).resolve()
    destination = Path(output_path).resolve()
    with Image.open(source) as opened:
        rgb = ImageOps.exif_transpose(opened).convert("RGB")
        source_size = rgb.size
        scale = min(1.0, float(max_long_side) / float(max(source_size)))
        output_size = _browser_scaled_size(source_size, scale)
        if output_size != source_size:
            rgb = rgb.resize(output_size, Image.Resampling.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(destination, format="JPEG", quality=int(jpeg_quality), optimize=False)
    return {
        "source_path": str(source),
        "source_sha256": _sha256_file(source),
        "source_width": int(source_size[0]),
        "source_height": int(source_size[1]),
        "prepared_path": str(destination),
        "prepared_sha256": _sha256_file(destination),
        "prepared_size_bytes": destination.stat().st_size,
        "prepared_width": int(output_size[0]),
        "prepared_height": int(output_size[1]),
        "max_long_side": int(max_long_side),
        "jpeg_quality_fraction": float(jpeg_quality / 100.0),
        "jpeg_quality_integer": int(jpeg_quality),
        "encoder": "Pillow JPEG quality=85 browser-canvas profile approximation",
    }


def prepare_browser_profile_video_jpegs(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    start_frame: int,
    frame_count: int,
    max_long_side: int = BROWSER_MAX_LONG_SIDE,
    jpeg_quality: int = BROWSER_JPEG_QUALITY,
) -> dict[str, Any]:
    source = Path(source_path).resolve()
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Video cannot be decoded: {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    capture.set(cv2.CAP_PROP_POS_FRAMES, int(start_frame))
    frames: list[dict[str, Any]] = []
    try:
        for offset in range(frame_count):
            ok, bgr = capture.read()
            if not ok or bgr is None:
                raise ValueError(f"Video ended before frame {start_frame + offset}: {source}")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            source_size = (int(rgb.shape[1]), int(rgb.shape[0]))
            scale = min(1.0, float(max_long_side) / float(max(source_size)))
            output_size = _browser_scaled_size(source_size, scale)
            image = Image.fromarray(rgb)
            if output_size != source_size:
                image = image.resize(output_size, Image.Resampling.LANCZOS)
            frame_path = destination / f"browser_frame_{offset + 1:02d}_source_{start_frame + offset:06d}.jpg"
            image.save(frame_path, format="JPEG", quality=int(jpeg_quality), optimize=False)
            frames.append(
                {
                    "sequence": offset + 1,
                    "source_frame_index": int(start_frame + offset),
                    "source_timestamp_seconds": (round(float((start_frame + offset) / fps), 6) if fps > 0 else None),
                    "path": str(frame_path),
                    "sha256": _sha256_file(frame_path),
                    "size_bytes": frame_path.stat().st_size,
                    "width": int(output_size[0]),
                    "height": int(output_size[1]),
                }
            )
    finally:
        capture.release()
    dimensions = {(item["width"], item["height"]) for item in frames}
    if len(dimensions) != 1:
        raise RuntimeError("Prepared browser-profile video frames have inconsistent dimensions")
    output_width, output_height = next(iter(dimensions))
    return {
        "source_type": "mp4_consecutive_frames",
        "source_path": str(source),
        "source_sha256": _sha256_file(source),
        "source_width": source_width,
        "source_height": source_height,
        "source_fps": fps,
        "source_total_frames": total_frames,
        "start_frame": int(start_frame),
        "prepared_frame_count": len(frames),
        "prepared_frame_hashes_unique": len({item["sha256"] for item in frames}) == len(frames),
        "prepared_width": int(output_width),
        "prepared_height": int(output_height),
        "max_long_side": int(max_long_side),
        "jpeg_quality_fraction": float(jpeg_quality / 100.0),
        "jpeg_quality_integer": int(jpeg_quality),
        "encoder": "Pillow JPEG quality=85 browser-canvas profile approximation",
        "dataset_id": "D046/OFDVDNET_023",
        "scene": "public ex vivo chicken-leg fluorescence surgery proxy video",
        "domain_boundary": "public_ex_vivo_fluorescence_proxy_non_target_domain",
        "frames": frames,
    }


def run_live_fast_output_gate(
    *,
    candidate_config_path: str | Path,
    mainline_config_path: str | Path,
    production_config_path: str | Path,
    source_image_path: str | Path | None,
    source_video_path: str | Path | None = None,
    video_start_frame: int = 319,
    output_dir: str | Path,
    timed_frames: int = 8,
    full_frame_warmup_frames: int = 1,
    max_e2e_p95_ms: float = 1000.0,
    max_model_p95_ms: float = 500.0,
    max_peak_gpu_memory_mb: float = 4096.0,
) -> dict[str, Any]:
    if timed_frames < MIN_TIMED_FRAMES:
        raise ValueError(f"timed_frames must be at least {MIN_TIMED_FRAMES}")
    if full_frame_warmup_frames < 1:
        raise ValueError("full_frame_warmup_frames must be at least 1")
    candidate_config = Path(candidate_config_path).resolve()
    mainline_config = Path(mainline_config_path).resolve()
    production_config = Path(production_config_path).resolve()
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    config_hashes_before = {
        "candidate": _sha256_file(candidate_config),
        "mainline": _sha256_file(mainline_config),
        "production": _sha256_file(production_config),
    }
    frontend_profile = _frontend_capture_profile()
    if source_video_path:
        capture = prepare_browser_profile_video_jpegs(
            source_video_path,
            destination / "input",
            start_frame=video_start_frame,
            frame_count=timed_frames,
        )
        frame_bytes = [Path(item["path"]).read_bytes() for item in capture["frames"]]
    elif source_image_path:
        capture = prepare_browser_profile_jpeg(
            source_image_path,
            destination / "input" / "browser_profile_frame_960.jpg",
        )
        capture["source_type"] = "repeated_still_image"
        capture["prepared_frame_count"] = timed_frames
        capture["prepared_frame_hashes_unique"] = False
        capture["domain_boundary"] = "public_or_synthetic_proxy_non_target_domain"
        capture["frames"] = [
            {
                "sequence": index + 1,
                "source_frame_index": None,
                "source_timestamp_seconds": None,
                "path": capture["prepared_path"],
                "sha256": capture["prepared_sha256"],
                "size_bytes": capture["prepared_size_bytes"],
                "width": capture["prepared_width"],
                "height": capture["prepared_height"],
            }
            for index in range(timed_frames)
        ]
        frame_bytes = [Path(capture["prepared_path"]).read_bytes() for _ in range(timed_frames)]
    else:
        raise ValueError("source_video_path or source_image_path is required")
    capture["frontend_profile"] = frontend_profile
    policy = {
        "minimum_timed_frames": MIN_TIMED_FRAMES,
        "full_frame_warmup_frames": int(full_frame_warmup_frames),
        "maximum_service_e2e_p95_ms": float(max_e2e_p95_ms),
        "maximum_model_p95_ms": float(max_model_p95_ms),
        "maximum_peak_gpu_memory_mb": float(max_peak_gpu_memory_mb),
        "required_output_profile": "live_fast",
        "required_overlay_format": "jpeg",
        "required_accelerator": "cuda",
        "required_amp": True,
    }

    candidate = _run_model_protocol(
        label="current_production_candidate",
        config_path=candidate_config,
        frame_bytes=frame_bytes,
        capture=capture,
        timed_frames=timed_frames,
        full_frame_warmup_frames=full_frame_warmup_frames,
        policy=policy,
    )
    _release_cuda()
    mainline = _run_model_protocol(
        label="previous_mainline_comparator",
        config_path=mainline_config,
        frame_bytes=frame_bytes,
        capture=capture,
        timed_frames=timed_frames,
        full_frame_warmup_frames=full_frame_warmup_frames,
        policy=policy,
    )
    _release_cuda()
    candidate["runtime_role"] = "current_production_model_via_isolated_candidate_config"
    mainline["runtime_role"] = "previous_mainline_comparator_snapshot"

    comparable_fields = _protocol_comparison(candidate, mainline)
    comparison = {
        "strictly_comparable": all(comparable_fields.values()),
        "protocol_field_checks": comparable_fields,
        "candidate_delta_percent": {
            "service_e2e_p50": _percent_delta(
                candidate["latency_ms"]["service_e2e"]["p50"],
                mainline["latency_ms"]["service_e2e"]["p50"],
            ),
            "service_e2e_p95": _percent_delta(
                candidate["latency_ms"]["service_e2e"]["p95"],
                mainline["latency_ms"]["service_e2e"]["p95"],
            ),
            "model_p50": _percent_delta(
                candidate["latency_ms"]["model"]["p50"],
                mainline["latency_ms"]["model"]["p50"],
            ),
            "model_p95": _percent_delta(
                candidate["latency_ms"]["model"]["p95"],
                mainline["latency_ms"]["model"]["p95"],
            ),
            "peak_gpu_memory": _percent_delta(
                candidate["peak_gpu_memory_mb"],
                mainline["peak_gpu_memory_mb"],
            ),
        },
    }
    config_hashes_after = {
        "candidate": _sha256_file(candidate_config),
        "mainline": _sha256_file(mainline_config),
        "production": _sha256_file(production_config),
    }
    production_unchanged = config_hashes_before["production"] == config_hashes_after["production"]
    comparator_unchanged = config_hashes_before["mainline"] == config_hashes_after["mainline"]
    candidate_unchanged = config_hashes_before["candidate"] == config_hashes_after["candidate"]
    production_model_id = _selected_segmentation_model(_load_yaml(production_config))
    checks = {
        "candidate_gate_passed": candidate["gate_passed"],
        "previous_mainline_gate_passed": mainline["gate_passed"],
        "candidate_previous_mainline_protocol_strictly_comparable": comparison["strictly_comparable"],
        "candidate_config_unchanged": candidate_unchanged,
        "previous_mainline_comparator_snapshot_unchanged": comparator_unchanged,
        "current_production_config_unchanged": production_unchanged,
        "current_production_model_matches_candidate": production_model_id == candidate["model_id"],
        "frontend_capture_profile_matches_gate": (
            frontend_profile["max_long_side"] == BROWSER_MAX_LONG_SIDE
            and frontend_profile["jpeg_quality_fraction"] == BROWSER_JPEG_QUALITY / 100.0
        ),
        "competition_runtime_replacement_performed": False,
    }
    checks["pass"] = (
        all(value for key, value in checks.items() if key != "competition_runtime_replacement_performed")
        and checks["competition_runtime_replacement_performed"] is False
    )
    return {
        "schema_version": "osteo-vision-keyframe-live-fast-output-gate-v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "capture_protocol": capture,
        "execution_protocol": {
            "service": "backend.osteo_vision_api.services.live_frame_service.LiveFrameAnalysisService",
            "transport_scope": "direct service call; HTTP, browser scheduling, and network transfer excluded",
            "timed_frames_per_model": int(timed_frames),
            "full_frame_warmup_frames_per_model": int(full_frame_warmup_frames),
            "model_load_and_warmup_excluded_from_timed_samples": True,
            "frame_sequence": "serial; next frame starts after the preceding result completes",
            "input_encoding": "JPEG",
            "input_source_type": capture["source_type"],
            "accelerator_required": "CUDA",
        },
        "environment": {
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
        "gate_policy": policy,
        "candidate": candidate,
        "previous_mainline": mainline,
        "comparison": comparison,
        "config_integrity": {
            "candidate_path": str(candidate_config),
            "candidate_sha256_before": config_hashes_before["candidate"],
            "candidate_sha256_after": config_hashes_after["candidate"],
            "candidate_unchanged": candidate_unchanged,
            "mainline_path": str(mainline_config),
            "mainline_sha256_before": config_hashes_before["mainline"],
            "mainline_sha256_after": config_hashes_after["mainline"],
            "mainline_unchanged": comparator_unchanged,
            "historical_mainline_production_sha256": (
                "3ddcf50a4701d1ce825b7a0cab62217af13c1f14462b23bef8ea1b4a640fc3cd"
            ),
            "production_path": str(production_config),
            "production_sha256_before": config_hashes_before["production"],
            "production_sha256_after": config_hashes_after["production"],
            "production_unchanged": production_unchanged,
            "competition_runtime_selected": production_model_id,
            "automatic_replacement_performed": False,
        },
        "checks": checks,
        "claim_boundary": (
            "This is non-target-domain engineering latency and output-integrity evidence from a browser-profile "
            "JPEG passed directly to the live-frame service. It does not establish clinical performance, target "
            "microscope transport latency, continuous 4K full-frame inference, or operating-room performance."
        ),
    }


def _run_model_protocol(
    *,
    label: str,
    config_path: Path,
    frame_bytes: list[bytes],
    capture: dict[str, Any],
    timed_frames: int,
    full_frame_warmup_frames: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    service = LiveFrameAnalysisService(str(config_path))
    model_id = service.default_model_id
    warmup_started = perf_counter()
    warmup = service.warmup(model_id)
    model_warmup_ms = (perf_counter() - warmup_started) * 1000.0
    adapter = service._adapter(model_id)
    spec = adapter.describe()
    selected_device = select_torch_device(spec.device_policy)
    excluded_warmups: list[dict[str, Any]] = []
    for index in range(full_frame_warmup_frames):
        payload = service.analyze(
            case_id=f"live_fast_gate_{label}_warmup",
            frame_bytes=frame_bytes[0],
            filename=f"browser_frame_warmup_{index + 1:02d}.jpg",
            parameters={"captured_at": datetime.now(UTC).isoformat()},
        )
        excluded_warmups.append(
            {
                "frame_id": payload["frame_id"],
                "service_e2e_ms": payload["inference_latency_ms"],
                "model_ms": _model_inference(payload).get("elapsed_ms"),
                "source_path": payload["source_path"],
                "mask_path": payload["mask_path"],
                "overlay_path": payload["overlay_path"],
            }
        )
    if selected_device.type == "cuda":
        torch.cuda.synchronize(selected_device)

    frame_records: list[dict[str, Any]] = []
    for index in range(timed_frames):
        caller_started = perf_counter()
        payload = service.analyze(
            case_id=f"live_fast_gate_{label}",
            frame_bytes=frame_bytes[index],
            filename=f"browser_frame_{index + 1:02d}.jpg",
            parameters={"captured_at": datetime.now(UTC).isoformat()},
        )
        caller_elapsed_ms = (perf_counter() - caller_started) * 1000.0
        frame_records.append(
            _inspect_frame(
                index=index + 1,
                payload=payload,
                expected_size=(int(capture["prepared_width"]), int(capture["prepared_height"])),
                prepared_sha256=str(capture["frames"][index]["sha256"]),
                caller_elapsed_ms=caller_elapsed_ms,
            )
        )

    service_latencies = [float(item["service_e2e_ms"]) for item in frame_records]
    caller_latencies = [float(item["caller_observed_e2e_ms"]) for item in frame_records]
    model_latencies = [float(item["model_latency_ms"]) for item in frame_records]
    peak_memory_values = [
        float(item["peak_gpu_memory_mb"]) for item in frame_records if item.get("peak_gpu_memory_mb") is not None
    ]
    inference_protocols = [item["inference_protocol"] for item in frame_records]
    first_protocol = dict(inference_protocols[0])
    first_protocol.update(
        {
            "configured_fast_output": bool(spec.extra.get("fast_output", False)),
            "configured_overlay_format": str(spec.extra.get("overlay_format", "png")).lower(),
            "configured_overlay_jpeg_quality": int(spec.extra.get("overlay_jpeg_quality", 85)),
        }
    )
    unique_fields = (
        "frame_id",
        "source_path",
        "mask_path",
        "overlay_path",
        "risk_mask_path",
        "uncertain_mask_path",
    )
    checks = {
        "cuda_available": torch.cuda.is_available(),
        "selected_device_is_cuda": selected_device.type == "cuda",
        "warmup_available": warmup.get("available") is True,
        "warmup_model_matches": str(warmup.get("model_id")) == model_id,
        "minimum_timed_frames_met": len(frame_records) >= int(policy["minimum_timed_frames"]),
        "serial_frames_completed": len(frame_records) == timed_frames,
        "model_id_matches_every_frame": all(item["model_id"] == model_id for item in frame_records),
        "all_evidence_files_exist": all(item["all_evidence_files_exist"] for item in frame_records),
        "source_bytes_preserved": all(item["source_bytes_match_prepared_jpeg"] for item in frame_records),
        "mask_and_overlay_dimensions_match_input": all(
            item["mask_size_matches"] and item["overlay_size_matches"] for item in frame_records
        ),
        "binary_masks": all(item["mask_binary"] for item in frame_records),
        "jpeg_overlays": all(item["overlay_suffix"] in {".jpg", ".jpeg"} for item in frame_records),
        "fast_output_profile": all(
            item["inference_protocol"].get("output_profile") == policy["required_output_profile"]
            for item in frame_records
        ),
        "amp_enabled": all(item["inference_protocol"].get("use_amp") is True for item in frame_records),
        "tta_disabled": all(item["inference_protocol"].get("tta_enabled") is False for item in frame_records),
        "full_evidence_outputs_suppressed": all(
            item["probability_path"] is None and item["pseudo_color_path"] is None for item in frame_records
        ),
        "inference_protocol_stable": all(protocol == inference_protocols[0] for protocol in inference_protocols),
        "unique_evidence_paths": all(
            len({str(item[field]) for item in frame_records}) == len(frame_records) for field in unique_fields
        ),
        "service_e2e_p95_within_gate": _latency_summary(service_latencies)["p95"]
        <= float(policy["maximum_service_e2e_p95_ms"]),
        "model_p95_within_gate": _latency_summary(model_latencies)["p95"] <= float(policy["maximum_model_p95_ms"]),
        "peak_gpu_memory_within_gate": bool(peak_memory_values)
        and max(peak_memory_values) <= float(policy["maximum_peak_gpu_memory_mb"]),
    }
    checks["pass"] = all(checks.values())
    config = _load_yaml(config_path)
    model_mapping = _configured_model_mapping(config, model_id)
    checkpoint_path = _resolve_project_path(model_mapping.get("checkpoint_path"))
    return {
        "label": label,
        "model_id": model_id,
        "model_family": spec.family,
        "config_path": str(config_path),
        "config_sha256": _sha256_file(config_path),
        "checkpoint_path": str(checkpoint_path) if checkpoint_path is not None else None,
        "checkpoint_sha256": _sha256_file(checkpoint_path) if checkpoint_path and checkpoint_path.is_file() else None,
        "selected_device": str(selected_device),
        "precision": spec.precision,
        "threshold": spec.extra.get("threshold"),
        "warmup": {
            "model_load_and_synthetic_forward_ms": round(model_warmup_ms, 3),
            "full_frame_samples_excluded": excluded_warmups,
        },
        "timed_frame_count": len(frame_records),
        "latency_ms": {
            "service_e2e": _latency_summary(service_latencies),
            "caller_observed_e2e": _latency_summary(caller_latencies),
            "model": _latency_summary(model_latencies),
        },
        "peak_gpu_memory_mb": round(max(peak_memory_values), 3) if peak_memory_values else None,
        "protocol": first_protocol,
        "component_count": _value_summary([float(item["component_count"]) for item in frame_records]),
        "positive_area_fraction": _value_summary([float(item["positive_area_fraction"]) for item in frame_records]),
        "checks": checks,
        "gate_passed": checks["pass"],
        "frames": frame_records,
    }


def _inspect_frame(
    *,
    index: int,
    payload: dict[str, Any],
    expected_size: tuple[int, int],
    prepared_sha256: str,
    caller_elapsed_ms: float,
) -> dict[str, Any]:
    paths = {
        "source": _required_path(payload.get("source_path"), "source_path"),
        "mask": _required_path(payload.get("mask_path"), "mask_path"),
        "overlay": _required_path(payload.get("overlay_path"), "overlay_path"),
        "risk_mask": _required_path(payload.get("risk_mask_path"), "risk_mask_path"),
        "uncertain_mask": _required_path(payload.get("uncertain_mask_path"), "uncertain_mask_path"),
    }
    inference = _model_inference(payload)
    with Image.open(paths["mask"]) as mask_image:
        mask_size = mask_image.size
        mask_values = np.unique(np.asarray(mask_image.convert("L"), dtype=np.uint8)).tolist()
    with Image.open(paths["overlay"]) as overlay_image:
        overlay_size = overlay_image.size
    raw_quantification = payload.get("quantification")
    quantification: dict[str, Any] = dict(raw_quantification) if isinstance(raw_quantification, dict) else {}
    service_elapsed = payload.get("inference_latency_ms")
    model_elapsed = inference.get("elapsed_ms")
    if not isinstance(service_elapsed, (int, float)) or not isinstance(model_elapsed, (int, float)):
        raise RuntimeError("Live frame result is missing numeric service or model latency")
    return {
        "sequence": int(index),
        "frame_id": str(payload.get("frame_id")),
        "model_id": str(payload.get("model_id")),
        "service_e2e_ms": float(service_elapsed),
        "caller_observed_e2e_ms": round(float(caller_elapsed_ms), 3),
        "model_latency_ms": float(model_elapsed),
        "peak_gpu_memory_mb": inference.get("peak_gpu_memory_mb"),
        "source_path": str(paths["source"]),
        "source_sha256": _sha256_file(paths["source"]),
        "source_bytes_match_prepared_jpeg": _sha256_file(paths["source"]) == prepared_sha256,
        "mask_path": str(paths["mask"]),
        "mask_sha256": _sha256_file(paths["mask"]),
        "mask_size": list(mask_size),
        "mask_size_matches": mask_size == expected_size,
        "mask_values": mask_values,
        "mask_binary": set(mask_values).issubset({0, 255}),
        "overlay_path": str(paths["overlay"]),
        "overlay_sha256": _sha256_file(paths["overlay"]),
        "overlay_size": list(overlay_size),
        "overlay_size_matches": overlay_size == expected_size,
        "overlay_suffix": paths["overlay"].suffix.lower(),
        "risk_mask_path": str(paths["risk_mask"]),
        "uncertain_mask_path": str(paths["uncertain_mask"]),
        "probability_path": payload.get("probability_path"),
        "pseudo_color_path": payload.get("pseudo_color_path"),
        "all_evidence_files_exist": all(path.is_file() and path.stat().st_size > 0 for path in paths.values()),
        "component_count": int(quantification.get("component_count") or 0),
        "positive_area_fraction": float(quantification.get("positive_area_fraction") or 0.0),
        "inference_protocol": {
            "mode": inference.get("mode"),
            "tile_size": inference.get("tile_size"),
            "tile_overlap": inference.get("tile_overlap"),
            "tile_count": inference.get("tile_count"),
            "tile_batch_size": inference.get("tile_batch_size"),
            "max_whole_pixels": inference.get("max_whole_pixels"),
            "input_width": inference.get("input_width"),
            "input_height": inference.get("input_height"),
            "tta_enabled": inference.get("tta_enabled"),
            "use_amp": inference.get("use_amp"),
            "output_profile": inference.get("output_profile"),
        },
    }


def _protocol_comparison(candidate: dict[str, Any], mainline: dict[str, Any]) -> dict[str, bool]:
    candidate_protocol = candidate["protocol"]
    mainline_protocol = mainline["protocol"]
    fields = (
        "mode",
        "tile_size",
        "tile_overlap",
        "tile_count",
        "tile_batch_size",
        "max_whole_pixels",
        "input_width",
        "input_height",
        "tta_enabled",
        "use_amp",
        "output_profile",
        "configured_fast_output",
        "configured_overlay_format",
        "configured_overlay_jpeg_quality",
    )
    return {
        "timed_frame_count": candidate["timed_frame_count"] == mainline["timed_frame_count"],
        **{field: candidate_protocol.get(field) == mainline_protocol.get(field) for field in fields},
    }


def render_reports(report: dict[str, Any], *, zh_path: str | Path, en_path: str | Path) -> None:
    zh = Path(zh_path).resolve()
    en = Path(en_path).resolve()
    zh.parent.mkdir(parents=True, exist_ok=True)
    en.parent.mkdir(parents=True, exist_ok=True)
    zh.write_text(_render_zh(report), encoding="utf-8")
    en.write_text(_render_en(report), encoding="utf-8")


def _render_zh(report: dict[str, Any]) -> str:
    candidate = report["candidate"]
    mainline = report["previous_mainline"]
    comparison = report["comparison"]
    capture = report["capture_protocol"]
    checks = report["checks"]
    return "\n".join(
        [
            "# Residual Attention 当前生产模型实时单帧 fast-output 运行门控",
            "",
            "## 结论",
            "",
            f"- 综合门控：`{'通过' if checks['pass'] else '未通过'}`。",
            f"- 当前生产模型门控：`{'通过' if candidate['gate_passed'] else '未通过'}`；上一版 ConvNeXt 主线同协议门控：`{'通过' if mainline['gate_passed'] else '未通过'}`。",
            f"- 同协议可比性：`{comparison['strictly_comparable']}`。当前生产配置 SHA256 在运行前后保持一致，本门控未执行模型切换。",
            f"- 当前生产配置 SHA256：`{report['config_integrity']['production_sha256_after']}`；上一版 ConvNeXt 隔离快照 SHA256：`{report['config_integrity']['mainline_sha256_after']}`。",
            "- 本结果仅提供非目标域工程延迟和输出完整性证据，所有分割结果继续要求医生复核。",
            "",
            "## 实测协议",
            "",
            f"- 输入：D046/OFDVDNET_023 公开离体荧光代理 MP4 的连续帧，经浏览器档位生成 JPEG；长边 `{capture['max_long_side']}`，质量 `{capture['jpeg_quality_fraction']}`，实际尺寸 `{capture['prepared_width']}x{capture['prepared_height']}`。",
            f"- 设备：`{report['environment']['cuda_device']}`；CUDA：`{report['environment']['cuda_available']}`。",
            f"- 每个模型先执行模型 warmup 和 `{report['execution_protocol']['full_frame_warmup_frames_per_model']}` 帧完整尺寸 warmup，再串行运行 `{report['execution_protocol']['timed_frames_per_model']}` 帧计时样本。",
            "- 已目视抽查源视频第 319 帧与第 326 帧：画面为白光/荧光多视口离体组织场景，无标题页；用途边界保持为公开离体非目标域荧光代理。",
            "- 端到端范围覆盖 JPEG 解码、唯一原始证据写入、模型推理、mask/risk/uncertain mask 与 JPEG overlay 生成及落盘；HTTP、浏览器调度和网络传输未计入。",
            "",
            "## 结果对比",
            "",
            "| 运行角色 / 模型 | 服务 E2E P50 / P95 ms | 模型 P50 / P95 ms | 峰值显存 MB | mask/overlay | 唯一路径 | 门控 |",
            "|---|---:|---:|---:|---|---|---|",
            _zh_result_row(candidate),
            _zh_result_row(mainline),
            "",
            f"当前生产 Residual Attention 相对上一版 ConvNeXt 主线的服务 E2E P95 变化为 `{_fmt(comparison['candidate_delta_percent']['service_e2e_p95'])}%`，模型 P95 变化为 `{_fmt(comparison['candidate_delta_percent']['model_p95'])}%`。正值表示当前生产模型耗时更高。",
            "",
            "## 输出核验",
            "",
            f"- 当前生产模型 `{candidate['timed_frame_count']}` 帧与上一版主线 `{mainline['timed_frame_count']}` 帧均使用 `live_fast`、CUDA AMP、关闭 TTA 的协议。",
            f"- 实际推理模式：当前生产模型 `{candidate['protocol']['mode']}`，上一版主线 `{mainline['protocol']['mode']}`。",
            "- 每帧源 JPEG、二值 mask、risk mask、uncertain mask 和 JPEG overlay 均有独立路径；mask 与 overlay 尺寸匹配输入。",
            "- fast-output 路径不落盘 probability map、uncertainty map 和伪彩图，保留前端实时显示与复核所需的 mask、风险提示和 overlay。",
            "",
            "## 边界",
            "",
            "输入来自公开或代理非目标域图像，且通过直接服务调用执行。当前证据不覆盖企业显微镜传输、浏览器到 API 的网络开销、4K 连续逐帧推理、真实术中 ICG 颌骨骨髓炎临床性能和手术室长时稳定性。",
            "",
        ]
    )


def _render_en(report: dict[str, Any]) -> str:
    candidate = report["candidate"]
    mainline = report["previous_mainline"]
    comparison = report["comparison"]
    capture = report["capture_protocol"]
    checks = report["checks"]
    return "\n".join(
        [
            "# Residual Attention Current-Production Live Single-Frame Fast-Output Runtime Gate",
            "",
            "## Decision",
            "",
            f"- Combined gate: `{'passed' if checks['pass'] else 'failed'}`.",
            f"- Current production-model gate: `{'passed' if candidate['gate_passed'] else 'failed'}`; same-protocol previous ConvNeXt mainline gate: `{'passed' if mainline['gate_passed'] else 'failed'}`.",
            f"- Strict protocol comparability: `{comparison['strictly_comparable']}`. The current production config SHA256 remained unchanged and this gate performed no model switch.",
            f"- Current production config SHA256: `{report['config_integrity']['production_sha256_after']}`; isolated previous ConvNeXt snapshot SHA256: `{report['config_integrity']['mainline_sha256_after']}`.",
            "- These results provide non-target-domain engineering latency and output-integrity evidence only. Physician review remains required.",
            "",
            "## Measured Protocol",
            "",
            f"- Input: consecutive frames from the public ex vivo fluorescence proxy MP4 D046/OFDVDNET_023, encoded as browser-profile JPEG at `{capture['max_long_side']}` maximum long side and `{capture['jpeg_quality_fraction']}` quality; measured size `{capture['prepared_width']}x{capture['prepared_height']}`.",
            f"- Device: `{report['environment']['cuda_device']}`; CUDA available: `{report['environment']['cuda_available']}`.",
            f"- Each model completed model warmup and `{report['execution_protocol']['full_frame_warmup_frames_per_model']}` excluded full-size frame, followed by `{report['execution_protocol']['timed_frames_per_model']}` serial timed frames.",
            "- Visual checks of source frames 319 and 326 confirmed a multi-viewport white-light/fluorescence ex vivo tissue scene without a title card. Its role remains a public ex vivo non-target-domain fluorescence proxy.",
            "- Service end-to-end timing covers JPEG decode, uniquely addressed source evidence, model inference, mask/risk/uncertain-mask rendering, JPEG overlay generation, and file writes. HTTP, browser scheduling, and network transfer are excluded.",
            "",
            "## Same-Protocol Results",
            "",
            "| Runtime role / model | Service E2E P50 / P95 ms | Model P50 / P95 ms | Peak GPU MB | Mask/overlay | Unique paths | Gate |",
            "|---|---:|---:|---:|---|---|---|",
            _en_result_row(candidate),
            _en_result_row(mainline),
            "",
            f"Current-production Residual Attention service E2E P95 changed by `{_fmt(comparison['candidate_delta_percent']['service_e2e_p95'])}%` relative to the previous ConvNeXt mainline; model P95 changed by `{_fmt(comparison['candidate_delta_percent']['model_p95'])}%`. Positive values indicate higher current-production latency.",
            "",
            "## Output Audit",
            "",
            f"- All `{candidate['timed_frame_count']}` current-production frames and `{mainline['timed_frame_count']}` previous-mainline frames used `live_fast`, CUDA AMP, and disabled TTA.",
            f"- Observed inference modes: current production `{candidate['protocol']['mode']}`; previous mainline `{mainline['protocol']['mode']}`.",
            "- Every frame has uniquely addressed source JPEG, binary mask, risk mask, uncertain mask, and JPEG overlay evidence. Mask and overlay geometry matches the input.",
            "- The fast-output profile omits probability, uncertainty, and pseudocolor files while retaining the renderable mask, risk prompts, and overlay used by live review.",
            "",
            "## Boundary",
            "",
            "The input is a public or proxy non-target-domain image and execution used direct service calls. This evidence excludes enterprise microscope transport, browser-to-API network overhead, continuous full-frame 4K inference, clinical performance on intraoperative ICG jaw osteomyelitis, and operating-room endurance.",
            "",
        ]
    )


def _zh_result_row(run: dict[str, Any]) -> str:
    return (
        f"| `{run['runtime_role']}` / `{run['model_id']}` | {_fmt(run['latency_ms']['service_e2e']['p50'])} / "
        f"{_fmt(run['latency_ms']['service_e2e']['p95'])} | {_fmt(run['latency_ms']['model']['p50'])} / "
        f"{_fmt(run['latency_ms']['model']['p95'])} | {_fmt(run['peak_gpu_memory_mb'])} | "
        f"{'通过' if run['checks']['mask_and_overlay_dimensions_match_input'] else '未通过'} | "
        f"{'通过' if run['checks']['unique_evidence_paths'] else '未通过'} | "
        f"{'通过' if run['gate_passed'] else '未通过'} |"
    )


def _en_result_row(run: dict[str, Any]) -> str:
    return (
        f"| `{run['runtime_role']}` / `{run['model_id']}` | {_fmt(run['latency_ms']['service_e2e']['p50'])} / "
        f"{_fmt(run['latency_ms']['service_e2e']['p95'])} | {_fmt(run['latency_ms']['model']['p50'])} / "
        f"{_fmt(run['latency_ms']['model']['p95'])} | {_fmt(run['peak_gpu_memory_mb'])} | "
        f"{'pass' if run['checks']['mask_and_overlay_dimensions_match_input'] else 'fail'} | "
        f"{'pass' if run['checks']['unique_evidence_paths'] else 'fail'} | "
        f"{'pass' if run['gate_passed'] else 'fail'} |"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the live fast-output gate for a keyframe candidate and mainline.")
    parser.add_argument(
        "--candidate-config",
        default="artifacts/platform_smoke/keyframe_residual_attention_4k_gate_20260715/candidate_strict_runtime.yml",
    )
    parser.add_argument(
        "--mainline-config",
        default=(
            "artifacts/platform_smoke/keyframe_residual_attention_live_fast_gate_20260715_consecutive/"
            "previous_convnext_strict_runtime_snapshot.yml"
        ),
    )
    parser.add_argument("--production-config", default="configs/inference/osteo_vision_competition_strict.yml")
    parser.add_argument(
        "--source-image",
        default=None,
    )
    parser.add_argument(
        "--source-video",
        default=(
            "research/datasets/public-candidates/d046_fluorescence_osteomyelitis_videos/raw/"
            "fluorescence_proxy/ofdvdnet_dryad_v6wwpzh3w/extracted/"
            "OL-2021-07-20-131158-000014-record.mp4"
        ),
    )
    parser.add_argument("--video-start-frame", type=int, default=319)
    parser.add_argument(
        "--output-dir",
        default="artifacts/platform_smoke/keyframe_residual_attention_live_fast_gate_20260715_consecutive",
    )
    parser.add_argument("--timed-frames", type=int, default=8)
    parser.add_argument("--full-frame-warmup-frames", type=int, default=1)
    parser.add_argument("--max-e2e-p95-ms", type=float, default=1000.0)
    parser.add_argument("--max-model-p95-ms", type=float, default=500.0)
    parser.add_argument("--max-peak-gpu-memory-mb", type=float, default=4096.0)
    parser.add_argument(
        "--report-zh",
        default="research/reports/modeling/keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md",
    )
    parser.add_argument(
        "--report-en",
        default="research/reports/modeling/keyframe_residual_attention_live_fast_runtime_gate_20260715_en.md",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_live_fast_output_gate(
        candidate_config_path=args.candidate_config,
        mainline_config_path=args.mainline_config,
        production_config_path=args.production_config,
        source_image_path=args.source_image,
        source_video_path=args.source_video,
        video_start_frame=args.video_start_frame,
        output_dir=args.output_dir,
        timed_frames=args.timed_frames,
        full_frame_warmup_frames=args.full_frame_warmup_frames,
        max_e2e_p95_ms=args.max_e2e_p95_ms,
        max_model_p95_ms=args.max_model_p95_ms,
        max_peak_gpu_memory_mb=args.max_peak_gpu_memory_mb,
    )
    output_path = Path(args.output_dir).resolve() / "live_fast_output_gate.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_reports(report, zh_path=args.report_zh, en_path=args.report_en)
    print(json.dumps({"output": str(output_path), "checks": report["checks"]}, ensure_ascii=False, indent=2))
    return 0 if report["checks"]["pass"] else 1


def _model_inference(payload: dict[str, Any]) -> dict[str, Any]:
    quantification = payload.get("quantification")
    if not isinstance(quantification, dict):
        return {}
    inference = quantification.get("inference")
    return dict(inference) if isinstance(inference, dict) else {}


def _required_path(value: Any, name: str) -> Path:
    if not value:
        raise RuntimeError(f"Live frame result is missing {name}")
    path = Path(str(value)).resolve()
    if not path.is_file():
        raise RuntimeError(f"Live frame result {name} does not exist: {path}")
    return path


def _latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        raise ValueError("Latency values cannot be empty")
    return {
        "samples": len(values),
        "p50": round(_percentile(values, 50.0), 3),
        "p95": round(_percentile(values, 95.0), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(float(sum(values) / len(values)), 3),
        "values": [round(float(value), 3) for value in values],
    }


def _value_summary(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "mean": round(float(sum(values) / len(values)), 6),
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * float(percentile / 100.0)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _percent_delta(value: float, baseline: float) -> float | None:
    if float(baseline) == 0.0:
        return None
    return round((float(value) - float(baseline)) / float(baseline) * 100.0, 3)


def _configured_model_mapping(config: dict[str, Any], model_id: str) -> dict[str, Any]:
    raw_runtime = config.get("runtime")
    runtime: dict[str, Any] = dict(raw_runtime) if isinstance(raw_runtime, dict) else {}
    for item in runtime.get("models") or []:
        if isinstance(item, dict) and str(item.get("model_id")) == model_id:
            return dict(item)
    return {}


def _selected_segmentation_model(config: dict[str, Any]) -> str:
    raw_runtime = config.get("runtime")
    runtime: dict[str, Any] = dict(raw_runtime) if isinstance(raw_runtime, dict) else {}
    raw_tasks = runtime.get("tasks")
    tasks: dict[str, Any] = dict(raw_tasks) if isinstance(raw_tasks, dict) else {}
    raw_segmentation = tasks.get("segmentation")
    segmentation: dict[str, Any] = dict(raw_segmentation) if isinstance(raw_segmentation, dict) else {}
    return str(segmentation.get("model_id") or "")


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def _resolve_project_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_cuda() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


def _browser_scaled_size(source_size: tuple[int, int], scale: float) -> tuple[int, int]:
    return (
        max(1, int(source_size[0] * scale + 0.5)),
        max(1, int(source_size[1] * scale + 0.5)),
    )


def _frontend_capture_profile() -> dict[str, Any]:
    path = ROOT / "frontend" / "src" / "utils" / "browserFrameCapture.ts"
    text = path.read_text(encoding="utf-8")
    quality_match = re.search(r"LIVE_FRAME_JPEG_QUALITY\s*=\s*([0-9.]+)", text)
    long_side_match = re.search(r"LIVE_FRAME_MAX_LONG_SIDE\s*=\s*(\d+)", text)
    if quality_match is None or long_side_match is None:
        raise RuntimeError(f"Cannot read the browser live-frame profile from {path}")
    return {
        "source_path": str(path),
        "source_sha256": _sha256_file(path),
        "jpeg_quality_fraction": float(quality_match.group(1)),
        "max_long_side": int(long_side_match.group(1)),
    }


if __name__ == "__main__":
    raise SystemExit(main())
