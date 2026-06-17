from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_v3_experiment_cli_flow(tmp_path) -> None:
    spec_result = subprocess.run(
        [
            sys.executable,
            "scripts/new_experiment.py",
            "--experiment-id",
            "smoke_v3",
            "--output-dir",
            str(tmp_path / "experiments"),
            "--run-output-dir",
            str(tmp_path / "runs"),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert spec_result.returncode == 0, spec_result.stderr
    spec_payload = json.loads(spec_result.stdout)
    spec_path = Path(spec_payload["experiment_spec"])
    assert spec_path.exists()

    run_result = subprocess.run(
        [sys.executable, "scripts/run_experiment.py", "--spec", str(spec_path)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert run_result.returncode == 0, run_result.stderr
    run_payload = json.loads(run_result.stdout)
    run_dir = Path(run_payload["run_dir"])
    assert (run_dir / "training_report.json").exists()
    assert (run_dir / "evaluation_report.json").exists()
    assert (run_dir / "oof_predictions.csv").exists()
    assert (run_dir / "model_card.json").exists()
    assert (run_dir / "checkpoint_manifest.json").exists()
    assert (run_dir / "promotion_record.json").exists()

    promotion_result = subprocess.run(
        [
            sys.executable,
            "scripts/promote_model.py",
            "--run-dir",
            str(run_dir),
            "--output",
            str(tmp_path / "runtime_promotion_draft.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert promotion_result.returncode == 0, promotion_result.stderr
    promotion_payload = json.loads(promotion_result.stdout)
    assert Path(promotion_payload["output_path"]).exists()
    assert promotion_payload["runtime_patch"]["runtime"]["models"][0]["clinical_claim_allowed"] is False
