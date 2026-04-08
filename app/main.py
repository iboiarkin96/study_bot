"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.users import router as users_router
from app.core.config import get_settings
from app.errors.validation import build_validation_error_payload

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Study App API",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return stable, code-based payload for all request validation errors."""
    return JSONResponse(
        status_code=422,
        content=build_validation_error_payload(request, exc),
    )


@app.get("/health", tags=["System"], summary="Health check")
def health() -> dict[str, str]:
    """Return basic service status."""
    return {"status": "ok"}


app.include_router(users_router, prefix="/api/v1")
