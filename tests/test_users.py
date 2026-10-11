from fastapi import status


def test_get_users_missing_button_name_fails(client):
    """
    button_name is mandatory on Endpoint C to prevent accidental massive table scans.
    Should return 422 Unprocessable Entity when missing.
    """
    response = client.get("/api/v1/button-clicks/users")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    # Verify that the missing parameter is identified
    issues = [str(d) for d in body["error"].get("details", [])]
    assert any("button_name" in issue for issue in issues)


def test_get_users_success(client):
    """Test retrieving unique users who clicked a button."""
    response = client.get("/api/v1/button-clicks/users?button_name=checkout_submit")
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert "data" in body
    assert "pagination" in body

    users = body["data"]
    assert len(users) == 2

    user = users[0]
    assert user["user_id"] == "EX09202601674"
    assert user["user_clicks"] == 5
    assert "last_event_timestamp" in user
    assert "customer" in user
    assert user["customer"]["role"] == "Sales"
    assert user["customer"]["depo"] == "Depo Tangerang"
    assert user["customer"]["region"] == "Jawa Barat"
    assert user["customer"]["area"] == "Tangerang Kota"


def test_get_users_with_customer_filter(client):
    """Test retrieving users filtered by specific area."""
    url = "/api/v1/button-clicks/users?button_name=checkout_submit&area=Tangerang%20Kota"
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    users = body["data"]
    assert len(users) == 1
    assert users[0]["user_id"] == "EX09202601674"
    assert users[0]["customer"]["area"] == "Tangerang Kota"


def test_get_raw_events_optional_endpoint(client):
    """Test Endpoint D (raw events inspection)."""
    url = "/api/v1/button-clicks/events?button_name=checkout_submit&page=1&page_size=10"
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert "data" in body
    assert len(body["data"]) == 1
    event = body["data"][0]
    assert event["event_name"] == "begin_checkout"
    assert event["platform"] == "ANDROID"
    assert event["device_brand"] == "Samsung"
    assert event["customer"]["role"] == "Sales"
