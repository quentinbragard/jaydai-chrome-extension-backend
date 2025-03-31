import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

def test_get_user_stats(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting user statistics."""
    # Mock the chats response
    mock_chats = [
        {"id": 1, "created_at": "2025-03-01T12:00:00+00:00"},
        {"id": 2, "created_at": "2025-03-05T12:00:00+00:00"},
        {"id": 3, "created_at": "2025-03-10T12:00:00+00:00"}
    ]
    
    # Create a response for total chats
    chats_response = MagicMock()
    chats_response.data = mock_chats
    
    # Create response for recent chats
    recent_chats_response = MagicMock()
    recent_chats_response.data = [mock_chats[1], mock_chats[2]]
    
    # Mock the messages response
    mock_messages = [
        {
            "id": 1,
            "chat_provider_id": "chat_1",
            "role": "user",
            "content": "Hello, how are you?",
            "created_at": "2025-03-01T12:00:00+00:00",
            "message_provider_id": "msg_1",
            "model": "gpt-4"
        },
        {
            "id": 2,
            "chat_provider_id": "chat_1",
            "role": "assistant",
            "content": "I'm doing well, thank you for asking!",
            "created_at": "2025-03-01T12:00:05+00:00",
            "parent_message_provider_id": "msg_1",
            "message_provider_id": "msg_2",
            "model": "gpt-4"
        },
        {
            "id": 3,
            "chat_provider_id": "chat_2",
            "role": "user",
            "content": "What is the weather like today?",
            "created_at": "2025-03-05T12:00:00+00:00",
            "message_provider_id": "msg_3",
            "model": "gpt-3.5-turbo"
        },
        {
            "id": 4,
            "chat_provider_id": "chat_2",
            "role": "assistant",
            "content": "I don't have access to real-time weather information. You would need to check a weather service or look outside.",
            "created_at": "2025-03-05T12:00:10+00:00",
            "parent_message_provider_id": "msg_3",
            "message_provider_id": "msg_4",
            "model": "gpt-3.5-turbo"
        }
    ]
    
    messages_response = MagicMock()
    messages_response.data = mock_messages
    
    # Set up the mock returns
    # First mock call returns chats, second returns messages
    mock_supabase["stats"].table().select().eq().execute.side_effect = [chats_response, messages_response]
    mock_supabase["stats"].table().select().eq().gte().execute.return_value = recent_chats_response
    
    # Mock datetime.now() for consistent test results
    current_date = datetime(2025, 3, 15)
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_date
        # datetime.fromisoformat is used in the stats calculation, so we need to pass through the real implementation
        mock_datetime.fromisoformat = datetime.fromisoformat
        # Make the request
        response = test_client.get("/stats/user", headers=valid_auth_header)
    
    # Basic assertions
    assert response.status_code == 200
    assert "total_chats" in response.json()
    assert "token_usage" in response.json()
    assert "energy_usage" in response.json()
    assert "thinking_time" in response.json()
    assert "model_usage" in response.json()
    
    # Verify the correct values were returned
    assert response.json()["total_chats"] == 3
    assert "gpt-4" in response.json()["model_usage"]
    assert "gpt-3.5-turbo" in response.json()["model_usage"]
    
    # Verify table calls were made
    assert mock_supabase["stats"].table.called