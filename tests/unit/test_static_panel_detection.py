from __future__ import annotations

import numpy as np
from PIL import Image

from src.datasets.static_panel_detection import crop_quality_warnings, detect_panel_crop_suggestions


def _grid_image(
    columns: int, rows: int, *, panel_width: int = 120, panel_height: int = 100, gutter: int = 8
) -> Image.Image:
    width = columns * panel_width + (columns - 1) * gutter
    height = rows * panel_height + (rows - 1) * gutter
    array = np.full((height, width, 3), 255, dtype=np.uint8)
    for row in range(rows):
        for column in range(columns):
            x = column * (panel_width + gutter)
            y = row * (panel_height + gutter)
            array[y : y + panel_height, x : x + panel_width] = (
                25 + column * 20,
                45 + row * 30,
                70 + column * 5,
            )
    return Image.fromarray(array)


def test_detects_regular_five_by_two_panel_grid() -> None:
    suggestions = detect_panel_crop_suggestions(_grid_image(5, 2))

    assert len(suggestions) == 10
    assert all(item.quality_status in {"pass", "warning"} for item in suggestions)
    assert suggestions[0].bbox == {"x": 0, "y": 0, "width": 123, "height": 103}
    assert suggestions[-1].bbox["x"] > suggestions[0].bbox["x"]
    assert suggestions[-1].bbox["y"] > suggestions[0].bbox["y"]


def test_expected_two_panel_fallback_handles_weak_seam() -> None:
    image = Image.new("RGB", (600, 360), color=(40, 70, 90))

    suggestions = detect_panel_crop_suggestions(image, expected_panel_count=2)

    assert [item.bbox for item in suggestions] == [
        {"x": 0, "y": 0, "width": 300, "height": 360},
        {"x": 300, "y": 0, "width": 300, "height": 360},
    ]


def test_crop_quality_flags_full_image_and_low_resolution() -> None:
    image = Image.new("RGB", (120, 80), color=(30, 50, 70))

    warnings = crop_quality_warnings(image, {"x": 0, "y": 0, "width": 120, "height": 80})

    assert "crop_dimension_below_96px" in warnings
    assert "crop_near_full_source_image" in warnings


def test_crop_quality_rejects_out_of_bounds_box() -> None:
    image = Image.new("RGB", (200, 120), color=(30, 50, 70))

    warnings = crop_quality_warnings(image, {"x": 180, "y": 0, "width": 40, "height": 100})

    assert warnings == ["crop_out_of_bounds"]
