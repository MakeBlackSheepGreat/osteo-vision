from __future__ import annotations

import json
import subprocess
import sys


def test_benchmark_cli_completes(tmp_path) -> None:
    output = tmp_path / "benchmark"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/benchmark.py",
            "--config",
            "configs/inference/demo.yml",
            "--manifest",
            "tests/fixtures/benchmark_manifest.csv",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    run_dirs = [path for path in output.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "predictions.csv").exists()
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "benchmark_report.json").exists()
    assert (run_dir / "threshold_analysis.md").exists()
    assert (run_dir / "config_snapshot.yml").exists()
    assert (run_dir / "task_package_snapshot.yml").exists()
    assert (run_dir / "model_specs.json").exists()
    payload = json.loads((run_dir / "benchmark_report.json").read_text(encoding="utf-8"))
    assert payload["model_version"] == "micf-fixture-v0"

