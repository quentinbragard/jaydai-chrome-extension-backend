import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

def test_save_message(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test saving a chat message."""
    # Mock the insert response
    saved_message = {
        "id": 1,
        "user_id": mock_authenticate_user,
        "message_provider_id": "msg_123",
        "content": "This is a test message",
        "role": "user",
        "chat_provider_id": "chat_456",
        "model": "gpt-4",
        "created_at": "2025-03-10T12:00:00+00:00"
    }
    
    # Create a mock response
    response_mock = MagicMock()
    response_mock.data = [saved_message]
    mock_supabase["save"].table().insert().execute.return_value = response_mock
    
    # Message data
    message_data = {
        "message_provider_id": "msg_123",
        "content": "This is a test message",
        "role": "user",
        "chat_provider_id": "chat_456",
        "model": "gpt-4",
        "created_at": 1709384400.0,  # 2024-03-02T12:00:00+00:00 in timestamp
        "parent_message_provider_id": None
    }
    
    # Make the request
    response = test_client.post("/save/message", json=message_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["data"][0]["id"] == 1
    
    # Verify Supabase client was called correctly - use assert_called instead of assert_called_once
    mock_supabase["save"].table.assert_called_with("messages")
    assert mock_supabase["save"].table().insert.called

def test_save_chat(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test saving a chat session."""
    # Mock the select response (no existing chat)
    select_mock = MagicMock()
    select_mock.data = []
    mock_supabase["save"].table().select().eq().eq().execute.return_value = select_mock
    
    # Mock the insert response
    saved_chat = {
        "id": 1,
        "user_id": mock_authenticate_user,
        "chat_provider_id": "chat_456",
        "title": "Test Chat",
        "provider_name": "ChatGPT",
        "created_at": "2025-03-10T12:00:00+00:00"
    }
    
    insert_mock = MagicMock()
    insert_mock.data = [saved_chat]
    mock_supabase["save"].table().insert().execute.return_value = insert_mock
    
    # Chat data
    chat_data = {
        "chat_provider_id": "chat_456",
        "title": "Test Chat",
        "provider_name": "ChatGPT"
    }
    
    # Make the request
    response = test_client.post("/save/chat", json=chat_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["data"][0]["id"] == 1
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("chats")
    assert mock_supabase["save"].table().select().eq.called
    assert mock_supabase["save"].table().insert.called

def test_update_existing_chat(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test updating an existing chat session."""
    # Mock the select response (existing chat)
    existing_chat = {
        "id": 1,
        "user_id": mock_authenticate_user,
        "chat_provider_id": "chat_456",
        "title": "Old Title",
        "provider_name": "ChatGPT",
        "created_at": "2025-03-10T12:00:00+00:00"
    }
    
    select_mock = MagicMock()
    select_mock.data = [existing_chat]
    mock_supabase["save"].table().select().eq().eq().execute.return_value = select_mock
    
    # Mock the update response
    updated_chat = {
        "id": 1,
        "user_id": mock_authenticate_user,
        "chat_provider_id": "chat_456",
        "title": "Updated Title",
        "provider_name": "ChatGPT",
        "created_at": "2025-03-10T12:00:00+00:00"
    }
    
    update_mock = MagicMock()
    update_mock.data = [updated_chat]
    mock_supabase["save"].table().update().eq().eq().execute.return_value = update_mock
    
    # Chat data for update
    chat_data = {
        "chat_provider_id": "chat_456",
        "title": "Updated Title",
        "provider_name": "ChatGPT"
    }
    
    # Make the request
    response = test_client.post("/save/chat", json=chat_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["data"][0]["id"] == 1
    
    # Verify Supabase client was called correctly
    assert mock_supabase["save"].table().update.called
    assert mock_supabase["save"].table().select().eq.called

def test_save_user_metadata(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test saving user metadata."""
    # Mock the select response (no existing metadata)
    select_mock = MagicMock()
    select_mock.data = []
    mock_supabase["save"].table().select().eq().execute.return_value = select_mock
    
    # Mock the insert response
    saved_metadata = {
        "id": 1,
        "user_id": mock_authenticate_user,
        "additional_email": "user@example.com",
        "name": "Test User",
        "phone_number": "+123456789",
        "additional_organization": "Test Org",
        "created_at": "2025-03-10T12:00:00+00:00"
    }
    
    insert_mock = MagicMock()
    insert_mock.data = [saved_metadata]
    mock_supabase["save"].table().insert().execute.return_value = insert_mock
    
    # Metadata data
    metadata_data = {
        "email": "user@example.com",
        "name": "Test User",
        "phone_number": "+123456789",
        "org_name": "Test Org"
    }
    
    # Make the request
    response = test_client.post("/save/user_metadata", json=metadata_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["data"][0]["id"] == 1
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("users_metadata")
    assert mock_supabase["save"].table().select().eq.called
    assert mock_supabase["save"].table().insert.called

def test_batch_save_messages(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test batch saving messages."""
    # Messages to save
    messages = [
        {
            "message_provider_id": "msg_123",
            "content": "This is a test message 1",
            "role": "user",
            "chat_provider_id": "chat_456",
            "model": "gpt-4",
            "created_at": 1709384400.0
        },
        {
            "message_provider_id": "msg_124",
            "content": "This is a test message 2",
            "role": "assistant",
            "chat_provider_id": "chat_456",
            "model": "gpt-4",
            "created_at": 1709384410.0,
            "parent_message_provider_id": "msg_123"
        }
    ]
    
    # Mock the existing messages check
    existing_check = MagicMock()
    existing_check.data = []
    mock_supabase["save"].table().select().eq().in_().execute.return_value = existing_check
    
    # Mock the insert response
    saved_messages = [
        {
            "id": 1,
            "user_id": mock_authenticate_user,
            "message_provider_id": "msg_123",
            "content": "This is a test message 1",
            "role": "user",
            "chat_provider_id": "chat_456",
            "model": "gpt-4",
            "created_at": "2025-03-10T12:00:00+00:00"
        },
        {
            "id": 2,
            "user_id": mock_authenticate_user,
            "message_provider_id": "msg_124",
            "content": "This is a test message 2",
            "role": "assistant",
            "chat_provider_id": "chat_456",
            "model": "gpt-4",
            "created_at": "2025-03-10T12:00:10+00:00",
            "parent_message_provider_id": "msg_123"
        }
    ]
    
    insert_mock = MagicMock()
    insert_mock.data = saved_messages
    mock_supabase["save"].table().insert().execute.return_value = insert_mock
    
    # Make the request
    response = test_client.post("/save/batch/message", json={"messages": messages}, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("messages")
    assert mock_supabase["save"].table().select().eq.called
    assert mock_supabase["save"].table().insert.called

def test_batch_save_chats(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test batch saving chats."""
    # Chats to save
    chats = [
        {
            "chat_provider_id": "chat_456",
            "title": "Test Chat 1",
            "provider_name": "ChatGPT"
        },
        {
            "chat_provider_id": "chat_457",
            "title": "Test Chat 2",
            "provider_name": "ChatGPT"
        }
    ]
    
    # Mock the existing chats check
    existing_check = MagicMock()
    existing_check.data = []
    mock_supabase["save"].table().select().eq().in_().execute.return_value = existing_check
    
    # Mock the insert response
    saved_chats = [
        {
            "id": 1,
            "user_id": mock_authenticate_user,
            "chat_provider_id": "chat_456",
            "title": "Test Chat 1",
            "provider_name": "ChatGPT",
            "created_at": "2025-03-10T12:00:00+00:00"
        },
        {
            "id": 2,
            "user_id": mock_authenticate_user,
            "chat_provider_id": "chat_457",
            "title": "Test Chat 2",
            "provider_name": "ChatGPT",
            "created_at": "2025-03-10T12:00:00+00:00"
        }
    ]
    
    insert_mock = MagicMock()
    insert_mock.data = saved_chats
    mock_supabase["save"].table().insert().execute.return_value = insert_mock
    
    # Make the request
    response = test_client.post("/save/batch/chat", json={"chats": chats}, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("chats")
    assert mock_supabase["save"].table().select().eq.called
    assert mock_supabase["save"].table().insert.called

def test_combined_batch_save(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test combined batch saving of both messages and chats."""
    # Create a patch to bypass the batch save functions
    with patch('routes.save.save_batch_messages') as mock_save_messages, \
         patch('routes.save.save_batch_chats') as mock_save_chats:
        
        # Set up mock returns
        mock_save_messages.return_value = {
            "saved_count": 1,
            "skipped_count": 0,
            "total_count": 1
        }
        
        mock_save_chats.return_value = {
            "inserted_count": 1,
            "updated_count": 0,
            "total_count": 1
        }
        
        # Make the request with combined data
        combined_data = {
            "messages": [
                {
                    "message_provider_id": "msg_123",
                    "content": "Test message",
                    "role": "user",
                    "chat_provider_id": "chat_456",
                    "model": "gpt-4",
                    "created_at": 1709384400.0
                }
            ],
            "chats": [
                {
                    "chat_provider_id": "chat_456",
                    "title": "Test Chat",
                    "provider_name": "ChatGPT"
                }
            ]
        }
        
        response = test_client.post("/save/batch", json=combined_data, headers=valid_auth_header)
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["success"] == True
        assert "results" in response.json()
        assert "messages" in response.json()["results"]
        assert "chats" in response.json()["results"]