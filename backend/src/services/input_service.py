from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from PIL import Image

from backend.src.domains.cases.enums import CaseStatus, InputChannel, QualityFlagCode
from backend.src.domains.cases.schemas import CaseInputAsset, CaseRecord, InputCreateRequest, QualityFlag
from src.preprocess.input_validation import validate_input


class InputService:
    def __init__(self, allowed_roots: list[str | Path] | None = None) -> None:
        self.allowed_roots = [Path(root).expanduser().resolve() for root in (allowed_roots or [])]

    def add_inputs(
        self,
        case: CaseRecord,
        inputs: list[InputCreateRequest],
        *,
        replace_existing_channels: bool = True,
    ) -> CaseRecord:
        assets = list(case.inputs)
        for item in inputs:
            if replace_existing_channels:
                # 同一病例每个采集通道只保留当前选择的官方输入，防止重选文件后仍由旧输入参与分析。
                assets = [asset for asset in assets if asset.channel != item.channel]
            assets.append(self._asset_from_request(item))
        quality_flags = self.case_quality_flags(assets)
        status = CaseStatus.LOADED if assets else case.status
        return case.model_copy(update={"inputs": assets, "quality_flags": quality_flags, "status": status})

    def _asset_from_request(self, item: InputCreateRequest) -> CaseInputAsset:
        if item.channel == InputChannel.VIDEO and item.path.startswith("camera://"):
            camera_metadata = {
                "input_type": "browser_camera",
                "metadata_status": "live_preview",
                **item.metadata,
            }
            return CaseInputAsset(
                input_id=f"input_{uuid4().hex[:10]}",
                channel=item.channel,
                path=item.path,
                mime_type=item.mime_type or "application/x-browser-camera",
                dimensions=[],
                metadata=camera_metadata,
                quality_flags=[],
            )
        source = self._validate_source_path(item.path)
        summary = validate_input(source)
        metadata: dict[str, Any] = {"input_type": summary.input_type, **summary.metadata, **item.metadata}
        if item.channel == InputChannel.DEVICE_OVERLAY:
            metadata = {
                **metadata,
                "derived_by_device": True,
                "analysis_input_allowed": False,
                "evidence_role": "device_display_reference",
            }
        flags = [_warning_to_flag(warning) for warning in summary.warnings]
        if item.channel == InputChannel.FLUORESCENCE:
            flags.extend(_fluorescence_intensity_flags(source))
        dimensions = _dimensions_from_metadata(metadata)
        return CaseInputAsset(
            input_id=f"input_{uuid4().hex[:10]}",
            channel=item.channel,
            path=str(source),
            mime_type=item.mime_type,
            dimensions=dimensions,
            metadata=metadata,
            quality_flags=flags,
        )

    def _validate_source_path(self, value: str | Path) -> Path:
        # Unit-level callers may construct synthetic/nonexistent paths; the API route
        # supplies allowed_roots and enables the strict filesystem boundary.
        if not self.allowed_roots:
            return Path(value)
        requested = Path(value).expanduser()
        if not requested.is_absolute():
            requested = Path.cwd() / requested
        if requested.is_symlink() or any(part.is_symlink() for part in requested.parents):
            raise ValueError("Symlink input paths are not allowed")
        try:
            resolved = requested.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError("Input path does not exist") from exc
        if self.allowed_roots and not any(_is_relative_to(resolved, root) for root in self.allowed_roots):
            raise ValueError("Input path is outside the permitted data roots")
        if not resolved.is_file() and not resolved.is_dir():
            raise ValueError("Input path must reference a regular file or directory")
        return resolved

    def case_quality_flags(self, assets: list[CaseInputAsset]) -> list[QualityFlag]:
        flags: list[QualityFlag] = []
        white = next((asset for asset in assets if asset.channel == InputChannel.WHITE_LIGHT), None)
        fluor = next((asset for asset in assets if asset.channel == InputChannel.FLUORESCENCE), None)
        overlay = next((asset for asset in assets if asset.channel == InputChannel.DEVICE_OVERLAY), None)
        if white and fluor and white.dimensions and fluor.dimensions and white.dimensions != fluor.dimensions:
            flags.append(
                QualityFlag(
                    code=QualityFlagCode.MISMATCHED,
                    message=(
                        "White-light and fluorescence inputs differ in dimensions; the current fallback uses "
                        "resize-only alignment and requires physician review."
                    ),
                    blocking=False,
                    details={"white_light": white.dimensions, "fluorescence": fluor.dimensions},
                )
            )
        if overlay and overlay.dimensions:
            reference = white or fluor
            if reference and reference.dimensions and overlay.dimensions != reference.dimensions:
                flags.append(
                    QualityFlag(
                        code=QualityFlagCode.MISMATCHED,
                        message="Device overlay dimensions differ from the source image channel; evidence comparison requires review.",
                        blocking=False,
                        details={
                            "device_overlay": overlay.dimensions,
                            "reference_channel": reference.channel.value,
                            "reference_dimensions": reference.dimensions,
                        },
                    )
                )
        for asset in assets:
            flags.extend(asset.quality_flags)
        return flags


def _warning_to_flag(warning: dict[str, Any]) -> QualityFlag:
    code = str(warning.get("code") or "")
    flag_code = (
        QualityFlagCode.OFFICIAL_PROFILE_MISMATCH
        if code.startswith("official_") or code == "ffprobe_unavailable"
        else QualityFlagCode.UNUSABLE
    )
    return QualityFlag(
        code=flag_code,
        message=str(warning.get("message") or "Input cannot be used."),
        blocking=bool(warning.get("blocking")),
        details={"source_warning_code": code, **dict(warning.get("details") or {})},
    )


def _dimensions_from_metadata(metadata: dict[str, Any]) -> list[int]:
    width = metadata.get("width")
    height = metadata.get("height")
    if width and height:
        return [int(width), int(height)]
    return []


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _fluorescence_intensity_flags(path: str | Path) -> list[QualityFlag]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return []
    try:
        with Image.open(p) as image:
            array = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    except Exception:
        return []
    mean = float(np.mean(array))
    p95 = float(np.percentile(array, 95))
    flags: list[QualityFlag] = []
    if p95 < 0.08:
        flags.append(
            QualityFlag(code=QualityFlagCode.WEAK_SIGNAL, message="Fluorescence signal is weak.", details={"p95": p95})
        )
    if mean > 0.92:
        flags.append(
            QualityFlag(
                code=QualityFlagCode.OVEREXPOSED,
                message="Fluorescence image appears overexposed.",
                details={"mean": mean},
            )
        )
    if mean < 0.02:
        flags.append(
            QualityFlag(
                code=QualityFlagCode.UNDEREXPOSED,
                message="Fluorescence image appears underexposed.",
                details={"mean": mean},
            )
        )
    return flags
