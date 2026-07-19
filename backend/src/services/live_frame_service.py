from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import numpy as np
from PIL import Image

from backend.src.core.artifacts import case_artifact_dir
from backend.src.core.disclaimers import disclaimer_context
from src.core.config import load_yaml
from src.core.paths import artifact_dirs
from src.core.schemas import AdapterRequest
from src.models.adapters import build_adapter, model_spec_from_mapping


class LiveFrameAnalysisService:
    """Low-latency single-frame inference for the intraoperative preview path."""

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self._config = load_yaml(config_path)
        self._runtime = dict(self._config.get("runtime") or {})
        self._live_frame_root = artifact_dirs(self._config)["visual"] / "live_frames"
        self._adapters: dict[str, Any] = {}

    @property
    def default_model_id(self) -> str:
        tasks = self._runtime.get("tasks")
        segmentation = tasks.get("segmentation") if isinstance(tasks, dict) else None
        configured = segmentation.get("model_id") if isinstance(segmentation, dict) else None
        return str(configured or "convnext2d_keyframe_proxy_segmenter")

    def analyze(
        self,
        *,
        case_id: str,
        frame_bytes: bytes,
        filename: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        started = perf_counter()
        image = _decode_rgb_image(frame_bytes)
        output_root = case_artifact_dir(
            self._live_frame_root,
            case_id,
        )
        frame_id = f"live_{uuid4().hex[:12]}"
        evidence_path = output_root / frame_id / _safe_filename(filename)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        if evidence_path.write_bytes(frame_bytes) != len(frame_bytes):
            raise ValueError("Live frame could not be stored for inference.")

        captured_at = _valid_timestamp(parameters.get("captured_at")) or started_at
        model_id = str(parameters.get("segmentation_model_id") or self.default_model_id)
        output = self._predict_frame(
            model_id=model_id,
            frame_case_id=f"{case_id}_{frame_id}",
            source_path=str(evidence_path),
            rgb=image,
        )
        evidence = _record(output.get("lesion_evidence"))
        segmentation_mask = _record(output.get("segmentation_mask"))
        signal_masks = _record(output.get("video_signal_segmentation")) or _record(output.get("signal_masks"))
        quantification = _record(output.get("quantification"))
        elapsed_ms = round((perf_counter() - started) * 1000.0, 2)
        return {
            "frame_id": frame_id,
            "case_id": case_id,
            "captured_at": captured_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "inference_latency_ms": elapsed_ms,
            "model_id": output.get("model_id") or model_id,
            "model_family": output.get("model_family"),
            "analysis_method": output.get("analysis_method"),
            "source_path": str(evidence_path),
            "overlay_path": evidence.get("overlay_path"),
            "mask_path": segmentation_mask.get("path"),
            "probability_path": evidence.get("probability_path"),
            "risk_mask_path": evidence.get("risk_mask_path"),
            "uncertain_mask_path": evidence.get("uncertain_mask_path"),
            "pseudo_color_path": evidence.get("pseudo_color_path"),
            "signal_masks": signal_masks,
            "quantification": quantification,
            "warnings": list(output.get("warnings") or []),
            "medical_boundary": (
                "实时单帧荧光/灌注风险提示，需医生复核；" "当前模型尚无真实颌骨骨髓炎术中 ICG 临床性能验证。"
            ),
            "disclaimer_context": disclaimer_context(),
        }

    def warmup(self, model_id: str | None = None) -> dict[str, Any]:
        """Load the configured live model once before the first camera frame arrives."""

        model_id = str(model_id or self.default_model_id)
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

    def _adapter(self, model_id: str) -> Any:
        cached = self._adapters.get(model_id)
        if cached is not None:
            return cached
        model_mapping = _runtime_model_mapping(self._runtime, model_id)
        if model_mapping is None:
            raise ValueError(f"Live frame model {model_id} is not configured.")
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
                metadata={"roi_hints": [], "predecoded_rgb": rgb},
            )
        )
        payload = result.to_dict()
        segmentation_mask = _record(payload.get("segmentation_mask"))
        if segmentation_mask.get("path"):
            return payload
        raise RuntimeError(f"Live frame model {model_id} did not produce a segmentation mask.")

    @staticmethod
    def _load_model_if_needed(adapter: Any) -> None:
        load_model = getattr(adapter, "_load_model", None)
        if callable(load_model) and getattr(adapter, "_model", None) is None:
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

        from src.models.keyframe_segmenter import select_torch_device

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


def _decode_rgb_image(frame_bytes: bytes) -> np.ndarray:
    try:
        with Image.open(BytesIO(frame_bytes)) as image:
            return np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
    except (OSError, ValueError) as error:
        raise ValueError("Live frame is not a readable image.") from error


def _safe_filename(value: str) -> str:
    suffix = Path(value).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        suffix = ".jpg"
    return f"frame{suffix}"


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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
