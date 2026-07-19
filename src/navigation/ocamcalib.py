from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

OCAMCALIB_POLYNOMIAL_V1 = "scaramuzza_ocamcalib_polynomial_v1"
_ROOT_IMAGINARY_TOLERANCE = 1e-7
_AXIS_EPSILON = 1e-20


class OcamCalibError(ValueError):
    """Raised when an omnidirectional calibration or projection is unusable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class OcamCalibPolynomialV1:
    width: int
    height: int
    cx: float
    cy: float
    a0: float
    a1: float
    a2: float
    a3: float
    a4: float
    c: float
    d: float
    e: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> OcamCalibPolynomialV1:
        image_size = value.get("image_size_px")
        if not isinstance(image_size, (list, tuple)) or len(image_size) != 2:
            raise OcamCalibError(
                "ocam_image_size_missing_or_invalid",
                "OCamCalib image_size_px must contain width and height.",
            )
        parameters = value.get("camera_parameters", value)
        if not isinstance(parameters, Mapping):
            raise OcamCalibError(
                "ocam_parameters_missing_or_invalid",
                "OCamCalib camera_parameters must be an object.",
            )
        try:
            calibration = cls(
                width=int(image_size[0]),
                height=int(image_size[1]),
                **{
                    field: float(parameters[field])
                    for field in ("cx", "cy", "a0", "a1", "a2", "a3", "a4", "c", "d", "e")
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OcamCalibError(
                "ocam_parameters_missing_or_invalid",
                "OCamCalib parameters must contain finite cx, cy, a0-a4, c, d and e.",
            ) from exc
        calibration.validate()
        return calibration

    def validate(self) -> None:
        scalars = np.asarray(
            [self.cx, self.cy, self.a0, self.a1, self.a2, self.a3, self.a4, self.c, self.d, self.e],
            dtype=np.float64,
        )
        if self.width <= 0 or self.height <= 0 or not np.isfinite(scalars).all():
            raise OcamCalibError(
                "ocam_parameters_missing_or_invalid",
                "OCamCalib dimensions must be positive and all parameters must be finite.",
            )
        if not 0 <= self.cx < self.width or not 0 <= self.cy < self.height:
            raise OcamCalibError(
                "ocam_principal_point_invalid",
                "OCamCalib principal point must lie inside the image.",
            )
        stretch = np.asarray([[self.c, self.e], [self.d, 1.0]], dtype=np.float64)
        if abs(float(np.linalg.det(stretch))) <= 1e-12:
            raise OcamCalibError(
                "ocam_affine_stretch_singular",
                "OCamCalib affine stretch matrix must be invertible.",
            )
        if abs(self.a4) <= 1e-18:
            raise OcamCalibError(
                "ocam_polynomial_invalid",
                "C3VD polynomial v1 requires a non-zero fourth-order coefficient.",
            )

    def project_camera_points(
        self,
        points: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Project camera-space points using C3VD's Scaramuzza polynomial."""
        array = np.asarray(points, dtype=np.float64)
        if array.ndim != 2 or array.shape[1] != 3 or not np.isfinite(array).all():
            raise OcamCalibError(
                "ocam_projection_points_invalid",
                "OCamCalib projection points must be a finite Nx3 array.",
            )

        output = np.empty((array.shape[0], 2), dtype=np.float64)
        for index, (x, y, z) in enumerate(array):
            radial_norm = float(np.hypot(x, y))
            if radial_norm <= _AXIS_EPSILON:
                raw_x = 0.0
                raw_y = 0.0
            else:
                slope = float(z / (radial_norm + _AXIS_EPSILON))
                coefficients = np.asarray(
                    [self.a4, self.a3, self.a2, self.a1 - slope, self.a0],
                    dtype=np.float64,
                )
                roots = np.roots(coefficients)
                positive_real_roots = sorted(
                    float(root.real)
                    for root in roots
                    if root.real > 0.0
                    and abs(float(root.imag)) <= _ROOT_IMAGINARY_TOLERANCE * max(1.0, abs(float(root.real)))
                )
                rho = positive_real_roots[0] if positive_real_roots else 0.0
                raw_x = float(x / (radial_norm + _AXIS_EPSILON) * rho)
                raw_y = float(y / (radial_norm + _AXIS_EPSILON) * rho)

            # GLM mat2(c, d, e, 1) is column-major in the C3VD renderer.
            output[index, 0] = self.c * raw_x + self.e * raw_y + self.cx
            output[index, 1] = self.d * raw_x + raw_y + self.cy

        if not np.isfinite(output).all():
            raise OcamCalibError(
                "ocam_projection_pixels_non_finite",
                "OCamCalib projected pixels must be finite.",
            )
        return output
