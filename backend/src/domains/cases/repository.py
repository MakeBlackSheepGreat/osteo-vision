from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from backend.src.domains.cases.enums import CaseStatus
from backend.src.domains.cases.schemas import CaseRecord
from src.core.paths import ensure_dir


class CaseRepository(Protocol):
    def create(self, record: CaseRecord) -> CaseRecord: ...

    def get(self, case_id: str) -> CaseRecord | None: ...

    def save(self, record: CaseRecord) -> CaseRecord: ...

    def list(self) -> list[CaseRecord]: ...


class CaseVersionConflictError(RuntimeError):
    def __init__(self, case_id: str, *, expected_version: int, actual_version: int | None) -> None:
        self.case_id = case_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        message = (
            f"Case {case_id} version conflict: expected {expected_version}, "
            f"actual {actual_version if actual_version is not None else 'missing'}"
        )
        super().__init__(message)


class JsonCaseRepository:
    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path)
        ensure_dir(self.store_path.parent)

    def _load_all(self) -> list[dict]:
        if not self.store_path.exists():
            return []
        data = json.loads(self.store_path.read_text(encoding="utf-8") or "[]")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _dump_all(self, rows: list[dict]) -> None:
        ensure_dir(self.store_path.parent)
        self.store_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, record: CaseRecord) -> CaseRecord:
        rows = self._load_all()
        rows = [row for row in rows if row.get("case_id") != record.case_id]
        rows.append(_case_payload(record))
        self._dump_all(rows)
        return record.model_copy(update={"version": _record_version(record)})

    def get(self, case_id: str) -> CaseRecord | None:
        for row in self._load_all():
            if row.get("case_id") == case_id:
                return CaseRecord.model_validate(row)
        return None

    def save(self, record: CaseRecord) -> CaseRecord:
        rows = self._load_all()
        updated_rows: list[dict] = []
        matched = False
        updated = _next_saved_record(record)
        for row in rows:
            if row.get("case_id") != record.case_id:
                updated_rows.append(row)
                continue
            matched = True
            actual_version = _payload_version(row)
            expected_version = _record_version(record)
            if actual_version != expected_version:
                raise CaseVersionConflictError(
                    record.case_id, expected_version=expected_version, actual_version=actual_version
                )
            updated_rows.append(_case_payload(updated))
        if not matched:
            raise CaseVersionConflictError(record.case_id, expected_version=_record_version(record), actual_version=None)
        self._dump_all(updated_rows)
        return updated

    def list(self) -> list[CaseRecord]:
        return [CaseRecord.model_validate(row) for row in self._load_all()]


def update_case_status(record: CaseRecord, status: CaseStatus) -> CaseRecord:
    return record.model_copy(update={"status": status})


class SQLiteCaseRepository:
    """Transactional case repository for the local platform service."""

    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path)
        ensure_dir(self.store_path.parent)
        self._initialize()

    def create(self, record: CaseRecord) -> CaseRecord:
        created = record.model_copy(update={"version": _record_version(record)})
        payload = _case_payload(created)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR REPLACE INTO cases(case_id, payload, created_at, updated_at, version)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    created.case_id,
                    json.dumps(payload, ensure_ascii=False),
                    str(payload.get("created_at") or ""),
                    str(payload.get("updated_at") or ""),
                    _payload_version(payload),
                ),
            )
        return created

    def get(self, case_id: str) -> CaseRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            return None
        return CaseRecord.model_validate(json.loads(str(row["payload"])))

    def save(self, record: CaseRecord) -> CaseRecord:
        expected_version = _record_version(record)
        updated = _next_saved_record(record)
        payload = _case_payload(updated)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = connection.execute(
                """
                UPDATE cases
                SET payload = ?, updated_at = ?, version = ?
                WHERE case_id = ? AND version = ?
                """,
                (
                    json.dumps(payload, ensure_ascii=False),
                    str(payload.get("updated_at") or ""),
                    _payload_version(payload),
                    record.case_id,
                    expected_version,
                ),
            )
            if result.rowcount == 0:
                current = connection.execute(
                    "SELECT version FROM cases WHERE case_id = ?", (record.case_id,)
                ).fetchone()
                actual_version = int(current["version"]) if current is not None else None
                raise CaseVersionConflictError(
                    record.case_id, expected_version=expected_version, actual_version=actual_version
                )
        return updated

    def list(self) -> list[CaseRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM cases ORDER BY created_at ASC, case_id ASC").fetchall()
        return [CaseRecord.model_validate(json.loads(str(row["payload"]))) for row in rows]

    def export_json(self, target_path: str | Path) -> Path:
        target = Path(target_path)
        ensure_dir(target.parent)
        rows = [record.model_dump(mode="json") for record in self.list()]
        target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(cases)").fetchall()
                if row["name"] is not None
            }
            if "version" not in columns:
                connection.execute("ALTER TABLE cases ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            for row in connection.execute("SELECT case_id, payload FROM cases").fetchall():
                try:
                    payload = json.loads(str(row["payload"]))
                except json.JSONDecodeError:
                    payload = {}
                version = _payload_version(payload if isinstance(payload, dict) else {})
                connection.execute("UPDATE cases SET version = ? WHERE case_id = ?", (version, row["case_id"]))
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON cases(updated_at)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.store_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


def build_case_repository(store_path: str | Path, backend: str | None = None) -> CaseRepository:
    path = Path(store_path)
    selected = (backend or "").strip().lower()
    if not selected:
        selected = "json" if path.suffix.lower() == ".json" else "sqlite"
    if selected == "json":
        return JsonCaseRepository(path)
    if selected in {"sqlite", "sqlite3"}:
        return SQLiteCaseRepository(path)
    raise ValueError(f"Unsupported case repository backend: {backend}")


def _case_payload(record: CaseRecord) -> dict:
    return record.model_dump(mode="json")


def _record_version(record: CaseRecord) -> int:
    return max(1, int(record.version or 1))


def _payload_version(payload: dict) -> int:
    try:
        return max(1, int(payload.get("version") or 1))
    except (TypeError, ValueError):
        return 1


def _next_saved_record(record: CaseRecord) -> CaseRecord:
    return record.model_copy(update={"version": _record_version(record) + 1, "updated_at": datetime.now(timezone.utc)})
