from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.main import analyze_fluorescence_pair


def test_analyze_fluorescence_pair_returns_visual_outputs(tmp_path: Path) -> None:
    white = np.zeros((20, 20, 3), dtype=np.uint8)
    white[..., 0] = 90
    white[..., 1] = 100
    white[..., 2] = 110
    fluorescence = np.zeros((20, 20), dtype=np.uint8)
    fluorescence[5:15, 5:15] = 240
    white_path = tmp_path / "white.png"
    fluorescence_path = tmp_path / "fluorescence.png"
    Image.fromarray(white).save(white_path)
    Image.fromarray(fluorescence).save(fluorescence_path)
    config_path = tmp_path / "config.yml"
    visual_dir = tmp_path / "visual"
    reports_dir = tmp_path / "reports"
    config_path.write_text(
        "\n".join(
            [
                "reports:",
                f"  output_dir: {reports_dir.as_posix()}",
                f"  visual_dir: {visual_dir.as_posix()}",
            ]
        ),
        encoding="utf-8",
    )

    result_md, warnings_md, overlay, heatmap, normalized, report = analyze_fluorescence_pair(
        white_path,
        fluorescence_path,
        alpha=0.5,
        threshold=0.6,
        colormap="amber",
        config_path=str(config_path),
    )

    assert "Status: `completed`" in result_md
    assert "research_prototype_only" in warnings_md
    for output_path in [overlay, heatmap, normalized, report]:
        assert output_path
        assert Path(output_path).exists()
