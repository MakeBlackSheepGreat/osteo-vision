from __future__ import annotations

import json
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
        rows.append(record.model_dump(mode="json"))
        self._dump_all(rows)
        return record

    def get(self, case_id: str) -> CaseRecord | None:
        for row in self._load_all():
            if row.get("case_id") == case_id:
                return CaseRecord.model_validate(row)
        return None

    def save(self, record: CaseRecord) -> CaseRecord:
        return self.create(record)

    def list(self) -> list[CaseRecord]:
        return [CaseRecord.model_validate(row) for row in self._load_all()]


def update_case_status(record: CaseRecord, status: CaseStatus) -> CaseRecord:
    return record.model_copy(update={"status": status})
