import pytest
from unittest.mock import patch, MagicMock

def test_sign_up_success(test_client, mock_supabase):
    """Test successful user sign up."""
    # Create proper mock response objects
    # User mock
    user_mock = MagicMock()
    user_mock.id = "test-user-id"
    user_mock.email = "test@example.com"
    
    # Session mock
    session_mock = MagicMock()
    session_mock.access_token = "fake_access_token"
    session_mock.refresh_token = "fake_refresh_token"
    session_mock.expires_at = 3600
    
    # Response object
    auth_response = MagicMock()
    auth_response.user = user_mock
    auth_response.session = session_mock
    
    # Mock the auth signup method
    mock_supabase["auth"].auth.sign_up.return_value = auth_response
    
    # Mock user metadata
    metadata_mock = {"user_id": "test-user-id", "name": "Test User"}
    metadata_response = MagicMock()
    metadata_response.data = [metadata_mock]
    
    # Mock the insert method
    mock_supabase["auth"].table().insert().execute.return_value = metadata_response
    
    # Make the request
    response = test_client.post(
        "/auth/sign_up",
        json={"email": "test@example.com", "password": "password123", "name": "Test User"}
    )
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "user" in response.json()
    assert "session" in response.json()
    assert "message" in response.json()
    assert response.json()["session"]["access_token"] == "fake_access_token"

def test_sign_in_success(test_client, mock_supabase):
    """Test successful user sign in."""
    # Create proper class instances (not dictionaries or MagicMocks)
    class User:
        def __init__(self):
            self.id = "test-user-id"
            self.email = "test@example.com"
            # Regular classes have a __dict__ that the route handler can spread

    class Session:
        def __init__(self):
            self.access_token = "fake_access_token"
            self.refresh_token = "fake_refresh_token"
            self.expires_at = 3600

    class AuthResponse:
        def __init__(self):
            self.user = User()
            self.session = Session()

    # Create our auth response as an actual class instance
    auth_response = AuthResponse()
    mock_supabase["auth"].auth.sign_in_with_password.return_value = auth_response
    
    # Mock user metadata
    metadata_response = MagicMock()
    metadata_response.data = {
        "name": "Test User",
        "additional_email": "test@example.com",
        "phone_number": None,
        "additional_organization": None,
        "pinned_official_folder_ids": [1],
        "pinned_organization_folder_ids": []
    }
    
    # Mock the metadata query
    mock_supabase["auth"].table().select().eq().single().execute.return_value = metadata_response
    
    # Mock the notifications service
    with patch('utils.notification_service.NotificationService.create_welcome_notification'):
        # Make the request
        response = test_client.post(
            "/auth/sign_in",
            json={"email": "test@example.com", "password": "password123"}
        )
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "user" in response.json()
    assert "session" in response.json()

def test_refresh_token_success(test_client, mock_supabase):
    """Test successful token refresh."""
    # Create session mock
    session_mock = MagicMock()
    session_mock.access_token = "new_access_token"
    session_mock.refresh_token = "new_refresh_token"
    session_mock.expires_at = 3600
    
    # Create response mock
    auth_response = MagicMock()
    auth_response.session = session_mock
    
    # Mock refresh_session method
    mock_supabase["auth"].auth.refresh_session.return_value = auth_response
    
    # Make the request
    response = test_client.post(
        "/auth/refresh_token",
        json={"refresh_token": "old_refresh_token"}
    )
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "session" in response.json()
    assert response.json()["session"]["access_token"] == "new_access_token"
    assert response.json()["session"]["refresh_token"] == "new_refresh_token"