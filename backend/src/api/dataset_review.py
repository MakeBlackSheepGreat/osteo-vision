from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.src.services.static_dataset_review import (
    StaticDatasetReviewError,
    StaticDatasetReviewNotFoundError,
    StaticDatasetReviewSecurityError,
    StaticDatasetReviewService,
)


class DatasetMaskReviewRequest(BaseModel):
    mask_png_base64: str = Field(min_length=1)
    review_state: str = Field(min_length=1)
    reviewer_notes: str | None = None
    reviewer_role: str = "project_reviewer"


class DatasetSeedRequest(BaseModel):
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    colormap: str = "green"


class DatasetCropRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=16)
    height: int = Field(ge=16)
    panel_role: str = "unclassified"
    pair_id: str | None = None
    crop_notes: str | None = None
    suggestion_id: str | None = None
    crop_review_action: str = "modified"


def router(service: StaticDatasetReviewService) -> APIRouter:
    api = APIRouter()

    @api.get("/dataset-review/queue")
    def dataset_review_queue() -> dict[str, Any]:
        return service.list_queue()

    @api.get("/dataset-review/{record_id}/image")
    def dataset_review_image(record_id: str) -> FileResponse:
        path = _service_path(lambda: service.image_path_for(record_id))
        return FileResponse(path)

    @api.get("/dataset-review/{record_id}/mask")
    def dataset_review_mask(record_id: str) -> FileResponse:
        path = _service_path(lambda: service.mask_path_for(record_id))
        return FileResponse(path, media_type="image/png")

    @api.post("/dataset-review/{record_id}/mask")
    def save_dataset_review_mask(record_id: str, request: DatasetMaskReviewRequest) -> dict[str, Any]:
        try:
            return service.save_mask(
                record_id,
                mask_png_base64=request.mask_png_base64,
                review_state=request.review_state,
                reviewer_notes=request.reviewer_notes,
                reviewer_role=request.reviewer_role,
            )
        except StaticDatasetReviewNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except StaticDatasetReviewSecurityError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except StaticDatasetReviewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/dataset-review/{record_id}/seed")
    def generate_dataset_review_seed(record_id: str, request: DatasetSeedRequest) -> dict[str, Any]:
        try:
            return service.generate_seed(
                record_id,
                threshold=request.threshold,
                colormap=request.colormap,
            )
        except StaticDatasetReviewNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except StaticDatasetReviewSecurityError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except StaticDatasetReviewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/dataset-review/{record_id}/crop")
    def save_dataset_review_crop(record_id: str, request: DatasetCropRequest) -> dict[str, Any]:
        try:
            return service.save_crop(
                record_id,
                x=request.x,
                y=request.y,
                width=request.width,
                height=request.height,
                panel_role=request.panel_role,
                pair_id=request.pair_id,
                crop_notes=request.crop_notes,
                suggestion_id=request.suggestion_id,
                crop_review_action=request.crop_review_action,
            )
        except StaticDatasetReviewNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except StaticDatasetReviewSecurityError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except StaticDatasetReviewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return api


def _service_path(loader: Any) -> Path:
    try:
        return Path(loader())
    except StaticDatasetReviewNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StaticDatasetReviewSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
