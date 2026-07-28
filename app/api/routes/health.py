"""Liveness health endpoint."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API process is alive."""

    return HealthResponse(status="ok")
