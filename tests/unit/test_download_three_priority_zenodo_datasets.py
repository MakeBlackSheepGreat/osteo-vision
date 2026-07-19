from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/download_three_priority_zenodo_datasets.py"
SPEC = importlib.util.spec_from_file_location("download_three_priority_zenodo_datasets", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_selected_files_preserves_requested_order() -> None:
    files = [{"key": "a"}, {"key": "b"}, {"key": "c"}]

    selected = MODULE._selected_files(files, ["c", "a"])

    assert [item["key"] for item in selected] == ["c", "a"]


def test_selected_files_returns_all_when_no_filter() -> None:
    files = [{"key": "a"}, {"key": "b"}]

    assert MODULE._selected_files(files, None) == files


def test_safe_name_removes_windows_reserved_characters() -> None:
    assert MODULE._safe_name('a<b>:c"d/e\\f|g?h*i') == "a_b_c_d_e_f_g_h_i"


def test_merge_existing_rows_preserves_previous_subset_downloads(tmp_path: Path) -> None:
    manifest = {
        "records": [
            {
                "candidate_id": "D064",
                "original_file_name": "old.zip",
                "size_bytes": 1,
            }
        ]
    }
    (tmp_path / "three_priority_zenodo_manifest.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")

    rows = MODULE._merge_existing_rows(
        tmp_path,
        [
            {
                "candidate_id": "D074",
                "original_file_name": "new.zip",
                "size_bytes": 2,
            }
        ],
    )

    assert [(row["candidate_id"], row["original_file_name"]) for row in rows] == [
        ("D064", "old.zip"),
        ("D074", "new.zip"),
    ]
