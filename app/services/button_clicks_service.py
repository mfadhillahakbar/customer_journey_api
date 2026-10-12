import math
from datetime import date, timedelta
from typing import Optional
from fastapi import Depends
from app.core.exceptions import BigQueryReadinessError, InvalidDateRangeException
from app.repositories.bigquery_repository import BigQueryRepository, get_bigquery_repository
from app.schemas.button_clicks import (
    DashboardAnalyticsResponse,
    DashboardCharts,
    DashboardDateRange,
    DashboardDailyTrendItem,
    DashboardFeatureDistributionItem,
    DashboardFiltersApplied,
    DashboardKPI,
    DashboardPeriod,
    DashboardTopButton,
    ButtonClickFilters,
    ButtonClickItem,
    ButtonClickSummaryResponse,
    ButtonClickUserItem,
    ButtonClickUsersResponse,
    CustomerDetail,
    FilterOptionsResponse,
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

    def get_filter_options(
        self,
        field: str,
        search: Optional[str],
        page: int,
        page_size: int,
    ) -> FilterOptionsResponse:
        """Load distinct values for a filter control."""
        values, total_records = self.repository.get_filter_options(
            field=field,
            search=search,
            page=page,
            page_size=page_size,
        )
        return FilterOptionsResponse(
            field=field,
            data=values,
            pagination=self._calculate_pagination(page, page_size, total_records),
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
                    user_id=str(row.get("user_id")),
                    user_pseudo_id=str(row.get("user_pseudo_id")) if row.get("user_pseudo_id") is not None else None,
                    event_name=row.get("event_name"),
                    screen_name=row.get("screen_name"),
                    button_name=row.get("button_name"),
                    ga_session_id=str(row.get("ga_session_id")) if row.get("ga_session_id") is not None else None,
                    ga_session_number=int(row.get("ga_session_number")) if row.get("ga_session_number") is not None else None,
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

    def _resolve_dashboard_date_range(
        self,
        period: DashboardPeriod,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> tuple[date, date]:
        """Resolve effective date range from period preset or custom input."""
        today = date.today()

        if period == DashboardPeriod.today:
            return today, today

        if period == DashboardPeriod.yesterday:
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday

        if period == DashboardPeriod.last_7_days:
            return today - timedelta(days=6), today

        if period == DashboardPeriod.last_30_days:
            return today - timedelta(days=29), today

        if period == DashboardPeriod.custom:
            if start_date is None or end_date is None:
                raise InvalidDateRangeException("Untuk period=custom, start_date dan end_date wajib diisi.")
            if start_date > end_date:
                raise InvalidDateRangeException("start_date harus lebih awal dari atau sama dengan end_date.")
            return start_date, end_date

        raise InvalidDateRangeException("Nilai period tidak dikenali.")

    def get_dashboard_analytics(
        self,
        period: DashboardPeriod,
        start_date: Optional[date],
        end_date: Optional[date],
        role: Optional[str],
        depo: Optional[str],
        region: Optional[str],
        area: Optional[str],
    ) -> DashboardAnalyticsResponse:
        """Process unified dashboard analytics response (KPI + charts)."""
        resolved_start_date, resolved_end_date = self._resolve_dashboard_date_range(
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        filters = ButtonClickFilters(
            start_date=resolved_start_date,
            end_date=resolved_end_date,
            role=role,
            depo=depo,
            region=region,
            area=area,
        )

        payload = self.repository.get_dashboard_analytics(filters=filters)
        kpi_raw = payload.get("kpi") or {}
        top_button_raw = kpi_raw.get("top_button") or {}

        return DashboardAnalyticsResponse(
            kpi=DashboardKPI(
                total_clicks=int(kpi_raw.get("total_clicks") or 0),
                unique_users=int(kpi_raw.get("unique_users") or 0),
                avg_clicks_per_user=round(float(kpi_raw.get("avg_clicks_per_user") or 0.0), 2),
                top_button=DashboardTopButton(
                    button_name=top_button_raw.get("button_name"),
                    total_clicks=int(top_button_raw.get("total_clicks") or 0),
                ),
            ),
            charts=DashboardCharts(
                daily_trend=[
                    DashboardDailyTrendItem(
                        date=str(item.get("label")),
                        total_clicks=int(item.get("total_clicks") or 0),
                    )
                    for item in (payload.get("daily_trend") or [])
                ],
                feature_distribution=[
                    DashboardFeatureDistributionItem(
                        category=str(item.get("label")),
                        total_clicks=int(item.get("total_clicks") or 0),
                    )
                    for item in (payload.get("feature_distribution") or [])
                ],
            ),
            filters_applied=DashboardFiltersApplied(
                period=period,
                date_range=DashboardDateRange(
                    start_date=str(resolved_start_date),
                    end_date=str(resolved_end_date),
                ),
                role=role,
                region=region,
                depo=depo,
                area=area,
            ),
        )

    def check_readiness(self) -> bool:
        """Verify BigQuery connectivity for readiness probe."""
        is_alive = self.repository.check_connection()
        if not is_alive:
            raise BigQueryReadinessError("Koneksi BigQuery tidak siap untuk menerima traffic.")
        return True
