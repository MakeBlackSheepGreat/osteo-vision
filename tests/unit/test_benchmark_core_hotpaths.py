from __future__ import annotations

from tools.benchmark_core_hotpaths import run_benchmark


def test_core_hotpath_benchmark_preserves_reference_outputs() -> None:
    payload = run_benchmark(repeats=1)

    results = payload["results"]
    assert results["connected_components"]["outputs_match"] is True
    assert results["quality_evaluation"]["outputs_match"] is True
    assert results["nearest_pose_lookup"]["outputs_match"] is True
    assert results["job_registry_cached_lookup"]["outputs_match"] is True
    assert results["quality_evaluation"]["evaluation_shape"] == [2160, 3840]
    assert results["quality_evaluation"]["full_resolution_quality_metrics"] is True
    assert results["quality_evaluation"]["full_resolution_evidence_preserved"] is True
