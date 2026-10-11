from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class UnauthorizedException(AppException):
    """Exception for missing or invalid API key."""

    def __init__(self, message: str = "Akses ditolak: API Key tidak valid atau tidak disertakan."):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InvalidDateRangeException(AppException):
    """Exception for invalid date range (e.g. start_date > end_date)."""

    def __init__(self, message: str = "start_date harus lebih awal dari atau sama dengan end_date."):
        super().__init__(
            code="INVALID_DATE_RANGE",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class BigQueryExecutionError(AppException):
    """Exception for errors during BigQuery execution."""

    def __init__(self, message: str = "Terjadi kegagalan saat menjalankan query analitik pada BigQuery."):
        super().__init__(
            code="BIGQUERY_ERROR",
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class BigQueryReadinessError(AppException):
    """Exception when BigQuery service is not reachable during health probe."""

    def __init__(self, message: str = "Koneksi ke BigQuery gagal diinisialisasi atau tidak responsif."):
        super().__init__(
            code="BIGQUERY_NOT_READY",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ==============================================================================
# FastAPI Exception Handlers
# ==============================================================================


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle custom application exceptions."""
    payload = {
        "error": {
            "code": exc.code,
            "message": exc.message,
        }
    }
    if exc.details:
        payload["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format Pydantic request validation errors consistently."""
    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []) if loc != "query")
        msg = err.get("msg", "Input tidak valid")
        # Handle custom date range validation message if triggered by Pydantic
        if "start_date" in msg and "end_date" in msg:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "INVALID_DATE_RANGE",
                        "message": "start_date harus lebih awal dari atau sama dengan end_date.",
                    }
                },
            )
        errors.append({"field": field or "body", "issue": msg})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Format parameter request tidak valid.",
                "details": errors,
            }
        },
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    code_mapping = {
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    }
    code = code_mapping.get(exc.status_code, "HTTP_ERROR")
    detail_msg = exc.detail if isinstance(exc.detail, str) else "Permintaan gagal diproses."

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": detail_msg,
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions to prevent stack trace leaks."""
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Terjadi kesalahan internal pada server. Silakan hubungi administrator.",
            }
        },
    )
