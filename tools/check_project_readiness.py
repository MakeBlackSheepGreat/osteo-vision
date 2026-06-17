"""Read-only readiness checks for the osteo-vision development workspace."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def print_section(title: str) -> None:
    print(f"\n== {title} ==")


def check_file(path: str) -> bool:
    exists = (ROOT / path).exists()
    print(f"{status(exists):8} {path}")
    return exists


def check_dir(path: str) -> bool:
    exists = (ROOT / path).is_dir()
    print(f"{status(exists):8} {path}/")
    return exists


def read_csv_with_encoding(path: Path, encoding: str) -> list[dict[str, str]] | None:
    try:
        with path.open("r", encoding=encoding, newline="") as f:
            return list(csv.DictReader(f))
    except UnicodeDecodeError:
        return None


def check_utf8_csv(path: str) -> None:
    target = ROOT / path
    if not target.exists():
        print(f"MISSING  {path}")
        return
    rows = read_csv_with_encoding(target, "utf-8-sig")
    if rows is None:
        print(f"ENCODING {path} is not valid UTF-8")
        return
    print(f"OK       {path} rows={len(rows)}")


def check_dataset_inventory_fallback() -> None:
    target = ROOT / "research/literature/inventory/dataset_inventory.csv"
    if not target.exists():
        return
    utf8_rows = read_csv_with_encoding(target, "utf-8-sig")
    if utf8_rows is not None:
        return
    gb_rows = read_csv_with_encoding(target, "gb18030")
    if gb_rows is None:
        print("WARN     dataset_inventory.csv cannot be decoded as UTF-8 or GB18030")
        return
    print(f"INFO     dataset_inventory.csv decodes as GB18030 rows={len(gb_rows)}; convert before final handoff")


def check_pdf_paths() -> None:
    target = ROOT / "research/literature/inventory/paper_inventory.csv"
    rows = read_csv_with_encoding(target, "utf-8-sig") if target.exists() else None
    if rows is None:
        print("SKIP     paper PDF path check")
        return
    paths = [row.get("本地PDF路径", "") for row in rows if row.get("本地PDF路径")]
    present = sum(1 for p in paths if Path(p).exists())
    print(f"INFO     paper local PDF paths present={present} missing={len(paths) - present}")


def check_command(command: list[str], label: str) -> None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"MISSING  {label}: {exc}")
        return
    output = (result.stdout or result.stderr).strip().splitlines()
    detail = output[0] if output else f"exit={result.returncode}"
    prefix = "OK" if result.returncode == 0 else "WARN"
    print(f"{prefix:8} {label}: {detail}")


def check_code_snapshots() -> None:
    required_egnet = [
        "research/model-snapshots/code/egnet/model/CRA.py",
        "research/model-snapshots/code/egnet/model/Fusion.py",
        "research/model-snapshots/code/egnet/model/Transformer.py",
        "research/model-snapshots/code/egnet/model/bgnet.py",
        "research/model-snapshots/code/egnet/model/lib",
        "research/model-snapshots/code/egnet/tester.py",
    ]
    required_frs = [
        "research/model-snapshots/code/frs_loss/models.py",
        "research/model-snapshots/code/frs_loss/loss_function.py",
        "research/model-snapshots/code/frs_loss/FRS.py",
    ]
    print("EGNet snapshot:")
    for item in required_egnet:
        check_file(item) if not item.endswith("/lib") else check_dir(item)
    print("FRS Loss snapshot:")
    for item in required_frs:
        check_file(item)


def check_gitignore_rules() -> None:
    target = ROOT / ".gitignore"
    if not target.exists():
        print("MISSING  .gitignore")
        return
    text = target.read_text(encoding="utf-8")
    required = [
        "*.dcm",
        "*.nii",
        "*.nii.gz",
        "*.pt",
        "*.pth",
        "research/datasets/**/raw/",
        "research/datasets/**/derived/",
        "artifacts/reports/*",
        "artifacts/visual_evidence/*",
        "node_modules/",
        "frontend/dist/",
    ]
    missing = [pattern for pattern in required if pattern not in text]
    if missing:
        print(f"WARN     .gitignore missing patterns={missing}")
        return
    print("OK       .gitignore excludes raw imaging, checkpoints, frontend builds, and transient artifacts")


def main() -> None:
    print(f"Project root: {ROOT}")

    print_section("Core Files")
    for path in [
        "README.md",
        "AGENTS.md",
        "README_CN.md",
        "configs/tasks/osteo_vision.yml",
        "configs/inference/osteo_vision.yml",
        "research/planning/DOWNLOAD_STATUS.md",
        "research/planning/engineering_preparation.md",
        "research/literature/inventory/competition_feasibility_report.md",
        "research/literature/inventory/literature_and_dataset_summary.md",
        "research/literature/inventory/paper_inventory.csv",
        "research/literature/inventory/dataset_inventory.csv",
        "research/planning/requirements-prototype.txt",
    ]:
        check_file(path)

    print_section("CSV Encoding")
    check_utf8_csv("research/literature/inventory/paper_inventory.csv")
    check_utf8_csv("research/literature/inventory/dataset_inventory.csv")
    check_dataset_inventory_fallback()

    print_section("Local Literature Assets")
    check_dir("research/literature/inventory/papers")
    check_pdf_paths()

    print_section("Dataset Directories")
    for path in [
        "research/datasets/public-candidates/d024_dentvoxel",
        "research/datasets/public-candidates/d025_lesion_cbct",
        "research/datasets/public-candidates/d036_toothfairy2",
        "research/datasets/public-candidates/d042_modid",
        "research/datasets/public-candidates/d044_fgs_video",
    ]:
        check_dir(path)

    print_section("Code Snapshots")
    check_dir("research/model-snapshots/code/nnunet")
    check_dir("research/model-snapshots/code/egnet")
    check_dir("research/model-snapshots/code/frs_loss")
    check_code_snapshots()

    print_section("Platform Workspace")
    for path in [
        "frontend/",
        "backend/",
        "specs/001-software-platform-target/checklists/",
    ]:
        check_dir(path)
    check_gitignore_rules()

    print_section("Local Tools")
    check_command(["python", "--version"], "python")
    check_command(["dotnet", "--version"], "dotnet")
    check_command(["git", "--version"], "git")


if __name__ == "__main__":
    main()
