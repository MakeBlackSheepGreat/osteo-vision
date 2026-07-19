from __future__ import annotations

import json

import torch

from scripts.benchmark_d024_frontier_segmentation_models import (
    frontier_evidence_sources,
    frontier_model_catalog,
    render_report,
    write_summary_reports,
)
from scripts.benchmark_d024_segmentation_models import model_catalog as baseline_model_catalog


def test_frontier_catalog_has_ten_new_models() -> None:
    catalog = frontier_model_catalog()

    assert len(catalog) == 10
    assert not (set(catalog) & set(baseline_model_catalog()))
    assert {"umamba_bottleneck_proxy", "segmamba_multiscale_proxy", "mednext_tiny_proxy"} <= set(catalog)


def test_frontier_models_forward_shape() -> None:
    shape = (16, 16, 16)
    x = torch.randn(1, 1, *shape)

    for candidate in frontier_model_catalog().values():
        model = candidate.constructor(shape, 7)
        with torch.no_grad():
            y = model(x)
        assert tuple(y.shape) == (1, 7, *shape), candidate.model_id


def test_frontier_report_paths_and_sources(tmp_path) -> None:
    payload = {
        "run_id": "test",
        "data": {
            "case_count": 100,
            "fold": 0,
            "train_count": 80,
            "val_count": 20,
            "target_shape": [16, 16, 16],
        },
        "config": {"max_train_batches": 1, "max_val_cases": 1},
        "environment": {"device": "cpu", "torch_version": torch.__version__, "cuda_device_name": None},
        "results": [
            {
                "model_id": "mednext_tiny_proxy",
                "display_name": "MedNeXt Tiny Proxy",
                "status": "completed",
                "foreground_mean_dice": 0.1,
                "foreground_mean_iou": 0.05,
                "parameter_count": 1,
                "train_loss": 1.0,
                "elapsed_seconds": 1.0,
                "peak_memory_mb": None,
            }
        ],
        "model_sources": [source.__dict__ for source in frontier_evidence_sources()],
        "paths": {"summary_json": "summary.json", "results_csv": "results.csv"},
    }

    paths = write_summary_reports(payload, tmp_path)
    zh = tmp_path / "d024_frontier_10_model_benchmark_zh.md"
    en = tmp_path / "d024_frontier_10_model_benchmark_en.md"

    assert paths == {"zh_report": str(zh), "en_report": str(en)}
    assert zh.exists()
    assert en.exists()
    assert "第二轮前沿分割模型" in zh.read_text(encoding="utf-8")
    assert "Frontier Segmentation" in en.read_text(encoding="utf-8")


def test_frontier_report_renders_json_serializable_payload() -> None:
    payload = {
        "run_id": "test",
        "data": {
            "case_count": 100,
            "fold": 0,
            "train_count": 80,
            "val_count": 20,
            "target_shape": [16, 16, 16],
        },
        "config": {"max_train_batches": 1, "max_val_cases": 1},
        "environment": {"device": "cpu", "torch_version": torch.__version__, "cuda_device_name": None},
        "results": [],
        "model_sources": [source.__dict__ for source in frontier_evidence_sources()],
        "paths": {
            "summary_json": "summary.json",
            "results_csv": "results.csv",
            "zh_report": "zh.md",
            "en_report": "en.md",
        },
    }

    rendered = render_report(json.loads(json.dumps(payload)), language="en")

    assert "SAM-Med3D" in rendered
    assert "Medical Boundary" in rendered
