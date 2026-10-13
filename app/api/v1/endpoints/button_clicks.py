from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from app.core.exceptions import InvalidDateRangeException
from app.core.security import verify_api_key
from app.schemas.button_clicks import (
    ButtonClickFilters,
    DashboardAnalyticsResponse,
    DashboardPeriod,
    ButtonClickSummaryResponse,
    ButtonClickUsersResponse,
    RawEventsResponse,
)
from app.services.button_clicks_service import ButtonClicksService

router = APIRouter(
    prefix="/button-clicks",
    tags=["Button Journey Analytics"],
    dependencies=[Depends(verify_api_key)],
)


def _validate_date_range(start_date: Optional[date], end_date: Optional[date]) -> None:
    """Validate that start_date is not strictly after end_date."""
    if start_date and end_date and start_date > end_date:
        raise InvalidDateRangeException("start_date harus lebih awal dari atau sama dengan end_date.")


@router.get(
    "",
    response_model=ButtonClickSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ringkasan Statistik Tombol",
    description=(
        "Mengembalikan daftar seluruh kombinasi screen_name, button_name, dan event_name "
        "beserta total_clicks, total_users unik, dan user_avg_clicks. "
        "Mendukung filter tanggal, role, depo, region, area, dan navigasi."
    ),
)
async def get_button_clicks_summary(
    start_date: Optional[date] = Query(default=None, description="Tanggal awal periode (YYYY-MM-DD inklusif)"),
    end_date: Optional[date] = Query(default=None, description="Tanggal akhir periode (YYYY-MM-DD inklusif)"),
    role: Optional[str] = Query(default=None, description="Filter role customer dari tabel master"),
    depo: Optional[str] = Query(default=None, description="Filter depo customer dari tabel master"),
    region: Optional[str] = Query(default=None, description="Filter region customer dari tabel master"),
    area: Optional[str] = Query(default=None, description="Filter area customer dari tabel master"),
    screen_name: Optional[str] = Query(default=None, description="Filter screen_name"),
    button_name: Optional[str] = Query(default=None, description="Filter button_name"),
    event_name: Optional[str] = Query(default=None, description="Filter event_name"),
    page: int = Query(default=1, ge=1, description="Nomor halaman pagination"),
    page_size: int = Query(default=50, ge=1, le=100, description="Ukuran halaman pagination (maks 100)"),
    service: ButtonClicksService = Depends(),
) -> ButtonClickSummaryResponse:
    """Endpoint B — Ringkasan Statistik Tombol."""
    _validate_date_range(start_date, end_date)

    filters = ButtonClickFilters(
        start_date=start_date,
        end_date=end_date,
        role=role,
        depo=depo,
        region=region,
        area=area,
        screen_name=screen_name,
        button_name=button_name,
        event_name=event_name,
    )

    return service.get_summary(filters=filters, page=page, page_size=page_size)


@router.get(
    "/users",
    response_model=ButtonClickUsersResponse,
    status_code=status.HTTP_200_OK,
    summary="Daftar Pengguna yang Mengklik Tombol",
    description=(
        "Mengembalikan daftar pengguna unik yang pernah mengklik tombol tertentu "
        "beserta jumlah klik (user_clicks), waktu klik terakhir (last_event_timestamp), "
        "dan detail customer dari tabel master. Parameter button_name wajib diisi."
    ),
)
async def get_button_click_users(
    button_name: str = Query(..., min_length=1, description="Nama tombol yang wajib dipilih"),
    screen_name: Optional[str] = Query(default=None, description="Filter opsional screen_name"),
    event_name: Optional[str] = Query(default=None, description="Filter opsional event_name"),
    start_date: Optional[date] = Query(default=None, description="Tanggal awal periode (YYYY-MM-DD inklusif)"),
    end_date: Optional[date] = Query(default=None, description="Tanggal akhir periode (YYYY-MM-DD inklusif)"),
    role: Optional[str] = Query(default=None, description="Filter role customer"),
    depo: Optional[str] = Query(default=None, description="Filter depo customer"),
    region: Optional[str] = Query(default=None, description="Filter region customer"),
    area: Optional[str] = Query(default=None, description="Filter area customer"),
    page: int = Query(default=1, ge=1, description="Nomor halaman pagination"),
    page_size: int = Query(default=50, ge=1, le=100, description="Ukuran halaman pagination (maks 100)"),
    service: ButtonClicksService = Depends(),
) -> ButtonClickUsersResponse:
    """Endpoint C — Daftar Pengguna yang Mengklik Tombol."""
    _validate_date_range(start_date, end_date)

    filters = ButtonClickFilters(
        start_date=start_date,
        end_date=end_date,
        role=role,
        depo=depo,
        region=region,
        area=area,
        screen_name=screen_name,
        button_name=button_name,
        event_name=event_name,
    )

    return service.get_users(filters=filters, page=page, page_size=page_size)


@router.get(
    "/events",
    response_model=RawEventsResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspeksi Event Mentah Individual",
    description=(
        "Endpoint opsional untuk menginspeksi catatan event individual dari BigQuery "
        "dengan kontrol pagination dan batasan filter ketat."
    ),
)
async def get_raw_events(
    button_name: Optional[str] = Query(default=None, description="Filter button_name"),
    screen_name: Optional[str] = Query(default=None, description="Filter screen_name"),
    event_name: Optional[str] = Query(default=None, description="Filter event_name"),
    user_id: Optional[str] = Query(default=None, description="Filter user_id"),
    start_date: Optional[date] = Query(default=None, description="Tanggal awal periode (YYYY-MM-DD inklusif)"),
    end_date: Optional[date] = Query(default=None, description="Tanggal akhir periode (YYYY-MM-DD inklusif)"),
    role: Optional[str] = Query(default=None, description="Filter role customer"),
    depo: Optional[str] = Query(default=None, description="Filter depo customer"),
    region: Optional[str] = Query(default=None, description="Filter region customer"),
    area: Optional[str] = Query(default=None, description="Filter area customer"),
    page: int = Query(default=1, ge=1, description="Nomor halaman pagination"),
    page_size: int = Query(default=50, ge=1, le=100, description="Ukuran halaman pagination (maks 100)"),
    service: ButtonClicksService = Depends(),
) -> RawEventsResponse:
    """Endpoint D — Detail Event Mentah Opsional."""
    _validate_date_range(start_date, end_date)

    filters = ButtonClickFilters(
        start_date=start_date,
        end_date=end_date,
        role=role,
        depo=depo,
        region=region,
        area=area,
        screen_name=screen_name,
        button_name=button_name,
        event_name=event_name,
    )

    return service.get_raw_events(filters=filters, user_id=user_id, page=page, page_size=page_size)


@router.get(
    "/dashboard",
    response_model=DashboardAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Ringkasan Dashboard Analytics",
    description=(
        "Mengembalikan KPI dan data grafik dashboard dalam satu response. "
        "Mendukung period preset (7 hari terakhir, 30 hari terakhir, kemarin, hari ini, custom) "
        "serta filter opsional role, depo, region, area, screen_name, dan button_name."
    ),
)
async def get_dashboard_analytics(
    period: DashboardPeriod = Query(default=DashboardPeriod.last_7_days, description="Preset periode dashboard"),
    start_date: Optional[date] = Query(default=None, description="Tanggal awal untuk period=custom (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(default=None, description="Tanggal akhir untuk period=custom (YYYY-MM-DD)"),
    role: Optional[str] = Query(default=None, description="Filter role customer dari tabel master"),
    depo: Optional[str] = Query(default=None, description="Filter depo customer dari tabel master"),
    region: Optional[str] = Query(default=None, description="Filter region customer dari tabel master"),
    area: Optional[str] = Query(default=None, description="Filter area customer dari tabel master"),
    screen_name: Optional[str] = Query(default=None, description="Filter screen_name"),
    button_name: Optional[str] = Query(default=None, description="Filter button_name partial"),
    service: ButtonClicksService = Depends(),
) -> DashboardAnalyticsResponse:
    """Endpoint dashboard agregasi KPI dan grafik dalam satu payload."""
    return service.get_dashboard_analytics(
        period=period,
        start_date=start_date,
        end_date=end_date,
        role=role,
        depo=depo,
        region=region,
        area=area,
        screen_name=screen_name,
        button_name=button_name,
    )
