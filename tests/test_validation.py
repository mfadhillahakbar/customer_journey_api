from fastapi import status


def test_invalid_date_format(client):
    """Test passing invalid date format string."""
    response = client.get("/api/v1/button-clicks?start_date=invalid-date")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_start_date_greater_than_end_date(client):
    """
    Test condition when start_date > end_date.
    Must return 400 Bad Request with code INVALID_DATE_RANGE.
    """
    response = client.get("/api/v1/button-clicks?start_date=2026-09-30&end_date=2026-09-01")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    body = response.json()
    assert body["error"]["code"] == "INVALID_DATE_RANGE"
    assert "start_date harus lebih awal dari atau sama dengan end_date." in body["error"]["message"]


def test_page_size_exceeds_maximum(client):
    """page_size greater than 100 must be rejected."""
    response = client.get("/api/v1/button-clicks?page_size=150")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_page_less_than_one(client):
    """page less than 1 must be rejected."""
    response = client.get("/api/v1/button-clicks?page=0")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_missing_api_key_unauthorized(unauthenticated_client):
    """Protected endpoints must return 401 UNAUTHORIZED when X-API-Key is missing."""
    response = unauthenticated_client.get("/api/v1/button-clicks")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_invalid_api_key_unauthorized(app):
    """Protected endpoints must return 401 UNAUTHORIZED when X-API-Key is invalid."""
    from fastapi.testclient import TestClient
    bad_client = TestClient(app, headers={"X-API-Key": "wrong-secret-key"})
    response = bad_client.get("/api/v1/button-clicks")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
