import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.exceptions import BigQueryExecutionError, InvalidFilterFieldException
from app.main import create_app
from app.repositories.bigquery_repository import BigQueryRepository, get_bigquery_repository
from app.schemas.button_clicks import ButtonClickFilters, split_filter_values


class MockBigQueryRepository(BigQueryRepository):
    """
    Mock implementation of BigQueryRepository for unit testing.
    Runs entirely without Google Cloud credentials or network calls.
    """

    def __init__(self, settings: Settings):
        super().__init__(settings=settings, client=None)
        self.should_fail: bool = False
        self.empty_result: bool = False
        self.is_ready: bool = True
        self.last_filters: Optional[ButtonClickFilters] = None

    def check_connection(self) -> bool:
        return self.is_ready

    def get_button_clicks_summary(
        self,
        filters: ButtonClickFilters,
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        self.last_filters = filters

        if self.should_fail:
            raise BigQueryExecutionError("Simulated BigQuery failure for testing.")

        if self.empty_result:
            return [], 0

        # Sample mock aggregation rows adhering to business query calculations
        all_data = [
            {
                "screen_name": "checkout",
                "button_name": "checkout_submit",
                "event_name": "begin_checkout",
                "total_clicks": 1500,
                "total_users": 750,
                "user_avg_clicks": 2,  # 1500 / 750 = 2
            },
            {
                "screen_name": "home_page",
                "button_name": "promo_banner_click",
                "event_name": "banner_click",
                "total_clicks": 800,
                "total_users": 400,
                "user_avg_clicks": 2,
            },
            {
                "screen_name": None,  # Preserved screen_name NULL
                "button_name": "floating_help_btn",
                "event_name": "help_click",
                "total_clicks": 120,
                "total_users": 60,
                "user_avg_clicks": 2,
            },
        ]

        # Filter by button_name if provided
        if filters.button_name:
            keywords = [value.lower() for value in split_filter_values(filters.button_name)]
            all_data = [
                d for d in all_data
                if any(keyword in d["button_name"].lower() for keyword in keywords)
            ] if keywords else []

        # Filter by screen_name if provided
        if filters.screen_name:
            values = split_filter_values(filters.screen_name)
            all_data = [d for d in all_data if d["screen_name"] in values] if values else []

        total_records = len(all_data)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_data = all_data[start_idx:end_idx]

        return paged_data, total_records

    def get_button_click_users(
        self,
        filters: ButtonClickFilters,
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        self.last_filters = filters

        if self.should_fail:
            raise BigQueryExecutionError("Simulated BigQuery failure for testing.")

        if self.empty_result:
            return [], 0

        all_users = [
            {
                "user_id": "EX09202601674",
                "user_clicks": 5,
                "last_event_timestamp": datetime.fromisoformat("2026-09-16T12:57:19.821000"),
                "role": "Sales",
                "depo": "Depo Tangerang",
                "region": "Jawa Barat",
                "area": "Tangerang Kota",
            },
            {
                "user_id": "EX09202609999",
                "user_clicks": 3,
                "last_event_timestamp": datetime.fromisoformat("2026-09-16T10:15:00.000000"),
                "role": "Sales",
                "depo": "Depo Tangerang",
                "region": "Jawa Barat",
                "area": "Tangerang Barat",
            },
        ]

        for field in ("role", "depo", "region", "area"):
            value = getattr(filters, field)
            if value:
                values = split_filter_values(value)
                all_users = [u for u in all_users if u[field] in values] if values else []

        total_records = len(all_users)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_users = all_users[start_idx:end_idx]

        return paged_users, total_records

    def get_raw_events(
        self,
        filters: ButtonClickFilters,
        user_id: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        if self.should_fail:
            raise BigQueryExecutionError("Simulated BigQuery failure for testing.")

        if self.empty_result:
            return [], 0

        events = [
            {
                "event_date": "2026-09-16",
                "event_timestamp": datetime.fromisoformat("2026-09-16T12:46:41.980000"),
                "user_id": "EX09202601674",
                "user_pseudo_id": "009ee1be58bce5c5bed77bdd5eca074f",
                "event_name": "begin_checkout",
                "screen_name": "checkout",
                "button_name": "checkout_submit",
                "ga_session_id": "1694868400",
                "ga_session_number": 1,
                "platform": "ANDROID",
                "device_category": "mobile",
                "device_brand": "Samsung",
                "device_model": "Galaxy S23",
                "os_version": "Android 14",
                "city": "Tangerang",
                "app_version": "3.15.17",
                "role": "Sales",
                "depo": "Depo Tangerang",
                "region": "Jawa Barat",
                "area": "Tangerang Kota",
            }
        ]

        return events, len(events)

    def get_filter_options(
        self,
        field: str,
        search: Optional[str],
        page: int,
        page_size: int,
    ) -> Tuple[List[str], int]:
        values_by_field = {
            "role": ["Sales", "Staff"],
            "depo": ["Depo Jakarta", "Depo Tangerang"],
            "region": ["Jawa Barat", "Jawa Timur"],
            "area": ["Tangerang Barat", "Tangerang Kota"],
            "screen_name": ["checkout", "home_page"],
            "button_name": ["checkout_submit", "floating_help_btn", "promo_banner_click"],
            "event_name": ["banner_click", "begin_checkout", "help_click"],
            "user_id": ["EX09202601674", "EX09202609999"],
        }
        if field not in values_by_field:
            raise InvalidFilterFieldException(f"Field filter tidak didukung: {field}.")
        values = values_by_field[field]
        if search and search.strip():
            keyword = search.strip().lower()
            values = [value for value in values if keyword in value.lower()]
        start_idx = (page - 1) * page_size
        return values[start_idx:start_idx + page_size], len(values)

    def get_dashboard_analytics(self, filters: ButtonClickFilters) -> Dict[str, Any]:
        self.last_filters = filters

        if self.should_fail:
            raise BigQueryExecutionError("Simulated BigQuery failure for testing.")

        if self.empty_result:
            return {
                "kpi": {
                    "total_clicks": 0,
                    "unique_users": 0,
                    "avg_clicks_per_user": 0.0,
                    "top_button": None,
                },
                "daily_trend": [],
                "feature_distribution": [],
            }

        return {
            "kpi": {
                "total_clicks": 200,
                "unique_users": 50,
                "avg_clicks_per_user": 4.0,
                "top_button": {
                    "button_name": "checkout_submit",
                    "total_clicks": 75,
                },
            },
            "daily_trend": [
                {
                    "label": "2026-10-10",
                    "total_clicks": 120,
                },
                {
                    "label": "2026-10-11",
                    "total_clicks": 80,
                },
            ],
            "feature_distribution": [
                {
                    "label": "checkout",
                    "total_clicks": 120,
                },
                {
                    "label": "home_page",
                    "total_clicks": 80,
                },
            ],
        }


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        ENVIRONMENT="testing",
        API_KEY="test-secret-api-key-12345",
        ALLOWED_ORIGINS="http://localhost:3000",
        GCP_PROJECT_ID="rangkul-355bb",
        BQ_DATASET="analytics_journey",
        BQ_EVENTS_TABLE="rangkul-355bb.analytics_journey.raw_events_agustus_september",
        BQ_CUSTOMERS_TABLE="rangkul-355bb.analytics_journey.all_customer_rangkul",
    )


@pytest.fixture
def mock_repo(test_settings: Settings) -> MockBigQueryRepository:
    return MockBigQueryRepository(settings=test_settings)


@pytest.fixture
def app(test_settings: Settings, mock_repo: MockBigQueryRepository):
    application = create_app(settings=test_settings)
    application.dependency_overrides[get_settings] = lambda: test_settings
    application.dependency_overrides[get_bigquery_repository] = lambda: mock_repo
    return application


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(
        app,
        headers={"X-API-Key": "test-secret-api-key-12345"},
    )


@pytest.fixture
def unauthenticated_client(app) -> TestClient:
    return TestClient(app)
