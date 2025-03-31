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
    
    mock_supabase["save"].table().insert().execute.return_value.data = [saved_message]
    
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
    assert response.json()["data"][0]["message_provider_id"] == "msg_123"
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("messages")
    # Check that insert was called with appropriate user_id
    mock_supabase["save"].table().insert.assert_called_once()
    # Get the call arguments
    call_args = mock_supabase["save"].table().insert.call_args[0][0]
    assert call_args["user_id"] == mock_authenticate_user
    assert call_args["message_provider_id"] == "msg_123"

def test_save_chat(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test saving a chat session."""
    # Mock the select response (no existing chat)
    mock_supabase["save"].table().select().eq().eq().execute.return_value.data = []
    
    # Mock the insert response
    saved_chat = {
        "id": 1,
        "user_id": mock_authenticate_user,
        "chat_provider_id": "chat_456",
        "title": "Test Chat",
        "provider_name": "ChatGPT",
        "created_at": "2025-03-10T12:00:00+00:00"
    }
    
    mock_supabase["save"].table().insert().execute.return_value.data = [saved_chat]
    
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
    assert response.json()["data"][0]["chat_provider_id"] == "chat_456"
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("chats")
    mock_supabase["save"].table().select().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["save"].table().select().eq().eq.assert_called_with("chat_provider_id", "chat_456")
    mock_supabase["save"].table().insert.assert_called_once()

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
    
    mock_supabase["save"].table().select().eq().eq().execute.return_value.data = [existing_chat]
    
    # Mock the update response
    updated_chat = {
        "id": 1,
        "user_id": mock_authenticate_user,
        "chat_provider_id": "chat_456",
        "title": "Updated Title",
        "provider_name": "ChatGPT",
        "created_at": "2025-03-10T12:00:00+00:00"
    }
    
    mock_supabase["save"].table().update().eq().eq().execute.return_value.data = [updated_chat]
    
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
    assert response.json()["data"][0]["title"] == "Updated Title"
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table().update.assert_called_once()
    mock_supabase["save"].table().update().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["save"].table().update().eq().eq.assert_called_with("chat_provider_id", "chat_456")

def test_save_user_metadata(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test saving user metadata."""
    # Mock the select response (no existing metadata)
    mock_supabase["save"].table().select().eq().execute.return_value.data = []
    
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
    
    mock_supabase["save"].table().insert().execute.return_value.data = [saved_metadata]
    
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
    assert response.json()["data"][0]["additional_email"] == "user@example.com"
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("users_metadata")
    mock_supabase["save"].table().select().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["save"].table().insert.assert_called_once()

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
    mock_supabase["save"].table().select().eq().in_().execute.return_value.data = []
    
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
    
    mock_supabase["save"].table().insert().execute.return_value.data = saved_messages
    
    # Make the request
    response = test_client.post("/save/batch/message", json={"messages": messages}, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["saved_count"] == 2
    assert response.json()["skipped_count"] == 0
    assert response.json()["total_count"] == 2
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("messages")
    mock_supabase["save"].table().select().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["save"].table().insert.assert_called_once()

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
    mock_supabase["save"].table().select().eq().in_().execute.return_value.data = []
    
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
    
    mock_supabase["save"].table().insert().execute.return_value.data = saved_chats
    
    # Make the request
    response = test_client.post("/save/batch/chat", json={"chats": chats}, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["inserted_count"] == 2
    assert response.json()["updated_count"] == 0
    assert response.json()["total_count"] == 2
    
    # Verify Supabase client was called correctly
    mock_supabase["save"].table.assert_called_with("chats")
    mock_supabase["save"].table().select().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["save"].table().insert.assert_called_once()

def test_combined_batch_save(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test combined batch saving of both messages and chats."""
    # Messages to save
    messages = [
        {
            "message_provider_id": "msg_123",
            "content": "This is a test message 1",
            "role": "user",
            "chat_provider_id": "chat_456",
            "model": "gpt-4",
            "created_at": 1709384400.0
        }
    ]
    
    # Chats to save
    chats = [
        {
            "chat_provider_id": "chat_456",
            "title": "Test Chat 1",
            "provider_name": "ChatGPT"
        }
    ]
    
    # Mock the necessary responses
    # For messages
    mock_supabase["save"].table().select().eq().in_().execute.return_value.data = []
    
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
        }
    ]
    
    # For chats
    saved_chats = [
        {
            "id": 1,
            "user_id": mock_authenticate_user,
            "chat_provider_id": "chat_456",
            "title": "Test Chat 1",
            "provider_name": "ChatGPT",
            "created_at": "2025-03-10T12:00:00+00:00"
        }
    ]
    
    # Setup the mock to return different values based on table name
    def mock_table_side_effect(table_name):
        table_mock = MagicMock()
        if table_name == "messages":
            table_mock.insert().execute.return_value.data = saved_messages
        elif table_name == "chats":
            table_mock.insert().execute.return_value.data = saved_chats
        
        # Add common methods
        table_mock.select().eq().in_().execute.return_value.data = []
        return table_mock
    
    # Apply the side effect
    mock_supabase["save"].table.side_effect = mock_table_side_effect
    
    # Make the request
    response = test_client.post(
        "/save/batch",
        json={"messages": messages, "chats": chats},
        headers=valid_auth_header
    )
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "results" in response.json()
    assert "messages" in response.json()["results"]
    assert "chats" in response.json()["results"]
    assert response.json()["results"]["messages"]["total_count"] == 1
    assert response.json()["results"]["chats"]["total_count"] == 1