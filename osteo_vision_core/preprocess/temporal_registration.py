from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from osteo_vision_core.preprocess.accelerated_fusion import register_adaptive_multiscale


@dataclass
class TemporalRegistrationSession:
    """Stateful paired-frame registration with scene-change and optical-context resets."""

    temporal_smoothing_alpha: float = 0.7
    max_temporal_jump_fraction: float = 0.03
    magnification_reset_fraction: float = 0.1
    working_distance_reset_mm: float = 20.0
    deformation_smoothing_alpha: float = 0.55
    _matrix: np.ndarray | None = field(default=None, init=False, repr=False)
    _deformation_grid: np.ndarray | None = field(default=None, init=False, repr=False)
    _magnification: float | None = field(default=None, init=False, repr=False)
    _working_distance_mm: float | None = field(default=None, init=False, repr=False)
    _frame_index: int = field(default=0, init=False, repr=False)

    def register(
        self,
        reference_rgb: np.ndarray,
        moving_gray: np.ndarray,
        *,
        magnification: float | None = None,
        working_distance_mm: float | None = None,
        prefer_gpu: bool = True,
        keep_registered_on_device: bool = False,
    ) -> tuple[Any, dict[str, Any]]:
        reset_reason = self._context_reset_reason(magnification, working_distance_mm)
        if reset_reason:
            self._matrix = None
            self._deformation_grid = None
        registered, report = register_adaptive_multiscale(
            reference_rgb,
            moving_gray,
            prefer_gpu=prefer_gpu,
            previous_matrix=self._matrix,
            temporal_smoothing_alpha=self.temporal_smoothing_alpha,
            max_temporal_jump_fraction=self.max_temporal_jump_fraction,
            previous_deformation_grid=self._deformation_grid,
            deformation_smoothing_alpha=self.deformation_smoothing_alpha,
            return_device_tensor=keep_registered_on_device,
        )
        self._frame_index += 1
        matrix = report.get("matrix_2x3")
        if report.get("applied") is True and isinstance(matrix, list):
            parsed = np.asarray(matrix, dtype=np.float32)
            if parsed.shape == (2, 3) and np.isfinite(parsed).all():
                self._matrix = parsed
        local_deformation = report.get("local_deformation")
        deformation_grid = (
            local_deformation.get("coarse_displacement_grid_xy") if isinstance(local_deformation, dict) else None
        )
        if report.get("applied") is True and deformation_grid is not None:
            parsed_grid = np.asarray(deformation_grid, dtype=np.float32)
            if parsed_grid.ndim == 3 and parsed_grid.shape[2] == 2 and np.isfinite(parsed_grid).all():
                self._deformation_grid = parsed_grid
            else:
                self._deformation_grid = None
        else:
            self._deformation_grid = None
        self._magnification = _positive_or_none(magnification)
        self._working_distance_mm = _positive_or_none(working_distance_mm)
        report["temporal_session"] = {
            "frame_index": self._frame_index,
            "context_reset": reset_reason is not None,
            "context_reset_reason": reset_reason,
            "magnification": self._magnification,
            "working_distance_mm": self._working_distance_mm,
            "state_available": self._matrix is not None,
            "local_deformation_state_available": self._deformation_grid is not None,
        }
        return registered, report

    def reset(self, reason: str = "manual_reset") -> dict[str, Any]:
        had_state = self._matrix is not None
        self._matrix = None
        self._deformation_grid = None
        self._magnification = None
        self._working_distance_mm = None
        self._frame_index = 0
        return {"reset": True, "reason": str(reason), "had_state": had_state}

    def _context_reset_reason(
        self,
        magnification: float | None,
        working_distance_mm: float | None,
    ) -> str | None:
        current_mag = _positive_or_none(magnification)
        current_distance = _positive_or_none(working_distance_mm)
        if self._magnification and current_mag:
            relative_change = abs(current_mag - self._magnification) / self._magnification
            if relative_change > self.magnification_reset_fraction:
                return "magnification_change"
        if self._working_distance_mm and current_distance:
            if abs(current_distance - self._working_distance_mm) > self.working_distance_reset_mm:
                return "working_distance_change"
        return None


def _positive_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    parsed = float(value)
    return parsed if np.isfinite(parsed) and parsed > 0.0 else None
