from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.osteo_vision_api.domains.annotations.enums import AnnotationStatus
from backend.osteo_vision_api.domains.annotations.schemas import AnnotationVersionRecord, ManualAnnotationRecord
from osteo_vision_core.core.paths import ensure_dir


class AnnotationNotFoundError(LookupError):
    pass


class AnnotationVersionConflictError(RuntimeError):
    def __init__(self, annotation_id: str, *, expected_version: int, actual_version: int | None) -> None:
        self.annotation_id = annotation_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Annotation {annotation_id} version conflict: expected {expected_version}, "
            f"actual {actual_version if actual_version is not None else 'missing'}"
        )


class AnnotationStateConflictError(RuntimeError):
    def __init__(self, annotation_id: str, *, expected_status: str, actual_status: str | None) -> None:
        self.annotation_id = annotation_id
        self.expected_status = expected_status
        self.actual_status = actual_status
        super().__init__(
            f"Annotation {annotation_id} state conflict: expected {expected_status}, "
            f"actual {actual_status if actual_status is not None else 'missing'}"
        )


class AnnotationRepository:
    """SQLite metadata store with immutable geometry and mask version records."""

    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path)
        ensure_dir(self.store_path.parent)
        self._initialize()

    def create(self, record: ManualAnnotationRecord, version: AnnotationVersionRecord) -> ManualAnnotationRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO manual_annotations(
                    annotation_id, case_id, status, current_version, payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.annotation_id,
                    record.case_id,
                    record.status.value,
                    record.current_version,
                    _json_payload(record),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
            connection.execute(
                """
                INSERT INTO manual_annotation_versions(annotation_id, version, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    version.annotation_id,
                    version.version,
                    _json_payload(version),
                    version.created_at.isoformat(),
                ),
            )
        return record

    def get(self, annotation_id: str) -> ManualAnnotationRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM manual_annotations WHERE annotation_id = ?", (annotation_id,)
            ).fetchone()
        if row is None:
            return None
        return ManualAnnotationRecord.model_validate(json.loads(str(row["payload"])))

    def list_records(self, *, case_id: str | None = None) -> list[ManualAnnotationRecord]:
        query = "SELECT payload FROM manual_annotations"
        parameters: tuple[str, ...] = ()
        if case_id is not None:
            query += " WHERE case_id = ?"
            parameters = (case_id,)
        query += " ORDER BY updated_at DESC, annotation_id ASC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [ManualAnnotationRecord.model_validate(json.loads(str(row["payload"]))) for row in rows]

    def list_for_cases(self, case_ids: list[str] | None = None) -> list[ManualAnnotationRecord]:
        if not case_ids:
            return self.list_records()
        placeholders = ",".join("?" for _ in case_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT payload FROM manual_annotations WHERE case_id IN ({placeholders}) "
                "ORDER BY case_id ASC, updated_at DESC, annotation_id ASC",
                tuple(case_ids),
            ).fetchall()
        return [ManualAnnotationRecord.model_validate(json.loads(str(row["payload"]))) for row in rows]

    def versions(self, annotation_id: str) -> list[AnnotationVersionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM manual_annotation_versions WHERE annotation_id = ? ORDER BY version ASC",
                (annotation_id,),
            ).fetchall()
        return [AnnotationVersionRecord.model_validate(json.loads(str(row["payload"]))) for row in rows]

    def append_version(
        self,
        record: ManualAnnotationRecord,
        version: AnnotationVersionRecord,
        *,
        expected_version: int,
        expected_status: AnnotationStatus,
    ) -> ManualAnnotationRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT current_version, status FROM manual_annotations WHERE annotation_id = ?",
                (record.annotation_id,),
            ).fetchone()
            self._validate_current(
                record.annotation_id,
                current,
                expected_version=expected_version,
                expected_status=expected_status,
            )
            connection.execute(
                """
                INSERT INTO manual_annotation_versions(annotation_id, version, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    version.annotation_id,
                    version.version,
                    _json_payload(version),
                    version.created_at.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE manual_annotations
                SET status = ?, current_version = ?, payload = ?, updated_at = ?
                WHERE annotation_id = ?
                """,
                (
                    record.status.value,
                    record.current_version,
                    _json_payload(record),
                    record.updated_at.isoformat(),
                    record.annotation_id,
                ),
            )
        return record

    def update(
        self,
        record: ManualAnnotationRecord,
        *,
        expected_version: int,
        expected_status: AnnotationStatus,
    ) -> ManualAnnotationRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT current_version, status FROM manual_annotations WHERE annotation_id = ?",
                (record.annotation_id,),
            ).fetchone()
            self._validate_current(
                record.annotation_id,
                current,
                expected_version=expected_version,
                expected_status=expected_status,
            )
            connection.execute(
                """
                UPDATE manual_annotations
                SET status = ?, payload = ?, updated_at = ?
                WHERE annotation_id = ?
                """,
                (
                    record.status.value,
                    _json_payload(record),
                    record.updated_at.isoformat(),
                    record.annotation_id,
                ),
            )
        return record

    def delete_draft(self, annotation_id: str, *, actor_id: str) -> bool:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM manual_annotations WHERE annotation_id = ?", (annotation_id,)
            ).fetchone()
            if row is None:
                return False
            record = ManualAnnotationRecord.model_validate(json.loads(str(row["payload"])))
            if record.status != AnnotationStatus.DRAFT or record.created_by.actor_id != actor_id:
                return False
            connection.execute("DELETE FROM manual_annotation_versions WHERE annotation_id = ?", (annotation_id,))
            connection.execute("DELETE FROM manual_annotations WHERE annotation_id = ?", (annotation_id,))
        return True

    def _validate_current(
        self,
        annotation_id: str,
        row: sqlite3.Row | None,
        *,
        expected_version: int,
        expected_status: AnnotationStatus,
    ) -> None:
        if row is None:
            raise AnnotationNotFoundError(annotation_id)
        actual_version = int(row["current_version"])
        if actual_version != expected_version:
            raise AnnotationVersionConflictError(
                annotation_id, expected_version=expected_version, actual_version=actual_version
            )
        actual_status = str(row["status"])
        if actual_status != expected_status.value:
            raise AnnotationStateConflictError(
                annotation_id, expected_status=expected_status.value, actual_status=actual_status
            )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS manual_annotations (
                    annotation_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS manual_annotation_versions (
                    annotation_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(annotation_id, version),
                    FOREIGN KEY(annotation_id) REFERENCES manual_annotations(annotation_id) ON DELETE CASCADE
                )
                """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_manual_annotations_case_updated "
                "ON manual_annotations(case_id, updated_at DESC)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.store_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


def _json_payload(model: ManualAnnotationRecord | AnnotationVersionRecord) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
