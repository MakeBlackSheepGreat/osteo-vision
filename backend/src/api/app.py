from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.src.api.routes import build_router
from backend.src.core.settings import load_settings
from backend.src.domains.cases.repository import CaseVersionConflictError


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(CaseVersionConflictError)
    async def case_version_conflict_handler(_request: Request, exc: CaseVersionConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "code": "case_version_conflict",
                    "message": "The case was updated by another operation. Reload the case and retry.",
                    "case_id": exc.case_id,
                    "expected_version": exc.expected_version,
                    "actual_version": exc.actual_version,
                }
            },
        )

    app.include_router(build_router(settings))
    return app


app = create_app()
