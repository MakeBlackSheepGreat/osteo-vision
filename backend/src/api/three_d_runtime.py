from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.src.api.helpers import require_case
from backend.src.core.settings import Settings
from backend.src.domains.cases.repository import CaseRepository
from backend.src.domains.cases.schemas import ThreeDRuntimeSnapshot
from backend.src.services.three_d_runtime_snapshot import (
    D024_REFERENCE_ID,
    ResolvedThreeDModelAsset,
    build_case_snapshot,
    build_public_reference_snapshot,
    resolve_case_model_asset,
    resolve_public_reference_model_asset,
)


def router(settings: Settings, repo: CaseRepository) -> APIRouter:
    api = APIRouter()

    @api.get(
        "/three-d-runtime/v1/cases/{case_id}/snapshot",
        response_model=ThreeDRuntimeSnapshot,
    )
    def get_case_snapshot(case_id: str) -> ThreeDRuntimeSnapshot:
        return build_case_snapshot(require_case(repo, case_id), settings)

    @api.get("/three-d-runtime/v1/cases/{case_id}/assets/{asset_id}")
    def download_case_model_asset(case_id: str, asset_id: str) -> FileResponse:
        asset = resolve_case_model_asset(require_case(repo, case_id), settings, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="3D runtime model asset is unavailable")
        return _model_file_response(asset)

    @api.get(
        "/three-d-runtime/v1/references/{reference_id}/snapshot",
        response_model=ThreeDRuntimeSnapshot,
    )
    def get_public_reference_snapshot(reference_id: str) -> ThreeDRuntimeSnapshot:
        snapshot = build_public_reference_snapshot(reference_id, settings)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="3D runtime public reference was not found")
        return snapshot

    @api.get("/three-d-runtime/v1/references/{reference_id}/assets/{asset_id}")
    def download_public_reference_model_asset(reference_id: str, asset_id: str) -> FileResponse:
        asset = resolve_public_reference_model_asset(reference_id, settings, asset_id)
        if asset is None:
            detail = "3D runtime public reference asset is unavailable"
            if reference_id != D024_REFERENCE_ID:
                detail = "3D runtime public reference was not found"
            raise HTTPException(status_code=404, detail=detail)
        return _model_file_response(asset)

    return api


def _model_file_response(asset: ResolvedThreeDModelAsset) -> FileResponse:
    return FileResponse(
        asset.path,
        media_type=asset.media_type,
        filename=asset.file_name,
        headers={
            "Cache-Control": "private, no-store",
            "ETag": f'"{asset.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
