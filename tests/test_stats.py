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
    
    # Mock for total chats
    chats_response = MagicMock()
    chats_response.data = mock_chats
    
    # Mock for recent chats
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
    
    # Setup the table mocks to return our prepared responses
    mock_supabase["stats"].table().select().eq().execute.side_effect = [chats_response, messages_response]
    mock_supabase["stats"].table().select().eq().gte().execute.return_value = recent_chats_response
    
    # Make the request
    response = test_client.get("/stats/user", headers=valid_auth_header)
    
    # Assertions - just check the status code and some fields
    assert response.status_code == 200
    assert "total_chats" in response.json()
    assert "token_usage" in response.json()
    assert "energy_usage" in response.json()
    assert "thinking_time" in response.json()
    assert "model_usage" in response.json()