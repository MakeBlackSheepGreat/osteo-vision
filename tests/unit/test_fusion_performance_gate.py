from __future__ import annotations

import numpy as np
from PIL import Image

from osteo_vision_core.preprocess import accelerated_fusion
from tools.run_fusion_performance_gate import (
    _build_shifted_occluded_input,
    _summary,
    _task2_compute_ms,
)


def test_fusion_gate_summary_uses_interpolated_p95() -> None:
    result = _summary([10.0, 20.0, 30.0, 40.0, 50.0])

    assert result["p50"] == 30.0
    assert result["p95"] == 48.0
    assert result["mean"] == 30.0


def test_fusion_gate_builds_shifted_occluded_input(tmp_path) -> None:
    source = np.tile(np.arange(96, dtype=np.uint8), (64, 1))
    source_path = tmp_path / "source.jpg"
    destination = tmp_path / "derived" / "shifted.jpg"
    Image.fromarray(source).save(source_path, quality=100)

    _build_shifted_occluded_input(source_path, destination, shift_x=5, shift_y=-3)

    with Image.open(destination) as image:
        derived = np.asarray(image.convert("L"))
    assert derived.shape == source.shape
    assert destination.is_file()
    assert float(derived[:16, 72:90].mean()) < float(source[:16, 72:90].mean())


def test_task2_compute_excludes_ai_and_evidence_io() -> None:
    assert _task2_compute_ms(40.125, 31.25) == 71.375


def test_fusion_accelerator_warmup_is_cached(monkeypatch) -> None:
    accelerated_fusion._FUSION_WARMUP_CACHE.clear()
    calls: list[tuple[int, int]] = []

    def fake_blend(white, fluorescence, **_kwargs):
        calls.append((white.shape[1], white.shape[0]))
        normalized = np.zeros(fluorescence.shape, dtype=np.float32)
        pseudo = np.zeros((*fluorescence.shape, 3), dtype=np.uint8)
        return (
            normalized,
            pseudo,
            pseudo,
            {
                "backend": "torch_cuda",
                "device": "cuda",
                "peak_gpu_memory_mb": 12.5,
            },
        )

    monkeypatch.setattr(accelerated_fusion, "accelerated_normalize_pseudocolor_blend", fake_blend)

    first = accelerated_fusion.warmup_fusion_accelerator(width=64, height=48)
    second = accelerated_fusion.warmup_fusion_accelerator(width=64, height=48)

    assert calls == [(64, 48)]
    assert first["gpu_ready"] is True
    assert first["cached"] is False
    assert second["cached"] is True
