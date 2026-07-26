from __future__ import annotations

from tools.run_task2_temporal_registration_gate import _longest_true_run, _summary, _translation_jitter


def test_temporal_gate_summary_and_jitter_are_deterministic() -> None:
    records = [
        {"magnification": 2.0, "working_distance_mm": 300.0, "raw": [1.0, 2.0], "smooth": [1.2, 2.0]},
        {"magnification": 2.0, "working_distance_mm": 300.0, "raw": [2.0, 2.0], "smooth": [1.4, 2.0]},
        {"magnification": 2.5, "working_distance_mm": 350.0, "raw": [4.0, 5.0], "smooth": [4.1, 5.0]},
        {"magnification": 2.5, "working_distance_mm": 350.0, "raw": [5.0, 5.0], "smooth": [4.3, 5.0]},
    ]

    assert _translation_jitter(records, "smooth") < _translation_jitter(records, "raw")
    assert _summary([10.0, 20.0, 30.0, 40.0, 50.0])["p95"] == 48.0
    assert _longest_true_run([False, True, True, False, True]) == 2
