import os
import pytest
from app.core.config import get_settings
from app.repositories.bigquery_repository import BigQueryRepository
from app.schemas.button_clicks import ButtonClickFilters

# Run live integration tests only if explicitly requested and credentials exist
RUN_LIVE_TESTS = os.getenv("RUN_LIVE_BQ_TESTS", "0") == "1"


@pytest.mark.skipif(
    not RUN_LIVE_TESTS,
    reason="Live BigQuery integration tests disabled. Enable by setting RUN_LIVE_BQ_TESTS=1 and providing valid GCP credentials.",
)
def test_live_bigquery_connection_and_query():
    """
    Integration test against actual Google BigQuery project.
    Runs only when RUN_LIVE_BQ_TESTS=1 and GOOGLE_APPLICATION_CREDENTIALS is set.
    """
    settings = get_settings()
    repo = BigQueryRepository(settings=settings)

    # 1. Test ping connectivity
    assert repo.check_connection() is True, "Failed to connect to Google BigQuery project."

    # 2. Test summary query with limited page size
    filters = ButtonClickFilters(page_size=5)
    rows, total_records = repo.get_button_clicks_summary(filters=filters, page=1, page_size=5)

    assert isinstance(rows, list)
    assert isinstance(total_records, int)
    if rows:
        row = rows[0]
        assert "button_name" in row
        assert "total_clicks" in row
        assert "total_users" in row
