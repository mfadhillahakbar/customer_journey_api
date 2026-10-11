from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.endpoints import health as health_endpoints
from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    starlette_http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import RequestLoggingMiddleware, setup_logging

logger = logging.getLogger("customer_journey_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Executes startup validation and graceful shutdown.
    """
    settings = get_settings()
    setup_logging(log_level="INFO" if settings.ENVIRONMENT == "production" else "DEBUG")
    logger.info(f"Starting {settings.API_TITLE} v{settings.API_VERSION} in [{settings.ENVIRONMENT}] mode")

    # Production safety checks
    if settings.ENVIRONMENT.lower() == "production":
        logger.info("Verifikasi konfigurasi mode production: API Key dan batasan CORS aktif.")

    yield

    logger.info("Shutting down Customer Journey Analytics API gracefully.")


def create_app(settings: Settings = None) -> FastAPI:
    """FastAPI application factory."""
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description=(
            "REST API untuk Analisis Customer Journey dari Google BigQuery. "
            "Menyajikan statistik klik tombol, jumlah pengguna unik, dan rata-rata klik "
            "berdasarkan event interaksi aplikasi mobile dan tabel master customer."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. Logging and Correlation ID Middleware
    app.add_middleware(RequestLoggingMiddleware)

    # 2. CORS Middleware with configured origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    # 3. Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 4. Mount Endpoint A at root /health for simple monitoring & ALB health probes
    app.include_router(health_endpoints.router)

    # 5. Mount API v1 router with prefix /api/v1
    app.include_router(api_v1_router, prefix=settings.API_PREFIX)

    return app


app = create_app()
