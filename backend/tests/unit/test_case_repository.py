from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.src.domains.cases.repository import (
    CaseVersionConflictError,
    JsonCaseRepository,
    SQLiteCaseRepository,
    build_case_repository,
)
from backend.src.domains.cases.schemas import CaseRecord


def test_sqlite_case_repository_persists_and_exports_json(tmp_path: Path) -> None:
    db_path = tmp_path / "cases.sqlite"
    repo = SQLiteCaseRepository(db_path)
    case = repo.create(CaseRecord(case_id="case_sqlite", title="SQLite case"))

    updated = repo.save(case.model_copy(update={"title": "SQLite case updated"}))
    reloaded = SQLiteCaseRepository(db_path).get("case_sqlite")

    assert updated.updated_at >= case.updated_at
    assert updated.version == case.version + 1
    assert reloaded is not None
    assert reloaded.title == "SQLite case updated"
    assert reloaded.version == updated.version

    export_path = repo.export_json(tmp_path / "exports" / "cases.json")
    rows = json.loads(export_path.read_text(encoding="utf-8"))
    assert rows[0]["case_id"] == "case_sqlite"
    assert rows[0]["title"] == "SQLite case updated"


def test_case_repository_builder_keeps_json_paths_compatible(tmp_path: Path) -> None:
    repo = build_case_repository(tmp_path / "cases.json")

    assert isinstance(repo, JsonCaseRepository)


def test_case_repository_builder_defaults_non_json_paths_to_sqlite(tmp_path: Path) -> None:
    repo = build_case_repository(tmp_path / "cases.sqlite")

    assert isinstance(repo, SQLiteCaseRepository)


def test_sqlite_case_repository_rejects_stale_save(tmp_path: Path) -> None:
    db_path = tmp_path / "cases.sqlite"
    repo = SQLiteCaseRepository(db_path)
    first_copy = repo.create(CaseRecord(case_id="case_conflict", title="first"))
    second_copy = repo.get("case_conflict")
    assert second_copy is not None

    repo.save(first_copy.model_copy(update={"title": "updated by first"}))

    with pytest.raises(CaseVersionConflictError) as exc_info:
        repo.save(second_copy.model_copy(update={"title": "updated by stale copy"}))
    assert exc_info.value.case_id == "case_conflict"
    assert exc_info.value.expected_version == 1
    assert exc_info.value.actual_version == 2
    reloaded = repo.get("case_conflict")
    assert reloaded is not None
    assert reloaded.title == "updated by first"


def test_json_case_repository_rejects_stale_save(tmp_path: Path) -> None:
    repo = JsonCaseRepository(tmp_path / "cases.json")
    first_copy = repo.create(CaseRecord(case_id="case_json_conflict", title="first"))
    second_copy = repo.get("case_json_conflict")
    assert second_copy is not None

    repo.save(first_copy.model_copy(update={"title": "updated by first"}))

    with pytest.raises(CaseVersionConflictError):
        repo.save(second_copy.model_copy(update={"title": "updated by stale copy"}))
    reloaded = repo.get("case_json_conflict")
    assert reloaded is not None
    assert reloaded.title == "updated by first"
    assert reloaded.version == 2
