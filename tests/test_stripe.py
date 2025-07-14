import pytest
from unittest.mock import patch
import utils.auth


def _request_data(user_id):
    return {
        "priceId": "price_123",
        "successUrl": "http://example.com/success",
        "cancelUrl": "http://example.com/cancel",
        "userId": user_id,
        "userEmail": "user@example.com",
    }


def test_invalid_success_url_scheme(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    data = _request_data(mock_authenticate_user)
    data["successUrl"] = "ftp://bad.url"
    test_client.app.dependency_overrides[utils.auth.get_current_user] = lambda: mock_authenticate_user
    with patch('routes.stripe.create_checkout_session.stripe_service.create_checkout_session') as mock_service:
        response = test_client.post("/stripe/create-checkout-session", json=data, headers=valid_auth_header)
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid redirect URL"
        mock_service.assert_not_called()
    test_client.app.dependency_overrides = {}


def test_invalid_cancel_url_scheme(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    data = _request_data(mock_authenticate_user)
    data["cancelUrl"] = "javascript:alert(1)"
    test_client.app.dependency_overrides[utils.auth.get_current_user] = lambda: mock_authenticate_user
    with patch('routes.stripe.create_checkout_session.stripe_service.create_checkout_session') as mock_service:
        response = test_client.post("/stripe/create-checkout-session", json=data, headers=valid_auth_header)
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid redirect URL"
        mock_service.assert_not_called()
    test_client.app.dependency_overrides = {}
