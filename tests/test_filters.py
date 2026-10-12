from fastapi import status

from app.core.exceptions import InvalidFilterFieldException
from app.repositories.bigquery_repository import BigQueryRepository


def test_filter_options_are_sorted_and_paginated(client):
    response = client.get("/api/v1/filters/button_name?page=2&page_size=2")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["field"] == "button_name"
    assert body["data"] == ["promo_banner_click"]
    assert body["pagination"] == {
        "page": 2,
        "page_size": 2,
        "total_records": 3,
        "total_pages": 2,
    }


def test_filter_options_support_search(client):
    response = client.get("/api/v1/filters/button_name?search=CHECKOUT")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"] == ["checkout_submit"]


def test_filter_options_reject_unknown_field(client):
    response = client.get("/api/v1/filters/not_a_column")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_filter_options_requires_api_key(unauthenticated_client):
    response = unauthenticated_client.get("/api/v1/filters/role")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_filter_options_parameterizes_search(test_settings, monkeypatch):
    repo = BigQueryRepository(settings=test_settings)
    captured = {}

    def fake_execute(query, parameters):
        captured["query"] = query
        captured["parameters"] = parameters
        return []

    monkeypatch.setattr(repo, "_execute_query", fake_execute)
    repo.get_filter_options(
        field="button_name",
        search="' OR 1=1 --",
        page=1,
        page_size=10,
    )

    assert "OR 1=1" not in captured["query"]
    assert next(parameter for parameter in captured["parameters"] if parameter.name == "search").value == "%\' or 1=1 --%"