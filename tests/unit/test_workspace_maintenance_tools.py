from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit_active_documentation import REQUIRED_ACTIVE_DOCUMENTS, canonical_version, run_audit
from tools.clean_workspace import (
    Candidate,
    _is_within_root,
    collect_candidates,
    remove_candidates,
    remove_candidates_best_effort,
    validate_repo_root,
)


def _repo_markers(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "osteo-vision"\nversion = "0.3.0rc2"\n',
        encoding="utf-8",
    )
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")


def test_workspace_cleanup_is_bounded_and_preserves_artifact_markers(tmp_path: Path) -> None:
    _repo_markers(tmp_path)
    cache = tmp_path / "src" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.pyc").write_bytes(b"cache")
    transient = tmp_path / ".pytest_tmp_case"
    transient.mkdir()
    (transient / "result.txt").write_text("temporary", encoding="utf-8")
    transient_file = tmp_path / ".codex_tmp_submission.docx"
    transient_file.write_bytes(b"temporary-document")
    nested_cache = transient / "nested" / "__pycache__"
    nested_cache.mkdir(parents=True)
    (nested_cache / "module.pyc").write_bytes(b"nested-cache")
    e2e_bucket = tmp_path / "artifacts" / "e2e"
    e2e_bucket.mkdir(parents=True)
    (e2e_bucket / ".gitkeep").write_text("", encoding="utf-8")
    (e2e_bucket / "generated.json").write_text("{}", encoding="utf-8")
    case_store = tmp_path / "artifacts" / "platform" / "cases.sqlite"
    case_store.parent.mkdir(parents=True)
    case_store.write_bytes(b"case-state")
    derived_dataset = tmp_path / "outputs" / "reviewed_dataset" / "manifest.json"
    derived_dataset.parent.mkdir(parents=True)
    derived_dataset.write_text("{}", encoding="utf-8")
    research_script = tmp_path / "tmp" / "research" / "inspect.py"
    research_script.parent.mkdir(parents=True)
    research_script.write_text("print('preserve')\n", encoding="utf-8")
    source = tmp_path / "src" / "keep.py"
    source.write_text("value = 1\n", encoding="utf-8")

    candidates = collect_candidates(tmp_path, include_artifacts=True)
    candidate_paths = {item.path for item in candidates}
    assert "src/__pycache__" in candidate_paths
    assert ".pytest_tmp_case" in candidate_paths
    assert ".codex_tmp_submission.docx" in candidate_paths
    assert ".pytest_tmp_case/nested/__pycache__" not in candidate_paths
    assert "artifacts/e2e/generated.json" in candidate_paths
    assert "artifacts/e2e/.gitkeep" not in candidate_paths
    assert "artifacts/platform/cases.sqlite" not in candidate_paths
    assert "outputs" not in candidate_paths
    assert "tmp" not in candidate_paths

    removed = remove_candidates(tmp_path, candidates)
    assert len(removed) == len(candidates)
    assert source.exists()
    assert not transient_file.exists()
    assert (e2e_bucket / ".gitkeep").exists()
    assert case_store.read_bytes() == b"case-state"
    assert derived_dataset.is_file()
    assert research_script.is_file()


def test_workspace_cleanup_rejects_candidate_outside_transient_allowlist(tmp_path: Path) -> None:
    _repo_markers(tmp_path)
    protected = tmp_path / "outputs" / "reviewed_dataset" / "manifest.json"
    protected.parent.mkdir(parents=True)
    protected.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the transient allowlist"):
        remove_candidates(
            tmp_path,
            [Candidate(path="outputs/reviewed_dataset/manifest.json", kind="file", size_bytes=2)],
        )

    assert protected.is_file()


def test_workspace_cleanup_best_effort_continues_after_locked_file(tmp_path: Path, monkeypatch) -> None:
    _repo_markers(tmp_path)
    locked = tmp_path / ".codex_tmp_locked.log"
    locked.write_text("locked", encoding="utf-8")
    removable = tmp_path / "artifacts_tavily_multimodal.json"
    removable.write_text("{}", encoding="utf-8")
    original_unlink = Path.unlink

    def guarded_unlink(path: Path, *args, **kwargs) -> None:
        if path == locked:
            raise PermissionError(32, "file is in use")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", guarded_unlink)
    candidates = collect_candidates(tmp_path)
    removed, failures = remove_candidates_best_effort(tmp_path, candidates)

    assert {item.path for item in removed} == {"artifacts_tavily_multimodal.json"}
    assert [item.path for item in failures] == [".codex_tmp_locked.log"]
    assert locked.is_file()
    assert not removable.exists()


def test_workspace_cleanup_rejects_invalid_root_and_external_paths(tmp_path: Path) -> None:
    invalid_root = tmp_path / "not-a-repository"
    invalid_root.mkdir()

    with pytest.raises(ValueError, match="missing"):
        validate_repo_root(invalid_root)

    root = tmp_path / "repository"
    root.mkdir()
    _repo_markers(root)
    assert _is_within_root(root / "tmp", root) is True
    assert _is_within_root(root, root) is False
    assert _is_within_root(tmp_path / "outside", root) is False


def test_active_documentation_audit_detects_stale_entry_and_version_drift(tmp_path: Path) -> None:
    _repo_markers(tmp_path)
    for relative in REQUIRED_ACTIVE_DOCUMENTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Current platform documentation.\n", encoding="utf-8")
    (tmp_path / "README_CN.md").write_text(
        "当前 V1 平台。\n"
        "python check_env.py\n"
        "research/planning/engineering_preparation.md\n"
        "software_focused_realistic_platform_zh.md\n"
        "competition_feasibility_report.md\n",
        encoding="utf-8",
    )
    for relative, version in (
        ("package.json", "0.3.0-rc.2"),
        ("package-lock.json", "0.3.0-rc.2"),
        ("frontend/package.json", "0.3.0-rc.2"),
        ("frontend/package-lock.json", "0.3.0-rc.1"),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": version}), encoding="utf-8")

    payload = run_audit(tmp_path)

    assert payload["passed"] is False
    codes = {item["code"] for item in payload["findings"]}
    assert {
        "archived_feasibility_path",
        "retired_quality_entry",
        "retired_research_path",
        "stage_label",
        "superseded_target_path",
        "version_mismatch",
    }.issubset(codes)


def test_canonical_version_normalizes_pep440_release_candidate() -> None:
    assert canonical_version("0.3.0rc2") == canonical_version("0.3.0-rc.2")
