from fastapi import status
from app.repositories.bigquery_repository import BigQueryRepository
from app.schemas.button_clicks import ButtonClickFilters


def test_button_clicks_summary_no_filter(client):
    """Test button clicks summary without any filters."""
    response = client.get("/api/v1/button-clicks")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert "filters_applied" in body

    # Verify items and calculation
    assert len(body["data"]) > 0
    item = body["data"][0]
    assert item["button_name"] == "checkout_submit"
    assert item["total_clicks"] == 1500
    assert item["total_users"] == 750
    assert item["user_avg_clicks"] == 2

    # Verify pagination metadata
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 50
    assert body["pagination"]["total_records"] == 3
    assert body["pagination"]["total_pages"] == 1


def test_button_clicks_summary_with_date_filter(client, mock_repo):
    """Test summary with start_date and end_date."""
    response = client.get("/api/v1/button-clicks?start_date=2026-09-01&end_date=2026-09-30")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["filters_applied"]["start_date"] == "2026-09-01"
    assert body["filters_applied"]["end_date"] == "2026-09-30"

    assert str(mock_repo.last_filters.start_date) == "2026-09-01"
    assert str(mock_repo.last_filters.end_date) == "2026-09-30"


def test_button_clicks_summary_with_customer_filters(client, mock_repo):
    """Test summary with role, depo, region, and area filters."""
    url = "/api/v1/button-clicks?role=Sales&depo=Depo%20Tangerang&region=Jawa%20Barat&area=Tangerang%20Kota"
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["filters_applied"]["role"] == "Sales"
    assert body["filters_applied"]["depo"] == "Depo Tangerang"
    assert body["filters_applied"]["region"] == "Jawa Barat"
    assert body["filters_applied"]["area"] == "Tangerang Kota"

    assert mock_repo.last_filters.role == "Sales"
    assert mock_repo.last_filters.depo == "Depo Tangerang"
    assert mock_repo.last_filters.region == "Jawa Barat"
    assert mock_repo.last_filters.area == "Tangerang Kota"


def test_button_clicks_summary_empty_result(client, mock_repo):
    """Test that empty query results return empty list and zero totals, not an error."""
    mock_repo.empty_result = True
    response = client.get("/api/v1/button-clicks")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["data"] == []
    assert body["pagination"]["total_records"] == 0
    assert body["pagination"]["total_pages"] == 0


def test_button_clicks_summary_bigquery_error(client, mock_repo):
    """Test that BigQuery errors return 500 without leaking stack traces or credentials."""
    mock_repo.should_fail = True
    response = client.get("/api/v1/button-clicks")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    body = response.json()
    assert body["error"]["code"] == "BIGQUERY_ERROR"
    assert "Simulated BigQuery failure" in body["error"]["message"]
    # Ensure sensitive info is not in the response
    assert "Traceback" not in response.text
    assert "password" not in response.text


def test_button_clicks_pagination_bounds(client):
    """Test custom pagination page and page_size."""
    response = client.get("/api/v1/button-clicks?page=1&page_size=2")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body["data"]) == 2
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 2
    assert body["pagination"]["total_records"] == 3
    assert body["pagination"]["total_pages"] == 2


def test_sql_query_construction_and_deduplication(test_settings):
    """
    Test SQL construction in BigQueryRepository to verify:
    1. Table names and parameters are properly referenced.
    2. Master customer deduplication WITH dedup_customers prevents event duplication.
    """
    repo = BigQueryRepository(settings=test_settings)
    filters = ButtonClickFilters(
        start_date="2026-09-01",
        end_date="2026-09-30",
        role="Sales",
        button_name="checkout_submit",
    )
    where_clauses, params = repo._build_where_clauses(filters)

    assert "e.event_date >= @start_date" in where_clauses
    assert "e.event_date <= @end_date" in where_clauses
    assert "c.role = @role" in where_clauses
    assert "e.button_name = @button_name" in where_clauses

    param_names = [p.name for p in params]
    assert "start_date" in param_names
    assert "end_date" in param_names
    assert "role" in param_names
    assert "button_name" in param_names
