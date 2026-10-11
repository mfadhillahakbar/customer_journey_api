from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.common import PaginationMetadata


class ButtonClickFilters(BaseModel):
    """Filter parameters used across button analytics endpoints."""
    start_date: Optional[date] = Field(default=None, description="Tanggal awal (YYYY-MM-DD, inklusif)")
    end_date: Optional[date] = Field(default=None, description="Tanggal akhir (YYYY-MM-DD, inklusif)")
    role: Optional[str] = Field(default=None, description="Filter role customer dari tabel master")
    depo: Optional[str] = Field(default=None, description="Filter depo customer dari tabel master")
    region: Optional[str] = Field(default=None, description="Filter region customer dari tabel master")
    area: Optional[str] = Field(default=None, description="Filter area customer dari tabel master")
    screen_name: Optional[str] = Field(default=None, description="Filter screen_name dari tabel event")
    button_name: Optional[str] = Field(default=None, description="Filter button_name dari tabel event")
    event_name: Optional[str] = Field(default=None, description="Filter event_name dari tabel event")

    @model_validator(mode="after")
    def validate_date_range(self) -> "ButtonClickFilters":
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("start_date harus lebih awal dari atau sama dengan end_date.")
        return self


class FiltersApplied(BaseModel):
    """Representasi filter yang diaplikasikan ke query BigQuery."""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    role: Optional[str] = None
    region: Optional[str] = None
    depo: Optional[str] = None
    area: Optional[str] = None
    screen_name: Optional[str] = None
    button_name: Optional[str] = None
    event_name: Optional[str] = None


class ButtonClickItem(BaseModel):
    """Item agregasi statistik klik tombol."""
    screen_name: Optional[str] = Field(default=None, description="Nama screen (bisa null)")
    button_name: str = Field(..., description="Nama tombol yang diklik")
    event_name: Optional[str] = Field(default=None, description="Nama event analitik")
    total_clicks: int = Field(..., description="Total event klik yang tercatat")
    total_users: int = Field(..., description="Jumlah pengguna unik yang mengklik tombol")
    user_avg_clicks: int = Field(..., description="Rata-rata klik per pengguna (pembagian integer)")


class ButtonClickSummaryResponse(BaseModel):
    """Response untuk Endpoint B (Ringkasan Statistik Tombol)."""
    data: List[ButtonClickItem]
    pagination: PaginationMetadata
    filters_applied: FiltersApplied


class CustomerDetail(BaseModel):
    """Detail atribut customer dari tabel master customer."""
    role: Optional[str] = None
    depo: Optional[str] = None
    region: Optional[str] = None
    area: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ButtonClickUserItem(BaseModel):
    """Item pengguna yang mengklik tombol."""
    user_id: str = Field(..., description="ID unik pengguna")
    user_clicks: int = Field(..., description="Jumlah klik tombol oleh pengguna ini")
    last_event_timestamp: Optional[datetime] = Field(default=None, description="Waktu klik terakhir")
    customer: Optional[CustomerDetail] = Field(default=None, description="Atribut customer master")


class ButtonClickUsersResponse(BaseModel):
    """Response untuk Endpoint C (Daftar Pengguna yang Mengklik Tombol)."""
    data: List[ButtonClickUserItem]
    pagination: PaginationMetadata
    filters_applied: Optional[FiltersApplied] = None


class RawEventItem(BaseModel):
    """Detail catatan event mentah individual."""
    event_date: Optional[str] = None
    event_timestamp: Optional[datetime] = None
    user_id: str
    user_pseudo_id: Optional[str] = None
    event_name: Optional[str] = None
    screen_name: Optional[str] = None
    button_name: Optional[str] = None
    ga_session_id: Optional[str] = None
    ga_session_number: Optional[int] = None
    platform: Optional[str] = None
    device_category: Optional[str] = None
    device_brand: Optional[str] = None
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    city: Optional[str] = None
    app_version: Optional[str] = None
    customer: Optional[CustomerDetail] = None


class RawEventsResponse(BaseModel):
    """Response untuk Endpoint D (Detail Event Opsional)."""
    data: List[RawEventItem]
    pagination: PaginationMetadata
    filters_applied: Optional[FiltersApplied] = None
