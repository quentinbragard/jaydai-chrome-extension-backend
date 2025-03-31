import pytest
from unittest.mock import patch, MagicMock

def test_get_user_metadata(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting user metadata."""
    # Mock the metadata response
    mock_metadata = {
        "name": "Test User",
        "additional_email": "test@example.com",
        "phone_number": "+123456789",
        "additional_organization": "Test Org",
        "pinned_official_folder_ids": [1, 2],
        "pinned_organization_folder_ids": [3]
    }
    
    mock_supabase["user"].table().select().eq().single().execute.return_value.data = mock_metadata
    
    # Make the request
    response = test_client.get("/user/metadata", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "data" in response.json()
    assert response.json()["data"]["name"] == "Test User"
    assert response.json()["data"]["additional_email"] == "test@example.com"
    assert response.json()["data"]["pinned_official_folder_ids"] == [1, 2]
    
    # Verify Supabase client was called correctly
    mock_supabase["user"].table.assert_called_with("users_metadata")
    mock_supabase["user"].table().select.assert_called_once()
    mock_supabase["user"].table().select().eq.assert_called_with("user_id", mock_authenticate_user)

def test_get_user_metadata_not_found(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting user metadata when none exists."""
    # Mock the metadata response (no data)
    mock_supabase["user"].table().select().eq().single().execute.return_value.data = None
    
    # Make the request
    response = test_client.get("/user/metadata", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "data" in response.json()
    # Check default values are provided
    assert response.json()["data"]["name"] is None
    assert response.json()["data"]["additional_email"] is None
    assert response.json()["data"]["pinned_official_folder_ids"] == []
    assert response.json()["data"]["pinned_organization_folder_ids"] == []

def test_get_folders_with_prompts(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting folders with prompts."""
    # Mock the metadata response
    mock_metadata = {
        "pinned_official_folder_ids": [1],
        "pinned_organization_folder_ids": [3]
    }
    
    # Mock prompts response
    mock_prompts = [
        {
            "id": 1,
            "folder_id": 1,
            "type": "official",
            "title": "Official Prompt 1",
            "content": "This is an official prompt"
        },
        {
            "id": 2,
            "folder_id": 2,
            "type": "official",
            "title": "Official Prompt 2",
            "content": "This is another official prompt"
        },
        {
            "id": 3,
            "folder_id": 3,
            "type": "organization",
            "title": "Organization Prompt",
            "content": "This is an organization prompt"
        },
        {
            "id": 4,
            "folder_id": 4,
            "type": "user",
            "title": "User Prompt",
            "content": "This is a user prompt"
        }
    ]
    
    # Mock folders responses
    mock_official_folders = [
        {
            "id": 1,
            "path": "/official/folder1",
            "type": "official",
            "tags": ["official", "starter"]
        },
        {
            "id": 2,
            "path": "/official/folder2",
            "type": "official",
            "tags": ["official", "advanced"]
        }
    ]
    
    mock_org_folders = [
        {
            "id": 3,
            "path": "/org/folder1",
            "type": "organization",
            "tags": ["organization"]
        }
    ]
    
    mock_user_folders = [
        {
            "id": 4,
            "path": "/user/folder1",
            "type": "user",
            "tags": ["personal"],
            "user_id": mock_authenticate_user
        }
    ]
    
    # Setup mocks
    mock_supabase["user"].table.side_effect = None  # Clear any existing side_effect
    
    # For metadata
    metadata_mock = MagicMock()
    metadata_mock.select().eq().single().execute.return_value.data = mock_metadata
    
    # For prompts
    prompts_mock = MagicMock()
    prompts_mock.select().execute.return_value.data = mock_prompts
    
    # For official folders
    official_folders_mock = MagicMock()
    official_folders_mock.select().execute.return_value.data = mock_official_folders
    
    # For organization folders
    org_folders_mock = MagicMock()
    org_folders_mock.select().execute.return_value.data = mock_org_folders
    
    # For user folders
    user_folders_mock = MagicMock()
    user_folders_mock.select().eq().execute.return_value.data = mock_user_folders
    
    # Set up the table method to return different mocks based on the argument
    def table_side_effect(table_name):
        if table_name == "users_metadata":
            return metadata_mock
        elif table_name == "prompt_templates":
            return prompts_mock
        elif table_name == "official_folders":
            return official_folders_mock
        elif table_name == "organization_folders":
            return org_folders_mock
        elif table_name == "user_folders":
            return user_folders_mock
        return MagicMock()
    
    mock_supabase["user"].table.side_effect = table_side_effect
    
    # Make the request
    response = test_client.get("/user/folders-with-prompts", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "data" in response.json()
    assert "official" in response.json()["data"]
    assert "organization" in response.json()["data"]
    assert "user" in response.json()["data"]
    
    # Check that folders have prompts and pinned status
    assert len(response.json()["data"]["official"]) == 2
    assert response.json()["data"]["official"][0]["is_pinned"] == True
    assert "prompts" in response.json()["data"]["official"][0]
    assert len(response.json()["data"]["official"][0]["prompts"]) == 1
    
    assert len(response.json()["data"]["organization"]) == 1
    assert response.json()["data"]["organization"][0]["is_pinned"] == True
    
    assert len(response.json()["data"]["user"]) == 1
    assert "prompts" in response.json()["data"]["user"][0]
    
    # Verify Supabase client was called for all expected tables
    assert mock_supabase["user"].table.call_count >= 5  # Called for metadata, prompts, and 3 folder types