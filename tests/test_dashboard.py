from datetime import date
from fastapi import status


def test_dashboard_default_period_last_7_days(client, mock_repo):
    response = client.get("/api/v1/button-clicks/dashboard")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert "kpi" in body
    assert "charts" in body
    assert "filters_applied" in body
    assert body["kpi"]["total_clicks"] == 200
    assert body["kpi"]["unique_users"] == 50
    assert body["kpi"]["avg_clicks_per_user"] == 4.0
    assert body["kpi"]["top_button"]["button_name"] == "checkout_submit"

    assert body["filters_applied"]["period"] == "last_7_days"
    start_date = date.fromisoformat(body["filters_applied"]["date_range"]["start_date"])
    end_date = date.fromisoformat(body["filters_applied"]["date_range"]["end_date"])
    assert end_date >= start_date
    assert (end_date - start_date).days == 6

    assert str(mock_repo.last_filters.start_date) == body["filters_applied"]["date_range"]["start_date"]
    assert str(mock_repo.last_filters.end_date) == body["filters_applied"]["date_range"]["end_date"]


def test_dashboard_custom_period_requires_dates(client):
    response = client.get("/api/v1/button-clicks/dashboard?period=custom")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    body = response.json()
    assert body["error"]["code"] == "INVALID_DATE_RANGE"
    assert "start_date dan end_date wajib diisi" in body["error"]["message"]


def test_dashboard_custom_period_invalid_range(client):
    response = client.get(
        "/api/v1/button-clicks/dashboard?period=custom&start_date=2026-10-11&end_date=2026-10-10"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    body = response.json()
    assert body["error"]["code"] == "INVALID_DATE_RANGE"


def test_dashboard_custom_period_with_filters(client, mock_repo):
    response = client.get(
        "/api/v1/button-clicks/dashboard?period=custom&start_date=2026-10-01&end_date=2026-10-10"
        "&role=Sales&depo=Depo%20Tangerang&region=Jawa%20Barat&area=Tangerang%20Kota"
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["filters_applied"]["period"] == "custom"
    assert body["filters_applied"]["date_range"]["start_date"] == "2026-10-01"
    assert body["filters_applied"]["date_range"]["end_date"] == "2026-10-10"
    assert body["filters_applied"]["role"] == "Sales"
    assert body["filters_applied"]["depo"] == "Depo Tangerang"
    assert body["filters_applied"]["region"] == "Jawa Barat"
    assert body["filters_applied"]["area"] == "Tangerang Kota"

    assert mock_repo.last_filters.role == "Sales"
    assert mock_repo.last_filters.depo == "Depo Tangerang"
    assert mock_repo.last_filters.region == "Jawa Barat"
    assert mock_repo.last_filters.area == "Tangerang Kota"
    assert str(mock_repo.last_filters.start_date) == "2026-10-01"
    assert str(mock_repo.last_filters.end_date) == "2026-10-10"


def test_dashboard_empty_result(client, mock_repo):
    mock_repo.empty_result = True
    response = client.get("/api/v1/button-clicks/dashboard")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["kpi"]["total_clicks"] == 0
    assert body["kpi"]["unique_users"] == 0
    assert body["kpi"]["avg_clicks_per_user"] == 0.0
    assert body["charts"]["daily_trend"] == []
    assert body["charts"]["feature_distribution"] == []


def test_dashboard_bigquery_error(client, mock_repo):
    mock_repo.should_fail = True
    response = client.get("/api/v1/button-clicks/dashboard")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    body = response.json()
    assert body["error"]["code"] == "BIGQUERY_ERROR"
