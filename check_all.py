from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(command: list[str], failures: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        failures.append(" ".join(command))


def require_text(path: Path, text: str, failures: list[str]) -> None:
    if not path.exists():
        failures.append(f"missing {path}")
        return
    content = path.read_text(encoding="utf-8", errors="ignore")
    if text not in content:
        failures.append(f"{path} missing required text: {text}")


def validate_json_command(command: list[str], failures: list[str]) -> dict:
    completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode:
        failures.append(" ".join(command))
        return {}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid JSON from {' '.join(command)}: {exc}")
        return {}


def require_json_safety(path: Path, failures: list[str]) -> None:
    if not path.exists():
        failures.append(f"missing {path}")
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"invalid JSON in {path}: {exc}")
        return
    if payload.get("clinical_claim_allowed") is not False:
        failures.append(f"{path} must declare clinical_claim_allowed=false")
    if "Research prototype" not in str(payload.get("disclaimer", "")):
        failures.append(f"{path} missing research prototype disclaimer")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []
    run([sys.executable, "check_env.py", *(["--strict"] if args.strict else [])], failures)
    run([sys.executable, "-m", "pytest", "tests/unit", "tests/smoke", "tests/integration"], failures)
    inventory = validate_json_command(
        [sys.executable, "scripts/model_inventory.py", "--config", "configs/inference/osteo_vision.yml"],
        failures,
    )
    if inventory and not any(row.get("spec", {}).get("family") == "fixture" and row.get("status", {}).get("available") for row in inventory.get("models", [])):
        failures.append("model inventory missing available fixture adapter")
    v3_root = Path("pytest_tmp/check_all_v3")
    experiment = validate_json_command(
        [
            sys.executable,
            "scripts/new_experiment.py",
            "--experiment-id",
            "check_all_v3",
            "--output-dir",
            str(v3_root / "experiments"),
            "--run-output-dir",
            str(v3_root / "runs"),
            "--force",
        ],
        failures,
    )
    experiment_path = experiment.get("experiment_spec")
    run_payload = {}
    if experiment_path:
        run_payload = validate_json_command([sys.executable, "scripts/run_experiment.py", "--spec", experiment_path], failures)
    run_dir = run_payload.get("run_dir")
    if run_dir:
        validate_json_command(
            [
                sys.executable,
                "scripts/promote_model.py",
                "--run-dir",
                run_dir,
                "--output",
                str(v3_root / "runtime_promotion_draft.json"),
            ],
            failures,
        )
        for name in ["model_card.json", "checkpoint_manifest.json", "promotion_record.json"]:
            require_json_safety(Path(run_dir) / name, failures)
    else:
        failures.append("V3 experiment run did not produce run_dir")
    require_text(Path("configs/tasks/osteo_vision.yml"), "clinical_claim_allowed: false", failures)
    require_text(Path("README_CN.md"), "不是临床诊断", failures)
    report_path = Path("artifacts/reports/final_validation.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if failures:
        report_path.write_text("# Final Validation\n\nFAILED\n\n" + "\n".join(f"- {item}" for item in failures), encoding="utf-8")
        return 1
    report_path.write_text("# Final Validation\n\nPASSED\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
