from __future__ import annotations

import numpy as np
import pytest

from osteo_vision_core.navigation.ocamcalib import OcamCalibError, OcamCalibPolynomialV1


def _c3vd_calibration() -> OcamCalibPolynomialV1:
    return OcamCalibPolynomialV1(
        width=1350,
        height=1080,
        cx=678.544839263292,
        cy=542.975887548343,
        a0=769.243600037458,
        a1=0.0,
        a2=-0.000812770624150226,
        a3=6.25674244578925e-07,
        a4=-1.19662182144280e-09,
        c=0.999986882249990,
        d=0.00288273829525059,
        e=-0.00296316513429569,
    )


def test_c3vd_polynomial_projects_independent_known_radius_vectors() -> None:
    calibration = _c3vd_calibration()
    rho = 100.0
    z = (
        calibration.a0
        + calibration.a1 * rho
        + calibration.a2 * rho**2
        + calibration.a3 * rho**3
        + calibration.a4 * rho**4
    )

    projected = calibration.project_camera_points(np.asarray([[rho, 0.0, z], [0.0, rho, z]], dtype=np.float64))

    assert projected[0] == pytest.approx([778.543527488291, 543.2641613778682], abs=1e-8)
    assert projected[1] == pytest.approx([678.2485227498624, 642.975887548343], abs=1e-8)


def test_optical_axis_projects_to_c3vd_principal_point() -> None:
    projected = _c3vd_calibration().project_camera_points(
        np.asarray([[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]], dtype=np.float64)
    )
    assert np.allclose(
        projected,
        [[678.544839263292, 542.975887548343]] * 2,
        atol=1e-12,
        rtol=0.0,
    )


def test_singular_c3vd_affine_stretch_is_rejected() -> None:
    calibration = _c3vd_calibration()
    invalid = OcamCalibPolynomialV1(
        **{
            **calibration.__dict__,
            "c": 0.0,
            "d": 0.0,
            "e": 0.0,
        }
    )
    with pytest.raises(OcamCalibError) as exc_info:
        invalid.validate()

    assert exc_info.value.code == "ocam_affine_stretch_singular"
