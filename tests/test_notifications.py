import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import json

def test_get_notifications(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting user notifications."""
    # Mock the notifications response
    mock_notifications = [
        {
            "id": 1,
            "created_at": "2025-03-01T10:00:00+00:00",
            "user_id": mock_authenticate_user,
            "type": "welcome_first_conversation",
            "title": "Welcome to Archimind",
            "body": "Get started by analyzing your first conversation.",
            "read_at": None,
            "metadata": {
                "action_type": "view",
                "action_title_key": "welcome_action", 
                "action_url": "/welcome"
            }
        },
        {
            "id": 2,
            "created_at": "2025-03-02T11:00:00+00:00",
            "user_id": mock_authenticate_user,
            "type": "insight_prompt_length",
            "title": "Prompt Length Insight",
            "body": "Your prompts are getting better!",
            "read_at": "2025-03-02T12:00:00+00:00",
            "metadata": {
                "action_type": "view", 
                "action_title_key": "insight_action",
                "action_url": "/insights/prompt-length"
            }
        }
    ]
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.data = mock_notifications
    mock_supabase["notifications"].table().select().eq().order().execute.return_value = mock_response
    
    # Skip the check_user_notifications call
    with patch('utils.notification_service.check_user_notifications'):
        # Make the request
        response = test_client.get("/notifications/", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 2
    
    # Verify table call was made
    assert mock_supabase["notifications"].table.called
    assert mock_supabase["notifications"].table().select().eq.called
    assert mock_supabase["notifications"].table().select().eq().order.called

def test_get_notification_count(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting notification counts."""
    # Mock the total counts
    total_response = MagicMock()
    total_response.count = 5
    total_response.data = [{"id": i} for i in range(5)]
    
    # Mock the unread counts
    unread_response = MagicMock()
    unread_response.count = 2
    unread_response.data = [{"id": i} for i in range(2)]
    
    # Setup the mock table method
    mock_supabase["notifications"].table().select().eq().execute.return_value = total_response
    mock_supabase["notifications"].table().select().eq().is_().execute.return_value = unread_response
    
    # Make the request
    response = test_client.get("/notifications/count", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["total"] == 5
    assert response.json()["unread"] == 2
    
    # Verify table calls
    assert mock_supabase["notifications"].table.called

def test_create_notification(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test creating a notification."""
    # Mock the notification creation response
    created_notification = {
        "id": 3,
        "created_at": "2025-03-03T12:00:00+00:00",
        "user_id": mock_authenticate_user,
        "type": "custom",
        "title": "Custom Notification",
        "body": "This is a custom notification",
        "read_at": None,
        "metadata": {
            "action_type": "view", 
            "action_title_key": "custom_action",
            "action_url": "/custom"
        }
    }
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.data = [created_notification]
    mock_supabase["notifications"].table().insert().execute.return_value = mock_response
    
    # Notification data to send
    notification_data = {
        "user_id": mock_authenticate_user,
        "type": "custom",
        "title": "Custom Notification",
        "body": "This is a custom notification",
        "metadata": {
            "action_type": "view", 
            "action_title_key": "custom_action",
            "action_url": "/custom"
        }
    }
    
    # Make the request
    response = test_client.post("/notifications/create", json=notification_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["title"] == "Custom Notification"
    
    # Verify table calls
    assert mock_supabase["notifications"].table.called
    assert mock_supabase["notifications"].table().insert.called

def test_mark_notification_read(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test marking a notification as read."""
    # Mock verification check
    verify_response = MagicMock()
    verify_response.data = [{"id": 1}]
    mock_supabase["notifications"].table().select().eq().eq().execute.return_value = verify_response
    
    # Mock update response
    update_response = MagicMock()
    update_response.data = [{
        "id": 1,
        "read_at": "2025-03-03T15:30:00+00:00"
    }]
    mock_supabase["notifications"].table().update().eq().execute.return_value = update_response
    
    # Make the request
    response = test_client.post("/notifications/1/read", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["notification_id"] == "1"
    
    # Verify table calls
    assert mock_supabase["notifications"].table.called
    assert mock_supabase["notifications"].table().select().eq().eq.called
    assert mock_supabase["notifications"].table().update().eq.called

def test_mark_all_notifications_read(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test marking all notifications as read."""
    # Mock unread notifications query
    unread_response = MagicMock()
    unread_response.data = [{"id": i} for i in range(3)]
    mock_supabase["notifications"].table().select().eq().is_().execute.return_value = unread_response
    
    # Mock update response
    update_response = MagicMock()
    update_response.data = unread_response.data
    mock_supabase["notifications"].table().update().eq().is_().execute.return_value = update_response
    
    # Make the request
    response = test_client.post("/notifications/read-all", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["notifications_updated"] == 3
    
    # Verify table calls
    assert mock_supabase["notifications"].table.called
    assert mock_supabase["notifications"].table().select().eq().is_().execute.called
    assert mock_supabase["notifications"].table().update().eq().is_().execute.called

def test_delete_notification(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test deleting a notification."""
    # Mock verification check
    verify_response = MagicMock()
    verify_response.data = [{"id": 1}]
    mock_supabase["notifications"].table().select().eq().eq().execute.return_value = verify_response
    
    # Mock delete response
    delete_response = MagicMock()
    delete_response.data = [{"id": 1}]
    mock_supabase["notifications"].table().delete().eq().execute.return_value = delete_response
    
    # Make the request
    response = test_client.delete("/notifications/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["notification_id"] == "1"
    
    # Verify table calls
    assert mock_supabase["notifications"].table.called
    assert mock_supabase["notifications"].table().select().eq().eq.called
    assert mock_supabase["notifications"].table().delete().eq.called