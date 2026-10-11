from fastapi import status


def test_health_check_public(unauthenticated_client):
    """Health check must be accessible without API key and return correct schema."""
    response = unauthenticated_client.get("/health")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
    assert "version" in body
    assert body["environment"] == "testing"


def test_readiness_probe_success(client, mock_repo):
    """Readiness probe verifies BigQuery connectivity."""
    mock_repo.is_ready = True
    response = client.get("/health/ready")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body["status"] == "ready"
    assert body["bigquery"] == "connected"
    assert body["project_id"] == "rangkul-355bb"


def test_readiness_probe_failure(client, mock_repo):
    """Readiness probe returns 503 when BigQuery is not available."""
    mock_repo.is_ready = False
    response = client.get("/health/ready")
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    body = response.json()
    assert body["error"]["code"] == "BIGQUERY_NOT_READY"
