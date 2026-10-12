from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.security import verify_api_key
from app.schemas.button_clicks import FilterOptionsResponse
from app.services.button_clicks_service import ButtonClicksService


router = APIRouter(
    prefix="/filters",
    tags=["Filter Options"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/{field}",
    response_model=FilterOptionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Daftar Opsi Filter",
    description="Mengembalikan opsi filter unik dan terurut untuk checkbox atau multi-select.",
)
async def get_filter_options(
    field: str = Path(..., min_length=1, max_length=64),
    search: Optional[str] = Query(default=None, max_length=100, description="Pencarian sebagian nilai"),
    page: int = Query(default=1, ge=1, description="Nomor halaman pagination"),
    page_size: int = Query(default=50, ge=1, le=100, description="Ukuran halaman pagination (maks 100)"),
    service: ButtonClicksService = Depends(),
) -> FilterOptionsResponse:
    return service.get_filter_options(field=field, search=search, page=page, page_size=page_size)