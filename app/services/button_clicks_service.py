import math
from typing import Optional
from fastapi import Depends
from app.core.exceptions import BigQueryReadinessError
from app.repositories.bigquery_repository import BigQueryRepository, get_bigquery_repository
from app.schemas.button_clicks import (
    ButtonClickFilters,
    ButtonClickItem,
    ButtonClickSummaryResponse,
    ButtonClickUserItem,
    ButtonClickUsersResponse,
    CustomerDetail,
    FiltersApplied,
    RawEventItem,
    RawEventsResponse,
)
from app.schemas.common import PaginationMetadata


class ButtonClicksService:
    """Service layer coordinating business logic between endpoints and BigQuery repository."""

    def __init__(self, repository: BigQueryRepository = Depends(get_bigquery_repository)):
        self.repository = repository

    def _build_filters_applied(self, filters: ButtonClickFilters) -> FiltersApplied:
        """Serialize applied filters into API response metadata."""
        return FiltersApplied(
            start_date=str(filters.start_date) if filters.start_date else None,
            end_date=str(filters.end_date) if filters.end_date else None,
            role=filters.role,
            region=filters.region,
            depo=filters.depo,
            area=filters.area,
            screen_name=filters.screen_name,
            button_name=filters.button_name,
            event_name=filters.event_name,
        )

    def _calculate_pagination(self, page: int, page_size: int, total_records: int) -> PaginationMetadata:
        """Compute pagination totals consistently."""
        total_pages = math.ceil(total_records / page_size) if total_records > 0 else 0
        return PaginationMetadata(
            page=page,
            page_size=page_size,
            total_records=total_records,
            total_pages=total_pages,
        )

    def get_summary(
        self,
        filters: ButtonClickFilters,
        page: int,
        page_size: int,
    ) -> ButtonClickSummaryResponse:
        """Process summary aggregation request for Endpoint B."""
        rows, total_records = self.repository.get_button_clicks_summary(
            filters=filters,
            page=page,
            page_size=page_size,
        )

        data = [
            ButtonClickItem(
                screen_name=row.get("screen_name"),
                button_name=row["button_name"],
                event_name=row.get("event_name"),
                total_clicks=row["total_clicks"],
                total_users=row["total_users"],
                user_avg_clicks=row["user_avg_clicks"],
            )
            for row in rows
        ]

        return ButtonClickSummaryResponse(
            data=data,
            pagination=self._calculate_pagination(page, page_size, total_records),
            filters_applied=self._build_filters_applied(filters),
        )

    def get_users(
        self,
        filters: ButtonClickFilters,
        page: int,
        page_size: int,
    ) -> ButtonClickUsersResponse:
        """Process unique users request for Endpoint C."""
        rows, total_records = self.repository.get_button_click_users(
            filters=filters,
            page=page,
            page_size=page_size,
        )

        data = []
        for row in rows:
            customer = CustomerDetail(
                role=row.get("role"),
                depo=row.get("depo"),
                region=row.get("region"),
                area=row.get("area"),
            )
            data.append(
                ButtonClickUserItem(
                    user_id=row["user_id"],
                    user_clicks=row["user_clicks"],
                    last_event_timestamp=row.get("last_event_timestamp"),
                    customer=customer,
                )
            )

        return ButtonClickUsersResponse(
            data=data,
            pagination=self._calculate_pagination(page, page_size, total_records),
            filters_applied=self._build_filters_applied(filters),
        )

    def get_raw_events(
        self,
        filters: ButtonClickFilters,
        user_id: Optional[str],
        page: int,
        page_size: int,
    ) -> RawEventsResponse:
        """Process raw events request for Endpoint D."""
        rows, total_records = self.repository.get_raw_events(
            filters=filters,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

        data = []
        for row in rows:
            customer = CustomerDetail(
                role=row.get("role"),
                depo=row.get("depo"),
                region=row.get("region"),
                area=row.get("area"),
            )
            data.append(
                RawEventItem(
                    event_date=str(row.get("event_date")) if row.get("event_date") else None,
                    event_timestamp=row.get("event_timestamp"),
                    user_id=row["user_id"],
                    user_pseudo_id=row.get("user_pseudo_id"),
                    event_name=row.get("event_name"),
                    screen_name=row.get("screen_name"),
                    button_name=row.get("button_name"),
                    ga_session_id=row.get("ga_session_id"),
                    ga_session_number=row.get("ga_session_number"),
                    platform=row.get("platform"),
                    device_category=row.get("device_category"),
                    device_brand=row.get("device_brand"),
                    device_model=row.get("device_model"),
                    os_version=row.get("os_version"),
                    city=row.get("city"),
                    app_version=row.get("app_version"),
                    customer=customer,
                )
            )

        return RawEventsResponse(
            data=data,
            pagination=self._calculate_pagination(page, page_size, total_records),
            filters_applied=self._build_filters_applied(filters),
        )

    def check_readiness(self) -> bool:
        """Verify BigQuery connectivity for readiness probe."""
        is_alive = self.repository.check_connection()
        if not is_alive:
            raise BigQueryReadinessError("Koneksi BigQuery tidak siap untuk menerima traffic.")
        return True
