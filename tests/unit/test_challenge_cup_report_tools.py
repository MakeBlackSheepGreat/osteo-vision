from __future__ import annotations

import pytest

from scripts.generate_thesis_docx import resolve_report_image_path
from tools.build_challenge_cup_figures import runtime_metrics


def test_report_image_path_stays_within_the_report_package() -> None:
    assert resolve_report_image_path("assets/sources/d083_frame_05_raw.jpg").is_file()

    with pytest.raises(ValueError, match="escapes the report package"):
        resolve_report_image_path("../../../../frontend/public/showcase/d083_frame_05_overlay.png")


def test_runtime_chart_metrics_are_loaded_from_versioned_reports() -> None:
    assert runtime_metrics() == {
        "four_k_model_p95_ms": 724.432,
        "four_k_e2e_p95_ms": 5776.683,
        "live_e2e_p95_ms": 176.457,
        "live_model_p95_ms": 36.377,
    }
