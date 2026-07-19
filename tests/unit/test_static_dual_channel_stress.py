from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from src.models.dual_channel_segmenter import TinyDualChannelSegmenter2D
from tools.run_static_dual_channel_stress import run_static_dual_channel_stress


def test_runs_unlabeled_near_domain_pair_stress_without_accuracy_claim(tmp_path: Path) -> None:
    white_path = tmp_path / "white.png"
    fluorescence_path = tmp_path / "fluorescence.png"
    white = np.zeros((80, 120, 3), dtype=np.uint8)
    white[15:65, 20:100] = (150, 110, 90)
    fluorescence = np.zeros((80, 120), dtype=np.uint8)
    fluorescence[20:60, 30:90] = 210
    Image.fromarray(white).save(white_path)
    Image.fromarray(fluorescence).save(fluorescence_path)
    manifest_path = tmp_path / "pairs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "pair_id": "fixture_pair",
                        "source_group_id": "fixture_group",
                        "pair_alignment": "weak_sequential",
                        "white_image_path": str(white_path),
                        "fluorescence_image_path": str(fluorescence_path),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    checkpoint_path = tmp_path / "dual.pt"
    model = TinyDualChannelSegmenter2D(base_channels=2)
    torch.save(
        {
            "model_config": {"base_channels": 2},
            "state_dict": model.state_dict(),
            "selected_mode": "early_fusion",
        },
        checkpoint_path,
    )

    result = run_static_dual_channel_stress(
        manifest_path,
        checkpoint_path,
        tmp_path / "output",
        tmp_path / "reports",
        image_shape=(32, 48),
        threshold=0.5,
        device_policy="cpu",
    )

    assert result["pair_count"] == 1
    assert result["runtime_allowed"] is False
    assert result["offline_benchmark_only"] is True
    assert result["clinical_claim_allowed"] is False
    assert result["rows"][0]["ground_truth_available"] is False
    assert result["rows"][0]["registration"]["status"] == "skipped"
    assert "weak_sequential_pair" in result["rows"][0]["risk_flags"]
    assert set(result["mode_summary"]) == {
        "white_only",
        "fluorescence_only",
        "early_fusion",
        "intermediate_fusion",
        "context_fusion",
    }
    assert Path(result["json_path"]).is_file()
    assert Path(result["report_zh_path"]).is_file()
