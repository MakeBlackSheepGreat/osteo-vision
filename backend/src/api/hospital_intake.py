from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.src.domains.cases.schemas import HospitalIntakeBatchRequest
from backend.src.services.hospital_intake_service import (
    HospitalIntakeConflictError,
    HospitalIntakeService,
)


def router(service: HospitalIntakeService) -> APIRouter:
    api = APIRouter()

    @api.post("/hospital-intake/batches")
    def admit_hospital_batch(request: HospitalIntakeBatchRequest) -> dict[str, Any]:
        try:
            return service.admit_batch(request)
        except HospitalIntakeConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "hospital_intake_conflict", "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "hospital_intake_invalid", "message": str(exc)},
            ) from exc

    @api.get("/hospital-intake/batches")
    def list_hospital_batches() -> dict[str, Any]:
        items = service.list_batches()
        return {"count": len(items), "items": items}

    @api.get("/hospital-intake/batches/{batch_id}")
    def get_hospital_batch(batch_id: str) -> dict[str, Any]:
        payload = service.get_batch(batch_id)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "hospital_intake_not_found",
                    "message": "Hospital intake batch not found",
                },
            )
        return payload

    return api
