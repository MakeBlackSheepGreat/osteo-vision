"""Run the platform demo alignment check end to end.

This script intentionally uses the real FastAPI routes through TestClient. It
creates proxy official-device 4K JPEG/MP4 inputs, runs fusion and keyframe
analysis, records an engineering-review event, exports the evidence bundle, and
writes a compact auditable summary. It is an internal engineering check aligned
to the official technical document, not an official platform acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import cv2
import numpy as np
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OFFICIAL_WIDTH = 3840
OFFICIAL_HEIGHT = 2160
DISCLAIMER_TEXT = "Platform software for research and engineering validation; not a clinical diagnosis and physician review is required."
T = TypeVar("T")


def run_demo_check(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else ROOT / "artifacts" / "platform_smoke" / f"platform_demo_check_{timestamp()}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = bind_runtime_environment(args.config, output_dir)

    timings: list[dict[str, Any]] = []
    input_dir = output_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    from backend.osteo_vision_api.api.app import create_app
    from osteo_vision_core.engine.inference import MedicalImagingInferenceService

    client = TestClient(create_app())
    ready_payload = checked_json(client.get("/ready"))
    service = MedicalImagingInferenceService.from_config(config_path)
    model_inventory = service.model_inventory()
    runtime = service.runtime
    runtime_readiness = dict(ready_payload.get("runtime_readiness") or {})
    active_config_path = str(ready_payload.get("inference_config") or "")
    runtime_config_bound = paths_match(active_config_path, config_path)

    white_path = timed(
        "generate_white_light_jpeg",
        lambda: create_proxy_jpeg(
            input_dir / "platform_white_4k.jpg", channel="white", width=args.width, height=args.height
        ),
        timings,
    )
    fluor_path = timed(
        "generate_icg_jpeg",
        lambda: create_proxy_jpeg(
            input_dir / "platform_icg_4k.jpg",
            channel="fluorescence",
            width=args.width,
            height=args.height,
        ),
        timings,
    )
    video_path = timed(
        "generate_mp4",
        lambda: create_proxy_video(
            input_dir / "platform_4k_proxy.mp4",
            width=args.width,
            height=args.height,
            frames=args.frames,
            fps=args.fps,
        ),
        timings,
    )

    case = timed(
        "create_case",
        lambda: checked_json(
            client.post(
                "/cases",
                json={
                    "title": "platform demo alignment check",
                    "metadata": {
                        "purpose": "platform_flow_demo_check",
                        "input_domain": "synthetic_proxy_not_real_patient_data",
                    },
                },
            )
        ),
        timings,
    )
    case_id = str(case["case_id"])

    white_upload = timed(
        "upload_white_light_jpeg",
        lambda: upload_file(client, white_path, "image/jpeg"),
        timings,
    )
    fluor_upload = timed(
        "upload_icg_jpeg",
        lambda: upload_file(client, fluor_path, "image/jpeg"),
        timings,
    )
    video_upload = timed(
        "upload_mp4",
        lambda: upload_file(client, video_path, "video/mp4"),
        timings,
    )
    upload_job = (
        timed(
            "read_upload_keyframe_job",
            lambda: checked_json(client.get(f"/uploads/jobs/{video_upload['keyframe_job_id']}")),
            timings,
        )
        if video_upload.get("keyframe_job_id")
        else {}
    )

    timed(
        "attach_jpeg_inputs",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/inputs",
                json=[
                    {"channel": "white_light", "path": white_upload["path"], "mime_type": "image/jpeg"},
                    {"channel": "fluorescence", "path": fluor_upload["path"], "mime_type": "image/jpeg"},
                ],
            )
        ),
        timings,
    )
    fusion_case = timed(
        "run_jpeg_fusion",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/analysis-runs",
                json={
                    "selected_input_ids": [],
                    "parameters": {"threshold": args.threshold, "alpha": 0.45, "colormap": "green"},
                    "roi_hints": [],
                },
            )
        ),
        timings,
    )

    timed(
        "attach_mp4_input",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/inputs",
                json=[{"channel": "video", "path": video_upload["path"], "mime_type": "video/mp4"}],
            )
        ),
        timings,
    )
    analysis_job_start = timed(
        "run_mp4_keyframe_analysis",
        lambda: checked_json(
            client.post(
                f"/cases/{case_id}/analysis-jobs",
                json={
                    "selected_input_ids": [],
                    "parameters": {
                        "mode": "video_file",
                        "keyframe_count": args.keyframes,
                        "keyframe_timestamps_sec": requested_timestamps(args.keyframes, args.fps, args.frames),
                        "hotspot_threshold": args.threshold,
                        "segmentation_model_id": configured_segmentation_model_id(runtime),
                    },
                    "roi_hints": [],
                },
            )
        ),
        timings,
    )
    analysis_job = timed(
        "read_mp4_analysis_job",
        lambda: checked_json(client.get(f"/analysis-jobs/{analysis_job_start['job_id']}")),
        timings,
    )
    analyzed_case = timed("load_analyzed_case", lambda: checked_json(client.get(f"/cases/{case_id}")), timings)

    review_result = timed(
        "record_engineering_review",
        lambda: review_first_candidate(client, analyzed_case),
        timings,
    )
    reviewed_case = timed("load_reviewed_case", lambda: checked_json(client.get(f"/cases/{case_id}")), timings)
    export_payload = timed(
        "export_evidence_bundle",
        lambda: checked_json(
            client.post(f"/cases/{case_id}/exports", json={"export_format": "bundle", "selected_artifacts": []})
        ),
        timings,
    )

    fusion_run = latest_run(fusion_case, mode="image_fusion")
    video_run = latest_run(reviewed_case, mode="video_file_keyframes")
    video_model_execution = video_segmentation_execution(video_run)
    required_formats = {
        "report_json",
        "report_md",
        "dicom_secondary_capture",
        "quantification_csv",
        "bundle_manifest",
        "evidence_bundle",
        "overlay",
        "heatmap",
        "probability_map",
        "roi_mask",
        "keyframe",
        "video_overlay",
        "video_mask",
        "video_segmentation_manifest",
    }
    formats = set((export_payload.get("summary") or {}).get("formats") or [])
    available_models = available_model_ids(model_inventory)
    required_models = required_runtime_model_ids(runtime)
    missing_required_models = required_models - available_models
    configured_segmentation_model = configured_segmentation_model_id(runtime)
    video_model_ids = set(video_model_execution["model_ids"])
    video_analysis_methods = set(video_model_execution["analysis_methods"])
    keyframe_mainline_exercised = bool(
        configured_segmentation_model
        and configured_segmentation_model in video_model_ids
        and video_analysis_methods == {"trainable_keyframe_segmenter"}
    )
    strict_runtime_active = bool(
        runtime_readiness.get("runtime_profile") == "strict_runtime"
        and runtime_readiness.get("strict_startup") is True
    )
    demo_check = {
        "runtime_config_bound": runtime_config_bound,
        "runtime_readiness_passed": runtime_readiness.get("passed") is True,
        "strict_runtime_active": strict_runtime_active,
        "jpeg_fusion_completed": (fusion_run or {}).get("status") == "completed",
        "mp4_analysis_completed": (video_run or {}).get("status") == "completed",
        "review_workflow_recorded": bool(
            review_result.get("review_event_count", 0) >= 1
            and review_result.get("roi_count", 0) >= 1
            and any(
                event.get("role") == "engineering_reviewer"
                for event in review_result.get("review_events") or []
                if isinstance(event, dict)
            )
        ),
        "bundle_exists": Path(str(export_payload.get("bundle_path", ""))).exists(),
        "required_formats_present": sorted(required_formats & formats),
        "missing_required_formats": sorted(required_formats - formats),
        "mainline_models_available": bool(required_models) and not missing_required_models,
        "keyframe_mainline_model_exercised": keyframe_mainline_exercised,
        "keyframe_fallback_used": "heuristic_hotspot_fallback" in video_analysis_methods,
        "video_frame_evidence_valid": video_model_execution.get("frame_evidence_valid") is True,
        "clinical_claim_allowed": False,
        "non_target_domain_disclosed": True,
        "not_official_platform_acceptance": True,
    }
    demo_check["pass"] = (
        demo_check["runtime_config_bound"]
        and demo_check["runtime_readiness_passed"]
        and demo_check["strict_runtime_active"]
        and demo_check["jpeg_fusion_completed"]
        and demo_check["mp4_analysis_completed"]
        and demo_check["review_workflow_recorded"]
        and demo_check["bundle_exists"]
        and not demo_check["missing_required_formats"]
        and demo_check["mainline_models_available"]
        and demo_check["keyframe_mainline_model_exercised"]
        and not demo_check["keyframe_fallback_used"]
        and demo_check["video_frame_evidence_valid"]
        and demo_check["non_target_domain_disclosed"]
    )

    summary = {
        "schema_version": "osteo-vision-platform-flow-demo-check-v2",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "case_id": case_id,
        "output_dir": str(output_dir),
        "config_path": str(config_path),
        "runtime": {
            "requested_config_path": str(config_path),
            "active_config_path": active_config_path,
            "config_bound": runtime_config_bound,
            "runtime_profile": runtime_readiness.get("runtime_profile"),
            "strict_startup": runtime_readiness.get("strict_startup"),
            "readiness_passed": runtime_readiness.get("passed"),
            "config_sha256": runtime_readiness.get("config_sha256"),
            "errors": runtime_readiness.get("errors") or [],
            "warnings": runtime_readiness.get("warnings") or [],
        },
        "official_input_boundary": {
            "source": "official technical document",
            "image_resolution": [OFFICIAL_WIDTH, OFFICIAL_HEIGHT],
            "image_format": "JPEG",
            "video_format": "MP4",
            "storage": "USB3.0",
        },
        "generated_proxy_inputs": {
            "white_light_jpeg": file_record(white_path),
            "icg_jpeg": file_record(fluor_path),
            "mp4": file_record(video_path),
            "width": args.width,
            "height": args.height,
            "frames": args.frames,
            "fps": args.fps,
            "not_real_patient_data": True,
        },
        "models": {
            "available_model_ids": sorted(available_models),
            "required_runtime_model_ids": sorted(required_models),
            "missing_required_model_ids": sorted(missing_required_models),
            "configured_segmentation_model_id": configured_segmentation_model,
            "video_execution": video_model_execution,
            "inventory": model_inventory,
        },
        "uploads": {
            "white_light": upload_record(white_upload),
            "fluorescence": upload_record(fluor_upload),
            "video": upload_record(video_upload),
            "video_upload_job": trim_job(upload_job),
        },
        "analysis": {
            "fusion_run": run_record(fusion_run),
            "video_run": run_record(video_run),
            "analysis_job": trim_job(analysis_job),
        },
        "review": review_result,
        "export": {
            "bundle_path": export_payload.get("bundle_path"),
            "bundle_exists": demo_check["bundle_exists"],
            "report_path": export_payload.get("report_path"),
            "manifest_path": export_payload.get("manifest_path"),
            "dicom_path": export_payload.get("dicom_path"),
            "summary": export_payload.get("summary", {}),
        },
        "demo_check": demo_check,
        "timings": timings,
        "medical_boundary": {
            "disclaimer": DISCLAIMER_TEXT,
            "icg_limitation": "ICG reflects perfusion, vascular permeability, and tissue activity differences; it is not a jaw osteomyelitis-specific probe.",
            "not_real_intraoperative_icg_jaw_osteomyelitis_video": True,
            "clinical_claim_allowed": False,
        },
    }
    summary_path = output_dir / "platform_flow_demo_check_summary.json"
    report_path = output_dir / "platform_flow_demo_check_report.md"
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/inference/osteo_vision_strict.yml")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--keyframes", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.6)
    parser.add_argument("--width", type=int, default=OFFICIAL_WIDTH)
    parser.add_argument("--height", type=int, default=OFFICIAL_HEIGHT)
    return parser.parse_args()


def create_proxy_jpeg(path: Path, *, channel: str, width: int, height: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    rng = np.random.default_rng(20260717)
    low_resolution_texture = rng.normal(
        0.0,
        1.0,
        size=(max(8, height // 16), max(8, width // 16)),
    ).astype(np.float32)
    shared_texture = cv2.resize(
        low_resolution_texture,
        (width, height),
        interpolation=cv2.INTER_CUBIC,
    )
    shared_texture = np.clip(shared_texture, -2.5, 2.5) * 12.0
    base = 52 + 96 * (0.55 * x + 0.45 * y) + shared_texture
    radial = np.exp(-(((x - 0.62) ** 2) / 0.010 + ((y - 0.47) ** 2) / 0.024))
    secondary = np.exp(-(((x - 0.34) ** 2) / 0.018 + ((y - 0.62) ** 2) / 0.018))
    rgb: np.ndarray
    if channel == "fluorescence":
        signal = np.clip(base * 0.55 + radial * 200 + secondary * 115, 0, 255)
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[..., 1] = signal.astype(np.uint8)
        rgb[..., 0] = np.clip(signal * 0.22, 0, 255).astype(np.uint8)
        rgb[..., 2] = np.clip(signal * 0.16, 0, 255).astype(np.uint8)
    else:
        rgb = np.stack(
            [
                np.clip(base + radial * 34, 0, 255),
                np.clip(base * 0.94 + secondary * 22, 0, 255),
                np.clip(base * 0.82, 0, 255),
            ],
            axis=-1,
        ).astype(np.uint8)
    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    return path


def create_proxy_video(path: Path, *, width: int, height: int, frames: int, fps: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),  # type: ignore[attr-defined]
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {path}")
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    for index in range(max(1, frames)):
        phase = index / max(1, frames - 1)
        cx = 0.35 + 0.28 * phase
        cy = 0.52 + 0.08 * np.sin(phase * np.pi)
        lesion = np.exp(-(((x - cx) ** 2) / 0.008 + ((y - cy) ** 2) / 0.018))
        vessel = np.exp(-(((x - 0.70) ** 2) / 0.004 + ((y - 0.35 - 0.16 * phase) ** 2) / 0.030))
        background = 36 + 80 * (0.45 * x + 0.55 * y)
        rgb: np.ndarray = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[..., 0] = np.clip(background * 0.55 + lesion * 36, 0, 255).astype(np.uint8)
        rgb[..., 1] = np.clip(background * 0.58 + lesion * 238 + vessel * 190, 0, 255).astype(np.uint8)
        rgb[..., 2] = np.clip(background * 0.50 + vessel * 30, 0, 255).astype(np.uint8)
        cv2.putText(
            rgb,
            f"proxy frame {index + 1}",
            (max(20, width // 70), max(40, height // 30)),
            cv2.FONT_HERSHEY_SIMPLEX,
            max(0.6, width / 2600),
            (210, 238, 220),
            max(1, width // 1600),
            cv2.LINE_AA,
        )
        writer.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    writer.release()
    return path


def upload_file(client: TestClient, path: Path, content_type: str) -> dict[str, Any]:
    response = client.post(
        "/uploads/raw",
        content=path.read_bytes(),
        headers={"content-type": content_type, "x-filename": path.name},
    )
    return checked_json(response)


def review_first_candidate(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    candidate = first_candidate(case)
    if candidate is None:
        return {"review_performed": False, "reason": "no_candidate_region", "review_event_count": 0, "roi_count": 0}
    candidate_id = str(candidate["candidate_id"])
    geometry = candidate.get("metadata", {}).get("bbox_normalized") or {
        "type": "rect",
        "coordinate_space": "normalized",
        "x": 0.36,
        "y": 0.36,
        "width": 0.22,
        "height": 0.22,
    }
    reviewed = checked_json(
        client.patch(
            f"/cases/{case_id}/candidate-regions/{candidate_id}",
            json={
                "review_state": "accepted",
                "geometry": geometry,
                "label": "engineering_reviewed_proxy_hotspot",
                "reviewer_notes": "Platform demo check: candidate accepted for demo workflow evidence.",
            },
        )
    )
    roi_case = checked_json(client.post(f"/cases/{case_id}/regions/from-candidate/{candidate_id}"))
    roi_id = f"roi_{candidate_id}"
    event_case = checked_json(
        client.post(
            f"/cases/{case_id}/review-events",
            json={
                "action": "accept_candidate_and_create_roi",
                "target_id": roi_id,
                "before_state": "review_required",
                "after_state": "accepted",
                "notes": "Platform demo check engineering-review event.",
            },
        )
    )
    return {
        "review_performed": True,
        "candidate_id": candidate_id,
        "roi_id": roi_id,
        "candidate_status_after_review": candidate_status(reviewed, candidate_id),
        "roi_count": len(roi_case.get("rois") or event_case.get("rois") or []),
        "review_event_count": len(event_case.get("review_events") or []),
        "review_events": event_case.get("review_events") or [],
        "review_summary": event_case.get("review_summary", {}),
    }


def first_candidate(case: dict[str, Any]) -> dict[str, Any] | None:
    for run in reversed(case.get("analysis_runs") or []):
        candidates = run.get("candidate_regions") or []
        if candidates:
            return candidates[0]
    return None


def candidate_status(case: dict[str, Any], candidate_id: str) -> str | None:
    for run in case.get("analysis_runs") or []:
        for candidate in run.get("candidate_regions") or []:
            if candidate.get("candidate_id") == candidate_id:
                return candidate.get("status")
    return None


def latest_run(case: dict[str, Any], *, mode: str) -> dict[str, Any] | None:
    for run in reversed(case.get("analysis_runs") or []):
        outputs = run.get("fused_outputs") or {}
        if mode == "image_fusion" and (outputs.get("outputs") or {}).get("overlay_path"):
            return run
        if outputs.get("mode") == mode:
            return run
    return None


def run_record(run: dict[str, Any] | None) -> dict[str, Any]:
    if not run:
        return {"available": False}
    summary = run.get("quantitative_summary") or {}
    outputs = run.get("fused_outputs") or {}
    fusion = outputs.get("fusion") if isinstance(outputs.get("fusion"), dict) else {}
    registration = fusion.get("registration_details") if isinstance(fusion, dict) else {}
    patient_conditioning = (
        outputs.get("patient_conditioning_evidence")
        if isinstance(outputs.get("patient_conditioning_evidence"), dict)
        else {}
    )
    return {
        "available": True,
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "candidate_count": len(run.get("candidate_regions") or []),
        "frame_count": summary.get("frame_count"),
        "keyframes_extracted": summary.get("keyframes_extracted"),
        "hotspot_candidate_count": summary.get("hotspot_candidate_count"),
        "positive_area_fraction": summary.get("positive_area_fraction"),
        "overlay_path": (outputs.get("outputs") or {}).get("overlay_path"),
        "timeline_manifest_path": outputs.get("timeline_manifest_path"),
        "frame_details_manifest_path": outputs.get("frame_details_manifest_path"),
        "video_segmentation_manifest_path": outputs.get("video_segmentation_manifest_path"),
        "segmentation_review_video_path": outputs.get("segmentation_review_video_path"),
        "mask_review_video_path": outputs.get("mask_review_video_path"),
        "registration_evidence": registration or {},
        "patient_conditioning": {
            "available": patient_conditioning.get("available") is True,
            "model_id": patient_conditioning.get("model_id"),
            "spatial_effect_applied": patient_conditioning.get("spatial_effect_applied") is True,
            "safe_fallback_applied": patient_conditioning.get("safe_fallback_applied") is True,
            "failure_reasons": patient_conditioning.get("failure_reasons") or [],
        },
        "warnings": run.get("warnings") or [],
    }


def available_model_ids(inventory: list[dict[str, Any]]) -> set[str]:
    model_ids: set[str] = set()
    for item in inventory:
        spec = item.get("spec") or {}
        status = item.get("status") or {}
        if status.get("available"):
            model_ids.add(str(spec.get("model_id")))
    return model_ids


def bind_runtime_environment(config_value: str | Path, output_dir: Path) -> Path:
    config_path = Path(config_value)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config_path = config_path.resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Inference config does not exist: {config_path}")
    os.environ["OSTEO_INFERENCE_CONFIG"] = str(config_path)
    os.environ["OSTEO_ARTIFACT_ROOT"] = str(output_dir / "artifacts")
    os.environ["OSTEO_CASE_STORE_PATH"] = str(output_dir / "cases.sqlite")
    os.environ["OSTEO_JOB_STORE_PATH"] = str(output_dir / "jobs" / "jobs.json")
    os.environ["OSTEO_JOB_EXECUTION_MODE"] = "background"
    return config_path


def paths_match(active_path: str, requested_path: str | Path) -> bool:
    if not active_path:
        return False
    try:
        return Path(active_path).resolve() == Path(requested_path).resolve()
    except OSError:
        return False


def required_runtime_model_ids(runtime: dict[str, Any]) -> set[str]:
    return {str(model_id).strip() for model_id in runtime.get("required_model_ids") or [] if str(model_id).strip()}


def configured_segmentation_model_id(runtime: dict[str, Any]) -> str | None:
    tasks = runtime.get("tasks") or {}
    segmentation = tasks.get("segmentation") if isinstance(tasks, dict) else None
    if not isinstance(segmentation, dict):
        return None
    model_id = str(segmentation.get("model_id") or "").strip()
    return model_id or None


def video_segmentation_execution(run: dict[str, Any] | None) -> dict[str, Any]:
    if not run:
        return {"available": False, "model_ids": [], "analysis_methods": [], "error": "video_run_missing"}
    outputs = run.get("fused_outputs") or {}
    manifest_value = outputs.get("video_segmentation_manifest_path")
    if not manifest_value:
        return {"available": False, "model_ids": [], "analysis_methods": [], "error": "manifest_path_missing"}
    manifest_path = Path(str(manifest_value))
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "manifest_path": str(manifest_path),
            "model_ids": [],
            "analysis_methods": [],
            "error": f"manifest_unreadable: {exc}",
        }
    summary = payload.get("summary") if isinstance(payload, dict) else None
    summary = summary if isinstance(summary, dict) else {}
    frames = payload.get("frames") if isinstance(payload, dict) else None
    frames = [item for item in frames or [] if isinstance(item, dict)]
    summary_model_ids = {str(value) for value in summary.get("model_ids") or [] if value}
    summary_analysis_methods = {str(value) for value in summary.get("analysis_methods") or [] if value}
    frame_model_ids: set[str] = set()
    frame_analysis_methods: set[str] = set()
    missing_probability_paths: list[str] = []
    for index, frame in enumerate(frames):
        segmentation = frame.get("segmentation_result")
        segmentation = segmentation if isinstance(segmentation, dict) else {}
        model_id = str(segmentation.get("model_id") or "").strip()
        method = str(segmentation.get("analysis_method") or "").strip()
        if model_id:
            frame_model_ids.add(model_id)
        if method:
            frame_analysis_methods.add(method)
        probability_path = str(segmentation.get("probability_path") or "").strip()
        if not probability_path or not Path(probability_path).is_file():
            missing_probability_paths.append(f"frame_{index + 1}")
    frame_evidence_valid = (
        bool(frames)
        and not missing_probability_paths
        and frame_model_ids == summary_model_ids
        and frame_analysis_methods == summary_analysis_methods
        and all(
            str(frame.get("segmentation_result", {}).get("model_id") or "").strip()
            and str(frame.get("segmentation_result", {}).get("analysis_method") or "").strip()
            for frame in frames
            if isinstance(frame.get("segmentation_result"), dict)
        )
    )
    return {
        "available": True,
        "manifest_path": str(manifest_path),
        "model_ids": sorted(summary_model_ids),
        "analysis_methods": sorted(summary_analysis_methods),
        "frame_count": len(frames),
        "frame_model_ids": sorted(frame_model_ids),
        "frame_analysis_methods": sorted(frame_analysis_methods),
        "missing_probability_paths": missing_probability_paths,
        "frame_evidence_valid": frame_evidence_valid,
    }


def requested_timestamps(keyframes: int, fps: float, frames: int) -> list[float]:
    if keyframes <= 0:
        return []
    duration = max(0.0, (frames - 1) / max(fps, 0.001))
    if keyframes == 1:
        return [round(duration / 2.0, 3)]
    return [round(duration * index / (keyframes - 1), 3) for index in range(keyframes)]


def checked_json(response: Any) -> dict[str, Any]:
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
    payload = response.json()
    return payload if isinstance(payload, dict) else {"value": payload}


def file_record(path: Path) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "sha256": _sha256_file(path) if exists else None,
    }


def upload_record(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    return {
        "path": payload.get("path"),
        "input_type": payload.get("input_type"),
        "size_bytes": payload.get("size_bytes"),
        "official_profile": metadata.get("official_input_profile") or metadata.get("official_profile") or {},
        "keyframe_job_id": payload.get("keyframe_job_id"),
        "keyframe_job_status": payload.get("keyframe_job_status"),
        "warnings": payload.get("warnings") or [],
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def trim_job(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result") or {}
    return {
        "job_id": payload.get("job_id"),
        "kind": payload.get("kind"),
        "status": payload.get("status"),
        "error": payload.get("error"),
        "keyframes": len(result.get("keyframes") or []),
        "run_id": result.get("run_id"),
        "run_status": result.get("run_status"),
    }


def render_report(summary: dict[str, Any]) -> str:
    demo_check = summary["demo_check"]
    export_summary = summary["export"].get("summary") or {}
    analysis = summary["analysis"]
    lines = [
        "# Osteo Vision Platform Flow Demo Check Report",
        "",
        "## Verdict",
        "",
        f"- Pass: `{demo_check['pass']}`",
        f"- Case ID: `{summary['case_id']}`",
        f"- Evidence bundle: `{summary['export'].get('bundle_path')}`",
        f"- Report JSON: `{summary['export'].get('report_path')}`",
        f"- DICOM Secondary Capture: `{summary['export'].get('dicom_path')}`",
        "",
        "## Platform Flow",
        "",
        f"- 4K JPEG dual-channel fusion status: `{analysis['fusion_run'].get('status')}`",
        f"- 4K MP4 keyframe analysis status: `{analysis['video_run'].get('status')}`",
        f"- Keyframes extracted: `{analysis['video_run'].get('keyframes_extracted')}`",
        f"- Segmentation manifest: `{analysis['video_run'].get('video_segmentation_manifest_path')}`",
        f"- Segmentation overlay video: `{analysis['video_run'].get('segmentation_review_video_path')}`",
        f"- Candidate regions reviewed: `{summary['review'].get('review_event_count')}` review event(s), `{summary['review'].get('roi_count')}` ROI(s)",
        f"- Export formats: `{', '.join(export_summary.get('formats') or [])}`",
        "",
        "## Models",
        "",
        f"- Required runtime models: `{', '.join(summary['models']['required_runtime_model_ids'])}`",
        f"- Configured keyframe segmentation model: `{summary['models']['configured_segmentation_model_id']}`",
        f"- Exercised video models: `{', '.join(summary['models']['video_execution']['model_ids'])}`",
        f"- Video analysis methods: `{', '.join(summary['models']['video_execution']['analysis_methods'])}`",
        "",
        "## Demo Checks",
        "",
        f"- Runtime config bound: `{demo_check['runtime_config_bound']}`",
        f"- Runtime profile: `{summary['runtime']['runtime_profile']}`",
        f"- Strict startup active: `{demo_check['strict_runtime_active']}`",
        f"- Missing required formats: `{', '.join(demo_check['missing_required_formats']) or 'none'}`",
        f"- Mainline models available: `{demo_check['mainline_models_available']}`",
        f"- Keyframe mainline model exercised: `{demo_check['keyframe_mainline_model_exercised']}`",
        f"- Keyframe fallback used: `{demo_check['keyframe_fallback_used']}`",
        f"- Per-frame model and probability evidence valid: `{demo_check['video_frame_evidence_valid']}`",
        f"- Non-target-domain disclosure included: `{demo_check['non_target_domain_disclosed']}`",
        f"- Official platform acceptance: `{not demo_check['not_official_platform_acceptance']}`",
        "",
        "## Medical Boundary",
        "",
        summary["medical_boundary"]["disclaimer"],
        "",
        summary["medical_boundary"]["icg_limitation"],
        "",
        "The generated MP4/JPEG files are synthetic proxy inputs, not real intraoperative ICG jaw osteomyelitis data.",
    ]
    return "\n".join(lines) + "\n"


def timed(name: str, func: Callable[[], T], timings: list[dict[str, Any]]) -> T:
    started = time.perf_counter()
    result = func()
    timings.append({"name": name, "elapsed_sec": round(time.perf_counter() - started, 4)})
    return result


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    summary = run_demo_check(parse_args())
    return 0 if summary.get("demo_check", {}).get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
