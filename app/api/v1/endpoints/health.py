from fastapi import APIRouter, Depends, status
from app.core.config import Settings, get_settings
from app.schemas.common import HealthResponse, ReadinessResponse
from app.services.button_clicks_service import ButtonClicksService

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness Health Check",
    description="Endpoint ringan untuk mengetahui apakah application service berjalan. Tidak memicu query BigQuery.",
)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return application liveness status without touching BigQuery."""
    return HealthResponse(
        status="ok",
        service=settings.API_TITLE,
        version=settings.API_VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
    description="Endpoint kesiapan untuk memverifikasi koneksi dan izin service account ke Google BigQuery.",
)
async def readiness_check(
    service: ButtonClicksService = Depends(),
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    """Verify BigQuery readiness and credentials."""
    service.check_readiness()
    return ReadinessResponse(
        status="ready",
        bigquery="connected",
        project_id=settings.GCP_PROJECT_ID,
    )
