# app/api/routes/health.py
from fastapi import APIRouter
from datetime import datetime

from app.config import get_settings
from app.schemas.responses import HealthResponse, HealthStatus

router = APIRouter()
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the service is healthy and running"
)
async def health_check() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=settings.app_version,
        timestamp=datetime.utcnow()
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness Check"
)
async def readiness_check() -> HealthResponse:
    """Check if service is ready to accept requests."""
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=settings.app_version,
        timestamp=datetime.utcnow()
    )
