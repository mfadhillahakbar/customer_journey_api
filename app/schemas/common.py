from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for pagination."""
    page: int = Field(default=1, ge=1, description="Nomor halaman (mulai dari 1)")
    page_size: int = Field(default=50, ge=1, le=100, description="Jumlah data per halaman (maksimum 100)")


class PaginationMetadata(BaseModel):
    """Metadata pagination pada response."""
    page: int = Field(..., description="Halaman saat ini")
    page_size: int = Field(..., description="Ukuran data per halaman")
    total_records: int = Field(..., description="Total seluruh data yang sesuai filter")
    total_pages: int = Field(..., description="Total seluruh halaman")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Optional[List[Dict[str, Any]]] = None


class StandardErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    bigquery: str
    project_id: str
