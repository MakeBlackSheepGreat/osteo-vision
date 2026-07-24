from __future__ import annotations

import json
import os
import shutil
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from threading import BoundedSemaphore, Event, Lock
from time import perf_counter, sleep
from typing import Any
from uuid import uuid4

import numpy as np
from PIL import Image

from backend.osteo_vision_api.core.artifacts import case_artifact_dir
from backend.osteo_vision_api.core.disclaimers import disclaimer_context
from osteo_vision_core.core.config import load_yaml
from osteo_vision_core.core.paths import artifact_dirs, resolve_path
from osteo_vision_core.core.schemas import AdapterRequest
from osteo_vision_core.models.adapters import build_adapter, model_spec_from_mapping

MAX_LIVE_IMAGE_DIMENSION = 4096
MAX_LIVE_IMAGE_PIXELS = 4096 * 2160
MAX_LIVE_CONCURRENT_INFERENCES = 8
DEFAULT_MAX_RETAINED_FRAMES_PER_CASE = 120
MAX_RETAINED_FRAMES_PER_CASE = 1000
LIVE_FRAME_MANIFEST_FILENAME = "live_frame_manifest.json"
MAX_LIVE_FRAME_MANIFEST_BYTES = 1024 * 1024
DIRECTORY_COMMIT_RETRY_DELAYS_SECONDS = (0.01, 0.025, 0.05, 0.1, 0.2)


class LiveFrameInputError(ValueError):
    """Raised for a client-provided frame or parameter that cannot be accepted."""


class LiveFrameCapacityError(RuntimeError):
    """Raised when accepting another frame would create an inference backlog."""

    def __init__(self, *, max_concurrent: int, waited_ms: float) -> None:
        super().__init__("Live frame inference capacity is currently exhausted.")
        self.max_concurrent = max_concurrent
        self.waited_ms = waited_ms


class LiveFrameCancelledError(RuntimeError):
    """Raised when the caller cancelled a frame before a result could be returned."""


class LiveFrameAdmission:
    """Idempotent ownership token for one live-frame inference slot."""

    def __init__(self, gate: BoundedSemaphore, *, waited_ms: float) -> None:
        self.waited_ms = waited_ms
        self._gate = gate
        self._released = False
        self._release_lock = Lock()

    def release(self) -> None:
        with self._release_lock:
            if self._released:
                return
            self._released = True
            self._gate.release()


@dataclass(frozen=True)
class _DecodedLiveFrame:
    rgb: np.ndarray
    image_format: str


class LiveFrameAnalysisService:
    """Low-latency single-frame inference for the intraoperative preview path."""

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self._config = load_yaml(config_path)
        self._runtime = dict(self._config.get("runtime") or {})
        self._live_frame_root = artifact_dirs(self._config)["visual"] / "live_frames"
        self._adapters: dict[str, Any] = {}
        live_runtime = self._runtime.get("live_frames")
        live_runtime = live_runtime if isinstance(live_runtime, dict) else {}
        self._max_concurrent_inferences = _validated_int(
            live_runtime.get("max_concurrent_inferences"),
            default=1,
            minimum=1,
            maximum=MAX_LIVE_CONCURRENT_INFERENCES,
            field_name="runtime.live_frames.max_concurrent_inferences",
        )
        self._admission_timeout_seconds = (
            _bounded_float(
                live_runtime.get("admission_timeout_ms"),
                default=0.0,
                minimum=0.0,
                maximum=5000.0,
            )
            / 1000.0
        )
        self._max_retained_frames_per_case = _validated_int(
            live_runtime.get("max_retained_frames_per_case"),
            default=DEFAULT_MAX_RETAINED_FRAMES_PER_CASE,
            minimum=1,
            maximum=MAX_RETAINED_FRAMES_PER_CASE,
            field_name="runtime.live_frames.max_retained_frames_per_case",
        )
        self._inference_gate = BoundedSemaphore(self._max_concurrent_inferences)
        self._adapter_lock = Lock()
        self._retention_lock = Lock()

    def acquire_admission(self, *, wait: bool | None = None) -> LiveFrameAdmission:
        """Reserve capacity before request bytes are accepted into memory."""

        should_wait = self._admission_timeout_seconds > 0 if wait is None else bool(wait)
        started = perf_counter()
        if should_wait and self._admission_timeout_seconds > 0:
            acquired = self._inference_gate.acquire(timeout=self._admission_timeout_seconds)
        else:
            acquired = self._inference_gate.acquire(blocking=False)
        waited_ms = (perf_counter() - started) * 1000.0
        if not acquired:
            raise LiveFrameCapacityError(
                max_concurrent=self._max_concurrent_inferences,
                waited_ms=round(waited_ms, 2),
            )
        return LiveFrameAdmission(self._inference_gate, waited_ms=round(waited_ms, 2))

    @property
    def default_model_id(self) -> str:
        tasks = self._runtime.get("tasks")
        segmentation = tasks.get("segmentation") if isinstance(tasks, dict) else None
        configured = segmentation.get("model_id") if isinstance(segmentation, dict) else None
        resolved = str(configured or "").strip()
        if resolved:
            return resolved
        if bool(self._runtime.get("strict_startup")):
            raise ValueError("Strict runtime requires runtime.tasks.segmentation.model_id.")
        return "convnext2d_keyframe_proxy_segmenter"

    def analyze(
        self,
        *,
        case_id: str,
        frame_bytes: bytes,
        filename: str,
        parameters: dict[str, Any],
        cancel_event: Event | None = None,
        admission: LiveFrameAdmission | None = None,
    ) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        started = perf_counter()
        lease = admission or self.acquire_admission()
        queue_wait_ms = lease.waited_ms
        frame_id = f"live_{uuid4().hex}"
        frame_case_id = f"{case_id}_{frame_id}"
        model_id = str(parameters.get("segmentation_model_id") or self.default_model_id).strip()
        staging_dir: Path | None = None
        output_root: Path | None = None
        final_dir: Path | None = None
        evidence_path: Path | None = None
        manifest_path: Path | None = None
        output: dict[str, Any] | None = None
        try:
            _raise_if_cancelled(cancel_event)
            decode_started = perf_counter()
            decoded = _decode_rgb_image(frame_bytes)
            image = decoded.rgb
            decode_ms = (perf_counter() - decode_started) * 1000.0

            captured_at = _valid_timestamp(parameters.get("captured_at")) or started_at
            applied_parameters = self._resolve_live_parameters(model_id, parameters)
            output_root = case_artifact_dir(self._live_frame_root, case_id)
            staging_dir = output_root / f".{frame_id}.tmp"
            final_dir = output_root / frame_id
            evidence_suffix = _safe_filename(filename, decoded.image_format)
            evidence_path = staging_dir / evidence_suffix
            write_started = perf_counter()
            staging_dir.mkdir(parents=True, exist_ok=False)
            _write_fsync_bytes(evidence_path, frame_bytes)
            if evidence_path.stat().st_size != len(frame_bytes):
                raise ValueError("Live frame could not be stored for inference.")
            evidence_write_ms = (perf_counter() - write_started) * 1000.0

            _raise_if_cancelled(cancel_event)
            model_started = perf_counter()
            output = self._predict_frame(
                model_id=model_id,
                frame_case_id=frame_case_id,
                source_path=str(evidence_path),
                rgb=image,
                live_parameters=applied_parameters,
            )
            model_ms = (perf_counter() - model_started) * 1000.0
            _raise_if_cancelled(cancel_event)

            evidence = _record(output.get("lesion_evidence"))
            segmentation_mask = _record(output.get("segmentation_mask"))
            signal_masks = _record(output.get("video_signal_segmentation")) or _record(output.get("signal_masks"))
            quantification = _record(output.get("quantification"))
            completed_at = datetime.now(timezone.utc).isoformat()
            actual_model_id = str(output.get("model_id") or model_id)
            manifest_path = staging_dir / LIVE_FRAME_MANIFEST_FILENAME
            _write_json_fsync(
                manifest_path,
                {
                    "schema_version": "live_frame_manifest.v1",
                    "frame_id": frame_id,
                    "frame_case_id": frame_case_id,
                    "case_id": case_id,
                    "model_id": actual_model_id,
                    "source_file": evidence_suffix,
                    "source_path": str(final_dir / evidence_suffix),
                    "managed_output_paths": sorted(str(path) for path in _paths_from_payload(output)),
                    "captured_at": captured_at,
                    "created_at": started_at,
                    "completed_at": completed_at,
                    "sequence": applied_parameters["sequence"],
                    "source_timestamp_sec": applied_parameters["source_timestamp_sec"],
                },
            )
            with self._retention_lock:
                _commit_staging_directory(staging_dir, final_dir)
                retention = _retain_recent_live_frames(
                    output_root=output_root,
                    max_retained_frames=self._max_retained_frames_per_case,
                    configured_output_roots=self._configured_output_roots(),
                    protected_frame_id=frame_id,
                )
            evidence_path = final_dir / evidence_suffix
            manifest_path = final_dir / LIVE_FRAME_MANIFEST_FILENAME
            elapsed_ms = (perf_counter() - started) * 1000.0
            performance = {
                "queue_wait_ms": round(queue_wait_ms, 2),
                "decode_ms": round(decode_ms, 2),
                "evidence_write_ms": round(evidence_write_ms, 2),
                "model_ms": round(model_ms, 2),
                "total_ms": round(elapsed_ms, 2),
                "input_bytes": len(frame_bytes),
                "decoded_width": int(image.shape[1]),
                "decoded_height": int(image.shape[0]),
                "max_concurrent_inferences": self._max_concurrent_inferences,
            }
            return {
                "frame_id": frame_id,
                "case_id": case_id,
                "captured_at": captured_at,
                "completed_at": completed_at,
                "sequence": applied_parameters["sequence"],
                "source_timestamp_sec": applied_parameters["source_timestamp_sec"],
                "applied_parameters": applied_parameters,
                "inference_latency_ms": performance["total_ms"],
                "model_inference_latency_ms": performance["model_ms"],
                "performance": performance,
                "model_id": actual_model_id,
                "model_family": output.get("model_family"),
                "analysis_method": output.get("analysis_method"),
                "source_path": str(evidence_path),
                "manifest_path": str(manifest_path),
                "overlay_path": evidence.get("overlay_path"),
                "mask_path": segmentation_mask.get("path"),
                "probability_path": evidence.get("probability_path"),
                "risk_mask_path": evidence.get("risk_mask_path"),
                "uncertain_mask_path": evidence.get("uncertain_mask_path"),
                "pseudo_color_path": evidence.get("pseudo_color_path"),
                "signal_masks": signal_masks,
                "quantification": quantification,
                "retention": retention,
                "warnings": list(output.get("warnings") or []) + list(applied_parameters["warnings"]),
                "medical_boundary": (
                    "实时单帧荧光/灌注风险提示，需医生复核；" "当前模型尚无真实颌骨骨髓炎术中 ICG 临床性能验证。"
                ),
                "disclaimer_context": disclaimer_context(),
            }
        except Exception:
            _cleanup_live_frame_artifacts(
                staging_dir=staging_dir,
                output_root=output_root,
                final_dir=final_dir,
                output=output,
                frame_case_id=frame_case_id,
                configured_output_dir=self._configured_output_dir(model_id),
                live_frame_root=self._live_frame_root,
            )
            raise
        finally:
            lease.release()

    def warmup(self, model_id: str | None = None) -> dict[str, Any]:
        """Load the configured live model once before the first camera frame arrives."""

        model_id = str(model_id or self.default_model_id)
        lease = self.acquire_admission()
        try:
            adapter = self._adapter(model_id)
            status = adapter.warmup()
            if not status.available:
                raise RuntimeError(
                    f"Live frame model {model_id} is unavailable: {'; '.join(status.reasons) or 'unknown reason'}"
                )
            self._load_model_if_needed(adapter)
            self._run_warmup_inference(adapter)
            return {
                "model_id": model_id,
                "model_family": adapter.describe().family,
                "available": True,
                "warnings": list(status.warnings),
            }
        finally:
            lease.release()

    def _adapter(self, model_id: str) -> Any:
        cached = self._adapters.get(model_id)
        if cached is not None:
            return cached
        with self._adapter_lock:
            cached = self._adapters.get(model_id)
            if cached is not None:
                return cached
            model_mapping = _runtime_model_mapping(self._runtime, model_id)
            if model_mapping is None:
                raise LiveFrameInputError("Requested live frame model is not configured.")
            adapter = build_adapter(model_spec_from_mapping(_live_model_mapping(model_mapping)))
            self._adapters[model_id] = adapter
            return adapter

    def _predict_frame(
        self,
        *,
        model_id: str,
        frame_case_id: str,
        source_path: str,
        rgb: np.ndarray,
        live_parameters: dict[str, Any],
    ) -> dict[str, Any]:
        adapter = self._adapter(model_id)
        status = adapter.warmup()
        if not status.available:
            raise RuntimeError(
                f"Live frame model {model_id} is unavailable: {'; '.join(status.reasons) or 'unknown reason'}"
            )
        self._load_model_if_needed(adapter)
        result = adapter.predict(
            AdapterRequest(
                case_id=frame_case_id,
                input_path=source_path,
                input_type="2d_image",
                task_type="segmentation",
                modality="surgical_keyframe",
                metadata={
                    "roi_hints": [],
                    "predecoded_rgb": rgb,
                    "live_frame_parameters": live_parameters,
                },
            )
        )
        payload = result.to_dict()
        segmentation_mask = _record(payload.get("segmentation_mask"))
        if segmentation_mask.get("path"):
            return payload
        raise RuntimeError(f"Live frame model {model_id} did not produce a segmentation mask.")

    def _resolve_live_parameters(self, model_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
        requested_threshold = _optional_unit_float(
            parameters.get("threshold"), "x-hotspot-threshold", client_value=True
        )
        requested_colormap = _optional_colormap(parameters.get("colormap"), "x-colormap", client_value=True)
        sequence = _optional_nonnegative_int(parameters.get("sequence"), "x-frame-sequence")
        source_timestamp_sec = _optional_nonnegative_float(parameters.get("timestamp_sec"), "x-source-timestamp-sec")
        mapping = _runtime_model_mapping(self._runtime, model_id)
        extra = dict(mapping.get("extra") or {}) if mapping is not None else {}
        configured_threshold = _optional_unit_float(extra.get("threshold"), "model threshold", client_value=False)
        actual_threshold = configured_threshold if configured_threshold is not None else 0.5
        configured_colormap = _optional_colormap(extra.get("colormap"), "model colormap", client_value=False)
        actual_colormap = configured_colormap or "green"
        warnings_list: list[dict[str, Any]] = []
        if requested_threshold is not None and abs(requested_threshold - actual_threshold) > 1e-9:
            warnings_list.append(
                {
                    "code": "live_frame_threshold_fixed_by_model",
                    "message": "The active live model uses its configured threshold; the request threshold was not applied.",
                    "blocking": False,
                    "requested": requested_threshold,
                    "applied": actual_threshold,
                }
            )
        if requested_colormap is not None and requested_colormap != actual_colormap:
            warnings_list.append(
                {
                    "code": "live_frame_colormap_fixed_by_model",
                    "message": "The active live model uses its configured colormap; the request colormap was not applied.",
                    "blocking": False,
                    "requested": requested_colormap,
                    "applied": actual_colormap,
                }
            )
        return {
            "sequence": sequence,
            "source_timestamp_sec": source_timestamp_sec,
            "requested_threshold": requested_threshold,
            "requested_colormap": requested_colormap,
            "threshold": actual_threshold,
            "colormap": actual_colormap,
            "runtime_override_applied": False,
            "threshold_source": "model_configuration_fixed",
            "colormap_source": "model_configuration_fixed",
            "warnings": warnings_list,
        }

    def _configured_output_dir(self, model_id: str) -> Path | None:
        mapping = _runtime_model_mapping(self._runtime, model_id)
        if mapping is None:
            return None
        extra = dict(mapping.get("extra") or {})
        output_dir = extra.get("output_dir")
        if not output_dir:
            return None
        return resolve_path(str(output_dir))

    def _configured_output_roots(self) -> set[Path]:
        roots: set[Path] = set()
        for mapping in self._runtime.get("models") or []:
            if not isinstance(mapping, dict):
                continue
            extra = mapping.get("extra")
            output_dir = extra.get("output_dir") if isinstance(extra, dict) else None
            if output_dir:
                roots.add(resolve_path(str(output_dir)))
        return roots

    def _load_model_if_needed(self, adapter: Any) -> None:
        load_model = getattr(adapter, "_load_model", None)
        if not callable(load_model) or getattr(adapter, "_model", None) is not None:
            return
        with self._adapter_lock:
            if getattr(adapter, "_model", None) is None:
                load_model()

    @staticmethod
    def _run_warmup_inference(adapter: Any) -> None:
        """Exercise the CUDA path before a surgeon requests the first overlay."""

        spec = adapter.describe()
        if not ("segmentation" in spec.task_types and "2d_image" in spec.input_types and 2 in spec.spatial_dims):
            return
        model = getattr(adapter, "_model", None)
        if model is None:
            return
        import torch

        from osteo_vision_core.models.keyframe_segmenter import select_torch_device

        device = select_torch_device(spec.device_policy)
        input_channels = max(1, int(spec.extra.get("input_channels", 3)))
        sample = torch.zeros((1, input_channels, 64, 64), dtype=torch.float32, device=device)
        with (
            torch.inference_mode(),
            torch.autocast(
                device_type="cuda",
                dtype=torch.float16,
                enabled=bool(spec.extra.get("use_amp", False) and device.type == "cuda"),
            ),
        ):
            model(sample)
        if device.type == "cuda":
            torch.cuda.synchronize(device)


def _decode_rgb_image(frame_bytes: bytes) -> _DecodedLiveFrame:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(frame_bytes)) as image:
                image_format = str(image.format or "").upper()
                if image_format not in {"JPEG", "PNG"}:
                    raise LiveFrameInputError("Live frame must contain a JPEG or PNG image.")
                if int(getattr(image, "n_frames", 1) or 1) != 1 or bool(getattr(image, "is_animated", False)):
                    raise LiveFrameInputError("Animated live frames are not accepted.")
                width, height = image.size
                if (
                    width <= 0
                    or height <= 0
                    or width > MAX_LIVE_IMAGE_DIMENSION
                    or height > MAX_LIVE_IMAGE_DIMENSION
                    or width * height > MAX_LIVE_IMAGE_PIXELS
                ):
                    raise LiveFrameInputError(
                        f"Live frame dimensions exceed the {MAX_LIVE_IMAGE_DIMENSION}px / "
                        f"{MAX_LIVE_IMAGE_PIXELS}px limit."
                    )
                image.load()
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
        return _DecodedLiveFrame(rgb=rgb, image_format=image_format)
    except LiveFrameInputError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError) as error:
        raise LiveFrameInputError("Live frame is not a readable JPEG or PNG image.") from error


def _safe_filename(_value: str, image_format: str) -> str:
    suffix = ".png" if image_format.upper() == "PNG" else ".jpg"
    return f"frame{suffix}"


def _write_fsync_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_json_fsync(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    _write_fsync_bytes(path, encoded)


def _commit_staging_directory(staging_dir: Path, final_dir: Path) -> None:
    if final_dir.exists():
        raise RuntimeError("Live frame evidence destination already exists.")
    for attempt in range(len(DIRECTORY_COMMIT_RETRY_DELAYS_SECONDS) + 1):
        try:
            os.replace(staging_dir, final_dir)
            return
        except PermissionError:
            if attempt >= len(DIRECTORY_COMMIT_RETRY_DELAYS_SECONDS):
                raise
            sleep(DIRECTORY_COMMIT_RETRY_DELAYS_SECONDS[attempt])


def _cleanup_live_frame_artifacts(
    *,
    staging_dir: Path | None,
    output_root: Path | None,
    final_dir: Path | None,
    output: dict[str, Any] | None,
    frame_case_id: str,
    configured_output_dir: Path | None,
    live_frame_root: Path,
) -> None:
    safe_case = _safe_artifact_name(frame_case_id)
    if output_root is not None:
        for frame_dir in (staging_dir, final_dir):
            if frame_dir is not None:
                _remove_frame_directory(frame_dir, output_root=output_root)
    managed_roots = {root for root in (configured_output_dir, staging_dir, final_dir, output_root) if root is not None}
    if configured_output_dir is not None and configured_output_dir.exists():
        for path in configured_output_dir.glob(f"{safe_case}_*"):
            _unlink_managed_output(path, allowed_roots={configured_output_dir}, safe_prefix=safe_case)
    for path in _paths_from_payload(output):
        _unlink_managed_output(path, allowed_roots=managed_roots, safe_prefix=safe_case)
    if output_root is not None and _is_direct_child(output_root, live_frame_root):
        try:
            output_root.rmdir()
        except OSError:
            pass


def _retain_recent_live_frames(
    *,
    output_root: Path,
    max_retained_frames: int,
    configured_output_roots: set[Path],
    protected_frame_id: str,
) -> dict[str, Any]:
    frame_entries: list[tuple[int, Path]] = []
    try:
        candidates = list(output_root.iterdir())
    except OSError:
        candidates = []
    for frame_dir in candidates:
        if (
            not frame_dir.name.startswith("live_")
            or not _is_direct_child(frame_dir, output_root)
            or frame_dir.is_symlink()
            or not frame_dir.is_dir()
        ):
            continue
        try:
            modified_ns = frame_dir.stat().st_mtime_ns
        except OSError:
            continue
        frame_entries.append((modified_ns, frame_dir))
    frame_entries.sort(
        key=lambda item: (item[1].name == protected_frame_id, item[0], item[1].name),
        reverse=True,
    )

    evicted_frame_ids: list[str] = []
    # Only candidates beyond the budget need manifest parsing on the normal path.
    for _modified_ns, frame_dir in frame_entries[max_retained_frames:]:
        manifest = _read_live_frame_manifest(frame_dir, output_root=output_root)
        if manifest is None:
            continue
        frame_case_id = str(manifest.get("frame_case_id") or "")
        safe_prefix = _safe_artifact_name(frame_case_id)
        if not safe_prefix:
            continue
        removed_frame = _remove_frame_directory(frame_dir, output_root=output_root)
        if not removed_frame:
            continue
        managed_paths = manifest.get("managed_output_paths")
        if isinstance(managed_paths, list):
            for value in managed_paths:
                if isinstance(value, str):
                    _unlink_managed_output(
                        Path(value),
                        allowed_roots=configured_output_roots,
                        safe_prefix=safe_prefix,
                    )
        for root in configured_output_roots:
            try:
                matching_paths = list(root.glob(f"{safe_prefix}_*")) if root.exists() else []
            except OSError:
                matching_paths = []
            for path in matching_paths:
                _unlink_managed_output(path, allowed_roots={root}, safe_prefix=safe_prefix)
        evicted_frame_ids.append(str(manifest.get("frame_id") or frame_dir.name))

    retained_count = max(0, len(frame_entries) - len(evicted_frame_ids))
    return {
        "max_retained_frames_per_case": max_retained_frames,
        "retained_frame_count": retained_count,
        "evicted_frame_ids": evicted_frame_ids,
    }


def _read_live_frame_manifest(frame_dir: Path, *, output_root: Path) -> dict[str, Any] | None:
    if not frame_dir.name.startswith("live_") or not _is_direct_child(frame_dir, output_root):
        return None
    manifest_path = frame_dir / LIVE_FRAME_MANIFEST_FILENAME
    try:
        if not manifest_path.is_file() or manifest_path.stat().st_size > MAX_LIVE_FRAME_MANIFEST_BYTES:
            return None
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or str(payload.get("frame_id") or "") != frame_dir.name:
        return None
    frame_case_id = str(payload.get("frame_case_id") or "")
    if not frame_case_id.endswith(f"_{frame_dir.name}"):
        return None
    return payload


def _remove_frame_directory(frame_dir: Path, *, output_root: Path) -> bool:
    if not _is_direct_child(frame_dir, output_root):
        return False
    try:
        if frame_dir.is_symlink() or not frame_dir.is_dir():
            return False
        shutil.rmtree(frame_dir)
        return True
    except OSError:
        return False


def _unlink_managed_output(path: Path, *, allowed_roots: set[Path], safe_prefix: str) -> bool:
    if not safe_prefix or not path.name.startswith(safe_prefix):
        return False
    if not any(_is_path_within(path, root) for root in allowed_roots):
        return False
    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
            return True
    except OSError:
        return False
    return False


def _is_path_within(path: Path, root: Path) -> bool:
    resolved_path = _resolve_without_error(path)
    resolved_root = _resolve_without_error(root)
    if resolved_path is None or resolved_root is None or resolved_path == resolved_root:
        return False
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        return False
    return True


def _is_direct_child(path: Path, root: Path) -> bool:
    resolved_path = _resolve_without_error(path)
    resolved_root = _resolve_without_error(root)
    return resolved_path is not None and resolved_root is not None and resolved_path.parent == resolved_root


def _resolve_without_error(path: Path) -> Path | None:
    try:
        return path.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return None


def _paths_from_payload(value: Any) -> set[Path]:
    paths: set[Path] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key == "path" or key.endswith("_path")):
                paths.add(Path(item))
            else:
                paths.update(_paths_from_payload(item))
    elif isinstance(value, list):
        for item in value:
            paths.update(_paths_from_payload(item))
    return paths


def _safe_artifact_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_", "."} else "_" for character in value)


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _raise_if_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise LiveFrameCancelledError("Live frame analysis was cancelled by the caller.")


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        parsed = default
    if not np.isfinite(parsed):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _validated_int(value: Any, *, default: int, minimum: int, maximum: int, field_name: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer between {minimum} and {maximum}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{field_name} must be an integer between {minimum} and {maximum}.") from error
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name} must be an integer between {minimum} and {maximum}.")
    return parsed


def _optional_unit_float(value: Any, field_name: str, *, client_value: bool) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        exception_type = LiveFrameInputError if client_value else ValueError
        raise exception_type(f"{field_name} must be a finite number between 0 and 1.") from error
    if not np.isfinite(parsed) or parsed < 0.0 or parsed > 1.0:
        exception_type = LiveFrameInputError if client_value else ValueError
        raise exception_type(f"{field_name} must be a finite number between 0 and 1.")
    return float(parsed)


def _optional_nonnegative_int(value: Any, field_name: str) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise LiveFrameInputError(f"{field_name} must be a non-negative integer.") from error
    if parsed < 0:
        raise LiveFrameInputError(f"{field_name} must be a non-negative integer.")
    return parsed


def _optional_nonnegative_float(value: Any, field_name: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise LiveFrameInputError(f"{field_name} must be a finite non-negative number.") from error
    if not np.isfinite(parsed) or parsed < 0.0:
        raise LiveFrameInputError(f"{field_name} must be a finite non-negative number.")
    return float(parsed)


def _optional_colormap(value: Any, field_name: str, *, client_value: bool) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).strip().lower()
    if normalized not in {"green", "amber", "magenta"}:
        exception_type = LiveFrameInputError if client_value else ValueError
        raise exception_type(f"{field_name} is unsupported.")
    return normalized


def _valid_timestamp(value: Any) -> str | None:
    if not value:
        return None
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return str(value)


def _runtime_model_mapping(runtime: dict[str, Any], model_id: str) -> dict[str, Any] | None:
    for item in runtime.get("models") or []:
        if isinstance(item, dict) and str(item.get("model_id") or "") == model_id:
            return dict(item)
    return None


def _live_model_mapping(model_mapping: dict[str, Any]) -> dict[str, Any]:
    """Apply the explicitly configured low-latency profile only to live-frame inference."""

    mapping = dict(model_mapping)
    extra = dict(mapping.get("extra") or {})
    live_stream = extra.get("live_stream")
    if not isinstance(live_stream, dict):
        return mapping
    for key in (
        "uncertainty_tta_enabled",
        "tile_size",
        "tile_overlap",
        "tile_batch_size",
        "force_tiled",
        "max_whole_pixels",
        "fast_output",
        "overlay_format",
        "overlay_jpeg_quality",
        "use_amp",
    ):
        if key in live_stream:
            extra[key] = live_stream[key]
    mapping["extra"] = extra
    return mapping
